"""
PHASE 11D — GENOME DSL: Execution Surface (Production Entrypoint)

High-level execution surface for genome evaluation with audit persistence.

CRITICAL RULES:
- Deterministic: same inputs → identical outputs and hashes
- Fail-closed: any error → deterministic NOOP outputs
- No wall-clock: time only from context.now_ms
- Audit persistence is OPTIONAL side-effect (never influences outputs)
- Size-bounded: audit records capped at 1MB with deterministic truncation
"""

import json
from typing import Dict, Any, Optional
from extensions.genome_dsl import types, interpreter, integration
from extensions.genome_dsl.canonical import to_canonical_json, canonical_hash, to_canonical_dict
from extensions.protocol.protocol import IntentType
from extensions.proposals.types import ProposalCard, ProposalStatus


# ────────────────────────────────────────────────────────────────────────────────
# GENOME JSON PARSER (Deterministic)
# ────────────────────────────────────────────────────────────────────────────────

def parse_genome_json(genome_json: Dict[str, Any]) -> types.StrategyGenome:
    """
    Parse genome from JSON dict (reverse of to_canonical_dict).
    
    Args:
        genome_json: JSON dict with __type__ markers
    
    Returns:
        StrategyGenome instance
    
    Raises:
        ValueError: If JSON is malformed or invalid
    """
    if not isinstance(genome_json, dict):
        raise ValueError("Genome JSON must be a dict")
    
    if "__type__" not in genome_json:
        raise ValueError("Genome JSON must have __type__ field")
    
    if genome_json["__type__"] != "StrategyGenome":
        raise ValueError(f"Expected StrategyGenome, got {genome_json['__type__']}")
    
    # Recursively reconstruct nodes
    def parse_node(data: Any) -> Any:
        if data is None:
            return None
        if not isinstance(data, dict):
            return data
        if "__type__" not in data:
            return data
        
        node_type = data["__type__"]
        node_class = getattr(types, node_type, None)
        
        if node_class is None:
            raise ValueError(f"Unknown node type: {node_type}")
        
        # Reconstruct fields
        fields = {k: v for k, v in data.items() if k != "__type__"}
        reconstructed_fields = {}
        
        for key, value in fields.items():
            if isinstance(value, dict) and "__type__" in value:
                reconstructed_fields[key] = parse_node(value)
            elif isinstance(value, list):
                reconstructed_fields[key] = [
                    parse_node(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                reconstructed_fields[key] = value
        
        return node_class(**reconstructed_fields)
    
    return parse_node(genome_json)


# ────────────────────────────────────────────────────────────────────────────────
# NOOP PROPOSAL WRAPPER (Deterministic Fallback)
# ────────────────────────────────────────────────────────────────────────────────

def create_noop_proposal_wrapper(
    intent_id: str,
    strategy_id: str,
    strategy_name: str,
    now_ms: int,
    reason: str = "Non-ENTRY intent or validation failure"
) -> ProposalCard:
    """
    Create deterministic NOOP ProposalCard wrapper for UI consistency.
    
    Args:
        intent_id: Intent ID for correlation
        strategy_id: Strategy identifier
        strategy_name: Strategy display name
        now_ms: Timestamp
        reason: Reason for NOOP
    
    Returns:
        Minimal NOOP ProposalCard
    """
    return ProposalCard(
        proposal_id=f"noop_{intent_id}",
        intent_id=intent_id,
        run_id="genome_run",
        correlation_id=intent_id,
        strategy_id=strategy_id,
        strategy_name=f"{strategy_name} (NOOP)",
        symbol="N/A",
        side_pretty="NOOP",
        side_style="neutral",
        size_pretty="0.0",
        rationale_text=reason,
        rationale_sections=[{"label": "noop_reason", "value": reason}],
        risk_metrics={"implied_loss_pct": 0.0, "reward_to_risk": 0.0, "max_loss_quote": 0.0},
        exit_plan_view={
            "stop_loss_price": None,
            "take_profit_price": None,
            "time_limit_ms": None,
            "time_limit_human": None
        },
        status=ProposalStatus.PENDING,
        created_at_ms=now_ms,
        expires_at_ms=now_ms + 600_000,  # 10 min default
        decided_at_ms=None,
        decided_by=None,
        executed_at_ms=None,
    )


# ────────────────────────────────────────────────────────────────────────────────
# HASH COMPUTATION LAYER
# ────────────────────────────────────────────────────────────────────────────────

def compute_hashes(
    genome: types.StrategyGenome,
    snapshot: Dict[str, Any],
    context: Dict[str, Any],
    evidence: types.DecisionEvidence,
    intent: Any,
    proposal: ProposalCard,
) -> Dict[str, str]:
    """
    Compute all reproducibility hashes.
    
    Returns:
        Dict with genome_hash, snapshot_hash, context_hash, evidence_hash, intent_hash, proposal_hash
    """
    # Genome hash
    genome_hash = canonical_hash(to_canonical_dict(genome))
    
    # Snapshot hash
    snapshot_hash = canonical_hash(snapshot)
    
    # Context hash (deterministic subset)
    context_subset = {
        "now_ms": context.get("now_ms", 0),
        "governance_level": context.get("governance_level", "AUTO"),
    }
    context_hash = canonical_hash(context_subset)
    
    # Evidence hash
    evidence_hash = canonical_hash(to_canonical_dict(evidence))
    
    # Intent hash
    intent_hash = canonical_hash(to_canonical_dict(intent))
    
    # Proposal hash
    proposal_hash = canonical_hash(proposal.to_dict())
    
    return {
        "genome_hash": genome_hash,
        "snapshot_hash": snapshot_hash,
        "context_hash": context_hash,
        "evidence_hash": evidence_hash,
        "intent_hash": intent_hash,
        "proposal_hash": proposal_hash,
    }


# ────────────────────────────────────────────────────────────────────────────────
# EVIDENCE BUNDLE (Reproducibility Artifact)
# ────────────────────────────────────────────────────────────────────────────────

def create_evidence_bundle(
    decision_id: str,
    now_ms: int,
    hashes: Dict[str, str],
    salient_nodes: list,
    audit_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create compact evidence bundle for reproducibility.
    
    Args:
        decision_id: Deterministic decision ID
        now_ms: Timestamp
        hashes: All reproducibility hashes
        salient_nodes: Top 5 salient nodes (summary)
        audit_ref: Optional audit record reference
    
    Returns:
        Evidence bundle dict (capped at 2KB for human summary)
    """
    bundle = {
        "schema_version": "1.0.0",
        "decision_id": decision_id,
        "timestamp_ms": now_ms,
        "hashes": hashes,
        "salient_nodes": salient_nodes[:5],  # Top 5 only
    }
    
    if audit_ref:
        bundle["audit_ref"] = audit_ref
    
    # Cap bundle size (2KB recommended for human summary)
    bundle_json = json.dumps(bundle, sort_keys=True)
    if len(bundle_json) > 2048:
        # Truncate salient_nodes further if needed
        bundle["salient_nodes"] = salient_nodes[:3]
        bundle["truncation_note"] = "BUNDLE_TRUNCATED"
    
    return bundle


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTE GENOME (Main Entrypoint)
# ────────────────────────────────────────────────────────────────────────────────

def execute_genome(
    genome_json: dict,
    snapshot: dict,
    context: dict,
    *,
    persist_audit: bool = True,
    audit_store: Optional[Any] = None,
) -> dict:
    """
    Execute genome and return comprehensive JSON-serializable results.
    
    Args:
        genome_json: Genome as JSON dict (with __type__ markers)
        snapshot: Market snapshot dict
        context: Execution context dict (must include now_ms)
        persist_audit: Whether to persist audit record (default True)
        audit_store: Optional AuditStore instance (default: FileAuditStore)
    
    Returns:
        Dict with keys:
        - decision_evidence: DecisionEvidence dict
        - strategy_intent: StrategyIntent dict
        - proposal_card: ProposalCard dict (real or NOOP wrapper)
        - audit_ref: Optional audit reference (if persisted)
        - hashes: All reproducibility hashes
        - evidence_bundle: Compact reproducibility artifact
    
    Raises:
        Never crashes - fail-closed to deterministic NOOP outputs
    """
    now_ms = context.get("now_ms", 0)
    
    try:
        # Parse genome
        genome = parse_genome_json(genome_json)
        
        # Evaluate genome
        evidence = interpreter.evaluate(genome, snapshot, context)
        
        # Generate intent
        intent = integration.genome_to_intent(genome, snapshot, context)
        
        # Generate proposal (or NOOP wrapper)
        try:
            proposal = integration.genome_to_proposal(genome, snapshot, context)
            
            # If integration returned NOOP card, keep it; otherwise ensure we have a card
            if proposal is None or "noop_" in proposal.proposal_id:
                # Use integration's NOOP card if available, else create wrapper
                if proposal is None:
                    strategy_id = genome.metadata.get("strategy_id", "genome_strategy")
                    strategy_name = genome.metadata.get("name", "Genome Strategy")
                    proposal = create_noop_proposal_wrapper(
                        intent.intent_id,
                        strategy_id,
                        strategy_name,
                        now_ms,
                        "Proposal creation returned None"
                    )
        except Exception as e:
            # Proposal creation failed: create NOOP wrapper
            strategy_id = genome.metadata.get("strategy_id", "genome_strategy")
            strategy_name = genome.metadata.get("name", "Genome Strategy")
            proposal = create_noop_proposal_wrapper(
                intent.intent_id,
                strategy_id,
                strategy_name,
                now_ms,
                f"Proposal creation failed: {str(e)[:100]}"
            )
        
        # Compute hashes
        hashes = compute_hashes(genome, snapshot, context, evidence, intent, proposal)
        
        # Select top 5 salient nodes
        salient_nodes_objs = integration.select_top_5_nodes(evidence)
        salient_nodes = [
            {
                "node_id": node.node_id,
                "node_type": node.node_type,
                "output": node.output,
                "severity": node.severity,
                "rationale": node.rationale[:256],  # Cap
            }
            for node in salient_nodes_objs
        ]
        
        # Persist audit if requested
        audit_ref = None
        if persist_audit and audit_store is not None:
            try:
                audit_record = {
                    "schema_version": "1.0.0",
                    "decision_id": intent.intent_id,
                    "timestamp_ms": now_ms,
                    "hashes": hashes,
                    "decision_evidence": to_canonical_dict(evidence),
                    "strategy_intent": to_canonical_dict(intent),
                    "proposal_card": proposal.to_dict(),
                    "salient_nodes": salient_nodes,
                }
                
                audit_ref = audit_store.append(audit_record)
            except Exception as e:
                # Audit persistence failure does not affect outputs
                audit_ref = f"ERROR:{str(e)[:100]}"
        
        # Create evidence bundle
        evidence_bundle = create_evidence_bundle(
            intent.intent_id,
            now_ms,
            hashes,
            salient_nodes,
            audit_ref
        )
        
        # Return complete result
        return {
            "decision_evidence": to_canonical_dict(evidence),
            "strategy_intent": to_canonical_dict(intent),
            "proposal_card": proposal.to_dict(),
            "audit_ref": audit_ref,
            "hashes": hashes,
            "evidence_bundle": evidence_bundle,
        }
    
    except Exception as e:
        # Fail-closed: return deterministic NOOP outputs
        noop_evidence = types.DecisionEvidence(
            signal="NOOP",
            confidence_raw=0.0,
            sizing_pct=0.0,
            veto_flags=sorted(["EXECUTION_ERROR"]),
            logic_trace=[],
            fallback_count=0,
            constitutional_violations=sorted([f"EXECUTION_ERROR:{str(e)[:100]}"]),
            evaluated_node_count=0,
            step_budget_used=0,
            step_budget_limit=0,
        )
        
        noop_intent_id = "noop_error"
        noop_intent = {
            "intent_id": noop_intent_id,
            "ts_ms": now_ms,
            "intent_type": "NOOP",
            "confidence": 0.0,
            "rationale": f"Execution failed: {str(e)[:200]}",
        }
        
        noop_proposal = create_noop_proposal_wrapper(
            noop_intent_id,
            "genome_error",
            "Execution Error",
            now_ms,
            f"Execution failed: {str(e)[:200]}"
        )
        
        # Compute hashes (attempt to hash inputs even on failure)
        try:
            genome_hash = canonical_hash(genome_json)
            snapshot_hash = canonical_hash(snapshot)
            context_hash = canonical_hash({"now_ms": now_ms})
        except:
            genome_hash = "ERROR"
            snapshot_hash = "ERROR"
            context_hash = "ERROR"
        
        hashes = {
            "genome_hash": genome_hash,
            "snapshot_hash": snapshot_hash,
            "context_hash": context_hash,
            "evidence_hash": canonical_hash(to_canonical_dict(noop_evidence)),
            "intent_hash": canonical_hash(noop_intent),
            "proposal_hash": canonical_hash(noop_proposal.to_dict()),
        }
        
        evidence_bundle = create_evidence_bundle(
            noop_intent_id,
            now_ms,
            hashes,
            [],
            None
        )
        
        return {
            "decision_evidence": to_canonical_dict(noop_evidence),
            "strategy_intent": noop_intent,
            "proposal_card": noop_proposal.to_dict(),
            "audit_ref": None,
            "hashes": hashes,
            "evidence_bundle": evidence_bundle,
        }

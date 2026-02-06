"""
Epoch D.1 — Two-Stage Research Engine

CORE LOGIC:
1. Gather context from providers
2. Stage 1 (Extract): LLM extracts facts → ExtractPayload
3. Validate Stage 1 (NO regime/sentiment allowed)
4. Stage 2 (Judge): LLM produces regime/sent→ JudgePayload
5. Apply Hard Overrides (deterministic, non-negotiable)
6. Assemble ResearchReport
7. FAIL-NEUTRAL: Any error → UNCERTAIN + 0.0 confidence
"""
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from lunia_core.app.services.research.models import (
    MacroRegime,
    VolatilityOutlook,
    RiskFlag,
    Evidence,
    Claim,
    ExtractPayload,
    JudgePayload,
    ResearchReport,
    create_default_uncertain_report,
)
from lunia_core.app.services.research.providers import (
    NewsProvider,
    CalendarProvider,
    MarketDataProvider,
    LLMAnalyst,
    NewsItem,
    CalendarEvent,
)

logger = logging.getLogger(__name__)


class ResearchAgent:
    """
    Two-stage research agent with anti-hallucination controls.
    
    STAGE 1 (Extract): Facts-only, NO regime/sentiment
    STAGE 2 (Judge): Regime/sentiment analysis
    HARD OVERRIDES: Deterministic governance (WAR, EXCHANGE_OUTAGE, etc.)
    FAIL-NEUTRAL: Any error → UNCERTAIN regime, 0.0 confidence
    """
    
    def __init__(
        self,
        news_provider: NewsProvider,
        calendar_provider: CalendarProvider,
        market_provider: MarketDataProvider,
        llm_analyst: LLMAnalyst,
        report_ttl_minutes: int = 15,
    ):
        self.news = news_provider
        self.calendar = calendar_provider
        self.market = market_provider
        self.llm = llm_analyst
        self.report_ttl_minutes = report_ttl_minutes
    
    def run_cycle(self, now_utc: datetime) -> ResearchReport:
        """
        Run full research cycle.
        
        Returns:
            ResearchReport (may be UNCERTAIN if errors occur)
        """
        try:
            # 1. Gather context
            context = self._gather_context()
            
            # 2. Stage 1: Extract facts
            extract_response = self.llm.generate_json(
                self._build_extract_prompt(context),
                timeout_s=10.0
            )
            
            # 3. Validate Stage 1
            extract = self._parse_and_validate_extract(extract_response)
            if extract is None:
                logger.warning("STAGE1_VALIDATION_FAILED")
                return self._create_fail_neutral_report(
                    now_utc,
                    reason="SCHEMA_VIOLATION (Stage 1)",
                    flags=[RiskFlag.SCHEMA_VIOLATION]
                )
            
            # 4. Stage 2: Judge regime
            judge_response = self.llm.generate_json(
                self._build_judge_prompt(extract, context),
                timeout_s=10.0
            )
            
            # 5. Parse and validate Stage 2
            judge = self._parse_and_validate_judge(judge_response)
            if judge is None:
                logger.warning("STAGE2_VALIDATION_FAILED")
                return self._create_fail_neutral_report(
                    now_utc,
                    reason="SCHEMA_VIOLATION (Stage 2)",
                    flags=[RiskFlag.SCHEMA_VIOLATION]
                )
            
            # 6. Apply Hard Overrides (CRITICAL)
            final_judge = self._apply_hard_overrides(judge, extract)
            
            # 7. Assemble final report
            report = self._build_report(extract, final_judge, context, now_utc)
            
            logger.info(
                f"RESEARCH_CYCLE_COMPLETE: regime={report.regime}, "
                f"confidence={report.confidence:.2f}, "
                f"flags={len(report.risk_flags)}"
            )
            
            return report
            
        except Exception as e:
            logger.error(f"RESEARCH_CYCLE_ERROR: {e}", exc_info=True)
            return self._create_fail_neutral_report(
                now_utc,
                reason=f"LLM_ERROR: {str(e)[:100]}",
                flags=[RiskFlag.LLM_ERROR]
            )
    
    # ========================================================================
    # CONTEXT GATHERING
    # ========================================================================
    
    def _gather_context(self) -> dict:
        """
        Gather context from all providers.
        
        Partial failures allowed (continue with available data).
        """
        context = {
            "news": [],
            "calendar": [],
            "market": {},
            "provider_versions": {},
        }
        
        # News (allow partial failure)
        try:
            context["news"] = self.news.fetch_headlines(limit=10)
            context["provider_versions"]["news"] = self.news.provider_version
        except Exception as e:
            logger.warning(f"NEWS_PROVIDER_FAILED: {e}")
        
        # Calendar (allow partial failure)
        try:
            context["calendar"] = self.calendar.fetch_upcoming_events(hours=24)
            context["provider_versions"]["calendar"] = self.calendar.provider_version
        except Exception as e:
            logger.warning(f"CALENDAR_PROVIDER_FAILED: {e}")
        
        # Market (allow partial failure)
        try:
            context["market"] = self.market.fetch_global_indices()
            context["provider_versions"]["market"] = self.market.provider_version
        except Exception as e:
            logger.warning(f"MARKET_PROVIDER_FAILED: {e}")
        
        context["provider_versions"]["llm"] = self.llm.model_version
        
        return context
    
    # ========================================================================
    # STAGE 1: EXTRACT
    # ========================================================================
    
    def _build_extract_prompt(self, context: dict) -> str:
        """Build Stage 1 (Extract) prompt."""
        prompt = """You are a financial research analyst. Extract FACTS ONLY from the provided context.

CRITICAL RULES:
1. DO NOT output regime, sentiment, confidence, or volatility
2. Extract evidence with source attribution
3. Create claims that cite evidence IDs
4. Output STRICT JSON matching ExtractPayload schema

Context:
"""
        # Add news
        if context["news"]:
            prompt += "\nNEWS HEADLINES:\n"
            for item in context["news"][:5]:
                prompt += f"- [{item.source_id}] {item.title}\n"
        
        # Add calendar
        if context["calendar"]:
            prompt += "\nUPCOMING EVENTS:\n"
            for event in context["calendar"]:
                prompt += f"- [{event.event_id}] {event.title} at {event.scheduled_at}\n"
        
        # Add market
        if context["market"]:
            prompt += "\nMARKET INDICES:\n"
            for symbol, index in context["market"].items():
                prompt += f"- {symbol}: {index.value} ({index.change_pct_24h:+.2f}%)\n"
        
        prompt += """\n
Output JSON (strict schema):
{
  "evidence": [...],
  "claims": [...],
  "extracted_at": "ISO timestamp",
  "extract_prompt_hash": "hash",
  "context_hash": "hash"
}
"""
        return prompt
    
    def _parse_and_validate_extract(self, response: str) -> Optional[ExtractPayload]:
        """
        Parse and validate Stage 1 response.
        
        FORBIDDEN FIELDS: regime, sentiment, confidence, volatility
        """
        try:
            data = json.loads(response)
            
            # Check for forbidden fields (anti-hallucination)
            forbidden = ['regime', 'sentiment', 'confidence', 'volatility']
            found_forbidden = [k for k in data if any(f in k.lower() for f in forbidden)]
            if found_forbidden:
                logger.error(f"STAGE1_FORBIDDEN_FIELDS: {found_forbidden}")
                return None
            
            # Parse into ExtractPayload
            extract = ExtractPayload(
                evidence=[Evidence(**e) for e in data.get("evidence", [])],
                claims=[Claim(**c) for c in data.get("claims", [])],
                extracted_at=datetime.fromisoformat(data["extracted_at"].replace('Z', '+00:00')),
                extract_prompt_hash=data.get("extract_prompt_hash", ""),
                context_hash=data.get("context_hash", ""),
            )
            
            # Validate evidence exists
            if not extract.evidence:
                logger.warning("STAGE1_NO_EVIDENCE")
                return None
            
            return extract
            
        except Exception as e:
            logger.error(f"STAGE1_PARSE_ERROR: {e}")
            return None
    
    # ========================================================================
    # STAGE 2: JUDGE
    # ========================================================================
    
    def _build_judge_prompt(self, extract: ExtractPayload, context: dict) -> str:
        """Build Stage 2 (Judge) prompt."""
        prompt = """You are a macro analyst. Analyze the extracted facts and produce regime assessment.

RULES:
1. Base analysis ONLY on provided evidence and claims
2. Output regime (RISK_ON/RISK_OFF/NEUTRAL/UNCERTAIN)
3. Provide sentiment score [-1, 1]
4. List risk flags if applicable
5. Output STRICT JSON matching JudgePayload schema

Extracted Evidence:
"""
        for claim in extract.claims:
            prompt += f"- {claim.text}\n"
        
        prompt += """\n
Output JSON (strict schema):
{
  "regime": "RISK_ON|RISK_OFF|NEUTRAL|UNCERTAIN",
  "volatility_outlook": "EXPANDING|COMPRESSING|STABLE",
  "sentiment_score": float,
  "risk_flags": [],
  "confidence": float,
  "reasoning": "string",
  "judge_prompt_hash": "hash",
  "context_hash": "hash"
}
"""
        return prompt
    
    def _parse_and_validate_judge(self, response: str) -> Optional[JudgePayload]:
        """Parse and validate Stage 2 response."""
        try:
            data = json.loads(response)
            
            judge = JudgePayload(
                regime=MacroRegime(data["regime"]),
                volatility_outlook=VolatilityOutlook(data["volatility_outlook"]),
                sentiment_score=float(data["sentiment_score"]),
                risk_flags=[RiskFlag(f) for f in data.get("risk_flags", [])],
                confidence=float(data["confidence"]),
                reasoning=data.get("reasoning", ""),
                judge_prompt_hash=data.get("judge_prompt_hash", ""),
                context_hash=data.get("context_hash", ""),
            )
            
            return judge
            
        except Exception as e:
            logger.error(f"STAGE2_PARSE_ERROR: {e}")
            return None
    
    # ========================================================================
    # HARD OVERRIDES (GOVERNANCE)
    # ========================================================================
    
    def _apply_hard_overrides(
        self,
        judge: JudgePayload,
        extract: ExtractPayload
    ) -> JudgePayload:
        """
        Apply deterministic hard overrides.
        
        RULES (NON-NEGOTIABLE):
        1. WAR → RISK_OFF or UNCERTAIN, confidence ≤ 0.6
        2. EXCHANGE_OUTAGE → UNCERTAIN + volatility EXPANDING, confidence ≤ 0.5
        3. FOMC_TODAY/CPI_SOON → cap confidence ≤ 0.6
        4. Conflicting signals (WAR + RISK_ON) → force UNCERTAIN
        5. All UNKNOWN reliability → UNCERTAIN + DATA_STALE
        """
        regime = judge.regime
        volatility = judge.volatility_outlook
        confidence = judge.confidence
        flags = set(judge.risk_flags)
        
        # WAR override
        if RiskFlag.WAR in flags or self._has_war_evidence(extract):
            logger.warning("HARD_OVERRIDE: WAR detected")
            if regime == MacroRegime.RISK_ON:
                # Conflict: force UNCERTAIN
                regime = MacroRegime.UNCERTAIN
            else:
                regime = MacroRegime.RISK_OFF
            confidence = min(confidence, 0.6)
            flags.add(RiskFlag.WAR)
        
        # EXCHANGE_OUTAGE override
        if RiskFlag.EXCHANGE_OUTAGE in flags or self._has_outage_evidence(extract):
            logger.warning("HARD_OVERRIDE: EXCHANGE_OUTAGE detected")
            regime = MacroRegime.UNCERTAIN
            volatility = VolatilityOutlook.EXPANDING
            confidence = min(confidence, 0.5)
            flags.add(RiskFlag.EXCHANGE_OUTAGE)
        
        # High-impact event confidence cap
        if RiskFlag.FOMC_TODAY in flags or RiskFlag.CPI_SOON in flags:
            logger.info("HARD_OVERRIDE: High-impact event, capping confidence")
            confidence = min(confidence, 0.6)
            
            # Check for surprise language
            if self._language_indicates_surprise(extract):
                flags.add(RiskFlag.POLICY_SHOCK)
        
        # Conflict detection (WAR/LIQUIDITY_STRESS + RISK_ON)
        if regime == MacroRegime.RISK_ON and (
            RiskFlag.WAR in flags or RiskFlag.LIQUIDITY_STRESS in flags
        ):
            logger.warning("HARD_OVERRIDE: Conflicting signals, forcing UNCERTAIN")
            regime = MacroRegime.UNCERTAIN
        
        # Unknown reliability check
        if all(e.reliability_tier == "UNKNOWN" for e in extract.evidence):
            logger.warning("HARD_OVERRIDE: All evidence UNKNOWN tier")
            regime = MacroRegime.UNCERTAIN
            flags.add(RiskFlag.DATA_STALE)
        
        # Return overridden judge
        return JudgePayload(
            regime=regime,
            volatility_outlook=volatility,
            sentiment_score=judge.sentiment_score,
            risk_flags=list(flags),
            confidence=confidence,
            reasoning=judge.reasoning,
            judge_prompt_hash=judge.judge_prompt_hash,
            context_hash=judge.context_hash,
        )
    
    def _has_war_evidence(self, extract: ExtractPayload) -> bool:
        """Check if evidence contains war-related keywords (TIER_1 only)."""
        war_keywords = ["war", "military", "conflict", "hostilities", "armed forces"]
        for evidence in extract.evidence:
            if evidence.reliability_tier == "TIER_1":
                text = (evidence.title + " " + evidence.snippet).lower()
                if any(kw in text for kw in war_keywords):
                    return True
        return False
    
    def _has_outage_evidence(self, extract: ExtractPayload) -> bool:
        """Check if evidence contains exchange outage keywords."""
        outage_keywords = ["exchange", "outage", "halt", "technical", "system failure"]
        for evidence in extract.evidence:
            text = (evidence.title + " " + evidence.snippet).lower()
            if all(kw in text for kw in ["exchange", "outage"]):
                return True
            if "trading halted" in text or "system failure" in text:
                return True
        return False
    
    def _language_indicates_surprise(self, extract: ExtractPayload) -> bool:
        """Check if evidence indicates surprise/shock."""
        surprise_keywords = ["surprise", "shock", "unexpected", "breaking"]
        for evidence in extract.evidence:
            text = (evidence.title + " " + evidence.snippet).lower()
            if any(kw in text for kw in surprise_keywords):
                return True
        return False
    
    # ========================================================================
    # REPORT ASSEMBLY
    # ========================================================================
    
    def _build_report(
        self,
        extract: ExtractPayload,
        judge: JudgePayload,
        context: dict,
        now_utc: datetime
    ) -> ResearchReport:
        """Assemble final research report."""
        # Calculate valid_until (bounded TTL)
        valid_until = now_utc + timedelta(minutes=self.report_ttl_minutes)
        
        # Build provider snapshot
        provider_snapshot = {
            "news_count": len(context.get("news", [])),
            "calendar_count": len(context.get("calendar", [])),
            "market_count": len(context.get("market", {})),
            "provider_versions": context.get("provider_versions", {}),
        }
        
        # Compute combined prompt hash
        prompt_hash = hashlib.sha256(
            f"{extract.extract_prompt_hash}:{judge.judge_prompt_hash}".encode()
        ).hexdigest()[:16]
        
        return ResearchReport(
            timestamp=now_utc,
            valid_until=valid_until,
            regime=judge.regime,
            volatility_outlook=judge.volatility_outlook,
            sentiment_score=judge.sentiment_score,
            risk_flags=judge.risk_flags,
            claims=extract.claims,
            evidence=extract.evidence,
            reasoning=judge.reasoning,
            confidence=judge.confidence,
            prompt_hash=prompt_hash,
            context_hash=extract.context_hash,
            provider_snapshot=provider_snapshot,
        )
    
    def _create_fail_neutral_report(
        self,
        now_utc: datetime,
        reason: str,
        flags: list[RiskFlag]
    ) -> ResearchReport:
        """
        Create fail-neutral UNCERTAIN report.
        
        Used when errors occur or validation fails.
        """
        return ResearchReport(
            timestamp=now_utc,
            valid_until=now_utc + timedelta(minutes=5),
            regime=MacroRegime.UNCERTAIN,
            volatility_outlook=VolatilityOutlook.STABLE,
            sentiment_score=0.0,
            risk_flags=flags,
            claims=[],
            evidence=[],
            reasoning=f"Fail-neutral mode: {reason}",
            confidence=0.0,
            prompt_hash="",
            context_hash="",
            provider_snapshot={},
        )

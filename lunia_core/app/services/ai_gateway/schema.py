"""
AI Gateway: JSON Schema Validation

Fail-closed schema validation for AI outputs.

INVARIANT: If schema validation fails, discard output entirely.
"""
import jsonschema
from typing import Dict, Optional


# AI Analysis Output Schema (HARD CONTRACT)
AI_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": [
        "summary",
        "risk_flags",
        "confirmation",
        "confidence_score",
        "conflicts_with_core",
        "reasoning_version",
        "model_revision"
    ],
    "properties": {
        "summary": {
            "type": "string",
            "maxLength": 500,
            "minLength": 10
        },
        "risk_flags": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 10
        },
        "confirmation": {
            "type": "boolean"
        },
        "confidence_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "confidence_reason": {
            "type": "string",
            "maxLength": 200
        },
        "conflicts_with_core": {
            "type": "boolean"
        },
        "conflict_reason": {
            "type": "string",
            "maxLength": 200
        },
        "invalid_if": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5
        },
        "reasoning_version": {
            "type": "string",
            "pattern": "^core_v[0-9]+\\.[0-9]+$"
        },
        "ai_constitution_hash": {
            "type": "string",
            "pattern": "^[a-f0-9]{64}$"
        },
        "model_revision": {
            "type": "string",
            "minLength": 3
        }
    },
    "additionalProperties": False  # Strict: no extra fields
}


def validate_ai_analysis(response: Dict) -> Optional[Dict]:
    """
    Validate AI analysis response against schema.
    
    Args:
        response: Raw LLM response (parsed JSON)
    
    Returns:
        Validated response if valid, None if invalid (FAIL-CLOSED)
    """
    try:
        jsonschema.validate(instance=response, schema=AI_ANALYSIS_SCHEMA)
        return response
    except jsonschema.ValidationError as e:
        # Schema validation failed - discard output
        print(f"[AI_GATEWAY] Schema validation failed: {e.message}")
        return None
    except jsonschema.SchemaError as e:
        # Schema itself is invalid (should never happen)
        print(f"[AI_GATEWAY] Schema error: {e.message}")
        return None


def get_schema_version() -> str:
    """Get schema version for provenance tracking."""
    return "v1.0.0"

"""E5.1 Preflight Context - Constraints and snapshot state"""
from decimal import Decimal
from typing import Dict
from pydantic import BaseModel
from lunia_core.app.services.allocation.models import SymbolConstraints

class PreflightContext(BaseModel):
    """
    Preflight execution context
    
    Contains:
    - Symbol constraints (validated, fresh)
    - Snapshot version (batch consistency)
    - Deterministic time reference
    """
    
    constraints_by_symbol:Dict[str,SymbolConstraints]
    now_ms:int  # Deterministic, injected
    snapshot_version:int
    price_reference_used:str="MID"  # For audit
    
    class Config:
        arbitrary_types_allowed=True
        json_encoders={Decimal:str}

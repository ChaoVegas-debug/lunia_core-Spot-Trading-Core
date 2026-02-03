"""D2 InMemory Store (tests only) - Complete implementation"""
from typing import Dict,List
from collections import defaultdict
import time
from .base import *
from ..models import HistoricalTick,CURRENT_SCHEMA_VERSION

class InMemoryHistoricalStore:
    def __init__(self):
        self._data:Dict[str,List[HistoricalTick]]=defaultdict(list)
        self._dedup_keys:Dict[str,set]=defaultdict(set)
    
    def append_tick(self,tick:HistoricalTick)->AppendResult:
        safe,_=self._sanitize(tick.symbol)
        if not safe:return AppendResult(ok=False,error_code=ErrorCode.HIST_PATH_UNSAFE)
        if tick.dedup_key in self._dedup_keys[tick.symbol]:
            return AppendResult(ok=True,metadata={"deduplicated":True})
        self._data[tick.symbol].append(tick)
        self._dedup_keys[tick.symbol].add(tick.dedup_key)
        self._data[tick.symbol].sort(key=lambda t:(t.timestamp_ms,t.snapshot_version))
        return AppendResult(ok=True)
    
    def get_ticks(self,symbol:str,start_ms:int,end_ms:int)->ReadResult:
        safe,_=self._sanitize(symbol)
        if not safe:return ReadResult(ok=False,error_code=ErrorCode.HIST_PATH_UNSAFE)
        ticks=[t for t in self._data[symbol] if start_ms<=t.timestamp_ms<=end_ms]
        return ReadResult(ok=True,ticks=ticks)
    
    def count(self,symbol:str)->int:
        return len(self._data.get(symbol,[]))
    
    def health(self)->HealthResult:
        return HealthResult(ok=True,checks={"backend":"inmemory","symbols":len(self._data)})
    
    def _sanitize(self,symbol:str):
        import re
        if not re.match(r'^[A-Z0-9_:\-/]+$',symbol):return(False,symbol)
        if '..' in symbol:return(False,symbol)
        return(True,symbol)

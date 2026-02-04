"""D2 Ingestion + Repository"""
import math
from typing import List,Optional
from pydantic import BaseModel
from lunia_core.app.services.market_data.realtime.models import MarketSnapshot,SnapshotState
from .models import HistoricalTick
from .store.base import *

class IngestionResult(BaseModel):
    ok:bool
    error_code:Optional[ErrorCode]=None
    metadata:dict={}

class HistoryIngestor:
    def __init__(self,store):
        self.store=store
    
    def ingest(self,snapshot:MarketSnapshot,now_ms:Optional[int]=None)->IngestionResult:
        if snapshot.snapshot_state!=SnapshotState.VALID:
            return IngestionResult(ok=False,error_code=ErrorCode.HIST_SNAPSHOT_INVALID)
        try:
            tick=HistoricalTick(
                symbol=snapshot.symbol,
                timestamp_ms=snapshot.last_update_ms,
                mid_price=snapshot.mid_price or 0.0,
                bid=snapshot.orderbook_l2.bids[0].price if snapshot.orderbook_l2 and snapshot.orderbook_l2.bids else None,
                ask=snapshot.orderbook_l2.asks[0].price if snapshot.orderbook_l2 and snapshot.orderbook_l2.asks else None,
                snapshot_version=snapshot.version,
                ingested_at_ms=now_ms or snapshot.last_update_ms
            )
            result=self.store.append_tick(tick)
            return IngestionResult(ok=result.ok,error_code=result.error_code,metadata=result.metadata)
        except Exception as e:
            return IngestionResult(ok=False,error_code=ErrorCode.HIST_UNKNOWN_ERROR,metadata={"error":str(e)})

class D2RepositoryAdapter:
    def __init__(self,store):
        self.store=store
    
    def get_ticks(self,symbol:str,start_ms:int,end_ms:int)->ReadResult:
        return self.store.get_ticks(symbol,start_ms,end_ms)
    
    def get_returns(self,symbol:str,end_ms:int,window_samples:int)->ReadResult:
        """Compute returns from ticks (fail-closed on insufficient samples)"""
        start_ms=end_ms-(window_samples*86400000) #Approx window start
        result=self.store.get_ticks(symbol,start_ms,end_ms)
        if not result.ok:
            return result
        if len(result.ticks)<window_samples:
            return ReadResult(ok=False,error_code=ErrorCode.HIST_INSUFFICIENT_SAMPLES)
        #Compute returns: r_t = ln(p_t/p_{t-1})
        prices=[t.mid_price for t in result.ticks[-window_samples:]]
        returns=[math.log(prices[i]/prices[i-1]) for i in range(1,len(prices))]
        return ReadResult(ok=True,ticks=[],metadata={"returns":returns,"samples":len(returns)})

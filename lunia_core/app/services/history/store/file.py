"""D2 File Store (JSONL MVP) - Production-ready with manifest/checksums/atomic writes"""
import os,json,time
from pathlib import Path
from typing import List
from .base import *
from ..models import HistoricalTick,CURRENT_SCHEMA_VERSION
from ..manifest import ManifestManager,Manifest,SegmentInfo,compute_checksum,verify_checksum

class FileHistoricalStore:
    def __init__(self,root_path:str):
        self.root=Path(root_path)
        self.mgr=ManifestManager(root_path)
    
    def append_tick(self,tick:HistoricalTick)->AppendResult:
        lock=self.mgr._get_partition_lock(tick.symbol)
        with lock:
            try:
                manifest=self.mgr.load_manifest(tick.symbol) or Manifest(symbol=tick.symbol,schema_version=CURRENT_SCHEMA_VERSION)
                dt=time.strftime('%Y-%m-%d',time.gmtime(tick.timestamp_ms/1000))
                seg_dir=self.root/tick.symbol/f"dt={dt}"
                seg_dir.mkdir(parents=True,exist_ok=True)
                seg_path=seg_dir/"events.jsonl"
                temp_path=seg_path.with_suffix('.tmp')
                
                #Load existing segment
                existing=[]
                if seg_path.exists():
                    with open(seg_path,'r') as f:
                        existing=[HistoricalTick(**json.loads(line)) for line in f if line.strip()]
                
                #Dedup
                keys={t.dedup_key for t in existing}
                if tick.dedup_key in keys:
                    return AppendResult(ok=True,metadata={"deduplicated":True})
                
                #Merge+sort
                all_ticks=existing+[tick]
                all_ticks.sort(key=lambda t:(t.timestamp_ms,t.snapshot_version))
                
                #Atomic write
                with open(temp_path,'w') as f:
                    for t in all_ticks:
                        f.write(json.dumps(t.dict())+'\n')
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path,seg_path)
                
               #Update manifest
                checksum=compute_checksum(seg_path)
                seg_info=SegmentInfo(
                    segment_path=str(seg_path.relative_to(self.root)),
                    min_ts_ms=min(t.timestamp_ms for t in all_ticks),
                    max_ts_ms=max(t.timestamp_ms for t in all_ticks),
                    row_count=len(all_ticks),
                    schema_version=CURRENT_SCHEMA_VERSION,
                    checksum=checksum,
                    created_at_ms=int(time.time()*1000)
                )
                manifest.segments=[s for s in manifest.segments if s.segment_path!=seg_info.segment_path]+[seg_info]
                self.mgr.save_manifest(manifest)
                return AppendResult(ok=True)
            except Exception as e:
                return AppendResult(ok=False,error_code=ErrorCode.HIST_WRITE_FAILED,metadata={"error":str(e)})
    
    def get_ticks(self,symbol:str,start_ms:int,end_ms:int)->ReadResult:
        manifest=self.mgr.load_manifest(symbol)
        if not manifest:
            return ReadResult(ok=False,error_code=ErrorCode.HIST_MANIFEST_MISSING)
        ticks=[]
        for seg in manifest.segments:
            if seg.max_ts_ms<start_ms or seg.min_ts_ms>end_ms:continue
            seg_path=self.root/seg.segment_path
            if not seg_path.exists():
                return ReadResult(ok=False,error_code=ErrorCode.HIST_SEGMENT_MISSING)
            if not verify_checksum(seg_path,seg.checksum):
                return ReadResult(ok=False,error_code=ErrorCode.HIST_CHECKSUM_MISMATCH)
            with open(seg_path,'r') as f:
                for line in f:
                    if not line.strip():continue
                    t=HistoricalTick(**json.loads(line))
                    if start_ms<=t.timestamp_ms<=end_ms:
                        ticks.append(t)
        return ReadResult(ok=True,ticks=sorted(ticks,key=lambda t:(t.timestamp_ms,t.snapshot_version)))
    
    def count(self,symbol:str)->int:
        manifest=self.mgr.load_manifest(symbol)
        return sum(s.row_count for s in manifest.segments) if manifest else 0
    
    def health(self)->HealthResult:
        if not self.root.exists():
            return HealthResult(ok=False,error_code=ErrorCode.HIST_MANIFEST_MISSING)
        return HealthResult(ok=True,checks={"backend":"file","root":str(self.root)})

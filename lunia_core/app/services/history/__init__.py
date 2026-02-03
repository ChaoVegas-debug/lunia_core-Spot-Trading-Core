"""History package exports"""
from .models import HistoricalTick,CURRENT_SCHEMA_VERSION
from .store.base import IHistoricalStore,AppendResult,ReadResult,HealthResult,ErrorCode
from .store.inmemory import InMemoryHistoricalStore
from .store.file import FileHistoricalStore
from .manifest import ManifestManager,Manifest
from .ingestion import HistoryIngestor,IngestionResult,D2RepositoryAdapter

try:
    from .store.parquet import ParquetHistoricalStore
except ImportError:
    ParquetHistoricalStore=None

__all__=[
    "HistoricalTick","CURRENT_SCHEMA_VERSION",
    "IHistoricalStore","AppendResult","ReadResult","HealthResult","ErrorCode",
    "InMemoryHistoricalStore","FileHistoricalStore","ParquetHistoricalStore",
    "ManifestManager","Manifest",
    "HistoryIngestor","IngestionResult","D2RepositoryAdapter"
]

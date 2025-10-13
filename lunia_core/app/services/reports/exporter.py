from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional

try:  # pragma: no cover - optional dependency
    import boto3
except Exception:  # pragma: no cover - offline fallback
    boto3 = None

from app.core.metrics import s3_export_last_status, s3_exports_total
from app.db.reporting import fetch_arbitrage_records

LOG_DIR = Path(__file__).resolve().parents[4] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class S3Exporter:
    """Uploads arbitrage data to S3/MinIO with offline-friendly fallback."""

    def __init__(self) -> None:
        self.enabled = os.getenv("S3_EXPORT_ENABLED", "false").lower() == "true"
        self.interval_min = int(os.getenv("S3_EXPORT_INTERVAL_MIN", "60"))
        self.bucket = os.getenv("S3_BUCKET_NAME", "")
        self.region = os.getenv("S3_REGION", "")
        self.endpoint = os.getenv("S3_ENDPOINT_URL")
        self.access_key = os.getenv("S3_ACCESS_KEY")
        self.secret_key = os.getenv("S3_SECRET_KEY")
        self.prefix = os.getenv("S3_EXPORT_PREFIX", "reports")
        self._last_run = 0.0

    def should_run(self) -> bool:
        if not self.enabled:
            return False
        return time.time() - self._last_run >= max(60, self.interval_min * 60)

    def export_if_due(self) -> Optional[Dict[str, str]]:
        if not self.should_run():
            return None
        return self.export_now()

    def export_now(self) -> Dict[str, str]:
        payload = {
            "proposals": fetch_arbitrage_records(limit=500, table="proposals"),
            "executions": fetch_arbitrage_records(limit=500, table="execs"),
            "generated_at": time.time(),
        }
        key_suffix = time.strftime("%Y/%m/%d/%H%M%S.json")
        object_key = f"{self.prefix}/{key_suffix}"
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        success = False
        if self.enabled and boto3 is not None and self.bucket:
            client_kwargs = {"region_name": self.region or None}
            if self.endpoint:
                client_kwargs["endpoint_url"] = self.endpoint
            if self.access_key and self.secret_key:
                client_kwargs["aws_access_key_id"] = self.access_key
                client_kwargs["aws_secret_access_key"] = self.secret_key
            client = boto3.client("s3", **{k: v for k, v in client_kwargs.items() if v})
            client.put_object(Bucket=self.bucket, Key=object_key, Body=body, ContentType="application/json")
            success = True
        else:  # offline fallback writes to logs directory
            out_dir = LOG_DIR / "exports"
            out_dir.mkdir(parents=True, exist_ok=True)
            local_path = out_dir / object_key.replace("/", "_")
            local_path.write_bytes(body)
            success = True
        self._last_run = time.time()
        status = "success" if success else "failed"
        s3_exports_total.labels(status=status).inc()
        s3_export_last_status.set(1.0 if success else 0.0)
        return {"key": object_key, "status": status}


_EXPORTER: Optional[S3Exporter] = None


def get_exporter() -> Optional[S3Exporter]:
    global _EXPORTER
    if _EXPORTER is None:
        exporter = S3Exporter()
        if exporter.enabled or True:  # offline fallback still useful
            _EXPORTER = exporter
        else:
            _EXPORTER = exporter
    return _EXPORTER


__all__ = ["S3Exporter", "get_exporter"]

from pathlib import Path

from app.services.reports.exporter import S3Exporter


def test_s3_export_writes_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("S3_EXPORT_ENABLED", "false")
    monkeypatch.setenv("S3_EXPORT_INTERVAL_MIN", "1")
    exporter = S3Exporter()
    result = exporter.export_now()
    assert result["status"] == "success"
    exports_dir = Path(__file__).resolve().parents[2] / "logs" / "exports"
    assert exports_dir.exists()
    # ensure at least one export file created
    files = list(exports_dir.glob("*.json"))
    assert files, "Fallback export file not created"

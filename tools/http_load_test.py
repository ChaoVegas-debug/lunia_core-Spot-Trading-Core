import argparse
import json
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import requests

DEFAULT_ENDPOINTS = [
    "/health",
    "/status",
    "/ops/state",
    "/portfolio/snapshot",
    "/ai/signals",
]


class Result:
    __slots__ = ("latencies", "status_counts", "errors")

    def __init__(self) -> None:
        self.latencies: List[float] = []
        self.status_counts: Counter[int] = Counter()
        self.errors: Counter[str] = Counter()


class LoadTester:
    def __init__(
        self,
        base_url: str,
        endpoints: List[str],
        token: Optional[str],
        rps: int,
        duration: int,
        concurrency: int,
        verify_tls: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoints = endpoints
        self.token = token
        self.rps = max(1, rps)
        self.duration = duration
        self.concurrency = concurrency
        self.verify_tls = verify_tls
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.lock = threading.Lock()
        self.result = Result()

    def _request_once(self, path: str) -> None:
        url = f"{self.base_url}{path}"
        start = time.perf_counter()
        try:
            resp = self.session.get(url, timeout=10, verify=self.verify_tls)
            latency = (time.perf_counter() - start) * 1000.0
            with self.lock:
                self.result.latencies.append(latency)
                self.result.status_counts[resp.status_code] += 1
        except Exception as exc:  # pragma: no cover - operational tool
            latency = (time.perf_counter() - start) * 1000.0
            with self.lock:
                self.result.latencies.append(latency)
                self.result.errors[type(exc).__name__] += 1

    def run(self) -> Result:
        end_time = time.time() + self.duration
        interval = 1.0 / self.rps
        paths = self._cycle_paths()

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            next_tick = time.time()
            while time.time() < end_time:
                now = time.time()
                if now < next_tick:
                    time.sleep(next_tick - now)
                path = next(paths)
                executor.submit(self._request_once, path)
                next_tick += interval
        return self.result

    def _cycle_paths(self):
        while True:
            for path in self.endpoints:
                yield path


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[int(k)]
    d0 = ordered[f] * (c - k)
    d1 = ordered[c] * (k - f)
    return d0 + d1


def login(base_url: str, email: str, password: str, verify: bool) -> Tuple[Optional[str], Optional[Dict]]:
    url = base_url.rstrip("/") + "/auth/login"
    try:
        resp = requests.post(url, json={"email": email, "password": password}, timeout=10, verify=verify)
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token"), data
    except Exception as exc:  # pragma: no cover - operational tool
        print(f"Login failed: {exc}")
        return None, None


def main() -> int:
    parser = argparse.ArgumentParser(description="HTTP load test for read-only endpoints")
    parser.add_argument("--base-url", required=True, help="Base URL, e.g., https://api.example.com")
    parser.add_argument("--rps", type=int, default=5, help="Requests per second")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--concurrency", type=int, default=10, help="Max concurrent workers")
    parser.add_argument("--endpoints", nargs="*", default=DEFAULT_ENDPOINTS, help="Endpoint paths to exercise")
    parser.add_argument("--login-email", help="Email for auth/login")
    parser.add_argument("--login-password", help="Password for auth/login")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification")

    args = parser.parse_args()
    token: Optional[str] = None

    if args.login_email and args.login_password:
        token, payload = login(args.base_url, args.login_email, args.login_password, not args.insecure)
        if not token:
            return 1
        print(f"Authenticated as {payload.get('role')} ({payload.get('user_id')})")

    tester = LoadTester(
        base_url=args.base_url,
        endpoints=args.endpoints,
        token=token,
        rps=args.rps,
        duration=args.duration,
        concurrency=args.concurrency,
        verify_tls=not args.insecure,
    )
    result = tester.run()

    total = sum(result.status_counts.values()) + sum(result.errors.values())
    success = sum(count for code, count in result.status_counts.items() if 200 <= code < 400)
    success_rate = (success / total * 100) if total else 0

    report = {
        "total_requests": total,
        "success_rate_pct": round(success_rate, 2),
        "status_counts": dict(result.status_counts),
        "errors": dict(result.errors),
        "latency_ms": {
            "count": len(result.latencies),
            "p50": round(percentile(result.latencies, 50), 2),
            "p95": round(percentile(result.latencies, 95), 2),
            "max": round(max(result.latencies) if result.latencies else 0, 2),
        },
    }

    print(json.dumps(report, indent=2))
    return 0 if success_rate > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

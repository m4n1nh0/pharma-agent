"""Mede a latência de cada request e coleta métricas de performance."""

import time
import uuid
import json
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Logger próprio: as linhas abaixo são JSON puro, sem prefixo de formatação.
# propagate=False para não duplicar no handler do root (ver basicConfig em app.py).
logger = logging.getLogger("pharma.access")
logger.setLevel(logging.INFO)
logger.propagate = False
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


class MetricsStore:
    def __init__(self, window: int = 1000):
        self._window = window
        self.total_requests = 0
        self.total_errors = 0
        self.durations: deque[float] = deque(maxlen=window)
        self.by_route: dict = defaultdict(lambda: {"count": 0, "errors": 0, "total_ms": 0.0, "max_ms": 0.0})

    def record(self, route: str, duration_ms: float, status_code: int) -> None:
        self.total_requests += 1
        self.durations.append(duration_ms)
        r = self.by_route[route]
        r["count"] += 1
        r["total_ms"] += duration_ms
        r["max_ms"] = max(r["max_ms"], duration_ms)
        if status_code >= 400:
            self.total_errors += 1
            r["errors"] += 1

    def _pct(self, p: int) -> float:
        if not self.durations:
            return 0.0
        s = sorted(self.durations)
        return round(s[min(int(len(s) * p / 100), len(s) - 1)], 2)

    def summary(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate_pct": round((self.total_errors / max(self.total_requests, 1)) * 100, 2),
            "latency_ms": {"p50": self._pct(50), "p95": self._pct(95), "p99": self._pct(99)},
            "by_route": {
                route: {**data, "avg_ms": round(data["total_ms"] / max(data["count"], 1), 2)}
                for route, data in self.by_route.items()
            },
        }


metrics = MetricsStore()


class TimingMiddleware(BaseHTTPMiddleware):
    SKIP = {"/health", "/metrics", "/static", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if any(request.url.path.startswith(p) for p in self.SKIP):
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        route = re.sub(r"/job_[a-z0-9]+", "/{id}", request.url.path)
        start = time.perf_counter()
        request.state.request_id = request_id
        request.state.start_time = start

        logger.info(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "request.start",
            "request_id": request_id,
            "method": request.method,
            "route": route,
        }))

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics.record(route, duration_ms, 500)
            logger.error(json.dumps({"event": "request.error", "request_id": request_id, "error": str(exc), "duration_ms": round(duration_ms, 2)}))
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        metrics.record(route, duration_ms, response.status_code)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        response.headers["X-Route"] = route
        if duration_ms > 5000:
            response.headers["X-Slow-Request"] = "true"

        logger.info(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "request.end",
            "request_id": request_id,
            "route": route,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }))
        return response

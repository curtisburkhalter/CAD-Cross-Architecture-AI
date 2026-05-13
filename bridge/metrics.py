"""
Metrics collection for the Bridge.
In-memory counters. No external dependencies.
"""

import time
from dataclasses import dataclass, field
from collections import deque


@dataclass
class RequestRecord:
    timestamp: float
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    session_id: str


class MetricsCollector:
    def __init__(self, window_seconds: int = 300):
        self._window_seconds = window_seconds
        self._records: deque[RequestRecord] = deque()
        self._total_prompt_tokens: int = 0
        self._total_completion_tokens: int = 0
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._start_time: float = time.time()

    def record_request(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        session_id: str,
    ) -> None:
        now = time.time()
        self._records.append(
            RequestRecord(
                timestamp=now,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                session_id=session_id,
            )
        )
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_requests += 1
        self._prune()

    def record_error(self) -> None:
        self._total_errors += 1

    def get_metrics(self, active_sessions: int) -> dict:
        self._prune()
        now = time.time()
        uptime_seconds = int(now - self._start_time)

        # Windowed stats
        window_records = list(self._records)
        window_requests = len(window_records)
        window_tokens = sum(r.prompt_tokens + r.completion_tokens for r in window_records)
        window_latencies = [r.latency_ms for r in window_records]

        avg_latency = (
            int(sum(window_latencies) / len(window_latencies))
            if window_latencies
            else 0
        )
        p95_latency = (
            int(sorted(window_latencies)[int(len(window_latencies) * 0.95)])
            if window_latencies
            else 0
        )

        # Requests per minute (over window)
        if window_records:
            window_span = now - window_records[0].timestamp
            rpm = (window_requests / max(window_span, 1)) * 60
        else:
            rpm = 0.0

        # Cost comparison (GPT-4o pricing: $2.50/M input, $10.00/M output)
        cloud_cost_input = (self._total_prompt_tokens / 1_000_000) * 2.50
        cloud_cost_output = (self._total_completion_tokens / 1_000_000) * 10.00
        cloud_cost_total = cloud_cost_input + cloud_cost_output

        return {
            "uptime_seconds": uptime_seconds,
            "active_sessions": active_sessions,
            "total": {
                "requests": self._total_requests,
                "errors": self._total_errors,
                "prompt_tokens": self._total_prompt_tokens,
                "completion_tokens": self._total_completion_tokens,
                "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            },
            "window": {
                "seconds": self._window_seconds,
                "requests": window_requests,
                "tokens": window_tokens,
                "avg_latency_ms": avg_latency,
                "p95_latency_ms": p95_latency,
                "requests_per_minute": round(rpm, 1),
            },
            "cloud_cost_equivalent": {
                "model": "GPT-4o",
                "input_cost_usd": round(cloud_cost_input, 4),
                "output_cost_usd": round(cloud_cost_output, 4),
                "total_cost_usd": round(cloud_cost_total, 4),
                "zgx_cost_usd": 0.00,
            },
        }

    def _prune(self) -> None:
        cutoff = time.time() - self._window_seconds
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()

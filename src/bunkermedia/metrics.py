from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean


@dataclass(slots=True)
class TimerSnapshot:
    count: int
    total: float
    avg: float
    p95: float


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._timers: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] += amount

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            bucket = self._timers[name]
            bucket.append(float(value))
            if len(bucket) > 5000:
                del bucket[: len(bucket) - 5000]

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            timers = {k: list(v) for k, v in self._timers.items()}

        timer_stats: dict[str, TimerSnapshot] = {}
        for name, values in timers.items():
            if not values:
                continue
            sorted_values = sorted(values)
            p95_index = min(len(sorted_values) - 1, int(0.95 * (len(sorted_values) - 1)))
            timer_stats[name] = TimerSnapshot(
                count=len(values),
                total=float(sum(values)),
                avg=float(mean(values)),
                p95=float(sorted_values[p95_index]),
            )

        return {
            "counters": counters,
            "gauges": gauges,
            "timers": timer_stats,
        }

    def render_prometheus(self) -> str:
        snap = self.snapshot()
        counters = snap["counters"]
        gauges = snap["gauges"]
        timers = snap["timers"]

        lines: list[str] = []
        for name, value in sorted(counters.items()):
            metric = _sanitize(name)
            lines.append(f"# TYPE {metric} counter")
            lines.append(f"{metric} {float(value):.6f}")

        for name, value in sorted(gauges.items()):
            metric = _sanitize(name)
            lines.append(f"# TYPE {metric} gauge")
            lines.append(f"{metric} {float(value):.6f}")

        for name, timer in sorted(timers.items()):
            prefix = _sanitize(name)
            lines.append(f"# TYPE {prefix}_count gauge")
            lines.append(f"{prefix}_count {timer.count}")
            lines.append(f"# TYPE {prefix}_sum gauge")
            lines.append(f"{prefix}_sum {timer.total:.6f}")
            lines.append(f"# TYPE {prefix}_avg gauge")
            lines.append(f"{prefix}_avg {timer.avg:.6f}")
            lines.append(f"# TYPE {prefix}_p95 gauge")
            lines.append(f"{prefix}_p95 {timer.p95:.6f}")

        return "\n".join(lines) + "\n"


def _sanitize(name: str) -> str:
    chars: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in {"_", ":"}:
            chars.append(ch)
        else:
            chars.append("_")
    sanitized = "".join(chars)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"m_{sanitized}"
    return sanitized

"""
Latency-under-load benchmark — measures p50/p95/p99 latency and throughput
under concurrent request load, split by which layer handles the request
(Policy Engine only vs. requests that reach the LLM Judge), since these
have fundamentally different latency profiles.

Run: python scripts/latency_benchmark.py
"""

import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from agent_sentinel.core.engine import SentinelEngine
from agent_sentinel.core.types import Action, Source

engine = SentinelEngine(config_path="config/default_policy.yaml")

CONCURRENCY_LEVELS = [1, 5, 10, 20]
REQUESTS_PER_LEVEL = 30


def make_policy_only_action():
    return Action(
        tool="write_file",
        args={"path": "/etc/passwd", "content": "x"},
        agent_id=f"bench-{uuid.uuid4().hex[:8]}",  # unique per request
        session_id=f"bench-{uuid.uuid4().hex[:8]}",
        source=Source.PYTHON_MIDDLEWARE,
        context={"original_task": "Benchmark run."},
    )


def make_judge_path_action():
    return Action(
        tool="send_email",
        args={"to": "teammate@company.com", "body": "Status update."},
        agent_id=f"bench-{uuid.uuid4().hex[:8]}",  # unique per request — avoids rate limiter
        session_id=f"bench-{uuid.uuid4().hex[:8]}",
        source=Source.PYTHON_MIDDLEWARE,
        context={"original_task": "Send the weekly status update."},
    )


def single_call(action_factory):
    action = action_factory()
    start = time.perf_counter()
    engine.evaluate(action)
    return (time.perf_counter() - start) * 1000


def percentile(data, p):
    data = sorted(data)
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def run_benchmark(label, action_factory):
    print(f"\n=== {label} ===")
    print(
        f"{'Concurrency':<12} {'p50 (ms)':<10} {'p95 (ms)':<10} {'p99 (ms)':<10} {'Max (ms)':<10} {'Throughput (req/s)':<18}"
    )
    print("-" * 75)

    for concurrency in CONCURRENCY_LEVELS:
        latencies = []
        wall_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(single_call, action_factory)
                for _ in range(REQUESTS_PER_LEVEL)
            ]
            for future in as_completed(futures):
                latencies.append(future.result())

        wall_elapsed = time.perf_counter() - wall_start
        throughput = REQUESTS_PER_LEVEL / wall_elapsed

        p50 = percentile(latencies, 50)
        p95 = percentile(latencies, 95)
        p99 = percentile(latencies, 99)
        max_lat = max(latencies)

        print(
            f"{concurrency:<12} {p50:<10.1f} {p95:<10.1f} {p99:<10.1f} {max_lat:<10.1f} {throughput:<18.2f}"
        )


if __name__ == "__main__":
    run_benchmark(
        "Policy Engine only (fast path, no LLM call)", make_policy_only_action
    )
    run_benchmark("Full pipeline through LLM Judge (slow path)", make_judge_path_action)

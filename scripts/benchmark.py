import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


def call_api(url: str, prompt: str, max_tokens: int) -> tuple[float, int | None, float | None]:
    started = time.perf_counter()
    response = httpx.post(
        f"{url.rstrip('/')}/generate",
        json={"prompt": prompt, "max_tokens": max_tokens},
        timeout=180,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    payload = response.json()
    return elapsed, payload.get("eval_count"), payload.get("tokens_per_second")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the Gemma serving API.")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for the API.")
    parser.add_argument("--requests", type=int, default=10, help="Total number of requests.")
    parser.add_argument("--concurrency", type=int, default=2, help="Concurrent workers.")
    parser.add_argument(
        "--prompt",
        default="Explain the role of observability in AI serving in three concise bullets.",
        help="Prompt to send to the model.",
    )
    parser.add_argument("--max-tokens", type=int, default=128, help="Maximum generated tokens.")
    args = parser.parse_args()

    latencies: list[float] = []
    token_rates: list[float] = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(call_api, args.url, args.prompt, args.max_tokens)
            for _ in range(args.requests)
        ]
        for future in as_completed(futures):
            latency, eval_count, tokens_per_second = future.result()
            latencies.append(latency)
            if tokens_per_second is not None:
                token_rates.append(tokens_per_second)
            token_rate_label = (
                f"{tokens_per_second:.2f}" if tokens_per_second is not None else "n/a"
            )
            print(
                f"request latency={latency:.2f}s "
                f"eval_tokens={eval_count if eval_count is not None else 'n/a'} "
                f"tokens_per_second={token_rate_label}"
            )

    print("\nsummary")
    print(f"requests={len(latencies)} concurrency={args.concurrency}")
    print(f"latency_avg={statistics.mean(latencies):.2f}s")
    latency_p95 = (
        f"{statistics.quantiles(latencies, n=20)[-1]:.2f}s" if len(latencies) >= 2 else "n/a"
    )
    print(f"latency_p95={latency_p95}")
    if token_rates:
        print(f"tokens_per_second_avg={statistics.mean(token_rates):.2f}")


if __name__ == "__main__":
    main()

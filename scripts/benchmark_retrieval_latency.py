"""
Measures the number claimed on the resume:
"Cut hybrid search query latency to p95 [Number]ms by building HNSW and GIN
indexes, managing a threaded connection pool, and pre-caching model weights."

Times storage.retriever.hybrid_search() directly, in-process — i.e. query
embedding + the single RRF SQL transaction. It deliberately does NOT go through
the /api/v1/query HTTP endpoint, because that path also calls gpt-4o-mini for
generation, and that LLM round trip (1-3s+) would dominate and bury the exact
thing this bullet is attributing to indexes/pooling/pre-caching.

Requires a real Postgres connection (same env contract as the rest of the app:
DB_PASSWORD etc. via .env.<APP_ENV>) and an indexed corpus.

Usage:
    python scripts/benchmark_retrieval_latency.py
    python scripts/benchmark_retrieval_latency.py --iterations 200 --warmup 10
    python scripts/benchmark_retrieval_latency.py --out-csv scripts/latency_results.csv
"""
import argparse
import csv
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.retriever import hybrid_search
from core.config import settings

DEFAULT_QUESTIONS = [
    "What is a RandomForestClassifier and how does it combine multiple trees?",
    "How does gradient boosting build an ensemble of weak learners?",
    "What is K-Means clustering and how does it choose cluster centers?",
    "How does DBSCAN identify noise points and core samples?",
    "What is the difference between Ridge and Lasso regression regularization?",
    "How does logistic regression estimate class probabilities?",
    "How is a decision tree built and split at each node?",
    "What criteria does scikit-learn use to choose decision tree splits?",
    "How does cross-validation help prevent overfitting?",
    "What does the alpha parameter control in Ridge regression?",
]


def percentile(sorted_data: list[float], pct: float) -> float:
    if not sorted_data:
        return float("nan")
    k = (len(sorted_data) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_data) - 1)
    if f == c:
        return sorted_data[f]
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5,
                         help="Untimed calls first — absorbs embedding-model lazy-load and DB pool ramp-up")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--questions-file", default=None, help="JSON list of question strings; defaults to a baked-in pool")
    parser.add_argument("--out-csv", default=None)
    args = parser.parse_args()

    questions = DEFAULT_QUESTIONS
    if args.questions_file:
        import json
        questions = json.loads(Path(args.questions_file).read_text())

    print(f"[BENCH] APP_ENV={settings.APP_ENV}  DB={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"[BENCH] Warming up ({args.warmup} calls, untimed) ...")
    for i in range(args.warmup):
        hybrid_search(questions[i % len(questions)], top_k=args.top_k)

    print(f"[BENCH] Running {args.iterations} timed calls to hybrid_search() ...")
    latencies_ms = []
    rows = []
    for i in range(args.iterations):
        question = questions[i % len(questions)]
        start = time.perf_counter()
        results = hybrid_search(question, top_k=args.top_k)
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed_ms)
        rows.append({"index": i, "question": question, "latency_ms": round(elapsed_ms, 2), "results_returned": len(results)})

    latencies_ms.sort()
    print("\n" + "=" * 60)
    print(" HYBRID SEARCH RETRIEVAL LATENCY (query embed + RRF SQL)")
    print("=" * 60)
    print(f" Iterations:  {len(latencies_ms)}")
    print(f" p50:         {percentile(latencies_ms, 50):.1f} ms")
    print(f" p95:         {percentile(latencies_ms, 95):.1f} ms")
    print(f" p99:         {percentile(latencies_ms, 99):.1f} ms")
    print(f" min/mean/max:{min(latencies_ms):.1f} / {statistics.mean(latencies_ms):.1f} / {max(latencies_ms):.1f} ms")
    print("=" * 60)
    print(f"\n Suggested resume number: p95 above, labeled "
          f"'{settings.APP_ENV.lower()}, N={len(latencies_ms)} calls, top_k={args.top_k}'.")

    if args.out_csv:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["index", "question", "latency_ms", "results_returned"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[BENCH] Per-call rows written to {args.out_csv}")


if __name__ == "__main__":
    main()

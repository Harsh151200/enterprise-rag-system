"""
Measures the retrieval-relevance improvement claimed on the resume:
"Improved retrieval relevance by [Metric]% through hybrid search orchestration."

Runs each question in the eval dataset through three retrieval strategies against
the SAME indexed corpus:
  - vector-only  (dense cosine search, no fusion)
  - fts-only     (English full-text search, no fusion)
  - hybrid       (production storage.retriever.hybrid_search — RRF fusion of both)

For each strategy it reports Recall@K (did a chunk from an expected source_file
land in the top K) and MRR (how high it ranked). The headline number is hybrid's
Recall@K / MRR lift over the best single-strategy baseline — that lift is the
[Metric]% for the resume bullet.

Requires a real Postgres connection (same env contract as the rest of the app:
DB_PASSWORD etc. via .env.<APP_ENV>) and an indexed corpus — run `cli.py ingest`
first if the target DB is empty.

Usage:
    python evaluation_scripts/eval_retrieval_relevance.py
    python evaluation_scripts/eval_retrieval_relevance.py --top-k 4 --dataset evaluation_scripts/eval_dataset.json
    python evaluation_scripts/eval_retrieval_relevance.py --out-csv evaluation_scripts/eval_results.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.db_pool import db_pool
from storage.retriever import hybrid_search
from components.embedding_provider import embedding_engine
from core.config import settings


def vector_only_sources(question: str, top_k: int) -> list[str]:
    vector = embedding_engine.embed_text(question)
    sql = """
        SELECT source_file
        FROM enterprise_documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (vector, top_k))
        rows = cursor.fetchall()
        cursor.close()
        return [row[0] for row in rows]
    finally:
        db_pool.putconn(conn)


def fts_only_sources(question: str, top_k: int) -> list[str]:
    sql = """
        SELECT source_file
        FROM enterprise_documents
        WHERE text_vector @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank_cd(text_vector, plainto_tsquery('english', %s)) DESC
        LIMIT %s;
    """
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, (question, question, top_k))
        rows = cursor.fetchall()
        cursor.close()
        return [row[0] for row in rows]
    finally:
        db_pool.putconn(conn)


def hybrid_sources(question: str, top_k: int) -> list[str]:
    return [row["source"] for row in hybrid_search(question, top_k=top_k)]


def first_hit_rank(retrieved_sources: list[str], expected_substrings: list[str]) -> int | None:
    for rank, source in enumerate(retrieved_sources, start=1):
        if any(expected.lower() in source.lower() for expected in expected_substrings):
            return rank
    return None


def evaluate_strategy(label, strategy_fn, dataset, top_k):
    per_question = []
    reciprocal_ranks = []
    hits = 0
    for item in dataset:
        sources = strategy_fn(item["question"], top_k)
        rank = first_hit_rank(sources, item["expected_source_contains"])
        if rank:
            hits += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
        per_question.append({
            "strategy": label,
            "question": item["question"],
            "expected": ";".join(item["expected_source_contains"]),
            "hit_rank": rank if rank else "",
            "retrieved_sources": ";".join(sources),
        })
    return {
        "label": label,
        "recall_at_k": hits / len(dataset),
        "mrr": mean(reciprocal_ranks),
        "rows": per_question,
    }


def pct_lift(hybrid_value: float, baseline_value: float) -> str:
    if baseline_value == 0:
        return "N/A (baseline scored 0)" if hybrid_value == 0 else "inf (baseline scored 0)"
    return f"{((hybrid_value - baseline_value) / baseline_value) * 100:+.1f}%"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "eval_dataset.json"))
    parser.add_argument("--top-k", type=int, default=4, help="Matches production top_k (default 4)")
    parser.add_argument("--out-csv", default=None, help="Optional path to dump per-question rows")
    args = parser.parse_args()

    dataset = json.loads(Path(args.dataset).read_text())
    if len(dataset) < 10:
        print(f"[WARN] Only {len(dataset)} eval questions — treat results as a smoke test, "
              f"not a resume-worthy number. Expand evaluation_scripts/eval_dataset.json for a credible sample size.",
              file=sys.stderr)

    print(f"[EVAL] APP_ENV={settings.APP_ENV}  DB={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"[EVAL] {len(dataset)} questions, top_k={args.top_k}\n")

    strategies = [
        ("vector-only", vector_only_sources),
        ("fts-only", fts_only_sources),
        ("hybrid-rrf", hybrid_sources),
    ]

    results = {}
    all_rows = []
    for label, fn in strategies:
        print(f"[EVAL] Running strategy: {label} ...")
        result = evaluate_strategy(label, fn, dataset, args.top_k)
        results[label] = result
        all_rows.extend(result["rows"])

    print("\n" + "=" * 72)
    print(f" RETRIEVAL RELEVANCE — Recall@{args.top_k} and MRR by strategy")
    print("=" * 72)
    print(f" {'Strategy':<14} | {'Recall@K':<10} | {'MRR':<8}")
    print(f" {'-' * 14} + {'-' * 10} + {'-' * 8}")
    for label, _ in strategies:
        r = results[label]
        print(f" {label:<14} | {r['recall_at_k']:<10.2%} | {r['mrr']:<8.3f}")
    print("=" * 72)

    baseline_label = max(
        ("vector-only", "fts-only"),
        key=lambda l: results[l]["recall_at_k"],
    )
    hybrid = results["hybrid-rrf"]
    baseline = results[baseline_label]

    print(f"\n Best single-strategy baseline: {baseline_label} "
          f"(Recall@{args.top_k}={baseline['recall_at_k']:.2%}, MRR={baseline['mrr']:.3f})")
    print(f" Hybrid RRF vs. that baseline:")
    print(f"   Recall@{args.top_k} lift: {pct_lift(hybrid['recall_at_k'], baseline['recall_at_k'])}")
    print(f"   MRR lift:        {pct_lift(hybrid['mrr'], baseline['mrr'])}")
    print(f"\n Suggested resume number: the Recall@{args.top_k} (or MRR) lift above, "
          f"labeled '{baseline_label} baseline, N={len(dataset)} questions, corpus=<describe corpus>'.")

    if args.out_csv:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["strategy", "question", "expected", "hit_rank", "retrieved_sources"])
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\n[EVAL] Per-question rows written to {args.out_csv}")


if __name__ == "__main__":
    main()

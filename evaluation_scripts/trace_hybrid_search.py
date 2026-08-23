"""
Dry-runs storage.retriever.hybrid_search() for a single query and shows the
work: the embedding call, the vector-only ranking, the FTS-only ranking, and
how Reciprocal Rank Fusion (RRF) blends the two into the final top_k.

hybrid_search() itself only returns the final blended rows — it never surfaces
which candidates came from which strategy, or why one row outranked another.
This script re-runs the same two CTEs from storage/retriever.py individually
so you can see the intermediate ranks before they get fused, plus (optionally)
the Postgres EXPLAIN ANALYZE plan for the real query.

Usage:
    python evaluation_scripts/trace_hybrid_search.py "your query here"
    python evaluation_scripts/trace_hybrid_search.py "your query here" --top-k 4 --explain
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.db_pool import db_pool
from components.embedding_provider import embedding_engine
from core.config import settings

RRF_K = 60.0  # matches the "60.0" constant hard-coded in storage/retriever.py


def vector_ranks(cursor, query_vector, candidate_limit):
    cursor.execute(
        """
        SELECT id, source_file, chunk_index,
               ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) AS rank,
               embedding <=> %s::vector AS distance
        FROM enterprise_documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """,
        (query_vector, query_vector, query_vector, candidate_limit),
    )
    return {row[0]: {"source": row[1], "chunk_index": row[2], "rank": row[3], "distance": row[4]}
            for row in cursor.fetchall()}


def fts_ranks(cursor, user_query, candidate_limit):
    cursor.execute(
        """
        SELECT id, source_file, chunk_index,
               ROW_NUMBER() OVER (ORDER BY ts_rank_cd(text_vector, plainto_tsquery('english', %s)) DESC) AS rank,
               ts_rank_cd(text_vector, plainto_tsquery('english', %s)) AS ts_score
        FROM enterprise_documents
        WHERE text_vector @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank_cd(text_vector, plainto_tsquery('english', %s)) DESC
        LIMIT %s;
        """,
        (user_query, user_query, user_query, user_query, candidate_limit),
    )
    return {row[0]: {"source": row[1], "chunk_index": row[2], "rank": row[3], "ts_score": row[4]}
            for row in cursor.fetchall()}


def explain_plan(cursor, query_vector, user_query, candidate_limit, top_k):
    from storage.retriever import hybrid_search  # reuse the exact production SQL string
    import inspect
    src = inspect.getsource(hybrid_search)
    start = src.index('"""', src.index("rrf_query")) + 3
    end = src.index('"""', start)
    rrf_query = src[start:end]
    cursor.execute(
        "EXPLAIN (ANALYZE, COSTS, TIMING, BUFFERS) " + rrf_query,
        (query_vector, query_vector, candidate_limit, user_query, user_query, user_query,
         candidate_limit, top_k),
    )
    return [row[0] for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", help="The user query string to trace")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--oversample-factor", type=int, default=5)
    parser.add_argument("--explain", action="store_true", help="Also print the Postgres EXPLAIN ANALYZE plan")
    args = parser.parse_args()

    candidate_limit = args.top_k * args.oversample_factor

    print(f"[TRACE] APP_ENV={settings.APP_ENV}  DB={settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}")
    print(f"[TRACE] query={args.query!r}  top_k={args.top_k}  candidate_limit={candidate_limit}\n")

    # Step 1: embedding
    print("STEP 1 — embed the query")
    query_vector = embedding_engine.embed_text(args.query)
    print(f"  embed_text() prefixes the string with 'search_document: ' (same prefix used at ingest time)")
    print(f"  vector dim={len(query_vector)}  first 6 values={[round(v, 4) for v in query_vector[:6]]}\n")

    conn = db_pool.getconn()
    try:
        cursor = conn.cursor()

        # Step 2: two independent rankings
        print(f"STEP 2 — rank candidates independently (LIMIT {candidate_limit} each)")
        vranks = vector_ranks(cursor, query_vector, candidate_limit)
        franks = fts_ranks(cursor, args.query, candidate_limit)
        print(f"  vector_search matched {len(vranks)} rows (always returns candidate_limit rows — cosine distance has no cutoff)")
        print(f"  fts_search matched {len(franks)} rows (can be fewer than candidate_limit — requires a lexeme overlap)\n")

        # Step 3: fuse
        all_ids = set(vranks) | set(franks)
        blended = []
        for doc_id in all_ids:
            v = vranks.get(doc_id)
            f = franks.get(doc_id)
            v_score = 1.0 / (RRF_K + v["rank"]) if v else 0.0
            f_score = 1.0 / (RRF_K + f["rank"]) if f else 0.0
            blended.append({
                "id": doc_id,
                "source": (v or f)["source"],
                "chunk_index": (v or f)["chunk_index"],
                "vector_rank": v["rank"] if v else None,
                "fts_rank": f["rank"] if f else None,
                "rrf_score": v_score + f_score,
            })
        blended.sort(key=lambda r: -r["rrf_score"])

        print(f"STEP 3 — RRF fusion: score = 1/({RRF_K:.0f}+vector_rank) + 1/({RRF_K:.0f}+fts_rank)")
        print(f"  {len(all_ids)} distinct docs surfaced by either strategy, before top_k trim\n")

        header = f"  {'#':<3} {'source':<45} {'chunk':<6} {'vec_rank':<9} {'fts_rank':<9} {'rrf_score':<10}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for i, row in enumerate(blended[:args.top_k], start=1):
            marker = " <-- FINAL top_k" if i <= args.top_k else ""
            print(f"  {i:<3} {Path(row['source']).name[:45]:<45} {row['chunk_index']:<6} "
                  f"{str(row['vector_rank']):<9} {str(row['fts_rank']):<9} {row['rrf_score']:<10.5f}{marker}")

        cutoff_rank_would_show = min(len(blended), args.top_k + 3)
        if cutoff_rank_would_show > args.top_k:
            print(f"\n  Just below the cut ({args.top_k+1}..{cutoff_rank_would_show}), to see how close the call was:")
            for i, row in enumerate(blended[args.top_k:cutoff_rank_would_show], start=args.top_k + 1):
                print(f"  {i:<3} {Path(row['source']).name[:45]:<45} {row['chunk_index']:<6} "
                      f"{str(row['vector_rank']):<9} {str(row['fts_rank']):<9} {row['rrf_score']:<10.5f}")

        if args.explain:
            print("\nSTEP 4 — Postgres EXPLAIN ANALYZE of the real production query")
            for line in explain_plan(cursor, query_vector, args.query, candidate_limit, args.top_k):
                if len(line) > 220:
                    line = line[:220] + " ...<vector literal truncated>"
                print(f"  {line}")

        cursor.close()
    finally:
        db_pool.putconn(conn)


if __name__ == "__main__":
    main()

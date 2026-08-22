"""
Ingests a curated, explicit list of scikit-learn doc pages — e.g. just the
"supervised learning" module pages — instead of a full-site crawl.

Why not just point `cli.py ingest --type web` at a topic index page like
https://scikit-learn.org/stable/supervised_learning.html?

DynamicWebCrawlerConnector.crawl_tree() (ingestion/connectors.py) parses every
<a href> on each fetched page — nav bar, sidebar, footer included — and enqueues
anything on the same domain matching path_filter. path_filter is a single
substring, hardcoded to "/stable/" in components/embedder.py, i.e. "anywhere in
the docs" — not scoped to a topic. So a BFS crawl seeded from one topic page
still pulls in the site's full nav within a page or two; limiting max_pages just
crops that wander short, it doesn't keep it on-topic.

This script sidesteps that instead of patching the crawler: it calls the ingestion
pipeline once per URL with max_resources=1. crawl_tree()'s loop condition is
`while queue and len(visited_urls) < max_pages` — with max_pages=1 it fetches
exactly the seed URL and stops before following any link found on it. Looping
that call in-process (rather than shelling out to `cli.py` once per URL) keeps
the embedding model loaded across calls instead of reloading it once per page.

Usage:
    python scripts/ingest_topic_subset.py --urls-file scripts/topic_urls_supervised_learning.json
    python scripts/ingest_topic_subset.py --urls-file scripts/topic_urls_supervised_learning.json --batch-size 50 --delay 1.0

Each URL becomes its own pipeline_runs audit row (visible via `cli.py status` /
GET /api/v1/logs) — that's expected, not a bug: one run per page.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.embedder import run_production_ingestion_pipeline
from core.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--urls-file", required=True, help="JSON list of exact page URLs to ingest")
    parser.add_argument("--batch-size", type=int, default=50, help="Embedding buffer, passed straight through to the pipeline")
    parser.add_argument("--delay", type=float, default=0.0, help="Extra seconds to sleep between pages, on top of the crawler's own 0.5s per fetch")
    args = parser.parse_args()

    urls = json.loads(Path(args.urls_file).read_text())
    print(f"[INGEST-SUBSET] APP_ENV={settings.APP_ENV}  target={len(urls)} pages from {args.urls_file}")

    succeeded, failed = 0, 0
    for i, url in enumerate(urls, start=1):
        print(f"\n[INGEST-SUBSET] ({i}/{len(urls)}) {url}")
        try:
            run_production_ingestion_pipeline(
                source_type="web",
                target_path=url,
                embedding_batch_size=args.batch_size,
                max_resources=1,
            )
            succeeded += 1
        except Exception as e:
            print(f"[INGEST-SUBSET ERROR] {url} failed: {e}", file=sys.stderr)
            failed += 1
        if args.delay:
            time.sleep(args.delay)

    print(f"\n[INGEST-SUBSET] Done. {succeeded} page(s) ingested or already indexed, {failed} failed.")
    print("[INGEST-SUBSET] Run `python cli.py status` to see chunk counts by format.")


if __name__ == "__main__":
    main()

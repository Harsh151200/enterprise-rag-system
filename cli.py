import argparse
import sys
from core.config import settings
from components.embedder import run_production_ingestion_pipeline
from components.orchestrator import generate_rag_response
from storage.analytics import get_platform_status_metrics

def execute_status_check() -> None:
    """Consumes the unified analytics module to render system distribution status."""
    print("[CLI] Fetching data repository storage status statistics...")
    try:
        metrics = get_platform_status_metrics()
        
        print("\n" + "=" * 60)
        print("          SYSTEM DATA PLATFORM HEALTH & STATUS REPORT")
        print("=" * 60)
        print(f" Database Target Status: CONNECTED")
        print(f" Total Vector Chunks Indexed: {metrics['total_chunks_indexed']}")
        print(f" Active Environment Mode: {settings.APP_ENV}")
        print("-" * 60)
        print(f" {'FORMAT':<15} | {'UNIQUE DOCUMENTS':<18} | {'TOTAL CHUNKS':<12}")
        print(f" {'-' * 15} + {'-' * 18} + {'-' * 12}")
        
        for fmt, data in metrics["formats_distribution"].items():
            print(f" {fmt.upper():<15} | {data['unique_documents']:<18} | {data['total_chunks']:<12}")
            
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"[CLI ERROR] Could not extract database status: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Enterprise RAG Automated Ingestion and Retrieval CLI Console Utility")
    subparsers = parser.add_subparsers(dest="command", help="Operational sub-commands")

    ingest_parser = subparsers.add_parser("ingest", help="Trigger the streaming data ingestion ETL pipeline")
    ingest_parser.add_argument("--type", choices=["local", "web"], required=True, help="The retrieval connector type")
    ingest_parser.add_argument("--path", required=True, help="The file path or website URL target")
    ingest_parser.add_argument("--limit", type=int, default=None, help="Document cap threshold")
    ingest_parser.add_argument("--batch-size", type=int, default=50, help="Memory processing chunk buffer limit")

    query_parser = subparsers.add_parser("query", help="Submit questions to the parallel hybrid RAG engine")
    query_parser.add_argument("question", type=str, help="The query string to evaluate")

    subparsers.add_parser("status", help="Display data health metrics")

    args = parser.parse_args()

    if args.command == "ingest":
        run_production_ingestion_pipeline(
            source_type=args.type, target_path=args.path,
            embedding_batch_size=args.batch_size, max_resources=args.limit
        )
    elif args.command == "query":
        answer = generate_rag_response(user_query=args.question)
        print(f"\n==================== CONSOLE ANSWER ====================\n{answer}\n========================================================\n")
    elif args.command == "status":
        execute_status_check()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
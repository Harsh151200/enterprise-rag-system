import argparse
import sys
import psycopg2
from core.config import settings
from components.embedder import run_production_ingestion_pipeline
from components.orchestrator import generate_rag_response

def execute_status_check() -> None:
    """Queries the database to report row statistics and data distribution."""
    print("[CLI] Fetching data repository storage status statistics...")
    try:
        conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
        cursor = conn.cursor()
        
        # Check total vector chunks stored
        cursor.execute("SELECT COUNT(*) FROM sklearn_docs;")
        total_chunks = cursor.fetchone()[0]
        
        # Check unique source documents grouped by format type
        cursor.execute("""
            SELECT doc_format, COUNT(DISTINCT source_file), COUNT(*) 
            FROM sklearn_docs 
            GROUP BY doc_format;
        """)
        distribution_rows = cursor.fetchall()
        
        print("\n" + "=" * 60)
        print("          SYSTEM DATA PLATFORM HEALTH & STATUS REPORT")
        print("=" * 60)
        print(f" Database Target Status: CONNECTED")
        print(f" Total Vector Chunks Indexed: {total_chunks}")
        print(f" Active Environment Mode: {settings.APP_ENV}")
        print("-" * 60)
        print(f" {'FORMAT':<15} | {'UNIQUE DOCUMENTS':<18} | {'TOTAL CHUNKS':<12}")
        print(f" {'-' * 15} + {'-' * 18} + {'-' * 12}")
        
        for fmt, distinct_docs, chunks in distribution_rows:
            format_label = str(fmt).upper()
            print(f" {format_label:<15} | {distinct_docs:<18} | {chunks:<12}")
            
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"[CLI ERROR] Could not extract database status: {e}", file=sys.stderr)
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Enterprise RAG Automated Ingestion and Retrieval CLI Console Utility"
    )
    subparsers = parser.add_subparsers(dest="command", help="Operational sub-commands")

    # 1. Ingestion Sub-command Configuration
    ingest_parser = subparsers.add_parser("ingest", help="Trigger the streaming data ingestion ETL pipeline")
    ingest_parser.add_argument(
        "--type", 
        choices=["local", "web"], 
        required=True, 
        help="The retrieval connector channel mechanism to initialize"
    )
    ingest_parser.add_argument(
        "--path", 
        required=True, 
        help="The local file-system folder path or seed website root URL target"
    )
    ingest_parser.add_argument(
        "--limit", 
        type=int, 
        default=None, 
        help="Pluggable page or document cap guardrail restriction threshold limit"
    )
    ingest_parser.add_argument(
        "--batch-size", 
        type=int, 
        default=50, 
        help="The size constraint limits for volatile memory vector mapping dispatches"
    )

    # 2. Query Sub-command Configuration
    query_parser = subparsers.add_parser("query", help="Submit questions to the parallel hybrid RAG engine")
    query_parser.add_argument(
        "question", 
        type=str, 
        help="The question string or search prompt statement to evaluate"
    )

    # 3. Status Sub-command Configuration
    subparsers.add_parser("status", help="Display data distribution layouts and repository index health metrics")

    # Parse system terminal inputs
    args = parser.parse_args()

    # Route execution to correct functional module anchors
    if args.command == "ingest":
        print(f"[CLI] Launching ingestion execution flow target path: {args.path}")
        try:
            run_production_ingestion_pipeline(
                source_type=args.type,
                target_path=args.path,
                embedding_batch_size=args.batch_size,
                max_resources=args.limit
            )
        except Exception as e:
            print(f"[CLI CRITICAL ERROR] Ingestion engine execution collapsed: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "query":
        try:
            answer = generate_rag_response(user_query=args.question)
            print("\n" + "=" * 40 + " CONSOLE ANSWER " + "=" * 40)
            print(answer)
            print("=" * 96 + "\n")
        except Exception as e:
            print(f"[CLI CRITICAL ERROR] Orchestrator query retrieval collapsed: {e}", file=sys.stderr)
            sys.exit(1)
            
    elif args.command == "status":
        execute_status_check()
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
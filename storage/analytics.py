import psycopg2
from typing import Dict, Any, List
from core.config import settings

def get_platform_status_metrics() -> Dict[str, Any]:
    """Queries the database to compile chunk distribution metrics across data formats."""
    conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM enterprise_documents;")
        total_chunks = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT doc_format, COUNT(DISTINCT source_file), COUNT(*) 
            FROM enterprise_documents 
            GROUP BY doc_format;
        """)
        distribution_rows = cursor.fetchall()
        
        format_summary = {}
        for row in distribution_rows:
            fmt_name = str(row[0]).lower()
            format_summary[fmt_name] = {
                "unique_documents": row[1],
                "total_chunks": row[2]
            }
            
        return {
            "database_connected": True,
            "total_chunks_indexed": total_chunks,
            "formats_distribution": format_summary
        }
    finally:
        cursor.close()
        conn.close()

def get_historical_pipeline_logs(limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves execution records directly from the pipeline_runs table for UI rendering."""
    conn = psycopg2.connect(settings.SQLALCHEMY_DATABASE_URI)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT run_id, pipeline_name, environment, status, 
                   records_extracted, records_transformed, records_indexed, 
                   error_message, started_at, completed_at 
            FROM pipeline_runs 
            ORDER BY started_at DESC 
            LIMIT %s;
        """, (limit,))
        rows = cursor.fetchall()
        
        logs = []
        for r in rows:
            logs.append({
                "run_id": r[0],
                "pipeline_name": r[1],
                "environment": r[2],
                "status": r[3],
                "extracted": r[4],
                "transformed": r[5],
                "indexed": r[6],
                "error": r[7],
                "started_at": str(r[8]) if r[8] else None,
                "completed_at": str(r[9]) if r[9] else None
            })
        return logs
    finally:
        cursor.close()
        conn.close()
import uuid
from datetime import datetime, timezone
import psycopg2
from core.config import settings

class PipelineLogger:
    """
    An isolated controller database interface responsible for logging 
    the active lifecycle states of document scraping, parsing, and vector ingestion jobs.
    """
    def __init__(self):
        # Read the automatically compiled database URI connection from your Pydantic layer
        self.db_uri = settings.SQLALCHEMY_DATABASE_URI

    def _get_connection(self):
        return psycopg2.connect(self.db_uri)

    def start_run(self, pipeline_name: str) -> uuid.UUID:
        """Creates an entry inside the audit log matrix flagging a pipeline startup execution."""
        run_id = uuid.uuid4()
        query = """
            INSERT INTO pipeline_runs (run_id, pipeline_name, environment, status, started_at)
            VALUES (%s, %s, %s, 'RUNNING', %s);
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (str(run_id), pipeline_name, settings.APP_ENV, datetime.now(timezone.utc)))
            conn.commit()
            print(f"[Audit Ledger Logged] Pipeline run {run_id} initiated successfully.")
            return run_id
        except Exception as e:
            conn.rollback()
            print(f"Failed to write startup pipeline log telemetry metric entry: {e}")
            return run_id
        finally:
            conn.close()

    def complete_run(self, run_id: uuid.UUID, extracted: int, transformed: int, indexed: int):
        """Updates the tracking record flag, shifting status to a clean SUCCESS checkpoint."""
        query = """
            UPDATE pipeline_runs 
            SET status = 'SUCCESS',
                records_extracted = %s,
                records_transformed = %s,
                records_indexed = %s,
                completed_at = %s
            WHERE run_id = %s;
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (extracted, transformed, indexed, datetime.now(timezone.utc), str(run_id)))
            conn.commit()
            print(f"[Audit Ledger Logged] Pipeline run {run_id} terminated with clear SUCCESS state metrics.")
        except Exception as e:
            conn.rollback()
            print(f"Failed to write completion state metric database updates for run {run_id}: {e}")
        finally:
            conn.close()

    def fail_run(self, run_id: uuid.UUID, error: Exception, extracted: int = 0, transformed: int = 0, indexed: int = 0):
        """Captures code stack trace panic strings, marking the target run entry as FAILED."""
        query = """
            UPDATE pipeline_runs 
            SET status = 'FAILED',
                records_extracted = %s,
                records_transformed = %s,
                records_indexed = %s,
                completed_at = %s,
                error_message = %s
            WHERE run_id = %s;
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (extracted, transformed, indexed, datetime.now(timezone.utc), str(error), str(run_id)))
            conn.commit()
            print(f"❌ [Audit Ledger Logged] Pipeline run {run_id} written to ledger with critical FAILED state marker.")
        except Exception as e:
            conn.rollback()
            print(f"⚠️ Failed to log crash signature trace for run {run_id}: {e}")
        finally:
            conn.close()
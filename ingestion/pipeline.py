import os
from typing import List, Dict, Any
from ingestion.deduplicator import ContentDeduplicator
from ingestion.transformer import SemanticChunkTransformer
from ingestion.parsers import TXTParser, HTMLParser, PDFParser, DOCXParser, CodeParser

class IngestionPipeline:
    """
    The master router that directs raw data through deduplication, parsing, and chunking.
    """
    def __init__(self):
        self.deduplicator = ContentDeduplicator()
        self.transformer = SemanticChunkTransformer(chunk_size=1000, chunk_overlap=150)
        
        # Router map to select the correct parser based on file extension
        self.parsers = {
            ".txt": TXTParser(),
            ".md": TXTParser(),
            ".html": HTMLParser(),
            ".htm": HTMLParser(),
            ".pdf": PDFParser(),
            ".docx": DOCXParser(),
            ".py": CodeParser(),
            ".json": CodeParser(),
            ".xml": CodeParser()
        }

    def _get_parser(self, file_path: str):
        """Resolves the file extension to the correct parser instance."""
        ext = os.path.splitext(file_path)[1].lower()
        return self.parsers.get(ext, TXTParser()) # Fallback to plain text

    def process_file(self, source_uri: str, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """Executes the full ETL chain on a single file payload."""
        if not raw_bytes:
            return []

        # 1. Filter: Deduplication Check
        content_hash = self.deduplicator.generate_hash(raw_bytes)
        if self.deduplicator.is_duplicate(content_hash):
            print(f"Skipping Duplicate: {source_uri}")
            return []

        # 2. Extract: Parse bytes to text
        parser = self._get_parser(source_uri)
        try:
            document = parser.parse(raw_bytes, source_uri)
        except Exception as e:
            print(f"Parsing failed for {source_uri}: {e}")
            return []

        # 3. Transform: Split text into semantic chunks
        chunks = self.transformer.transform(document)
        
        # 4. Finalize: Commit hash to ledger to prevent future reprocessing
        if chunks:
            self.deduplicator.mark_processed(content_hash)
            
        return chunks
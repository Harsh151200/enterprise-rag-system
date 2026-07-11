import os
from typing import List, Dict, Any
from ingestion.deduplicator import ContentDeduplicator
from ingestion.transformer import SemanticChunkTransformer
from ingestion.parsers import (
    TXTParser, HTMLParser, PDFParser, DOCXParser, 
    ExcelParser, PPTXParser, XMLAndCodeParser
)

class IngestionPipeline:
    """
    The main coordinator that manages data routing through 
    deduplication verification, format-specific parsing, and chunking.
    """
    def __init__(self):
        self.deduplicator = ContentDeduplicator()
        self.transformer = SemanticChunkTransformer(chunk_size=1000, chunk_overlap=150)
        
        # Central routing map binding extensions to concrete parser engines
        self.parser_registry = {
            ".txt": TXTParser(),
            ".md": TXTParser(),
            ".html": HTMLParser(),
            ".htm": HTMLParser(),
            ".pdf": PDFParser(),
            ".docx": DOCXParser(),
            ".xlsx": ExcelParser(),
            ".pptx": PPTXParser(),
            ".xml": XMLAndCodeParser(),
            ".py": XMLAndCodeParser(),
            ".json": XMLAndCodeParser(),
            ".ini": XMLAndCodeParser(),
            ".yaml": XMLAndCodeParser(),
            ".yml": XMLAndCodeParser()
        }

    def _resolve_parser(self, file_path: str):
        """Looks up the correct parser instance based on the file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        # Fall back gracefully to the TXTParser engine if extension is unrecognized
        return self.parser_registry.get(ext, self.parser_registry[".txt"])

    def process_file(self, source_uri: str, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Processes a raw binary file stream through deduplication, 
        parsing, and chunk transformation.
        """
        if not raw_bytes:
            print(f"[WARN] Received empty byte payload for source: {source_uri}")
            return []

        # 1. Deduplication Verification Phase
        content_hash = self.deduplicator.generate_hash(raw_bytes)
        if self.deduplicator.is_duplicate(content_hash):
            print(f"[INGESTION] Skipping duplicate item (SHA-256 Match Found): {source_uri}")
            return []

        # 2. Extract Phase (Dynamic Parser Routing)
        parser_engine = self._resolve_parser(source_uri)
        try:
            extracted_doc = parser_engine.parse(raw_bytes, source_uri)
        except Exception as parser_error:
            print(f"[ERROR] Ingestion parser crashed on asset {source_uri}: {parser_error}")
            return []

        # 3. Transform Phase (Semantic Slicing and Ordering Assignment)
        try:
            chunk_records = self.transformer.transform(extracted_doc)
        except Exception as transform_error:
            print(f"[ERROR] Context transformer chunking failed for {source_uri}: {transform_error}")
            return []

        # 4. Finalize Tracking
        if chunk_records:
            self.deduplicator.mark_processed(content_hash)
            
        return chunk_records
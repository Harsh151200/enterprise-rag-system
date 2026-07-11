from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ingestion.base import BaseTransformer, ExtractedDocument

class SemanticChunkTransformer(BaseTransformer):
    """
    Slices raw document string assets into uniform overlapping text segments 
    conforming to high-density vector space restrictions.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def transform(self, document: ExtractedDocument) -> List[Dict[str, Any]]:
        """
        Segments an ExtractedDocument object array into contextual chunk records
        with lineage and ordering fields.
        """
        if not document.raw_text.strip():
            return []

        text_slices = self.splitter.split_text(document.raw_text)
        
        processed_chunks = []
        for index, segment in enumerate(text_slices):
            chunk_record = {
                "text_content": segment,
                "source_file": document.metadata.get("source_file", "unknown"),
                "format": document.metadata.get("format", "unknown"),
                "chunk_index": index
            }
            processed_chunks.append(chunk_record)
            
        return processed_chunks
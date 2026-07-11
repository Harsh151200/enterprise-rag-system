from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ingestion.base import BaseTransformer, ExtractedDocument

class SemanticChunkTransformer(BaseTransformer):
    """
    Standardizes large document texts into manageable overlapping segments 
    optimized for LLM context windows and vector embedding constraints.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        # We reuse the reliable LangChain recursive splitter algorithm
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def transform(self, document: ExtractedDocument) -> List[Dict[str, Any]]:
        if not document.raw_text.strip():
            return []

        # Execute the recursive semantic character split
        text_slices = self.splitter.split_text(document.raw_text)
        
        processed_chunks = []
        for index, segment in enumerate(text_slices):
            # We bundle the raw text with its lineage metadata and a specific slice index
            chunk_record = {
                "text_content": segment,
                "source_file": document.metadata.get("source_file", "unknown"),
                "format": document.metadata.get("format", "unknown"),
                "chunk_index": index
            }
            processed_chunks.append(chunk_record)
            
        return processed_chunks
import hashlib
from typing import Union

class ContentDeduplicator:
    """
    Engine responsible for computing cryptographic hashes of file contents 
    to prevent duplicate processing and redundant vector embeddings.
    """
    
    @staticmethod
    def generate_hash(content: Union[bytes, str]) -> str:
        """
        Computes a deterministic SHA-256 hash for the given content payload.
        """
        hasher = hashlib.sha256()
        
        if isinstance(content, str):
            hasher.update(content.encode("utf-8"))
        else:
            hasher.update(content)
            
        return hasher.hexdigest()

    def is_duplicate(self, content_hash: str) -> bool:
        """
        Evaluates if the generated hash already exists in the tracking ledger.
        To be implemented in Task #8.
        """
        # Placeholder for the database or ledger lookup logic
        return False
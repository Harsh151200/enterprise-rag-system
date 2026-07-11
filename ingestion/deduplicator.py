import os
import json
import hashlib
from typing import Union, Set

class ContentDeduplicator:
    """
    Engine responsible for computing cryptographic hashes of file contents 
    and tracking them via a local JSON ledger to prevent duplicate processing.
    """
    def __init__(self):
        sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
        self.ledger_path = os.path.join(sandbox_dir, "processed_hashes.json")
        self.processed_hashes: Set[str] = set()
        self._load_ledger()

    def _load_ledger(self):
        """Loads the existing hash ledger from disk into a fast-lookup set."""
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, "r", encoding="utf-8") as f:
                    hash_list = json.load(f)
                    self.processed_hashes = set(hash_list)
            except Exception as e:
                print(f"Warning: Could not read deduplication ledger: {e}")
                self.processed_hashes = set()
        else:
            # Ensure directory exists before first write
            os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

    def _save_ledger(self):
        """Commits the active hash set to the JSON file."""
        try:
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                json.dump(list(self.processed_hashes), f, indent=4)
        except Exception as e:
            print(f"Error: Failed to write to deduplication ledger: {e}")

    @staticmethod
    def generate_hash(content: Union[bytes, str]) -> str:
        """Computes a deterministic SHA-256 hash for the given payload."""
        hasher = hashlib.sha256()
        if isinstance(content, str):
            hasher.update(content.encode("utf-8"))
        else:
            hasher.update(content)
        return hasher.hexdigest()

    def is_duplicate(self, content_hash: str) -> bool:
        """Checks if a hash is already in the ledger."""
        return content_hash in self.processed_hashes

    def mark_processed(self, content_hash: str):
        """Adds a new hash to the ledger and persists it to disk."""
        if content_hash not in self.processed_hashes:
            self.processed_hashes.add(content_hash)
            self._save_ledger()
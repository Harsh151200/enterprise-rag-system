from abc import ABC, abstractmethod
from typing import Any, Dict, List, Union

class ExtractedDocument:
    """
    Standardized data transfer object representing a fully parsed document.
    """
    def __init__(self, raw_text: str, metadata: Dict[str, Any]):
        self.raw_text = raw_text
        self.metadata = metadata

class BaseConnector(ABC):
    """
    Contract for data retrieval mechanisms (Local File System, URLs, Cloud Storage).
    """
    @abstractmethod
    def fetch(self, source_uri: str) -> Union[bytes, str]:
        """
        Retrieves the raw byte stream or text from a target location.
        """
        pass

class BaseParser(ABC):
    """
    Contract for text extraction algorithms handling specific file formats.
    """
    @abstractmethod
    def parse(self, raw_content: Union[bytes, str], file_name: str) -> ExtractedDocument:
        """
        Converts raw file bytes into a standardized ExtractedDocument object.
        """
        pass

class BaseTransformer(ABC):
    """
    Contract for text cleaning and semantic chunking engines.
    """
    @abstractmethod
    def transform(self, document: ExtractedDocument) -> List[Dict[str, Any]]:
        """
        Splits an ExtractedDocument into an array of dictionaries ready for vector embedding.
        """
        pass
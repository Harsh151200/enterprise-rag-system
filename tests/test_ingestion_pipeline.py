import pytest
from unittest.mock import patch, MagicMock
from ingestion.pipeline import IngestionPipeline, MAX_PAYLOAD_SIZE_BYTES
from ingestion.parsers import TXTParser, PDFParser, XMLAndCodeParser

@pytest.fixture
def pipeline():
    return IngestionPipeline()

def test_pipeline_drops_oversized_payloads(pipeline):
    # Create a byte string exactly 1 byte larger than the 10MB limit
    oversized_bytes = b"0" * (MAX_PAYLOAD_SIZE_BYTES + 1)
    
    result = pipeline.process_file("large_document.txt", oversized_bytes)
    
    # Should drop the file and return empty chunks
    assert result == []

def test_pipeline_drops_forbidden_extensions(pipeline):
    forbidden_files = ["malware.exe", "archive.zip", "image.png", "script.pyc"]
    valid_bytes = b"Hello World"
    
    for filename in forbidden_files:
        result = pipeline.process_file(filename, valid_bytes)
        assert result == []

@patch("ingestion.pipeline.ContentDeduplicator")
def test_pipeline_deduplication_skip(MockDeduplicator):
    # Configure the mock to simulate an already processed file
    mock_dedup_instance = MockDeduplicator.return_value
    mock_dedup_instance.is_duplicate.return_value = True
    
    pipeline = IngestionPipeline()
    pipeline.deduplicator = mock_dedup_instance
    
    result = pipeline.process_file("existing_file.txt", b"Hello World")
    
    # Should return empty because it was flagged as a duplicate
    assert result == []
    mock_dedup_instance.is_duplicate.assert_called_once()

def test_parser_registry_routing(pipeline):
    # Validate that specific extensions route to the correct parser engines
    assert isinstance(pipeline._resolve_parser("doc.txt"), TXTParser)
    assert isinstance(pipeline._resolve_parser("doc.md"), TXTParser)
    assert isinstance(pipeline._resolve_parser("report.pdf"), PDFParser)
    assert isinstance(pipeline._resolve_parser("script.py"), XMLAndCodeParser)
    assert isinstance(pipeline._resolve_parser("config.json"), XMLAndCodeParser)
    
    # Unknown extensions should fallback to TXTParser
    assert isinstance(pipeline._resolve_parser("unknown.xyz"), TXTParser)
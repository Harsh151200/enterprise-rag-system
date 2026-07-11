import io
from typing import Union, Dict, Any
from bs4 import BeautifulSoup

try:
    import docx
    import pypdf
except ImportError:
    docx = None
    pypdf = None
    

from ingestion.base import BaseParser, ExtractedDocument

class TXTParser(BaseParser):
    """Handles raw plain text and simple markdown files."""
    def parse(self, raw_content: Union[bytes, str], file_name: str) -> ExtractedDocument:
        if isinstance(raw_content, bytes):
            text = raw_content.decode("utf-8", errors="ignore")
        else:
            text = raw_content
            
        metadata = {"source_file": file_name, "format": "txt"}
        return ExtractedDocument(raw_text=text.strip(), metadata=metadata)


class HTMLParser(BaseParser):
    """Handles web pages and HTML documentation nodes."""
    def parse(self, raw_content: Union[bytes, str], file_name: str) -> ExtractedDocument:
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("utf-8", errors="ignore")
            
        soup = BeautifulSoup(raw_content, "lxml")
        
        # Prioritize the main article body if available (common in documentation)
        article_body = soup.find("article", class_="bd-article")
        if article_body:
            text_content = article_body.get_text(separator="\n")
        else:
            text_content = soup.get_text(separator="\n")
            
        # Clean up excessive whitespace
        clean_lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        final_text = "\n".join(clean_lines)
        
        metadata = {"source_file": file_name, "format": "html"}
        return ExtractedDocument(raw_text=final_text, metadata=metadata)


class PDFParser(BaseParser):
    """Handles portable document format (PDF) textual extraction."""
    def __init__(self):
        if pypdf is None:
            raise ImportError("pypdf is not installed. Please run: pip install pypdf")

    def parse(self, raw_content: Union[bytes, str], file_name: str) -> ExtractedDocument:
        if isinstance(raw_content, str):
            # PDFs must be handled as binary streams
            raw_content = raw_content.encode("utf-8")
            
        pdf_file_obj = io.BytesIO(raw_content)
        reader = pypdf.PdfReader(pdf_file_obj)
        
        extracted_pages = []
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text = page.extract_text()
            if text:
                extracted_pages.append(text)
                
        final_text = "\n\n".join(extracted_pages)
        
        metadata = {
            "source_file": file_name,
            "format": "pdf",
            "total_pages": len(reader.pages)
        }
        return ExtractedDocument(raw_text=final_text.strip(), metadata=metadata)
    

class DOCXParser(BaseParser):
    """Handles Microsoft Word (.docx) document extraction."""
    def __init__(self):
        if docx is None:
            raise ImportError("python-docx is not installed. Please run: pip install python-docx")

    def parse(self, raw_content: Union[bytes, str], file_name: str) -> ExtractedDocument:
        if isinstance(raw_content, str):
            raw_content = raw_content.encode("utf-8")
            
        file_stream = io.BytesIO(raw_content)
        document = docx.Document(file_stream)
        
        full_text = []
        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text)
                
        final_text = "\n".join(full_text)
        metadata = {"source_file": file_name, "format": "docx"}
        return ExtractedDocument(raw_text=final_text.strip(), metadata=metadata)


class CodeParser(BaseParser):
    """Handles source code files, treating them as text but isolating structural metadata."""
    def parse(self, raw_content: Union[bytes, str], file_name: str) -> ExtractedDocument:
        if isinstance(raw_content, bytes):
            text = raw_content.decode("utf-8", errors="ignore")
        else:
            text = raw_content
            
        # Extract the file extension to tag the programming language
        extension = file_name.split(".")[-1] if "." in file_name else "unknown"
        
        metadata = {
            "source_file": file_name, 
            "format": "code",
            "language": extension
        }
        return ExtractedDocument(raw_text=text.strip(), metadata=metadata)
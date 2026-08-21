import os
import time
import requests
from typing import Union, List, Dict, Any, Set, Generator
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from ingestion.base import BaseConnector

FORBIDDEN_URL_EXTENSIONS = {
    ".zip", ".tar", ".gz", ".rar", ".7z", 
    ".exe", ".bin", ".whl", ".pyc", 
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".mp4", ".mp3", ".wav"
}

# Match the pipeline limit
MAX_DOWNLOAD_SIZE_BYTES = 10 * 1024 * 1024 

def is_crawlable_url(url: str) -> bool:
    parsed_url = urlparse(url)
    ext = os.path.splitext(parsed_url.path)[1].lower()
    if ext in FORBIDDEN_URL_EXTENSIONS:
        return False
    return True

class LocalDirectoryConnector(BaseConnector):
    def __init__(self, directory_path: str, allowed_extensions: List[str] = None):
        self.directory_path = directory_path
        # Aligned with all extensions registered in IngestionPipeline.parser_registry
        self.allowed_extensions = allowed_extensions or [
            ".txt", ".md", ".html", ".htm", ".pdf", ".docx", 
            ".xlsx", ".pptx", ".xml", ".py", ".json", ".ini", 
            ".yaml", ".yml"
        ]

    def fetch(self, source_uri: str) -> bytes:
        with open(source_uri, "rb") as f:
            return f.read()

    def fetch_all(self) -> Generator[Dict[str, Any], None, None]:
        if not os.path.exists(self.directory_path):
            print(f"[ERROR] Specified directory path does not exist: {self.directory_path}")
            return

        for root, _, files in os.walk(self.directory_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.allowed_extensions:
                    file_path = os.path.join(root, file)
                    try:
                        raw_bytes = self.fetch(file_path)
                        yield {"source": file_path, "bytes": raw_bytes}
                    except Exception as e:
                        print(f"[ERROR] Skipping file due to extraction failure on {file_path}: {e}")

class DynamicWebCrawlerConnector(BaseConnector):
    def __init__(self, seed_url: str, domain_lock: str, path_filter: str, max_pages: int = 50):
        self.seed_url = seed_url
        self.domain_lock = domain_lock
        self.path_filter = path_filter
        self.max_pages = max_pages
        self.headers = {"User-Agent": "EnterpriseRAGBot/3.0"}
        self.visited_urls: Set[str] = set()
        self.url_queue: List[str] = [seed_url]

    def _clean_url(self, url: str) -> str:
        return url.split('#')[0]

    def fetch(self, source_uri: str) -> bytes:
        """Executes an HTTP request with streaming to prevent OOM on massive files."""
        try:
            with requests.get(source_uri, headers=self.headers, stream=True, timeout=10) as response:
                if response.status_code != 200:
                    return b""

                content_type = response.headers.get('Content-Type', '').lower()
                if any(bad_type in content_type for bad_type in ['video/', 'audio/', 'image/', 'application/zip', 'application/x-executable']):
                    print(f"[GUARDRAIL BLOCK] Rejected forbidden MIME type ({content_type}): {source_uri}")
                    return b""

                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_DOWNLOAD_SIZE_BYTES:
                    print(f"[GUARDRAIL BLOCK] Server reported payload exceeds 10MB limit: {source_uri}")
                    return b""

                downloaded_bytes = b""
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_bytes += chunk
                        if len(downloaded_bytes) > MAX_DOWNLOAD_SIZE_BYTES:
                            print(f"[GUARDRAIL BLOCK] Streamed payload exceeded 10MB limit. Aborting: {source_uri}")
                            return b""

                return downloaded_bytes

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] HTTP connection dropped for URL {source_uri}: {e}")
            return b""

    def crawl_tree(self) -> Generator[Dict[str, Any], None, None]:
        print(f"[INFO] Initializing tree traversal crawling on root node: {self.seed_url}")

        while self.url_queue and len(self.visited_urls) < self.max_pages:
            current_url = self._clean_url(self.url_queue.pop(0))

            if current_url in self.visited_urls:
                continue

            self.visited_urls.add(current_url)
            raw_bytes = self.fetch(current_url)
            if not raw_bytes:
                continue

            yield {"source": current_url, "bytes": raw_bytes}

            try:
                soup = BeautifulSoup(raw_bytes, "lxml")
                for anchor in soup.find_all("a", href=True):
                    absolute_link = urljoin(current_url, anchor["href"])
                    clean_link = self._clean_url(absolute_link)

                    is_same_domain = urlparse(clean_link).netloc == self.domain_lock
                    in_target_scope = self.path_filter in clean_link
                    is_new_node = clean_link not in self.visited_urls and clean_link not in self.url_queue
                    is_crawlable = is_crawlable_url(clean_link)

                    if is_same_domain and in_target_scope and is_new_node and is_crawlable:
                        self.url_queue.append(clean_link)
            except Exception as e:
                print(f"[WARNING] Failed parsing hyperlinks inside node {current_url}: {e}")

            time.sleep(0.5)
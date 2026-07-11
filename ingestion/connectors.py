import os
import time
import requests
from typing import Union, List, Dict, Any, Set, Generator
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from ingestion.base import BaseConnector

class LocalDirectoryConnector(BaseConnector):
    """
    Recursively scans and streams raw bytes from local file system
    directories using generators to maintain a minimal memory footprint.
    """
    def __init__(self, directory_path: str, allowed_extensions: List[str] = None):
        self.directory_path = directory_path
        self.allowed_extensions = allowed_extensions or [
            ".txt", ".md", ".html", ".htm", ".pdf", ".docx", ".xlsx", ".pptx", ".xml", ".py"
        ]

    def fetch(self, source_uri: str) -> bytes:
        """Reads raw binary bytes from a single local file path."""
        with open(source_uri, "rb") as f:
            return f.read()

    def fetch_all(self) -> Generator[Dict[str, Any], None, None]:
        """Scans the targeted directory structure and yields raw file objects sequentially."""
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
    """
    Manages link discovery, scope enforcement, and recursive tree 
    traversal to ingest remote web pages as raw byte strings.
    """
    def __init__(self, seed_url: str, domain_lock: str, path_filter: str, max_pages: int = 50):
        self.seed_url = seed_url
        self.domain_lock = domain_lock
        self.path_filter = path_filter
        self.max_pages = max_pages
        self.headers = {"User-Agent": "EnterpriseRAGBot/3.0"}
        self.visited_urls: Set[str] = set()
        self.url_queue: List[str] = [seed_url]

    def _clean_url(self, url: str) -> str:
        """Strips fragment hashes to maintain unique lookup strings."""
        return url.split('#')[0]

    def fetch(self, source_uri: str) -> bytes:
        """Executes a single synchronous HTTP GET request to capture remote raw bytes."""
        try:
            response = requests.get(source_uri, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.content
            return b""
        except Exception as e:
            print(f"[ERROR] HTTP connection dropped for URL {source_uri}: {e}")
            return b""

    def crawl_tree(self) -> Generator[Dict[str, Any], None, None]:
        """
        Traverses the web network graph recursively up to boundary limits
        and yields discovered documents one by one.
        """
        print(f"[INFO] Initializing tree traversal crawling on root node: {self.seed_url}")
        
        while self.url_queue and len(self.visited_urls) < self.max_pages:
            current_url = self._clean_url(self.url_queue.pop(0))

            if current_url in self.visited_urls:
                continue

            self.visited_urls.add(current_url)
            raw_bytes = self.fetch(current_url)
            if not raw_bytes:
                continue

            # Yield the network payload immediately before processing child branches
            yield {"source": current_url, "bytes": raw_bytes}

            # Discover anchor tags to expand the tree queue
            try:
                soup = BeautifulSoup(raw_bytes, "lxml")
                for anchor in soup.find_all("a", href=True):
                    absolute_link = urljoin(current_url, anchor["href"])
                    clean_link = self._clean_url(absolute_link)

                    is_same_domain = urlparse(clean_link).netloc == self.domain_lock
                    in_target_scope = self.path_filter in clean_link
                    is_new_node = clean_link not in self.visited_urls and clean_link not in self.url_queue

                    if is_same_domain and in_target_scope and is_new_node:
                        self.url_queue.append(clean_link)
            except Exception as e:
                print(f"[WARNING] Failed parsing hyperlinks inside node {current_url}: {e}")

            time.sleep(0.5)
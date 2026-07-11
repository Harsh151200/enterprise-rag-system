import os
import time
import requests
from typing import Union, List, Dict, Any, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from ingestion.base import BaseConnector

class LocalDirectoryConnector(BaseConnector):
    """Recursively reads raw bytes from local file system directories."""
    
    def __init__(self, directory_path: str, allowed_extensions: List[str] = None):
        self.directory_path = directory_path
        self.allowed_extensions = allowed_extensions or [".txt", ".pdf", ".html", ".docx", ".xml", ".py"]

    def fetch_all(self) -> List[Dict[str, Any]]:
        """Scans the directory and yields file paths and their raw bytes."""
        files_data = []
        if not os.path.exists(self.directory_path):
            print(f"[ERROR] Directory not found: {self.directory_path}")
            return files_data

        for root, _, files in os.walk(self.directory_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in self.allowed_extensions:
                    file_path = os.path.join(root, file)
                    raw_bytes = self.fetch(file_path)
                    files_data.append({"source": file_path, "bytes": raw_bytes})
                    
        return files_data

    def fetch(self, source_uri: str) -> bytes:
        with open(source_uri, "rb") as f:
            return f.read()


class DynamicWebCrawlerConnector(BaseConnector):
    """
    Handles link-graph discovery, domain enforcement, and recursive 
    fetching of documentation trees.
    """
    
    def __init__(self, seed_url: str, domain_lock: str, path_filter: str, max_pages: int = 50):
        self.seed_url = seed_url
        self.domain_lock = domain_lock
        self.path_filter = path_filter
        self.max_pages = max_pages
        
        self.headers = {"User-Agent": "Mozilla/5.0 (EnterpriseRAGBot/3.0)"}
        self.visited_urls: Set[str] = set()
        self.url_queue: List[str] = [seed_url]

    def _clean_url(self, url: str) -> str:
        """Strips fragment identifiers to prevent duplicate processing."""
        return url.split('#')[0]

    def fetch(self, source_uri: str) -> bytes:
        """Fetches raw network bytes from a singular URL node."""
        try:
            response = requests.get(source_uri, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.content
            return b""
        except Exception as e:
            print(f"[ERROR] Failed network fetch for {source_uri}: {e}")
            return b""

    def crawl_tree(self) -> List[Dict[str, Any]]:
        """
        Executes the recursive link discovery crawl up to the max page limits.
        """
        harvested_pages = []
        print(f"[INFO] Initializing Dynamic Web Ingestion Map on Root: {self.seed_url}")

        while self.url_queue and len(self.visited_urls) < self.max_pages:
            current_url = self._clean_url(self.url_queue.pop(0))

            if current_url in self.visited_urls:
                continue

            print(f"[INFO] Crawler Extracting Node [{len(self.visited_urls) + 1}/{self.max_pages}]: {current_url}")
            self.visited_urls.add(current_url)

            raw_bytes = self.fetch(current_url)
            if not raw_bytes:
                continue

            # Append payload object
            harvested_pages.append({"source": current_url, "bytes": raw_bytes})

            # Parse page anchors to find new links
            try:
                soup = BeautifulSoup(raw_bytes, "lxml")
                for anchor in soup.find_all("a", href=True):
                    absolute_link = urljoin(current_url, anchor["href"])
                    clean_link = self._clean_url(absolute_link)

                    is_same_domain = urlparse(clean_link).netloc == self.domain_lock
                    in_target_scope = self.path_filter in clean_link
                    is_new_url = clean_link not in self.visited_urls and clean_link not in self.url_queue

                    if is_same_domain and in_target_scope and is_new_url:
                        self.url_queue.append(clean_link)
            except Exception as e:
                print(f"[WARNING] Link extraction failed on {current_url}: {e}")

            # Polite crawl delay
            time.sleep(0.5)

        return harvested_pages
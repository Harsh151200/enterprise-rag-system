import os
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class DynamicDocumentationCrawler:
    def __init__(self, seed_url, domain_lock, path_filter, max_pages=50):
        """
        An enterprise-grade recursive crawler built to map and ingest documentation trees.
        
        :param seed_url: The entry point or root node of the documentation map.
        :param domain_lock: Safety rail ensuring the scraper never leaves the target host.
        :param path_filter: Ensures we only ingest valid documentation sub-pages.
        :param max_pages: Safe boundary limit to prevent infinite loops and control storage footprint.
        """
        self.seed_url = seed_url
        self.domain_lock = domain_lock
        self.path_filter = path_filter
        self.max_pages = max_pages
        
        self.visited_urls = set()
        self.url_queue = [seed_url]
        self.headers = {"User-Agent": "Mozilla/5.0 (EnterpriseRAGBot/2.0; ScaleUp-Ops)"}
        self.sandbox_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
        self.raw_data_dir = os.path.join(self.sandbox_dir, 'raw/', 'scikit_learn/')

    def clean_url(self, url):
        """Strips fragment identifiers (#) to prevent duplicate processing of the same page."""
        return url.split('#')[0]

    def generate_filename_from_url(self, url):
        """Transforms a URL path into a clean local file identifier slug."""
        parsed = urlparse(url)
        path_slug = parsed.path.strip("/").replace("/", "_")
        if not path_slug or path_slug.endswith("_"):
            path_slug += "index"
        if not path_slug.endswith(".txt"):
            path_slug = path_slug.replace(".html", "") + ".txt"
        return f"dynamic_{path_slug}"

    def run_crawler(self):
        os.makedirs(self.raw_data_dir, exist_ok=True)
        print(f"Launching Dynamic Tree Crawler...")
        print(f"Root Node: {self.seed_url}")
        print(f"Domain Lock: {self.domain_lock} | Scope Matcher: {self.path_filter}")
        print(f"Bounded Guardrail Capacity: Max {self.max_pages} pages.\n" + "="*60)

        while self.url_queue and len(self.visited_urls) < self.max_pages:
            current_url = self.clean_url(self.url_queue.pop(0))

            if current_url in self.visited_urls:
                continue

            print(f"[{len(self.visited_urls) + 1}/{self.max_pages}] Processing: {current_url}")
            self.visited_urls.add(current_url)

            try:
                response = requests.get(current_url, headers=self.headers, timeout=10)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "lxml")

                # --- 1. CONTEXT EXTRACTION LAYER ---
                article_body = soup.find("article", class_="bd-article")
                text_content = article_body.get_text(separator="\n") if article_body else soup.get_text(separator="\n")
                
                clean_lines = [line.strip() for line in text_content.splitlines() if line.strip()]
                final_text = "\n".join(clean_lines)

                # Commit text segment to the file sandbox
                filename = self.generate_filename_from_url(current_url)
                file_path = os.path.join(self.raw_data_dir, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(final_text)

                # --- 2. DYNAMIC LINK DISCOVERY LAYER (The Tree Graph Parser) ---
                for anchor in soup.find_all("a", href=True):
                    absolute_link = urljoin(current_url, anchor["href"])
                    clean_link = self.clean_url(absolute_link)

                    # Guardrail Checkpoints
                    is_same_domain = urlparse(clean_link).netloc == self.domain_lock
                    in_target_scope = self.path_filter in clean_link
                    is_new_url = clean_link not in self.visited_urls and clean_link not in self.url_queue

                    if is_same_domain and in_target_scope and is_new_url:
                        self.url_queue.append(clean_link)

                # Polite scraping pause to protect target network routers
                time.sleep(0.8)

            except Exception as e:
                print(f"Error processing {current_url}: {e}")

        print(f"\nDynamic Crawling Complete! Successfully mapped and harvested {len(self.visited_urls)} documentation sub-nodes.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Configuring the engine to crawl scikit-learn's stable User Guide tree hierarchy dynamically
    crawler = DynamicDocumentationCrawler(
        seed_url="https://scikit-learn.org/stable/user_guide.html",
        domain_lock="scikit-learn.org",
        path_filter="/stable/", # Targets everything in the stable documentation tree bounds
        max_pages=50            # Start with a safe pool boundary for initial scale testing
    )
    crawler.run_crawler()
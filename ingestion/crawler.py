import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# to load environment variables from a .env file
load_dotenv()

def fetch_and_parse_documentation():
    # Fetch url and configuration from environment variables
    target_url = os.getenv('TARGET_DOCS_URL')
    output_dir = os.getenv('RAW_DATA_DIR', 'data_sandbox/')

    print(f"Initializing connection to {target_url} ...")

    # Adding a standard User-Agent header to make request looks like a normal browser access
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try : 
        response = requests.get(target_url, headers=headers,timeout=10)
        response.raise_for_status() # to check if the request was successful

        # Parse raw HTML text stream with the high-performance 'lxml' engine
        soup = BeautifulSoup(response.text, 'lxml')

        # Extract Main text content from the parsed HTML document.
        # scikit-learn documentation has main structure inside <article> tag with class="bd-article"
        main_content = soup.find('article', class_='bd-article')

        if not main_content:
            # Fallback to standard html 'main' or 'article' tags if class structure shifts
            main_content = soup.find('main') or soup.find('article')

        if main_content:
            # Extract purely readable text string, removing residual script/style brackets
            clean_text = main_content.get_text(separator='\n', strip=True)

            # Save the cleaned text to a local file for later processing
            filename = "sklearn_user_guide.txt"
            output_path = os.path.join(output_dir, filename)

            # save data to data_sandboc/
            with open(output_path, 'w', encoding = 'utf-8') as f :
                f.write(clean_text)

            print(f"Documentation successfully fetched and saved to {output_path}")
        else:
            print("Failed to locate main content in the documentation page.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching the documentation: {e}")

if __name__ == "__main__":
    fetch_and_parse_documentation()
import os
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load local environment variables from .env file
load_dotenv()

def chunk_documentation():
    """Chunk raw documentation text into semantic text segments."""

    # 1. Paths and parameters defined dynamically
    input_dir = os.getenv("RAW_DATA_DIR", "data_sandbox/")
    input_file = os.path.join(input_dir, "sklearn_user_guide.txt")
    
    if not os.path.exists(input_file):
        print(f"Error: Source text file not found at {input_file}. Please run Phase 1 first.")
        return []
    
    print(f"Reading source data from: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # 2. Configure the Recursive Character Text Splitter
    # It recursively tries to split text by paragraph (\n\n), sentence (\n), then words to keep semantic contexts intact.
    # We will target a chunk size of 1000 characters with an overlap of 150 characters.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        length_function=len,
        is_separator_regex=False,
    )

    # 3. Execute the splitting algorithm
    print("Executing semantic text splitting...")
    chunks = text_splitter.split_text(raw_text)
    
    print(f"Splitting Complete: Generated {len(chunks)} text chunks.")
    
    # Printing sample chunks for verification
    if chunks:
        print("\n---SAMPLE CHUNK 1 ---")
        print(chunks[0] + "...")
        print("\n---SAMPLE CHUNK 2 ---")
        print(chunks[1][:300] + "...")
        print("------------------------\n")

    return chunks

if __name__ == "__main__":
    chunk_documentation()
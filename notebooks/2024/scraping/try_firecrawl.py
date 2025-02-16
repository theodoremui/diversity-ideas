from llama_index.readers.web import FireCrawlWebReader
from llama_index.core import SummaryIndex
import os

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

firecrawl_reader = FireCrawlWebReader(
    api_key=FIRECRAWL_API_KEY,  # Replace with your actual API key from https://www.firecrawl.dev/
    mode="scrape",  # Choose between "crawl" and "scrape" for single page scraping
    params={"additional": "parameters"}  # Optional additional parameters
)

OP_ED_LISTING = "https://www.columbiaspectator.com/opinion/op-eds/10/"
documents = firecrawl_reader.load_data(url=OP_ED_LISTING)


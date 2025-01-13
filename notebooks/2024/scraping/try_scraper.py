from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

import asyncio
import aiohttp

import os
from ingest.scraper import Scraper

scraper = Scraper(api_key=os.getenv("JINA_API_KEY"))

progress = {"completed": 0}
semaphore = asyncio.Semaphore(2)


async def scrape_url(url: str) -> str:
    html = ""
    async with aiohttp.ClientSession() as session:
        html = await scraper.fetch_markdown(session, url, semaphore, progress, 1)

    return html


if __name__ == "__main__":

    urls = [
        "https://www.columbiaspectator.com/opinion/2024/12/11/at-columbia-we-dont-strike-our-ideological-opponents/",
        "https://www.columbiaspectator.com/opinion/2024/12/08/columbias-complicity-in-cop29-the-greenwashing-of-human-rights-abuses/",
    ]
    markdowns = asyncio.run(scraper.fetch_urls_markdowns(urls))
    for md in markdowns:
        print(md)

    print(len(markdowns))

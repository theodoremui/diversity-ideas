from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from spider import Spider

import asyncio
from typing import List

# Initialize the Spider with your API key
app = Spider()

urls = [
    "https://www.columbiaspectator.com/opinion/op-eds/1/",
    "https://www.columbiaspectator.com/opinion/2024/12/11/at-columbia-we-dont-strike-our-ideological-opponents/",
    # "https://www.columbiaspectator.com/opinion/2024/12/08/columbias-complicity-in-cop29-the-greenwashing-of-human-rights-abuses/",
]

spider_params = {
    "limit": 1,
    "metadata": True,
    "request": "smart",
    "smart_mode": True,
    "respect_robots": False,
    "return_format": "raw",
    "anti_bot": True,
    "stealth": True,
    "fingerprint": True,
}


async def scrape_url(url: str) -> str:
    return app.scrape_url(url, params=spider_params)


async def scrape_urls(urls: List[str]) -> List[str]:
    return await asyncio.gather(*[scrape_url(url) for url in urls])


if __name__ == "__main__":
    markdowns = asyncio.run(scrape_urls(urls))
    for md in markdowns:
        print(md)

    print(f"\nNumber of markdowns: {len(markdowns)}")

# # Crawl a website
# crawler_params = {
#     "limit": 1,
#     "proxy_enabled": True,
#     "store_data": False,
#     "metadata": False,
#     "request": "http",
# }
# crawl_result = app.crawl_url(url, params=crawler_params)

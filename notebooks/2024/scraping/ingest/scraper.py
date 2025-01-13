#############################################################################
# crawler.py
#
# Crawler for URLs and sitemaps
#
# Theodore Mui
# 2025-01-13
#############################################################################


import asyncio
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List

import aiofiles
import aiohttp


@dataclass
class Scraper:
    JINA_READER = "https://r.jina.ai/"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.progress_lock = asyncio.Lock()

    def conditional_replacement(self, match):
        alt_text = match.group(1)
        if alt_text.lower().startswith("image"):
            return ""  # Replace with an empty string if it starts with "Image" (case-insensitive)
        return alt_text  # Otherwise, return the alt text

    async def remove_links_from_markdown(self, content: str) -> str:

        # Remove image links but keep the alt text ![alt text](url)
        content = re.sub(r"!\[([^\]]*?)\]\(.*?\)", r" ", content)
        # content = re.sub(r'!\[([^\]]*?)\]\(.*?\)', self.conditional_replacement,
        #                  content, flags=re.IGNORECASE)

        # Remove inline links [text](url)
        content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)

        # Remove reference links [text][id]
        content = re.sub(r"\[([^\]]+)\]\[[^\]]+\]", r"\1", content)

        # Remove reference link definitions [id]: url
        content = re.sub(r"^\[[^\]]+\]:\s*.*$", "", content, flags=re.MULTILINE)

        return content

    async def fetch(self, session, url, headers, semaphore):
        async with semaphore:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()  # Ensure we raise an error for bad responses
                if "application/json" in response.headers.get("Content-Type"):
                    return await response.json()
                # else:
                raise aiohttp.ContentTypeError(
                    request_info=response.request_info,
                    history=response.history,
                    message=f"Unexpected content type: {response.headers.get('Content-Type')}",
                )

    async def fetch_content(self, session, url, semaphore, progress, total):
        headers_common = {
            "Accept": "application/json",
        }

        headers_common["Authorization"] = f"Bearer {self.api_key}"

        headers_html = headers_common.copy()
        headers_html["X-Return-Format"] = "html"

        headers_markdown = headers_common.copy()
        headers_markdown["X-Return-Format"] = "markdown"

        try:
            # full html before the filtering pipeline, consume MOST tokens!
            response_html = self.fetch(
                session, self.JINA_READER + url, headers_html, semaphore
            )

            # default content behavior as if u access via https://r.jina.ai/url
            response_default = self.fetch(
                session, self.JINA_READER + url, headers_common, semaphore
            )

            # html->markdown but without smart filtering
            response_markdown = self.fetch(
                session, self.JINA_READER + url, headers_markdown, semaphore
            )

            html, markdown, default = await asyncio.gather(
                response_html, response_markdown, response_default
            )

            result = {
                "url": url,
                "default": default.get("data").get("content"),
                "html": html.get("data").get("html"),
                "markdown": markdown.get("data").get("content"),
            }
        except aiohttp.ContentTypeError as e:
            print(f"Skipping URL due to content type error: {url}, {e}")
            result = {
                "url": url,
                "default": None,
                "html": None,
                "markdown": None,
            }

        async with self.progress_lock:
            progress["completed"] += 1
            print(f"Completed {progress['completed']} out of {total} requests")

        return result

    async def fetch_sitemap_urls(self, sitemap_url):
        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds total timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(sitemap_url) as response:
                response.raise_for_status()
                sitemap_xml = await response.text()

        root = ET.fromstring(sitemap_xml)
        urls = [
            elem.text
            for elem in root.findall(
                ".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
            )
        ]
        return urls

    async def fetch_all_content(self, sitemap_url, max_concurrency=5):
        urls = await self.fetch_sitemap_urls(sitemap_url)
        total_urls = len(urls)
        progress = {"completed": 0}
        semaphore = asyncio.Semaphore(
            max_concurrency
        )  # Limit the number of concurrent tasks to 100

        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch_content(session, url, semaphore, progress, total_urls)
                for url in urls
            ]
            results = await asyncio.gather(*tasks)

        async with aiofiles.open("website.json", "w") as f:
            await f.write(json.dumps(results, indent=4))

    async def fetch_html(self, session, url, semaphore, progress, total) -> str:
        headers_markdown = {
            "Accept": "application/json",
            "X-Retain-Images": "none",
            "X-Return-Format": "html",
            "X-With-Iframe": "true",
            "X-With-Shadow-Dom": "true",
        }
        headers_markdown["Authorization"] = f"Bearer {self.api_key}"

        result = ""
        try:
            response = await self.fetch(
                session, self.JINA_READER + url, headers_markdown, semaphore
            )
            html = response.get("data").get("html")

            result = html
        except aiohttp.ContentTypeError as e:
            print(f"Skipping URL due to content type error: {url}, {e}")

        async with self.progress_lock:
            progress["completed"] += 1
            print(f"Completed {progress['completed']} out of {total} requests")

        return result

    async def fetch_markdown(self, session, url, semaphore, progress, total):
        headers_markdown = {
            "Accept": "application/json",
            "X-Retain-Images": "none",
            "X-Return-Format": "markdown",
            "X-With-Iframe": "true",
            "X-With-Shadow-Dom": "true",
        }
        headers_markdown["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = await self.fetch(
                session, self.JINA_READER + url, headers_markdown, semaphore
            )
            markdown = await self.remove_links_from_markdown(
                response.get("data").get("content")
            )

            result = {"source": url, "content": markdown}
        except aiohttp.ContentTypeError as e:
            print(f"Skipping URL due to content type error: {url}, {e}")
            result = {
                "source": url,
                "content": "",
            }

        async with self.progress_lock:
            progress["completed"] += 1
            print(f"Completed {progress['completed']} out of {total} requests")

        return result

    async def fetch_urls_htmls(
        self, urls: List[str], max_concurrency=os.cpu_count() - 2
    ) -> List[str]:
        total_urls = len(urls)
        progress = {"completed": 0}
        semaphore = asyncio.Semaphore(
            max_concurrency
        )  # Limit the number of concurrent tasks to 100

        async def safe_fetch_html(url):
            try:
                return await self.fetch_html(
                    session, url, semaphore, progress, total_urls
                )
            except Exception as e:
                print(f"Error processing URL {url}: {str(e)}")
                return {"source": url, "content": "", "error": str(e)}

        async with aiohttp.ClientSession() as session:
            tasks = [await safe_fetch_html(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        return results

    async def fetch_urls_markdowns(
        self, urls: List[str], max_concurrency=os.cpu_count() - 2
    ):
        total_urls = len(urls)
        progress = {"completed": 0}
        semaphore = asyncio.Semaphore(
            max_concurrency
        )  # Limit the number of concurrent tasks to 100

        async def safe_fetch_markdown(url):
            try:
                return await self.fetch_markdown(
                    session, url, semaphore, progress, total_urls
                )
            except Exception as e:
                print(f"Error processing URL {url}: {str(e)}")
                return {"source": url, "content": "", "error": str(e)}

        async with aiohttp.ClientSession() as session:
            tasks = [safe_fetch_markdown(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        return results

    async def fetch_sitemap_markdowns(self, sitemap_url, max_concurrency=5):
        urls = await self.fetch_sitemap_urls(sitemap_url)
        total_urls = len(urls)
        progress = {"completed": 0}
        semaphore = asyncio.Semaphore(
            max_concurrency
        )  # Limit the number of concurrent tasks to 100

        async with aiohttp.ClientSession() as session:
            tasks = [
                self.fetch_markdown(session, url, semaphore, progress, total_urls)
                for url in urls
            ]
            results = await asyncio.gather(*tasks)

        async with aiofiles.open("content_sitemap.json", "w") as f:
            await f.write(json.dumps(results, indent=4))


# ---------------------------------------------------------------------------#
#                                 main()                                    #
# ---------------------------------------------------------------------------#


async def test_single_page(api_key: str):
    url = "https://www.united.com/en/us/fly/travel/accessibility-and-assistance/service-animals.html"
    urls = [
        "https://www.united.com/en/us/fly/mileageplus/whats-new.html",
        "https://www.united.com/en/us/fly/mileageplus/awards/upgrades-types/pluspoints.html",
        "https://www.united.com/en/us/fly/products/business/passplus.html",
        # "https://www.united.com/en/us/fly/products/united-business-credit-cards.html",
        # "https://www.united.com/en/us/fly/products/united-personal-credit-cards.html",
        # "https://www.united.com/en/us/fly/products/upgrades-and-optional-service-charges.html",
        # "https://www.united.com/en/us/fly/reservations/change-cancel-flight.html",
        # "https://www.united.com/en/us/fly/tarmac-delay-contingency-plan.html",
        # "https://www.united.com/en/us/fly/text-messaging.html",
        # "https://www.united.com/en/us/fly/travel/accessibility-and-assistance/traveling-with-children.html"
    ]

    scraper = Scraper(api_key=api_key)
    pages = await scraper.fetch_urls_markdowns(urls)

    print(f"{30*'*'}>>> single page crawl:")
    for url, page in zip(urls, pages):
        content = page["content"].replace("\n", " ")
        print(f"url: {url}, content: {content[:50]} ...")


def test_sitemap(api_key: str):
    sitemap_url = "https://www.united.com/sitemap.xml"
    scraper = Scraper(api_key=api_key)
    urls = asyncio.run(scraper.fetch_sitemap_urls(sitemap_url))
    print(f"{30*'*'}>>> sitemap crawl:")
    for url in urls:
        print(f"==> {url}")


if __name__ == "__main__":
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv())
    JINA_API_KEY = os.environ.get("JINA_API_KEY")
    assert JINA_API_KEY is not None and len(JINA_API_KEY) > 1, "JINA_API_KEY not found"

    asyncio.run(test_single_page(JINA_API_KEY))
    # test_sitemap(JINA_API_KEY)

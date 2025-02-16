#########################################################################
# crawlcolumbia2parquet.py
# ------------------
# Scraping Columbia student paper opinion pieces with proxy services &
# saving to a local parquet file
#
# @author Phil Mui
# @email thephilmui@gmail.com
# @date Sun Sep  1 21:37:14 PDT 2024
#
# Retry logic: bit.ly/requests-retry
#########################################################################

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import argparse
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Any

from bs4 import BeautifulSoup
from bs4.element import Tag
from datetime import datetime
import os
import pandas as pd
from openai import OpenAI
import re
import random
import time
import yaml

from util import ouraws
from util import ourrequests
from util import textutil
from ingest import Scraper

scraper = Scraper(api_key=os.getenv("JINA_API_KEY"))

RETRIES: int = 6
CHECKPOINT_FREQUENCY: int = 10  # every 10 pages

OUTPUT_DIR = "data"
SCHOOL = "college"
SUBJECT = "opinions"

BASE_URL: str = "<base>"
LISTING_BASE_URL: str = f"<url>"
LISTING_INCREMENT: int = 10
ARTICLE_SELECTORS = [f"<selector>"]
TITLE_SELECTORS = [f"<title_selector>"]
CONTENT_SELECTORS = [f"<content_selector>"]
DATE_SELECTOR = f"<date_selector>"
URL_DATE_PATTERN = "https://college/article/(\d+)/(\d+)"
DATE_FORMATS = ["%b. %d, %Y", "%b %d, %Y", "%B %d, %Y"]

openai_client = OpenAI()


def parse_html_with_LLM(html_text: str) -> Tuple[str, str, Optional[datetime]]:

    PREFERRED_DATE_FORMAT = "%B %d, %Y"
    # Extract the title, main content, and date using LLM
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that extracts the title, main content, and date from a given HTML text.",
            },
            {
                "role": "user",
                "content": (
                    f"Extract the title, main content, and date from the following HTML:\n\n"
                    f"======================\n"
                    f"{html_text}\n"
                    f"======================\n"
                    f"Only return in JSON format with keys 'title', 'content', and 'date' and nothing else.\n"
                    f"Date should be in the format of {PREFERRED_DATE_FORMAT}\n"
                    f"Output: "
                ),
            },
        ],
        max_tokens=4096,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    # Parse the response
    result = response.choices[0].message.content.strip()

    # Convert the result to a dictionary
    result_dict = eval(result)

    # Convert the date string to a datetime object
    date_str = result_dict.get("date", "")
    date_obj = None
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, PREFERRED_DATE_FORMAT)
        except ValueError:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return result_dict.get("title", ""), result_dict.get("content", ""), date_obj


# date_pattern is used to extract the date from the date_selector
# for example:
#     date_pattern = r"([A-Za-z]+ \d{1,2}, \d{4})"
#     text = "May 24, 2024 | 6:37pm EDT"
# extracts:  May 24, 2024
TEXT_DATE_PATTERN = r"([A-Za-z]+ \d{1,2}, \d{4})"

progress = {"completed": 0}
semaphore = asyncio.Semaphore(2)

async def getArticleText(
    url: str, numRetries: int, useProxy: bool = True
) -> Tuple[str, Optional[datetime]]:
    attempts = 0
    content = ""
    dateObj = None
    if url is not None and len(url) > 0:
        while attempts <= numRetries and len(content) < 5:
            # only use proxy if we have tried and failed in attempt 0
            if attempts > 3:
                useProxy = True
                
            # content_obj = firecrawler.scrape_url(url)
            # content = textutil.clean_markdown(content_obj['markdown'])
            async with aiohttp.ClientSession() as session:
                content = await scraper.fetch_markdown(
                            session=session, 
                            url=url, 
                            semaphore=semaphore, 
                            progress=progress, 
                            total=1,
                            remove_links=True
                        )
                content = content["content"]
            attempts += 1

        try:
            date_groups = re.search(URL_DATE_PATTERN, url)
            if date_groups and len(date_groups.groups()) >= 2:
                try:
                    dateObj = datetime(
                        int(date_groups.group(1)),
                        int(date_groups.group(2)),
                        1,
                    )
                except (ValueError, TypeError) as e:
                    print(f"\tInvalid date values in URL {url}: {e}")
        except (AttributeError, TypeError) as e:
            print(f"\tFailed to extract date from URL {url}: {e}")

        print(
            f"\t\t\t{len(content)} ... "
            + content[-30:].replace("\n", "")
            + "\t:::"
            + (f"{dateObj.year}-{dateObj.month:02d}" if dateObj else "")
        )

    return content, dateObj


async def getArticleList(
    listUrl: str, numRetries: int, showProgress: bool = False, useProxy: bool = False
) -> List[Tag]:
    """Get articles linked off listing pages
    """
    articleList: List[Tag] = []
    pattern = r'\[(.*?)\]\((https://www.columbiaspectator.com/opinion/\d+/\d+/[^)]+)\)'
    try:
        # content = firecrawler.scrape_url(listUrl)['markdown']

        async with aiohttp.ClientSession() as session:
            content = await scraper.fetch_markdown(
                        session=session, 
                        url=listUrl, 
                        semaphore=semaphore, 
                        progress=progress, 
                        total=1,
                        remove_links=False
                    )
            content = content["content"]

        matches = re.findall(pattern, content)
        for match in matches:
            article_tag = Tag(name='a', attrs={'href': match[1]})
            article_tag.string = match[0]
            articleList.append(article_tag)
    except Exception as e:
        print(f"\tFailed to scrape listing page {listUrl}: {e}")

    return articleList


def getFullUrl(url: str) -> str:
    if not url.startswith("http"):
        url = BASE_URL + url
    return url


async def process_article(article: Tag) -> Tuple[Optional[Dict[str, Any]], int]:
    url = article.get("href")

    if url is not None and len(url) > 0:
        url = getFullUrl(url)

        if (
            url is not None
            and len(url) > 10
            and article.text is not None
            and len(article.text) > 0
            and article.text.strip() != ""
        ):

            body, dateObj = await getArticleText(url, RETRIES)
            return {
                "title": article.text.strip('"').strip(),
                "url": url,
                "body": body,
                "year": dateObj.year,
                "month": dateObj.month,
                "day": dateObj.day,
            }, body.count(" ")
    return None, 0


async def getArticles(
    baseURL: str, pageList: list, showProgress: bool = False, useProxy: bool = False
) -> Tuple[pd.DataFrame, List[int]]:
    CHECKPOINT_FILENAME: str = f"{OUTPUT_DIR}/{SCHOOL}-{SUBJECT}.parquet"
    failedPages: List[int] = []
    articles: List[Dict[str, Any]] = []
    dateObj = None
    for pageNumber in pageList:
        articleList = await getArticleList(
            baseURL + str(pageNumber), RETRIES, showProgress, useProxy
        )
        wordCount = 0
        if len(articleList) == 0:
            failedPages.append(pageNumber)
        else:
            # Process articles concurrently using asyncio.gather
            tasks = [process_article(article) for article in articleList]
            results = await asyncio.gather(*tasks)
            
            for result, word_count in results:
                if result is not None and result["url"] is not None:
                    url = result["url"]
                    # Only append if URL is not already in articles
                    if not any(article["url"] == url for article in articles):
                        articles.append(result)
                        wordCount += word_count
                        
        if pageNumber % CHECKPOINT_FREQUENCY == 0:
            ouraws.saveNewArticles(articles, checkpoint_name=CHECKPOINT_FILENAME)
        if showProgress:
            print(
                "-> {} : {} : {} : {}: failed: {}".format(
                    pageNumber,
                    len(articleList),
                    wordCount,
                    baseURL + str(pageNumber),
                    failedPages,
                )
            )
        pageNumber += 1
    df = ouraws.saveNewArticles(articles, checkpoint_name=CHECKPOINT_FILENAME)
    return df, failedPages


async def startProcessing(startPage: int, endPage: int, numRetries: int) -> None:
    pageNumbers = list(range(startPage, endPage + 1, LISTING_INCREMENT))
    print(f"==> Processing pages: {pageNumbers}")
    df, failedPages = await getArticles(LISTING_BASE_URL, pageNumbers, showProgress=True)
    while len(failedPages) > 0 and numRetries > 0:
        retry_df, failedPages = getArticles(
            LISTING_BASE_URL, failedPages, showProgress=True, useProxy=True
        )
        # merging together retrieved articles with newly retrieved ones
        if not retry_df.empty and retry_df.shape[0] > 0:
            df = df[~df["url"].isin(retry_df["url"])]
            df = pd.concat([df, retry_df])
        print(f"failed pages: {failedPages}")
        numRetries -= 1

    # DataFrame df has dimensions of (# articles, #attributes)
    print(
        "Total articles: {}, each with attributes: {}".format(df.shape[0], df.shape[1])
    )

    # Get the earliest article
    earliest = df.sort_values(["year", "month", "day"]).iloc[0]
    print(f"Earliest: {earliest['year']}-{earliest['month']}-{earliest['day']}")

    # Get the latest article
    latest = df.sort_values(["year", "month", "day"], ascending=False).iloc[0]
    print(f"Latest:   {latest['year']}-{latest['month']}-{latest['day']}")

    ouraws.saveByYear(
        df, output_dir=OUTPUT_DIR, prefix=f"{OUTPUT_DIR}/{SCHOOL}-{SUBJECT}"
    )


def load_config(config_file: str) -> Dict[str, Any]:
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    return config


# =====================================================================
# main
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process student paper opinion pieces")
    parser.add_argument("config", help="Path to the YAML configuration file")
    parser.add_argument("start_page", type=int, help="Starting page number")
    parser.add_argument("end_page", type=int, help="Ending page number")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        globals().update(config)

        print(
            f"Processing {SCHOOL} {SUBJECT} from {args.start_page} to {args.end_page}"
        )
        asyncio.run(startProcessing(args.start_page, args.end_page, config["RETRIES"]))
    except Exception as e:
        print(f"Exception: {e}")

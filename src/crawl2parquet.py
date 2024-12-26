#########################################################################
# crawl2parquet.py
# ------------------
# Scraping student paper opinion pieces with proxy services & 
# saving to a local parquet file
# 
# @author Phil Mui
# @email thephilmui@gmail.com
# @date Sun Sep  1 21:37:14 PDT 2024
#
# Retry logic: bit.ly/requests-retry
#########################################################################

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

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

RETRIES = 6
CHECKPOINT_FREQUENCY = 10 # every 10 pages

OUTPUT_DIR="data"
SCHOOL="college"
SUBJECT="opinions"

BASE_URL = "<base>"
LISTING_BASE_URL = f"<url>"
ARTICLE_SELECTOR = f"<selector>"
TITLE_SELECTOR = f"<title_selector>"
CONTENT_SELECTOR = f"<content_selector>"
DATE_SELECTOR = f"<date_selector>"
URL_DATE_PATTERN = "https://college/article/(\d+)/(\d+)"
DATE_FORMAT="%B %d, %Y"

openai_client = OpenAI()

def parse_html_with_LLM(html_text: str) -> tuple[str, str, datetime]:
    
    # Extract the title, main content, and date using LLM
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that extracts the title, main content, and date from a given HTML text."
            },
            {
                "role": "user",
                "content": (
                    f"Extract the title, main content, and date from the following HTML:\n\n"
                    f"======================\n"
                    f"{html_text}\n"
                    f"======================\n"
                    f"Only return in JSON format with keys 'title', 'content', and 'date' and nothing else.\n"
                    f"Date should be in the format of {DATE_FORMAT}\n"
                    f"Output: "
                )
            }
        ],
        max_tokens=4096,
        temperature=0.1,
        response_format={ "type": "json_object" }
    )
    
    # Parse the response
    result = response.choices[0].message.content.strip()
    
    # Convert the result to a dictionary
    result_dict = eval(result)
    
    # Convert the date string to a datetime object
    date_str = result_dict.get('date', '')
    date_obj = None
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, DATE_FORMAT)
        except ValueError:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return result_dict.get('title', ''), result_dict.get('content', ''), date_obj

# date_pattern is used to extract the date from the date_selector
# for example:
#     date_pattern = r"([A-Za-z]+ \d{1,2}, \d{4})"
#     text = "May 24, 2024 | 6:37pm EDT"
# extracts:  May 24, 2024
TEXT_DATE_PATTERN = r"([A-Za-z]+ \d{1,2}, \d{4})"

def getArticleText(url, numRetries, useProxy=True):
    attempts = 0
    content = ""
    dateObj = None
    if url is not None and len(url) > 0:
        while attempts <= numRetries and len(content) < 5: 
            # only use proxy if we have tried and failed in attempt 0
            if attempts > 3: useProxy = True
            html = ourrequests.requestHtml(url, attempts, useProxy)
            if html is not None and len(html) > 10:
                soup = BeautifulSoup(html, 'html.parser')
                titleObj = soup.select_one(TITLE_SELECTOR)
                contentObj  = soup.select_one(CONTENT_SELECTOR)
                dateObj = soup.select_one(DATE_SELECTOR)
                if titleObj is not None: content = titleObj.text.strip() + "\n"
                if contentObj is not None:  content += contentObj.text.strip()
                if dateObj is not None: 
                    match = re.search(TEXT_DATE_PATTERN, dateObj.text)
                    if match:
                        date_string = match.group(1)
                        try:
                            # Try full month name format first
                            dateObj = datetime.strptime(date_string, "%B %d, %Y")
                        except ValueError:
                            # If that fails, try abbreviated month format
                            dateObj = datetime.strptime(date_string, "%b. %d, %Y")
                    else:
                        dateObj = None
                    
                # for date, try to the URL first
                if dateObj is None:
                    try:
                        date_groups = re.search(URL_DATE_PATTERN, url)
                        if date_groups and len(date_groups.groups()) >= 2:
                            try:
                                dateObj = datetime(int(date_groups.group(1)), 
                                                 int(date_groups.group(2)), 1)
                            except (ValueError, TypeError) as e:
                                print(f"\tInvalid date values in URL {url}: {e}")
                    except (AttributeError, TypeError) as e:
                        print(f"\tFailed to extract date from URL {url}: {e}")

            if len(html) > 10 and (content is None or dateObj is None):
                title, content, dateObj = parse_html_with_LLM(html)
                content = title + "\n" + content

            attempts += 1

            # give the website a small break before next ping
            time.sleep(random.randint(0, 100 * attempts) / 1000.0)
        print(f"\t\t\t{len(content)} ... " + content[-30:].replace('\n','') + ": " + str(dateObj))

    return content, dateObj


def getArticleList(listUrl, numRetries, showProgress=False, useProxy=False):
    ''' Get articles linked off listing pages
        Retry logic: bit.ly/requests-retry
    '''
    articleList = []
    attempts = 0
    while attempts <= numRetries and len(articleList) == 0:
        # only use proxy if we have tried and failed in attempt 0
        if attempts > 3: useProxy = True
        html = ourrequests.requestHtml(listUrl, attempts, useProxy)
        if html is not None and len(html) > 0:
            soup = BeautifulSoup(html, "html.parser")
            articles = soup.select(ARTICLE_SELECTOR)
            if articles is not None and len(articles) > 0: articleList += articles
        if showProgress: print(f"\tretrieved: {len(articleList)}")
        attempts += 1

    return articleList

def getFullUrl(url):
    if not url.startswith("http"):
        url = BASE_URL + url
    return url

def process_article(article: Tag) -> tuple[dict, int]:
    url = article.get('href')

    if url is not None and len(url) > 0:
        url = getFullUrl(url)
    
        if url is not None and len(url) > 10 and \
            article.text is not None and len(article.text) > 0 and \
            article.text.strip() != "":
                
            body, dateObj = getArticleText(url, RETRIES)
            return { 
                'title' : article.text.strip("\"").strip(),
                'url'   : url,
                'body'  : body,
                'year'  : dateObj.year,
                'month' : dateObj.month,
                'day'   : dateObj.day
            }, body.count(' ')
    return None, 0

def getArticles(baseURL, pageList, showProgress=False, useProxy=False):
    CHECKPOINT_FILENAME = f"{OUTPUT_DIR}/{SCHOOL}-{SUBJECT}.parquet"
    failedPages = []
    articles = []
    dateObj = None
    for pageNumber in pageList:
        articleList = getArticleList(baseURL+str(pageNumber), 
                                     RETRIES, showProgress, useProxy)
        wordCount = 0
        if len(articleList) == 0: failedPages.append(pageNumber)
        else:
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(process_article, article) for article in articleList]
                for future in as_completed(futures):
                    try:
                        result, word_count = future.result(timeout=30)
                        if result is not None and result['url'] is not None:
                            url = result['url']
                            articles.append(result)
                            wordCount += word_count
                    except Exception as e:
                        print(f"\acannot processing article: {e}")
        if pageNumber % CHECKPOINT_FREQUENCY == 0: 
            ouraws.saveNewArticles(articles, checkpoint_name=CHECKPOINT_FILENAME)
        if showProgress: 
            print("-> {} : {} : {} : {}: failed: {}"
                  .format(pageNumber, len(articleList), wordCount, 
                          baseURL+str(pageNumber), failedPages))
        pageNumber += 1
    df = ouraws.saveNewArticles(articles, checkpoint_name=CHECKPOINT_FILENAME)
    return df, failedPages

def startProcessing(startPage, endPage, numRetries):
    df, failedPages = getArticles(LISTING_BASE_URL, range(startPage,endPage+1), 
                                  showProgress=True)
    while len(failedPages) > 0 and numRetries > 0:
        retry_df, failedPages = getArticles(LISTING_BASE_URL, 
                                            failedPages, 
                                            showProgress=True,
                                            useProxy=True)
        # merging together retrieved articles with newly retrieved ones
        if not retry_df.empty and retry_df.shape[0] > 0:
            df = df[~ df['url'].isin(retry_df['url'])]
            df = pd.concat([df, retry_df])
        print(f"failed pages: {failedPages}")
        numRetries -= 1

    # DataFrame df has dimensions of (# articles, #attributes)
    print("Total articles: {}, each with attributes: {}"
            .format(df.shape[0], df.shape[1]))

    # Get the earliest article
    earliest = df.sort_values(['year', 'month', 'day']).iloc[0]
    print(f"Earliest: {earliest['year']}-{earliest['month']}-{earliest['day']}")

    # Get the latest article
    latest = df.sort_values(['year', 'month', 'day'], ascending=False).iloc[0]
    print(f"Latest:   {latest['year']}-{latest['month']}-{latest['day']}")

    ouraws.saveByYear(df, output_dir=OUTPUT_DIR, 
                    prefix=f"{OUTPUT_DIR}/{SCHOOL}-{SUBJECT}")


def load_config(config_file):
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    return config

#=====================================================================
# main
#=====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process student paper opinion pieces")
    parser.add_argument("config", help="Path to the YAML configuration file")
    parser.add_argument("start_page", type=int, help="Starting page number")
    parser.add_argument("end_page", type=int, help="Ending page number")
    args = parser.parse_args()
    
    try:
        config = load_config(args.config)
        globals().update(config)
        
        print(f"Processing {SCHOOL} {SUBJECT} from {args.start_page} to {args.end_page}")
        startProcessing(args.start_page, args.end_page, config["RETRIES"])
    except Exception as e:
        print(f"Exception: {e}")


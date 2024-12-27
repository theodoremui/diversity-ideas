#########################################################################
#
# ourrequests.py
#
# @author: Phil Mui
# @email: thephilmui@gmail.com
# @date: Mon Jan 23 16:45:56 PST 2023
#
# Retry logic: bit.ly/requests-retry
#########################################################################

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
import os
import random
import time

import aiohttp
import asyncio
import requests
from requests.adapters import HTTPAdapter, Retry
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential

BAD_HTTP_CODES = (400,401,403,404,406,408,409,410,429,500,502,503,504)
USER_AGENT = UserAgent()
HTTP_RETRIES = 6

from scrapingant_client import ScrapingAntClient
SCRAPINGANT_API_TOKEN = os.environ.get("SCRAPINGANT_API_TOKEN")
scrapingant_client = ScrapingAntClient(token=SCRAPINGANT_API_TOKEN)

SCRAPINGDOC_API_KEY=os.environ.get('SCRAPINGDOC_API_KEY')
SCRAPINGDOG_PROXY="https://api.scrapingdog.com/scrape"
SCRAPINGDOG_PAYLOAD={'api_key': SCRAPINGDOC_API_KEY, 'dynamic': 'false',
                    'url': '', 'wait':'5000', 'session_number':'', 'premium': 'true', 'country': 'us'}

COUNTRY_CODE=['us','eu']
SCRAPERAPI_API_KEY=os.environ.get('SCRAPERAPI_API_KEY')
SCRAPERAPI_DEVICETYPE=['desktop', 'mobile']
SCRAPERAPI_PROXY='http://api.scraperapi.com'
SCRAPERAPI_PAYLOAD={'api_key': SCRAPERAPI_API_KEY,
                    'url': '', 'device_type': ''}

HEADERS  = [
{ 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36' },
{ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36' },
{ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36' },
{ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36' },
{ 'User-Agent': 'Mozilla/5.0 (Android 4.4; Mobile; rv:41.0) Gecko/41.0 Firefox/41.0' },
{ 'User-Agent': 'Mozilla/5.0 (Android 4.4; Tablet; rv:41.0) Gecko/41.0 Firefox/41.0' },
{ 'User-Agent': 'Mozilla/5.0 (X11; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0' },
{ 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:10.0) Gecko/20100101 Firefox/10.0' },
{ 'User-Agent': 'Mozilla/5.0 (Maemo; Linux armv7l; rv:10.0) Gecko/20100101 Firefox/10.0 Fennec/10.0' },
{ 'User-Agent': 'Mozilla/5.0 (Linux; Android 7.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Focus/1.0 Chrome/59.0.3029.83 Mobile Safari/537.36' },
{ 'User-Agent': 'Mozilla/5.0 (Linux; Android 7.0) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Focus/1.0 Chrome/59.0.3029.83 Safari/537.36' },
{ 'User-Agent': 'Mozilla/5.0 (Android 7.0; Mobile; rv:62.0) Gecko/62.0 Firefox/62.0' },
]



def requestWithProxy(url, numRetries=5):
    html = ""
    
    # ScrapingDog
    SCRAPINGDOG_PAYLOAD['url'] = url
    SCRAPINGDOG_PAYLOAD['session_number'] = random.randint(0,9999)
    result = requests.get(SCRAPINGDOG_PROXY, params=SCRAPINGDOG_PAYLOAD)
    if result.status_code == 200: 
        html = result.text.strip()
        print(f"\tdog: {len(html)}: {url}")
        
    # ScraperAPI
    if len(html) < 10:
        SCRAPERAPI_PAYLOAD['url'] = url
        SCRAPERAPI_PAYLOAD['device_type'] = random.choice(SCRAPERAPI_DEVICETYPE)
        SCRAPERAPI_PAYLOAD['country_code'] = random.choice(COUNTRY_CODE)
        SCRAPERAPI_PAYLOAD['session_number'] = random.randint(0,9999)
        # SCRAPERAPI_PAYLOAD['render'] = 'true'
        result = requests.get(url = SCRAPERAPI_PROXY, params = SCRAPERAPI_PAYLOAD)
        if result != None: html = result.text.strip()
        print(f"\tapi: {len(html)}: {url}")
        
    # ScrapingAnt
    if len(html) < 10:
        try:
            response = asyncio.run(scrapingant_client.general_request_async(url))
            if response is not None and response.status_code == 200:
                html = response.content
                print(f"\tant: {len(html)}: {url}")
        except Exception as e:
            print(f"\tant exception: {e}")

    return html

async def asyncGet(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            # Get the response status code
            status = response.status
            # Read the response body
            body = await response.text().strip()
            print(f"\tasy: {len(body)}: {url}")
            # print(f"\tpre: {status}: {body[:50]} ...")

"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
CHROME_OPTIONS = Options()
CHROME_PREFS = {"profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.javascript": 2}
CHROME_OPTIONS.add_argument("--disable-javascript")
CHROME_OPTIONS.add_argument("--disable-extensions")
CHROME_OPTIONS.add_argument("--disable-gpu")
CHROME_OPTIONS.add_argument("--headless")
CHROME_OPTIONS.add_experimental_option("prefs", CHROME_PREFS)
CHROME_OPTIONS.headless = True

# Ensure the latest version of ChromeDriver is installed
chrome_driver_path = ChromeDriverManager().install()
chrome_service = ChromeService(executable_path=chrome_driver_path)
CHROME_DRIVER = webdriver.Chrome(service=chrome_service, options=CHROME_OPTIONS)

def requestWithChrome(url, waitSeconds=1):
    try:
        CHROME_DRIVER.implicitly_wait(waitSeconds)
        CHROME_DRIVER.set_page_load_timeout(waitSeconds)
        CHROME_DRIVER.get(url)
    except Exception as e:
        print(f"\t{str(e)[:65]}")
    html = ""
    if CHROME_DRIVER.page_source != None:
        html = CHROME_DRIVER.page_source.encode("utf-8").strip()
    print(f"\tchr: {len(html)}: {url}: ...{html[-7:]}")
    return html
"""

def requestWithRetry(url, numRetries=HTTP_RETRIES):
    html = ""
    s = requests.Session()
    retries = Retry(total=2*numRetries,
                    connect=numRetries,
                    read=numRetries,
                    backoff_factor=0.1,
                    status_forcelist=BAD_HTTP_CODES)
    adapter = HTTPAdapter(max_retries=retries)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    html = ""
    try:
        response = s.get(url, headers=random.choice(HEADERS))
        response.raise_for_status()
        if response.status_code == 200:
            html = response.text.strip()
    except Exception as e:
        print(f"\trequest failed for {url}: {e}")
    s.close()
    print(f"\treq: {len(html)}: {url[:16]}...{url[-16:]}::: ...{html[-7:]}")

    return html

from spider import Spider
spider = Spider()

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def spiderHtml(url: str, attempt: int, useProxy: bool = True, return_format: str='raw') -> str:
    """Return HTML of <url> using spider.

    Args:
        url (str): url to get html from
        attempt (int): number of attempts to get html from url
        useProxy (bool, optional): _description_. Defaults to False.
        return_format (str, optional): return format of the url. Defaults to 'raw'.
            Possible values are markdown, commonmark, raw, text, and bytes. 
            Use raw to return the default format of the page like HTML etc.
    Returns:
        str: html of the url
    """
    html = ""
    try:
        crawler_params = {
            "anti_bot": True,
            # "delay": 2,
            'limit': 1,
            'metadata': True,
            'proxy_enabled': useProxy,
            'request': 'smart',
            'respect_robots': True,
            'return_format': return_format,
            "stealth": True,
            'store_data': True,
        }
        crawl_result = spider.crawl_url(url, params=crawler_params)
        html = crawl_result[0]['content'].strip()

    except Exception as e:
        print(f"\tspider exception: {e}")
        raise  # Re-raise the exception to trigger a retry

    return html


def requestHtml(url: str, attempt: int, useProxy: bool = True, return_format: str='raw') -> str:
    html = ""
    try:
        html = requestWithRetry(url, HTTP_RETRIES)
    except Exception as e: 
        print(f"\tsimple request: {e}")

    if len(html) < 10:
        try:
            html = requestWithProxy(url, HTTP_RETRIES)
        except Exception as e:
            print(f"\tproxy request: {e}")
        
    if len(html) < 10:  # spider is slow -- use judiciously
        try:
            html = spiderHtml(url, attempt, useProxy, return_format)
        except Exception as e:
            print(f"\tspider request: {e}")
            
    # selenium chrome is slow -- use judiciously
    # if len(html) < 10:
    #     try:
    #         html = requestWithChrome(url, waitSeconds=(attempt-1))
    #     except Exception as e:
    #         print(f"\tchrome request: {e}")

    return html




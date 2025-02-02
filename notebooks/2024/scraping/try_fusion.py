from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time


def scrape_fusion_app(url, wait_for_selector=None, scroll=False):
    """
    Scrapes content from a fusion-app website after ensuring dynamic content is loaded.

    Args:
        url (str): The URL to scrape
        wait_for_selector (str): CSS selector to wait for (indicates content is loaded)
        scroll (bool): Whether to scroll the page to load lazy content

    Returns:
        str: The rendered HTML content
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)

        # Wait for fusion-app initialization
        time.sleep(2)

        if wait_for_selector:
            # Wait for specific element that indicates content is loaded
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
            )

        if scroll:
            # Scroll to bottom to trigger lazy loading
            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

        # Get the rendered HTML
        html_content = driver.page_source

        # Parse with BeautifulSoup for easier handling
        soup = BeautifulSoup(html_content, "html.parser")
        return soup

    finally:
        driver.quit()


# Example usage
def example_scrape():
    url = "https://www.columbiaspectator.com/opinion/op-eds/1/"
    # Wait for a specific element that indicates content is loaded
    soup = scrape_fusion_app(url, wait_for_selector=".content-loaded", scroll=True)

    # Example: Extract all article titles
    articles = soup.select(".article-title")
    for article in articles:
        print(article.text.strip())


if __name__ == "__main__":
    example_scrape()

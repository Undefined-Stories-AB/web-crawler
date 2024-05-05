import json
import os
import re
import requests
from datetime import datetime
from dateutil import tz
from feedgen.feed import FeedGenerator
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define a mapping of local variable names to corresponding ENV variable names
# This will also work as a dictionary to store configuration values
cfg = {
    'urls': "URLS",
    'product_link_selector': "PRODUCT_LINK_CSS_SELECTOR",
    'stock_amount_selector': "SUGGESTED_STOCK_AMOUNT_CSS_SELECTOR",
    'stock_amount_attribute': "SUGGESTED_STOCK_AMOUNT_ATTRIBUTE_NAME",
    'purchase_amount_selector': "INPUT_PURCHASE_AMOUNT_CSS_SELECTOR",
    'purchase_submit_selector': "PURCHASE_SUBMIT_CSS_SELECTOR"
}

# Retrieve and assign values from ENV variables to the configuration dictionary
for key, env_name in cfg.items():
    value = os.getenv(env_name)
    if value is None:
        raise ValueError(f"Missing environment variable: {env_name}")
    cfg[key] = value


def process_product_pages(
    url: str, driver: webdriver.Chrome, entries: list = []
) -> list:
    # Navigate to the product page
    driver.get(url)

    # Find all product links on the page
    product_links = driver.find_elements(
        By.CSS_SELECTOR, 
        cfg['product_link_selector']
    )

    product_links_count = len(product_links)

    # Iterate through each product link
    for link in product_links[len(entries):]:
        product_url = link.get_attribute("href")

        if product_url:
            # Visit each product page
            driver.get(product_url)

            # Get the suggested current stock amount
            suggested_stock_amount = driver.find_element(
                By.CSS_SELECTOR, cfg['stock_amount_selector']
            ).get_attribute(cfg['stock_amount_attribute'])

            stock_amount = suggested_stock_amount
            msg = ""
            try:
                antal_input = driver.find_element(
                    By.CSS_SELECTOR,
                    cfg['purchase_amount_selector']
                )

                # Set value of order amount to 999
                driver.execute_script(
                    "arguments[0].value = arguments[1];", antal_input, 999
                )

                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                    antal_input,
                )

                # Click on buy button
                submit_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (
                            By.CSS_SELECTOR, 
                            cfg['purchase_submit_selector']
                        )
                    )
                )

                # This will redirect us to a simple Error page
                submit_button.submit()

                # Get the text content of the Error div
                error_message = (
                    WebDriverWait(driver, 10)
                    .until(EC.presence_of_element_located(
                            (
                                By.CLASS_NAME,
                                "Error"
                            )
                        )
                    )
                    .text
                )

                matched_stock_amount = re.search(r".*(\d+).*", error_message)
                if matched_stock_amount:
                    stock_amount = str(int(matched_stock_amount.group(1)))
                    msg = "Confirmed"
            except TimeoutException:
                msg = f"Unconfirmed. Assumed stock amount is: {suggested_stock_amount}"

            product = str(product_url.split("/")[-1])

            entry = {
                # "url": str(product_url),
                "product": product,
                "stock_amount": stock_amount,
                "suggested_stock_amount": suggested_stock_amount,
                "msg": msg,
            }
            entries.append(entry)

            if len(entries) >= product_links_count:
                break
            return process_product_pages(url, driver, entries)

    return entries


if __name__ == "__main__":
    # Set Chrome options to run headlessly
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode

    FEED_URL = "https://github.com/Undefined-Stories-AB/web-crawler/releases/download/feeds/stocks"

    # Launch the browser
    chrome_driver = webdriver.Chrome(options=chrome_options)

    try:
        with requests.get(FEED_URL + ".json") as feed:
            existing_entries = feed.json()
            new_entries = []
            for product_page_url in cfg['urls'].split(','):
                new_entries.append(
                    process_product_pages(
                        product_page_url,
                        chrome_driver
                    )
                )

            # Flatten the list of lists into a single list of dicts
            new_entries = [
                item for sublist in new_entries for item in sublist
            ] + existing_entries

            with open("stocks.json", "w", encoding="utf-8") as fp:
                fp.write(json.dumps(existing_entries + new_entries))

            # RSS feed configuration
            feed = FeedGenerator()
            feed.title("Stocks RSS Feed")
            feed.link(href=(FEED_URL + ".rss"))
            feed.subtitle("Simple RSS feed")

            # Adding new entries from data
            for entry in new_entries:
                item = feed.add_entry()
                item.title(entry["product"])
                item.link(href=entry["product"])
                item.description(entry["stock_amount"])
                item.published(datetime.now(tz.gettz('Europe/Stockholm')))
                item.updated(datetime.now(tz.gettz('Europe/Stockholm')))
            
            for entry in existing_entries:
                item = feed.add_entry()
                item.title(entry["product"])
                item.link(href=entry["product"])
                item.description(entry["stock_amount"])
                item.updated(datetime.now(tz.gettz('Europe/Stockholm')))
                if 'published' in entry:
                    item.published(entry['published'])

            # Save the RSS feed to a file
            feed.rss_file("stocks.rss")
    finally:
        # Quit the WebDriver
        chrome_driver.quit()

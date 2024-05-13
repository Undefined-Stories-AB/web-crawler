import json
import os
import re
from datetime import datetime
from dateutil import tz
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
    'purchase_submit_selector': "PURCHASE_SUBMIT_CSS_SELECTOR",
    'product_name_selector': "PRODUCT_NAME_CSS_SELECTOR",
    'product_brand_selector': "PRODUCT_BRAND_CSS_SELECTOR",
    'product_price_selector': "PRODUCT_PRICE_CSS_SELECTOR",
    'product_price_currency_selector': "PRODUCT_PRICE_CURRENCY_CSS_SELECTOR",
    'product_availability_selector': "PRODUCT_AVAILABILITY_CSS_SELECTOR",
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

            product_name = driver.find_element(
                By.CSS_SELECTOR,
                cfg['product_name_selector']).text.strip().split('\n').pop()
            product_brand = driver.find_element(
                By.CSS_SELECTOR,
                cfg['product_brand_selector']).text.strip()
            product_price = driver.find_element(
                By.CSS_SELECTOR,
                cfg['product_price_selector']).get_attribute('content')
            product_price_currency = driver.find_element(
                By.CSS_SELECTOR,
                cfg['product_price_currency_selector']).get_attribute('content')
            product_availability = driver.find_element(
                By.CSS_SELECTOR,
                cfg['product_availability_selector']).get_attribute('content')

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

                matched_stock_amount = re.search(
                    r".+[\s+](-?\d+).*", error_message)
                if matched_stock_amount:
                    stock_amount = str(int(matched_stock_amount.group(1)))
                    msg = "Confirmed"
            except TimeoutException:
                msg = f"Unconfirmed. Assumed stock amount is: {
                    suggested_stock_amount}"

            slug = str(product_url.split("/")[-1])

            entry = {
                "url": str(product_url),
                "date": datetime.now(tz.gettz('Europe/Stockholm')).isoformat(),
                "slug": slug,
                "name": product_name,
                "brand": product_brand,
                "price": product_price,
                "currency": product_price_currency,
                "availability": product_availability,
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

    # Launch the browser

    chrome_driver = webdriver.Chrome(options=chrome_options)
    try:
        new_entries = []
        for product_page_url in cfg['urls'].split(','):

            new_entries.append(
                process_product_pages(
                    product_page_url,
                    chrome_driver
                )
            )

        with open("stocks.json", "w", encoding="utf-8") as fp:
            fp.write(json.dumps(
                new_entries
            ))

    finally:
        # Quit the WebDriver
        chrome_driver.quit()

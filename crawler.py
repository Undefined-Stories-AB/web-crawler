import json
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv

load_dotenv()

URLS = os.getenv("URLS").split(",")
PRODUCT_LINK_CSS_SELECTOR = os.getenv("PRODUCT_LINK_CSS_SELECTOR")
SUGGESTED_STOCK_AMOUNT_CSS_SELECTOR = os.getenv(
    "SUGGESTED_STOCK_AMOUNT_CSS_SELECTOR")
SUGGESTED_STOCK_AMOUNT_ATTRIBUTE_NAME = os.getenv(
    "SUGGESTED_STOCK_AMOUNT_ATTRIBUTE_NAME")
INPUT_PURCHASE_AMOUNT_CSS_SELECTOR = os.getenv(
    "INPUT_PURCHASE_AMOUNT_CSS_SELECTOR")
PURCHASE_SUBMIT_CSS_SELECTOR = os.getenv("PURCHASE_SUBMIT_CSS_SELECTOR")


def process_product_pages(url, driver: webdriver.Chrome, entries: list = []) -> list:
    # Navigate to the product page
    driver.get(url)

    # Find all product links on the page
    product_links = driver.find_elements(
        By.CSS_SELECTOR, PRODUCT_LINK_CSS_SELECTOR)

    product_links_count = len(product_links)

    # Iterate through each product link
    for link in product_links[len(entries):]:
        product_url = link.get_attribute('href')

        if product_url:
            # Visit each product page
            driver.get(product_url)

            # Get the suggested current stock amount
            suggested_stock_amount = driver.find_element(
                By.CSS_SELECTOR,
                SUGGESTED_STOCK_AMOUNT_CSS_SELECTOR).get_attribute(SUGGESTED_STOCK_AMOUNT_ATTRIBUTE_NAME)

            stock_amount = suggested_stock_amount
            msg = ''
            try:
                antal_input = driver.find_element(
                    By.CSS_SELECTOR,
                    INPUT_PURCHASE_AMOUNT_CSS_SELECTOR)

                # Set value of order amount to 999
                driver.execute_script(
                    "arguments[0].value = arguments[1];", antal_input, 999)

                # Optionally, you can trigger a JavaScript change event to simulate user interaction
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", antal_input)

                # Click on buy button
                submit_button = driver.find_element(
                    By.CSS_SELECTOR,
                    PURCHASE_SUBMIT_CSS_SELECTOR
                )

                # This will redirect us to a simple Error page
                submit_button.submit()

                # Get the text content of the Error div
                error_message = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "Error"))
                ).text

                matched_stock_amount = re.search(
                    r".*([-+]?\d+).*", error_message)
                if matched_stock_amount:
                    stock_amount = matched_stock_amount.group(0)
                    msg = "Confirmed"
            except TimeoutException:
                msg = f"Unconfirmed. Assumed stock amount is: {suggested_stock_amount}"

            product = str(product_url.split('/')[-1])

            entry = {
                # "url": str(product_url),
                "product": product,
                "stock_amount": stock_amount,
                "suggested_stock_amount": suggested_stock_amount,
                "msg": msg
            }
            entries.append(entry)

            if len(entries) >= product_links_count:
                break
            return process_product_pages(url, driver, entries)

    return entries


# Example usage
if __name__ == "__main__":
    # Set Chrome options to run headlessly
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode

    # Launch the browser
    chrome_driver = webdriver.Chrome(options=chrome_options)

    try:
        with open("stocks.json", "a", encoding="utf-8") as fp:
            entries = []
            for url in URLS:
                entries.append(process_product_pages(url, chrome_driver))
            fp.write(json.dumps(entries))
    except:
        raise Exception("Failed to process product pages")
    finally:
        # Quit the WebDriver
        chrome_driver.quit()

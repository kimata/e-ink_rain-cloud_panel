#!/usr/bin/env python3
# - coding: utf-8 --

import os
import pathlib
import shutil

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

import datetime
import time

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
LOG_PATH = DATA_PATH / "log"

CHROME_DATA_PATH = str(DATA_PATH / "chrome")
DUMP_PATH = str(DATA_PATH / "deubg")

DRIVER_LOG_PATH = str(LOG_PATH / "webdriver.log")


def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1440")

    options.add_argument(
        '--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36"'
    )
    options.add_argument("--user-data-dir=" + CHROME_DATA_PATH)

    # NOTE: 下記がないと，snap で入れた chromium が「LC_ALL: cannot change locale (ja_JP.UTF-8)」
    # と出力し，その結果 ChromeDriverManager がバージョンを正しく取得できなくなる
    os.environ["LC_ALL"] = "C"

    if shutil.which("google-chrome") is not None:
        chrome_type = ChromeType.GOOGLE
    else:
        chrome_type = ChromeType.CHROMIUM

    driver = webdriver.Chrome(
        service=Service(
            ChromeDriverManager(chrome_type=chrome_type).install(),
            log_path=DRIVER_LOG_PATH,
            service_args=["--verbose"],
        ),
        options=options,
    )

    return driver


def shape_cloud_display(dirver):
    driver.find_element(By.XPATH, '//a[contains(@aria-label, "地形を表示")]').click()

    display_list = [
        {"class": "leaflet-bar", "mode": "none"},
        {"class": "leaflet-control-attribution", "mode": "none"},
        {"class": "jmatile-map-title", "mode": "block"},
        {"class": "jmatile-map-legend", "mode": "block"},
    ]

    for display in display_list:
        driver.execute_script(
            """
var elements = document.getElementsByClassName("{class_name}")
    for (i = 0; i < elements.length; i++) {{
        elements[i].style.display="{mode}"
    }}
""".format(
                class_name=display["class"],
                mode=display["mode"],
            )
        )

        driver.execute_script(
            """
var element = document.evaluate('{xpath}', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue
element.style.width="1920px"
element.style.height="1080px"
""".format(
                xpath='//div[contains(@id, "jmatile_map_")]'
            )
        )


def save_cloud_image(driver, url, img_path):
    wait = WebDriverWait(driver, 5)

    cloud_image_xpath = '//div[contains(@id, "jmatile_map_")]'

    driver.get(url)

    wait.until(EC.presence_of_element_located((By.XPATH, cloud_image_xpath)))
    shape_cloud_display(driver)

    wait.until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )

    driver.find_element(By.XPATH, '//div[contains(@id, "jmatile_map_")]').screenshot(
        img_path
    )


url = "https://www.jma.go.jp/bosai/nowc/#zoom:8/lat:32.683218/lon:132.333820/colordepth:deep/elements:hrpns&slmcs"

img_path = datetime.datetime.now().strftime("img/%Y%m%d_%H%M%S.png")
driver = create_driver()

save_cloud_image(driver, url, img_path)
driver.quit()

print("Finish.")

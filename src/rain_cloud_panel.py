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

import PIL.Image
import PIL.ImageDraw

import cv2
import numpy as np

import datetime
import time

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
LOG_PATH = DATA_PATH / "log"

CHROME_DATA_PATH = str(DATA_PATH / "chrome")
DUMP_PATH = str(DATA_PATH / "deubg")

DRIVER_LOG_PATH = str(LOG_PATH / "webdriver.log")

CLOUD_IMAGE_XPATH = '//div[contains(@id, "jmatile_map_")]'


def get_font(config, font_type, size):
    return PIL.ImageFont.truetype(
        str(
            pathlib.Path(
                os.path.dirname(__file__), config["PATH"], config["MAP"][font_type]
            )
        ),
        size,
    )


def get_face_map(font_config):
    return {
        "title": get_font(font_config, "JP_MEDIUM", 50),
    }


def draw_text(img, text, pos, font, align="left", color="#000"):
    draw = PIL.ImageDraw.Draw(img)

    if align == "center":
        pos = (pos[0] - font.getsize(text)[0] / 2, pos[1])
    elif align == "right":
        pos = (pos[0] - font.getsize(text)[0], pos[1])

    draw.text(pos, text, color, font, None, font.getsize(text)[1] * 0.4)

    return font.getsize(text)[0]


def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1080")

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


def shape_cloud_display(driver, parts_list, width, height, is_future):
    SCRIPT_CHANGE_DISPAY = """
var elements = document.getElementsByClassName("{class_name}")
    for (i = 0; i < elements.length; i++) {{
        elements[i].style.display="{mode}"
    }}
"""
    # driver.find_element(By.XPATH, '//a[contains(@aria-label, "地形を表示")]').click()

    driver.find_element(By.XPATH, '//a[contains(@aria-label, "色の濃さ")]').click()
    driver.find_element(By.XPATH, '//span[contains(text(), "濃い")]').click()

    driver.find_element(By.XPATH, '//a[contains(@aria-label, "地図を切り替え")]').click()
    driver.find_element(By.XPATH, '//span[contains(text(), "地名なし")]').click()

    for parts in parts_list:
        driver.execute_script(
            SCRIPT_CHANGE_DISPAY.format(
                class_name=parts["class"],
                mode=parts["mode"],
            )
        )

    if is_future:
        driver.find_element(
            By.XPATH,
            '//div[@class="jmatile-control"]//div[contains(text(), " +1時間 ")]',
        ).click()


def change_window_size(driver, url, width, height):
    wait = WebDriverWait(driver, 5)

    driver.get(url)
    # NOTE: まずは横幅を大きめにしておく
    driver.set_window_size(width, int(height * 1.5))
    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))

    element_size = driver.find_element(By.XPATH, CLOUD_IMAGE_XPATH).size
    if element_size["height"] != height:
        window_size = driver.get_window_size()
        driver.set_window_size(
            width,
            window_size["height"] + (height - element_size["height"]),
        )


def fetch_cloud_image(driver, url, width, height, is_future=False):
    PARTS_LIST = [
        {"class": "jmatile-map-title", "mode": "none"},
        {"class": "leaflet-bar", "mode": "none"},
        {"class": "leaflet-control-attribution", "mode": "none"},
        {"class": "leaflet-control-scale-line", "mode": "none"},
    ]

    wait = WebDriverWait(driver, 5)

    driver.get(url)

    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))
    for parts in PARTS_LIST:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, parts["class"])))

    shape_cloud_display(driver, PARTS_LIST, width, height, is_future)

    wait.until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )
    time.sleep(0.5)
    driver.save_screenshot("dump.png")

    png_data = driver.find_element(By.XPATH, CLOUD_IMAGE_XPATH).screenshot_as_png
    driver.refresh()

    return png_data


def retouch_cloud_image(png_data):
    RAINFALL_INTENSITY_LEVEL = [
        # NOTE: 白
        {"func": lambda h, s: (160 < h) & (h < 180) & (s < 20)},
        # NOTE: 薄水色
        {"func": lambda h, s: (140 < h) & (h < 150) & (90 < s) & (s < 100)},
        # NOTE: 水色
        {"func": lambda h, s: (145 < h) & (h < 155) & (210 < s) & (s < 230)},
        # NOTE: 青色
        {"func": lambda h, s: (155 < h) & (h < 165) & (230 < s)},
        # NOTE: 黄色
        {"func": lambda h, s: (35 < h) & (h < 45)},
        # NOTE: 橙色
        {"func": lambda h, s: (20 < h) & (h < 30)},
        # NOTE: 赤色
        {"func": lambda h, s: (0 < h) & (h < 8)},
        # NOTE: 紫色
        {"func": lambda h, s: (225 < h) & (h < 235) & (240 < s)},
    ]

    img_rgb = cv2.imdecode(
        np.asarray(bytearray(png_data), dtype=np.uint8), cv2.IMREAD_COLOR
    )

    img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    h, s, v = cv2.split(img_hsv)

    # NOTE: 降雨強度の色をグレースケール用に変換
    for i, level in enumerate(RAINFALL_INTENSITY_LEVEL):
        img_hsv[level["func"](h, s), 0] = 0
        img_hsv[level["func"](h, s), 1] = 80
        img_hsv[level["func"](h, s), 2] = 256 / 16 * (16 - i * 2)

    # NOTE: 白地図の色をやや明るめにする
    img_hsv[s < 30, 2] = np.clip(pow(v[(s < 30)], 1.35) * 0.3, 0, 255)

    return PIL.Image.fromarray(
        cv2.cvtColor(img_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB_FULL)
    )


def draw_equidistant_circle(img):
    draw = PIL.ImageDraw.Draw(img)
    x = img.size[0] / 2
    y = img.size[1] / 2

    size = 15
    draw.ellipse(
        (x - size / 2, y - size / 2, x + size / 2, y + size / 2),
        fill=(120, 120, 120),
        outline=(60, 60, 60),
        width=3,
    )
    # 5km
    size = 200
    draw.ellipse(
        (x - size / 2, y - size / 2, x + size / 2, y + size / 2),
        outline=(60, 60, 60),
        width=2,
    )


def draw_caption(img, title, face):
    draw_text(
        img,
        title,
        [10, 10],
        face["title"],
        "left",
        color="#000",
    )


def draw_rain_cloud_panel(panel_config, font_config):
    SUB_PANEL_CONFIG_LIST = [
        {"is_future": False, "title": "現在", "offset_x": 0},
        {
            "is_future": True,
            "title": "１時間後",
            "offset_x": int(config["RAIN_CLOUD"]["WIDTH"] / 2),
        },
    ]
    driver = create_driver()

    change_window_size(
        driver,
        config["RAIN_CLOUD"]["URL"],
        int(config["RAIN_CLOUD"]["WIDTH"] / 2),
        config["RAIN_CLOUD"]["HEIGHT"],
    )

    img = PIL.Image.new(
        "RGBA",
        (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        (255, 255, 255, 255),
    )
    face_map = get_face_map(font_config)

    sub_panel = []
    for sub_panel_config in SUB_PANEL_CONFIG_LIST:
        sub_img = retouch_cloud_image(
            fetch_cloud_image(
                driver,
                config["RAIN_CLOUD"]["URL"],
                int(config["RAIN_CLOUD"]["WIDTH"] / 2),
                config["RAIN_CLOUD"]["HEIGHT"],
                sub_panel_config["is_future"],
            )
        )
        draw_equidistant_circle(sub_img)
        draw_caption(sub_img, sub_panel_config["title"], face_map)
        img.paste(sub_img, (sub_panel_config["offset_x"], 0))

    driver.quit()

    return img.convert("L")


if __name__ == "__main__":
    import logger
    from config import load_config

    import logging

    logger.init("test")
    logging.info("Test")

    config = load_config()

    img = draw_rain_cloud_panel(config["RAIN_CLOUD"], config["FONT"])

    img.save("rain_cloud.png", "PNG")

    print("Finish.")

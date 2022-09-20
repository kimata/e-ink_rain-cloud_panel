#!/usr/bin/env python3
# - coding: utf-8 --
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import PIL.Image
import PIL.ImageDraw

import io
import cv2
import numpy as np
import time

from webdriver import create_driver
from pil_util import get_font, draw_text


WEEKLY_FORECAST_XPATH = '//table[@class="yjw_table"]'


def get_weekly_forecast_list(panel_config):
    driver = create_driver()
    wait = WebDriverWait(driver, 5)

    driver.get(panel_config["URL"])

    wait.until(EC.presence_of_element_located((By.XPATH, WEEKLY_FORECAST_XPATH)))

    TABLE_DEF = [
        {
            "name": "date",
            "xpath": "",
            "trans": lambda elem: elem.text.replace("\n", ""),
        },
        {
            "name": "weather",
            "xpath": "/img",
            "trans": lambda elem: [
                elem.get_attribute("alt"),
                elem.get_attribute("src").replace("size90", "size150"),
            ],
        },
        {
            "name": "temp",
            "xpath": "/small",
            "trans": lambda elem: list(map(int, elem.text.split("\n"))),
        },
        {"name": "prec", "xpath": "", "trans": lambda elem: int(elem.text)},
    ]

    forecast_list = []
    for col in range(2, 8):
        forecast = {}
        for row in range(1, 5):
            forecast[TABLE_DEF[row - 1]["name"]] = TABLE_DEF[row - 1]["trans"](
                driver.find_element(
                    By.XPATH,
                    (
                        '//div[@id="yjw_week"]/table//tr[{row}]/td[{col}]'
                        + TABLE_DEF[row - 1]["xpath"]
                    ).format(row=row, col=col),
                )
            )
        forecast_list.append(forecast)
    return forecast_list


def draw_weekly_forecast_panel(panel_config, font_config):
    forecast_list = get_weekly_forecast_list(panel_config)


def draw_weekly_forecast_panel2(panel_config, font_config):
    driver = create_driver()
    wait = WebDriverWait(driver, 5)

    driver.get(panel_config["URL"])

    wait.until(EC.presence_of_element_located((By.XPATH, WEEKLY_FORECAST_XPATH)))
    driver.execute_script(
        "return arguments[0].scrollIntoView(true)",
        driver.find_element(By.XPATH, WEEKLY_FORECAST_XPATH),
    )
    driver.execute_script(
        """
document.body.style.fontFamily = "A-OTF UD新ゴ Pr6N";
document.body.style.fontWeight = 500;
"""
    )
    wait.until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )

    img = PIL.Image.new(
        "RGBA",
        (panel_config["WIDTH"], panel_config["HEIGHT"]),
        (255, 255, 255, 255),
    )
    table_img = PIL.Image.open(
        io.BytesIO(
            driver.find_element(By.XPATH, WEEKLY_FORECAST_XPATH).screenshot_as_png
        )
    )

    img.paste(
        table_img,
        (
            int((img.size[0] - table_img.size[0]) / 2),
            int((img.size[1] - table_img.size[1]) / 2),
        ),
    )

    return img.convert("L")


if __name__ == "__main__":
    import logger
    from config import load_config

    import logging

    logger.init("test")
    logging.info("Test")

    config = load_config()

    img = draw_weekly_forecast_panel(config["WEEKLY_FORECAST"], config["FONT"])

    img.save("test_weekly_forecast_panel.png", "PNG")

    print("Finish.")

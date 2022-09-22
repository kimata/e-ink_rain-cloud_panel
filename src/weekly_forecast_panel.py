#!/usr/bin/env python3
# - coding: utf-8 --
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import PIL.Image
import PIL.ImageDraw

from urllib import request
from urllib.parse import urlparse
import math
import pathlib
import os
import io
import cv2
from cv2 import dnn_superres
import numpy as np
import time
import locale

from webdriver import create_driver
from pil_util import get_font, draw_text
import datetime

WEEKLY_FORECAST_XPATH = '//table[@class="yjw_table"]'


def get_face_map(font_config):
    return {
        "date": get_font(font_config, "EN_HEAVY", 80),
        "wday": get_font(font_config, "JP_REGULAR", 40),
        "weather": get_font(font_config, "JP_BOLD", 40),
        "temp": get_font(font_config, "EN_MEDIUM", 70),
    }


def get_image(info):
    tone = 32
    gamma = 0.24

    file_bytes = np.asarray(
        bytearray(request.urlopen(info["icon"]).read()), dtype=np.uint8
    )
    img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

    # NOTE: 透過部分を白で塗りつぶす
    img[img[..., -1] == 0] = [255, 255, 255, 0]
    img = img[:, :, :3]

    dump_path = str(
        pathlib.Path(
            os.path.dirname(__file__),
            "img",
            info["text"] + "_" + os.path.basename(urlparse(info["icon"]).path),
        )
    )

    PIL.Image.fromarray(img).save(dump_path)

    h, w = img.shape[:2]

    # NOTE: 一旦4倍の解像度に増やす
    sr = dnn_superres.DnnSuperResImpl_create()

    model_path = str(pathlib.Path(os.path.dirname(__file__), "data", "ESPCN_x4.pb"))

    sr.readModel(model_path)
    sr.setModel("espcn", 4)
    img = sr.upsample(img)

    # NOTE: 階調を削減
    tone_table = np.zeros((256, 1), dtype=np.uint8)
    for i in range(256):
        tone_table[i][0] = min(math.ceil(i / tone) * tone, 255)
    img = cv2.LUT(img, tone_table)

    # NOTE: ガンマ補正
    gamma_table = np.zeros((256, 1), dtype=np.uint8)
    for i in range(256):
        gamma_table[i][0] = 255 * (float(i) / 255) ** (1.0 / gamma)
    img = cv2.LUT(img, gamma_table)

    # NOTE: 最終的に欲しい解像度にする
    img = cv2.resize(img, (int(w * 1.6), int(h * 1.6)), interpolation=cv2.INTER_CUBIC)

    # NOTE: 白色を透明にする
    img = cv2.cvtColor(img, cv2.COLOR_RGB2RGBA)
    img[:, :, 3] = np.where(np.all(img == 255, axis=-1), 0, 255)

    return PIL.Image.fromarray(img).convert("LA")


def get_weekly_forecast_list(panel_config):
    driver = create_driver()
    wait = WebDriverWait(driver, 5)

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9), "JST"))

    driver.get(panel_config["URL"])

    wait.until(EC.presence_of_element_located((By.XPATH, WEEKLY_FORECAST_XPATH)))

    TABLE_DEF = [
        {
            "name": "date",
            "xpath": "",
            "trans": lambda elem: datetime.datetime.strptime(
                elem.text.split("(")[0].replace("\n", ""), "%m月%d日"
            ).replace(year=now.year),
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


def create(panel_config, font_config):
    forecast_list = get_weekly_forecast_list(panel_config)

    img = PIL.Image.new(
        "RGB",
        (panel_config["WIDTH"], panel_config["HEIGHT"]),
        (255, 255, 255),
    )
    step_x = panel_config["WIDTH"] / len(forecast_list)

    face = get_face_map(font_config)
    locale.setlocale(locale.LC_TIME, "ja_JP.UTF-8")

    for i, forecast in enumerate(forecast_list):
        icon_img = get_image(
            {"text": forecast["weather"][0], "icon": forecast["weather"][1]}
        )

        draw_text(
            img,
            forecast["date"].strftime("%d"),
            [int(step_x * (i + 0.5)), 10],
            face["date"],
            "center",
            color="#000",
        )
        draw_text(
            img,
            forecast["date"].strftime("(%a)"),
            [int(step_x * (i + 0.5)), 80],
            face["wday"],
            "center",
            color="#333",
        )
        img.paste(icon_img, (int((step_x * (i + 0.5)) - (icon_img.size[0] / 2)), 130))
        draw_text(
            img,
            forecast["weather"][0],
            [int(step_x * (i + 0.5)), 260],
            face["weather"],
            "center",
            color="#000",
        )
        draw_text(
            img,
            str(forecast["temp"][0]),
            [int(step_x * (i + 0.5)), 335],
            face["temp"],
            "center",
            color="#000",
        )
        draw_text(
            img,
            str(forecast["temp"][1]),
            [int(step_x * (i + 0.5)), 420],
            face["temp"],
            "center",
            color="#000",
        )

    return img


def create2(panel_config, font_config):
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

    img = create(config["WEEKLY_FORECAST"], config["FONT"])

    img.save("test_weekly_forecast_panel.png", "PNG")

    print("Finish.")

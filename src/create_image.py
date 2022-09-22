#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import textwrap
import PIL.Image
import logging

import logger

import weekly_forecast_panel
import rain_cloud_panel
from pil_util import get_font, draw_text

from config import load_config


def draw_panel(config, img):
    rain_cloud_img = rain_cloud_panel.create(config["RAIN_CLOUD"], config["FONT"])
    weekly_forecast_img = weekly_forecast_panel.create(
        config["WEEKLY_FORECAST"], config["FONT"]
    )

    img.paste(rain_cloud_img, (0, 0))
    img.paste(weekly_forecast_img, (0, config["RAIN_CLOUD"]["HEIGHT"]))


######################################################################
logger.init("panel.e-ink.rain")

logging.info("start to create image")

config = load_config()

img = PIL.Image.new(
    "RGBA",
    (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
    (255, 255, 255, 255),
)

try:
    draw_panel(config, img)
except:
    import traceback

    draw = PIL.ImageDraw.Draw(img)
    draw.rectangle(
        (0, 0, config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        fill=(255, 255, 255, 255),
    )

    draw_text(
        img,
        "ERROR",
        [10, 10],
        get_font(config["FONT"], "EN_BOLD", 160),
        "left",
        "#666",
    )

    draw_text(
        img,
        "\n".join(textwrap.wrap(traceback.format_exc(), 45)),
        [20, 200],
        get_font(config["FONT"], "EN_MEDIUM", 40),
        "left" "#333",
    )
    print(traceback.format_exc(), file=sys.stderr)

img.save(sys.stdout.buffer, "PNG")

exit(0)

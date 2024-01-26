import random
import re

import numpy as np
import pytesseract
import requests
from imageio.v2 import imread

from rightmove.enhancements import USER_AGENTS, logger


def download_img(url: str) -> np.ndarray:
    """
    Download an image from a given URL.

    Args:
        url (str): The URL of the image.

    Returns:
        np.ndarray: The downloaded image as a NumPy array.
    """
    r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)})

    if r.status_code != 200:
        logger.debug(f"Image download failed for URL {url}.")
        return None

    img = imread(r.content)

    return img


def extract_text(img: np.ndarray) -> str:
    """
    Extract text from an image using pytesseract.

    Args:
        img (np.ndarray): The image to extract text from.

    Returns:
        str: The extracted text.
    """

    text = pytesseract.image_to_string(img)
    return text


def extract_internal_area(text):
    """
    Extract the internal area from the text extracted from an image.

    Args:
        text (str): The text to extract the internal area from.

    Returns:
        dict: A dictionary with keys 'sqft' and 'sqm' and their corresponding values.
    """

    # Preprocessing
    cleaned_text = text.lower()
    sqm_out = None
    sqft_out = None

    # Text Analysis
    total_check = False
    for line in cleaned_text.split("\n"):
        sqft = None
        sqm = None

        for string in [
            "total",
            "internal area",
            "internal floor area",
            "approximate floor area",
            "approximate area",
        ]:
            if string in line:
                total_check = True
                break

        # Regular Expressions
        sqft_options = ["sq ft", "sqft", "sq. ft", "sq. ft.", "sq.ft.", "ft2", "ft^2"]
        sqft_pattern = re.compile(
            rf"(\d+(,\d{{3}})*\.\d+|\d+(,\d{{3}})*|\d+) ({'|'.join(sqft_options)})",
            re.IGNORECASE,
        )

        sqm_options = ["sq m", "sqm", "sq. m", "sq. m.", "sq.m.", "m2", "m^2"]
        sqm_pattern = re.compile(
            rf"(\d+(,\d{{3}})*\.\d+|\d+(,\d{{3}})*|\d+) ({'|'.join(sqm_options)})",
            re.IGNORECASE,
        )

        # Extracting data
        sqft_match = sqft_pattern.search(line)
        sqm_match = sqm_pattern.search(line)

        sqft = float(sqft_match.group(1).replace(",", "")) if sqft_match else None
        sqm = float(sqm_match.group(1).replace(",", "")) if sqm_match else None

        # Break loop if no data:
        if sqft is None and sqm is None:
            continue

        # Remove outliers:
        if sqft and sqft < 150:
            sqft = None
        if sqm and sqm < 14:
            sqm = None

        # Remove inconsistent conversions:
        if sqft and sqm:
            if abs((sqft / sqm) - 10.7639) > 1:
                continue

        # Convert sqm to sqft:
        if sqft is None and sqm:
            sqft = round(sqm * 10.7639, 0)

        if sqft and total_check:
            sqft_out = sqft
            sqm_out = sqm
            break

        if sqft:
            sqft_out = sqft
        if sqm:
            sqm_out = sqm

    return {"sqft": sqft_out, "sqm": sqm_out}

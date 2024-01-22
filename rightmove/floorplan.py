import logging
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import numpy as np
import pytesseract
import requests
from bs4 import BeautifulSoup
from imageio.v2 import imread
from tqdm import tqdm

from config.logging import logging_setup
from rightmove.database import get_floorplan_properties, insert_floorplans
from rightmove.models import PropertyFloorplan

logger = logging.getLogger(__name__)
logger = logging_setup(logger)

USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/54.0.2840.71 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/602.1.50 (KHTML,"
        " like Gecko) Version/10.0 Safari/602.1.50"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.11; rv:49.0) Gecko/20100101"
        " Firefox/49.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_0) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_0) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/54.0.2840.71 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/54.0.2840.71 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/602.2.14 (KHTML,"
        " like Gecko) Version/10.0.1 Safari/602.2.14"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12) AppleWebKit/602.1.50 (KHTML,"
        " like Gecko) Version/10.0 Safari/602.1.50"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/54.0.2840.71 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/54.0.2840.71 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:49.0) Gecko/20100101 Firefox/49.0",
    (
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like"
        " Gecko) Chrome/54.0.2840.71 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/54.0.2840.71 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:49.0) Gecko/20100101 Firefox/49.0",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0",
    (
        "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/53.0.2785.143 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/53.0.2785.143 Safari/537.36"
    ),
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:49.0) Gecko/20100101 Firefox/49.0",
]

FLOORPAN_REGEX = re.compile("_FLP_00_")


def get_floorplan_urls(property_id: int) -> List[str]:
    """
    Get a list of URLs for the floorplans of a given property ID.

    Args:
        property_id (int): The ID of the property.

    Returns:
        List[str]: A list of URLs of the floorplans.
    """
    url = f"https://www.rightmove.co.uk/properties/{property_id}#/"
    r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)})

    if r.status_code != 200:
        logger.debug(f"Floorplan download failed for property {property_id}.")
        return None

    soup = BeautifulSoup(r.content, "html.parser")

    floorplans = []
    for img in soup.find_all("img", attrs={"src": FLOORPAN_REGEX}):
        img = re.sub(r"(_\d{2}_\d{4})(.+)(.gif|.jpeg|.png)", r"\1\3", img["src"])
        floorplans.append(img)

    return floorplans


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


def get_floorplan(id: int) -> PropertyFloorplan:
    """
    Get the floorplan data of a given property ID.

    Args:
        id (int): The ID of the property.

    Returns:
        PropertyFloorplan: An instance of the PropertyFloorplan class.
    """

    urls = get_floorplan_urls(id)
    if urls:
        url = urls[0]
    else:
        return PropertyFloorplan(property_id=id)

    img = download_img(url)
    text = extract_text(img)
    area = extract_internal_area(text)

    return PropertyFloorplan(
        property_id=id,
        floorplan_url=url,
        area_sqft=area.get("sqft"),
        area_sqm=area.get("sqm"),
    )


def update_floorplans() -> None:
    """
    Updates the floorplan images in the database.
    """
    ids = get_floorplan_properties()
    progress = tqdm(
        total=len(ids),
        desc="Getting floorplans",
        bar_format="{desc:<20} {percentage:3.0f}%|{bar}| remaining: {remaining_s:.1f}",
    )

    futures = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for property_id in ids:
            futures[executor.submit(get_floorplan, property_id)] = property_id

        results = []
        for future in as_completed(futures):
            progress.update(1)
            results.append(future.result())

    insert_floorplans([x for x in results if x is not None])


if __name__ == "__main__":
    update_floorplans()

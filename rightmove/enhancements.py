import logging
import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from config.logging import logging_setup
from rightmove.database import get_enhancement_properties, insert_models
from rightmove.description import analyse_summary
from rightmove.floorplan import download_img, extract_text, extract_internal_area
from rightmove.models import PropertyFloorplan, PropertyDescription

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


def get_data(property_id: int) -> Dict:
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

    key_features = "\n".join(
        soup.find("ul", class_="_1uI3IvdF5sIuBtRIvKrreQ").stripped_strings
    )

    description = "\n".join(
        soup.find(
            "div", class_=["STw8udCxUaBUMfOOZu0iL", "kJR0bMoi8VLouNkBRKGww"]
        ).div.stripped_strings
    )

    summary = f"""## KEY FEATURES
    {key_features}
    
    ## DESCRIPTION
    {description}"""

    return {"floorplans": floorplans, "summary": summary}


def get_additional_data(id: int):
    """
    Get the floorplan data of a given property ID.

    Args:
        id (int): The ID of the property.

    Returns:
        PropertyFloorplan: An instance of the PropertyFloorplan class.
    """

    data = get_data(id)
    if not data:
        return None

    # Floorplan analysis:
    try:
        floorplan_url = data.get("floorplans")[0]
        img = download_img(floorplan_url)
        text = extract_text(img)
        area = extract_internal_area(text)
        floorplan = PropertyFloorplan(
            property_id=id,
            floorplan_url=floorplan_url,
            area_sqft=area.get("sqft"),
            area_sqm=area.get("sqm"),
        )
    except Exception:
        floorplan = PropertyFloorplan(property_id=id)

    # Description analysis:
    try:
        summary_text = data.get("summary")
        analysis = analyse_summary(summary_text)
        summary = PropertyDescription(
            property_id=id,
            summary=summary_text,
            garden=analysis.get("garden"),
        )
    except Exception:
        summary = PropertyDescription(property_id=id)

    return floorplan, summary


def update_enhanced_data() -> None:
    """
    Updates the floorplan images in the database.
    """
    ids = get_enhancement_properties()
    progress = tqdm(
        total=len(ids),
        desc="Getting floorplans",
        bar_format="{desc:<20} {percentage:3.0f}%|{bar}| remaining: {remaining_s:.1f}",
    )

    futures = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for property_id in ids:
            futures[executor.submit(get_additional_data, property_id)] = property_id

        results = []
        for future in as_completed(futures):
            progress.update(1)
            results.append(future.result())

    # Insert floorplans:
    insert_models(
        models=[x[0] for x in results if x is not None], table="property_floorplan"
    )

    # Insert descriptions:
    insert_models(
        models=[x[1] for x in results if x is not None], table="property_summary"
    )


if __name__ == "__main__":
    update_enhanced_data()

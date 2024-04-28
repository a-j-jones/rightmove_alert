import logging
import random
import re
from concurrent.futures import as_completed, ThreadPoolExecutor
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel
from tqdm import tqdm

from config.logging import logging_setup
from rightmove.database import get_enhancement_properties, insert_models
from rightmove.floorplan import download_img, extract_internal_area, extract_text
from rightmove.models import PropertyDescription, PropertyFloorplan
from rightmove.utils import USER_AGENTS

logger = logging.getLogger(__name__)
logger = logging_setup(logger)

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

    key_features_element = soup.find("ul", class_="_1uI3IvdF5sIuBtRIvKrreQ")
    if key_features_element:
        key_features = "\n".join(key_features_element.stripped_strings)
    else:
        key_features = ""

    description_element = soup.find("div", class_="_1a8kqJPMw6HOD9SDZq61E8")
    if description_element:
        description = "\n".join(description_element.stripped_strings)
    else:
        description = ""

    summary = ""
    if key_features:
        summary += f"## KEY FEATURES:\n{key_features}\n"
    if description:
        summary += f"## DESCRIPTION:\n{description}"

    return {"floorplans": floorplans, "summary": summary}


def get_additional_data(id: int) -> Tuple[BaseModel, BaseModel]:
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
    # try:
    #     summary_text = data.get("summary")
    #     if summary_text:
    #         analysis = analyse_summary(summary_text)
    #         summary = PropertyDescription(
    #             property_id=id,
    #             summary=summary_text,
    #             garden=analysis.get("garden"),
    #         )
    #     else:
    #         summary = PropertyDescription(property_id=id)
    # except Exception:
    summary = PropertyDescription(property_id=id)

    return floorplan, summary


def update_enhanced_data(ids: List = None) -> None:
    """
    Updates the floorplan images in the database.
    """
    if not ids:
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
    insert_models(models=[x[0] for x in results if x is not None], table="property_floorplan")

    # Insert descriptions:
    insert_models(models=[x[1] for x in results if x is not None], table="property_summary")


if __name__ == "__main__":
    update_enhanced_data()

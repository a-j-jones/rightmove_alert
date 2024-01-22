import json
import logging
from os import path
from pathlib import Path

import numba
import numpy as np
import pandas as pd
from numba import njit

from config.logging import logging_setup
from rightmove.database import (
    model_executemany,
    get_location_dataframe,
    get_database_connection,
)
from rightmove.models import PropertyLocationExcluded, TravelTimePrecise

# Setting up logger
logger = logging.getLogger(__name__)
logger = logging_setup(logger)


@njit()
def point_in_polygon(x: float | np.ndarray, y: float | np.ndarray, polygon: np.ndarray):
    """
    Check if a given point is inside a polygon

    Args:
        x (float): x-coordinate of the point
        y (float): y-coordinate of the point
        polygon (list): list of tuples representing the vertices of the polygon

    Returns:
        bool: True if the point is inside the polygon, False otherwise
    """
    n = len(polygon)
    inside = False
    p2x = 0.0
    p2y = 0.0
    xints = 0.0
    p1x, p1y = polygon[0]
    for i in numba.prange(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


@njit(parallel=True)
def points_in_polygon_parallel(points: np.ndarray, polygon: np.ndarray):
    """
    Check an array of points and return an array representing whether each point is inside the given polygon.

    Args:
        points (numpy.ndarray): array of points where each point is represented as a tuple of x and y coordinates
        polygon (list): list of tuples representing the vertices of the polygon

    Returns:
        numpy.ndarray: array of booleans representing whether each point is inside the polygon
    """
    D = np.empty(len(points), dtype=numba.boolean)
    for i in numba.prange(0, len(D)):
        D[i] = point_in_polygon(points[i, 0], points[i, 1], polygon)

    return D


def get_shape(filepath: Path):
    """
    Function to read a geojson file and return the coordinates of the polygon

    {
        "search_id": "Search 0",
        "shapes": [
            {
                "shell": [
                    {
                        "lat": 51.502888,
                        "lng": -0.025201356
                    }
                    ...
                ]
            }
        ]
    }

    Args:
        filepath (str): path to the geojson file

    Returns:
        list: list of dictionaries representing the shapes in the geojson file
    """
    with open(filepath) as f:
        data = json.load(f)

    return data["shapes"]


def update_locations():
    """
    Add time travel data for properties which have not been updated yet.
    """
    df = get_location_dataframe()

    if len(df) == 0:
        logger.info("No new properties found.")
        return

    logger.info(f"Updating {len(df)} properties...")

    points = df[["latitude", "longitude"]].values

    keep_cols = []
    parent_dir = Path(path.dirname(path.dirname(__file__)))

    # Loop through all of the travel time polygons:
    files = sorted(list(parent_dir.glob("shapes/sub_*.json")))
    for file in files:
        result = np.zeros(len(points), dtype=bool)
        for polygon_data in get_shape(file):
            polygon = pd.DataFrame(polygon_data["shell"]).values
            result = np.logical_or(result, points_in_polygon_parallel(points, polygon))
            for hole in polygon_data["holes"]:
                polygon = pd.DataFrame(hole).values
                result = np.logical_and(
                    result, ~points_in_polygon_parallel(points, polygon)
                )

        col = int(file.stem.replace("sub_", "").replace("m", ""))
        keep_cols.append(col)
        df[col] = result
        df[int(file.stem.replace("sub_", "").replace("m", ""))] = result

    # Loop through any excluded polygons and set the travel time to 999 if the property is in the polygon:
    files = sorted(list(parent_dir.glob("shapes/exclude_*.json")))
    exclude_location = np.zeros(len(points), dtype=bool)
    for file in files:
        for polygon_data in get_shape(file):
            polygon = pd.DataFrame(polygon_data["shell"]).values
            result = points_in_polygon_parallel(points, polygon)
            exclude_location = np.logical_or(exclude_location, result)

    df = df.melt(
        id_vars=["property_id"],
        value_vars=keep_cols,
        var_name="travel_time",
        value_name="in_polygon",
    )
    df["travel_time"] = df.travel_time.where(df.in_polygon, 999)
    df = df.groupby("property_id").agg({"travel_time": "min"}).reset_index()
    df = df.sort_values("property_id")
    df["excluded"] = exclude_location

    travel_time_values = []
    excluded_values = []
    for index, row in df.iterrows():
        travel_time_values.append(TravelTimePrecise(**row.to_dict()))
        excluded_values.append(PropertyLocationExcluded(**row.to_dict()))

    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            model_executemany(cursor, "travel_time_precise", travel_time_values)
            model_executemany(cursor, "property_location_excluded", excluded_values)
            conn.commit()


if __name__ == "__main__":
    update_locations()

import json

import numba
import numpy as np
import pandas as pd
from numba import njit
from sqlmodel import create_engine

from models import sqlite_url


@njit()
def point_in_polygon(x, y, polygon):
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
def points_in_polygon_parallel(points, polygon):
    """
    Executes the point_in_polygon
    """
    D = np.empty(len(points), dtype=numba.boolean)
    for i in numba.prange(0, len(D)):
        D[i] = point_in_polygon(points[i, 0], points[i, 1], polygon)

    return D


def get_shape(input_file):
    """
    Reads a geojson file and returns the coordinates of the polygon
    """
    with open(input_file) as f:
        data = json.load(f)

    return data["results"][0]["shapes"]


if __name__ == "__main__":
    engine = create_engine(sqlite_url, echo=False)
    sql = "SELECT * FROM alert_properties"
    df = pd.read_sql(sql, engine)
    points = df[["latitude", "longitude"]].values

    for file in ["35mins", "40mins", "45mins"]:
        result = np.zeros(len(points), dtype=bool)
        for polygon_data in get_shape(f"shapes/{file}.json"):
            polygon = pd.DataFrame(polygon_data["shell"]).values
            result = np.logical_or(result, points_in_polygon_parallel(points, polygon))

        df[file] = result

    df["gbp_per_sqft"] = df["price_amount"] / df["area"]
    df = df.sort_values("gbp_per_sqft")
    df[df["40mins"]].to_csv("40mins.csv", index=False)

import json

import numba
import numpy as np
import pandas as pd
from numba import njit
from sqlmodel import create_engine, Session
from os import path

from rightmove.models import sqlite_url, TravelTime


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
    parent_dir = path.dirname(path.dirname(__file__))
    filepath = path.join(parent_dir, "shapes", input_file)

    with open(filepath) as f:
        data = json.load(f)

    return data["results"][0]["shapes"]


def update_locations():
    engine = create_engine(sqlite_url, echo=False)
    sql = "SELECT * FROM alert_properties where not travel_reviewed"
    df = pd.read_sql(sql, engine)

    if len(df) == 0:
        return

    points = df[["latitude", "longitude"]].values

    for file in ["sub_35m", "sub_40m", "sub_45m"]:
        result = np.zeros(len(points), dtype=bool)
        for polygon_data in get_shape(f"{file}.json"):
            polygon = pd.DataFrame(polygon_data["shell"]).values
            result = np.logical_or(result, points_in_polygon_parallel(points, polygon))

        df[file] = result

    df = df[['property_id', 'sub_35m', 'sub_40m', 'sub_45m']]

    engine = create_engine(sqlite_url, echo=False)
    with Session(engine) as session:
        for index, row in df.iterrows():
            session.add(TravelTime(
                **row.to_dict()
            ))

        session.commit()


if __name__ == "__main__":
    update_locations()

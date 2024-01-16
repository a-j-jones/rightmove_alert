import asyncio
import datetime as dt

import pandas as pd
import psycopg2

from config import DATABASE_URI
from rightmove.api_wrapper import Rightmove
from rightmove.database import RightmoveDatabase, model_executemany, model_execute
from rightmove.models import ReviewDates, ReviewedProperties
from rightmove.search_algorithm import RightmoveSearcher


async def download_properties(channel):
    # Initialise objects
    database = RightmoveDatabase(DATABASE_URI)
    async with Rightmove(database=database) as rightmove_api:
        searcher = RightmoveSearcher(rightmove_api=rightmove_api, database=database)
        task = searcher.get_all_properties(
            region_search="LONDON",
            lat1=51.313447,
            lat2=51.720223,
            lon1=-0.5245971,
            lon2=0.36117554,
            channel=channel,
            exclude=["newHome", "sharedOwnership", "retirement"],
            include=["garden"],
            load_sql=True,
        )
        await task

        while True:
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            if len(asyncio.all_tasks()) == 1:
                break
            await asyncio.sleep(1)

        searcher.progress.close()


async def download_property_data(update, cutoff=None):
    # Initialise objects
    database = RightmoveDatabase(DATABASE_URI)

    async with Rightmove(database=database) as rightmove_api:
        searcher = RightmoveSearcher(rightmove_api=rightmove_api, database=database)

        task = searcher.get_all_property_data(update=update, update_cutoff=cutoff)
        await task
        while True:
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            if len(asyncio.all_tasks()) == 1:
                break
            await asyncio.sleep(1)


def mark_properties_reviewed():
    conn = psycopg2.connect(DATABASE_URI)
    conn.autocommit = False
    cursor = conn.cursor()

    cursor.execute(
        "select distinct property_id from alert_properties where property_reviewed = 0"
    )
    property_ids = cursor.fetchall()

    cursor.execute("select coalesce(max(email_id), 0) as last_id from reviewdates")
    review_id = cursor.fetchone()[0] + 1

    if len(property_ids) == 0:
        cursor.close()
        conn.close()
        return

    review_date = dt.datetime.now()
    review = ReviewDates(
        email_id=review_id,
        reviewed_date=review_date,
        str_date=review_date.strftime("%d-%b-%Y"),
    )
    model_execute(cursor, table_name="reviewdates", value=review)

    values = [
        ReviewedProperties(
            property_id=property_id[0], reviewed_date=review_date, emailed=False
        )
        for property_id in property_ids
    ]
    model_executemany(cursor, table_name="reviewedproperties", values=values)

    conn.commit()
    cursor.close()
    conn.close()


def get_properties(sql_filter):
    sql = f"""
    select * from alert_properties
    where 
        travel_time < 45
        and {sql_filter}
    """

    # Reading data from CSV
    df = pd.read_sql(sql, DATABASE_URI)

    properties = []
    for index, property in df.iterrows():
        travel_time = f"About {property.travel_time} minutes"

        data = {
            "link": f"https://www.rightmove.co.uk/properties/{property.property_id}",
            "title": property.property_description,
            "address": property.address,
            "status": f"Last update {property.last_update}",
            "description": property.summary,
            "price": f"£{property.price_amount:,.0f}",
            "travel_time": travel_time,
        }

        if type(property["images"]) == str:
            data["images"] = [
                {"url": img.strip().replace("171x162", "476x317"), "alt": "Property"}
                for img in property["images"].split(",")
            ][:2]
        else:
            data["images"] = []

        properties.append(data)

    return properties

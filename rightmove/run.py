import asyncio
import datetime as dt

import pandas as pd
from sqlmodel import create_engine, Session

from rightmove.api_wrapper import Rightmove
from rightmove.database import RightmoveDatabase
from rightmove.models import ReviewDates, ReviewedProperties, sqlite_url
from rightmove.search_algorithm import RightmoveSearcher


async def download_properties(channel):
    # Initialise objects
    database = RightmoveDatabase(sqlite_url)
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
    database = RightmoveDatabase(sqlite_url)

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
    engine = create_engine(sqlite_url, echo=False)
    property_ids = pd.read_sql(
        "SELECT property_id FROM alert_properties where not property_reviewed", engine
    )
    review_id = (
        pd.read_sql("select max(email_id) as last_id from reviewdates", engine).last_id[
            0
        ]
        + 1
    )

    with Session(engine) as session:
        review_date = dt.datetime.now()
        if len(property_ids) > 0:
            session.add(
                ReviewDates(
                    email_id=review_id,
                    reviewed_date=review_date,
                    str_date=review_date.strftime("%d-%b-%Y"),
                )
            )

        for id in property_ids.property_id.unique():
            session.add(
                ReviewedProperties(
                    property_id=id, reviewed_date=review_date, emailed=False
                )
            )

        session.commit()


def get_properties(sql_filter):
    sql = f"""
    select * from alert_properties
    where 
        travel_time < 45
        and {sql_filter}
    """

    # Reading data from CSV
    engine = create_engine(sqlite_url, echo=False)
    df = pd.read_sql(sql, engine)

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

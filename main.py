import asyncio

from rightmove.database import RightmoveDatabase
from rightmove.models import sqlite_url
from rightmove.api_wrapper import Rightmove
from rightmove.search_algorithm import RightmoveSearcher

from rightmove.geolocation import update_locations
from email_html.html_renderer import run_app


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
            load_sql=True
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

        task = searcher.get_all_property_data(
            update=update,
            update_cutoff=cutoff
        )
        await task
        while True:
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            if len(asyncio.all_tasks()) == 1:
                break
            await asyncio.sleep(1)


if __name__ == "__main__":

    # Download and update properties:
    asyncio.run(download_properties("BUY"))
    asyncio.run(download_property_data(update=False))

    # Check locations against travel time shape file:
    update_locations()

    # Display properties:
    run_app()
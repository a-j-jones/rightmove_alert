import asyncio

from rightmove.api_wrapper import Rightmove
from rightmove.database import RightmoveDatabase
from rightmove.search_algorithm import RightmoveSearcher


async def download_properties(channel):
    # Initialise objects
    async with RightmoveDatabase() as database:
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
            await searcher.rm.save_property_data(channel)


async def download_property_data(update, cutoff=None):
    # Initialise objects
    async with RightmoveDatabase() as database:
        async with Rightmove(database=database) as rightmove_api:
            searcher = RightmoveSearcher(rightmove_api=rightmove_api, database=database)

            task = searcher.get_all_property_data(update=update, update_cutoff=cutoff)
            await task
            while True:
                await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
                if len(asyncio.all_tasks()) == 1:
                    break
                await asyncio.sleep(1)

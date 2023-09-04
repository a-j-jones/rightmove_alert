import asyncio
import json

from rightmove.api_wrapper import Rightmove
from rightmove.database import RightmoveDatabase
from rightmove.models import sqlite_url
from rightmove.search_algorithm import RightmoveSearcher


async def main():
    # Initialise objects
    database = RightmoveDatabase(sqlite_url)
    async with Rightmove(database=database) as rightmove_api:
        searcher = RightmoveSearcher(rightmove_api=rightmove_api, database=database)
        await searcher.get_all_property_data()
        while True:
            await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
            if len(asyncio.all_tasks()) == 1:
                break
            await asyncio.sleep(1)


async def get_property(property_id, channel="BUY"):
    # Initialise objects
    database = RightmoveDatabase(sqlite_url)
    async with Rightmove(database=database) as rightmove_api:
        data = await rightmove_api.get_property_data(channel, [property_id])
        print(json.dumps(data, indent=4))


def get_ids():
    db = RightmoveDatabase(sqlite_url)
    for list in db.get_id_list(False):
        print(len(list), list)


def get_id_len():
    db = RightmoveDatabase(sqlite_url)
    length = db.get_id_len(False, "RENT")
    print(length)


if __name__ == "__main__":
    asyncio.run(get_property(127535897))

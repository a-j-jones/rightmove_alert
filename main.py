from rightmove import Rightmove
from database import RightmoveDatabase
from search_algorithm import RightmoveSearcher
import asyncio
import datetime as dt


async def download_properties(channel):
	# Initialise objects
	database = RightmoveDatabase("database.db")
	async with Rightmove(database=database) as rightmove_api:
		searcher = RightmoveSearcher(rightmove_api=rightmove_api, database=database)
		task = searcher.get_all_properties(
			region_search="LONDON",
			lat1=51.313447,
			lat2=51.720223,
			lon1=-0.5245971,
			lon2=0.36117554,
			channel=channel,
			exclude=["sharedOwnership", "retirement"],
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
	database = RightmoveDatabase("database.db")

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
	# cutoff = dt.datetime.strptime("2022-10-23 22:52:19.077663", '%Y-%m-%d %H:%M:%S.%f')
	# asyncio.run(download_properties("RENT"))
	# asyncio.run(download_properties("BUY"))
	asyncio.run(download_property_data(update=True))


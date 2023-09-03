import asyncio
import datetime as dt
from typing import Optional

import numpy as np
from tqdm.asyncio import tqdm

from database import RightmoveDatabase
from rightmove import Rightmove


class RightmoveSearcher:
	def __init__(self, rightmove_api: Rightmove, database: RightmoveDatabase):
		self.rm = rightmove_api
		self.database = database
		self.progress_format = "{desc:<20} {percentage:3.0f}%|{bar}| remaining: {remaining_s:.1f}"
		self.progress = None
		self.tasks = []

	async def get_all_properties(self,
								 region_search: str,
								 lat1: float,
								 lat2: float,
								 lon1: float,
								 lon2: float,
								 load_sql: bool = True,
								 channel: Optional[str] = "BUY",
								 index: Optional[int] = 0,
								 radius: Optional[int] = 5,
								 sstc: Optional[bool] = False,
								 exclude: Optional[list] = None,
								 include: Optional[list] = None) -> bool:
		"""
		Interacts with the rightmove.Rightmove API wrapper to perform a grid search of an entire area, finding
		every possible property on the website within given coordinates and region search term.

		It is not possible to search all of the UK in a single search term, so a broad term such as "LONDON" must
		be given and then corresponding coordinates provided.

		Required parameters
		:param region_search:   str     A search parameter for the region to be searched (e.g. LONDON)
		:param lat1:            float   1st Latitude value
		:param lat2:            float   2nd Latitude value
		:param lon1:            float   1st Longitude value
		:param lon2:            float   2nd Longitude value

		Optional parameters
		:param load_sql:        bool    (default=True)  Loads the downloaded properties into the Database
		:param channel:         str     (default=BUY)   RENT or BUY channel
		:param index:           int     (default=0)     Starting index of the properties
		:param radius:          int     (default=5)     Search radius in miles
		:param sstc:            bool    (default=False) Sold Subject to Contracts (include True or False)
        :param exclude:         list    (default=None)  List of options to exclude
                                                        Valid options are:
                                                            - newHome
                                                            - retirement
                                                            - sharedOwnership
		"""

		api_args = dict(locals())
		del api_args["self"]

		self.progress = tqdm(
			total=self.get_viewport_size(lat1, lat2, lon1, lon2),
			desc="Map search",
			bar_format=self.progress_format
		)
		await self._get_all_properties_recurse(**api_args)

	async def _get_all_properties_recurse(self,
										  region_search: str,
										  lat1: float,
										  lat2: float,
										  lon1: float,
										  lon2: float,
										  load_sql: bool = True,
										  channel: Optional[str] = "BUY",
										  index: Optional[int] = 0,
										  radius: Optional[int] = 5,
										  sstc: Optional[bool] = False,
										  exclude: Optional[list] = None,
										  include: Optional[list] = None) -> bool:
		"""
		See documentation for get_all_properties()
		"""

		# Passes the arguments to the Rightmove API.
		api_args = dict(locals())
		del api_args["self"]

		data = await self.rm.get_properties(**api_args)
		len_properties = len(data["properties"])
		# print(f"Found {len_properties} properties")
		if len_properties < 400:
			self.progress.update(self.get_viewport_size(lat1, lat2, lon1, lon2))
			return True

		for viewport in self.get_new_viewports(lat1, lat2, lon1, lon2):
			api_args.update(viewport)
			# print(f"Running code for {viewport}")
			self.tasks.append(asyncio.create_task(self._get_all_properties_recurse(**api_args)))

	async def get_all_property_data(self, update: bool = False, update_cutoff: dt.datetime = None) -> None:
		"""
		Gets all property data for both RENT/BUY channels and uploads to the Database.
		:param update:          bool            If True the function will look to update data for already held
												properties.
		:param update_cutoff:   dt.datetime     If update=True then a cutoff for last update can be used.
		"""

		for channel in ["RENT", "BUY"]:
			total = self.database.get_id_len(update, channel=channel, update_cutoff=update_cutoff)
			self.progress = tqdm(
				total=total,
				desc=f"Downloading {channel}",
				bar_format=self.progress_format
			)
			for ids in self.database.get_id_list(update, channel=channel, update_cutoff=update_cutoff):
				await self.rm.get_property_data(channel=channel, ids=ids, progress=self.progress)
			self.progress.close()

	@staticmethod
	def get_viewport_size(lat1: float,
						  lat2: float,
						  lon1: float,
						  lon2: float) -> float:
		"""
		Takes the viewport parameters (two sets of longitude and latitude) and returns the size of the rectangle
		:param lat1:            float   1st Latitude value
		:param lat2:            float   2nd Latitude value
		:param lon1:            float   1st Longitude value
		:param lon2:            float   2nd Longitude value
		:return:                float   Size of rectangle
		"""

		a = abs(lat1 - lat2)
		b = abs(lon1 - lon2)
		return a * b

	@staticmethod
	def get_new_viewports(lat1: float,
						  lat2: float,
						  lon1: float,
						  lon2: float) -> list[dict, dict]:
		"""
		Takes a viewport and divides it into two equal viewports which can then be used to narrow the search
		for properties.

		The function will divide the viewport by the longest dimension (in order to return the most square viewport)

		:param lat1:            float   1st Latitude value
		:param lat2:            float   2nd Latitude value
		:param lon1:            float   1st Longitude value
		:param lon2:            float   2nd Longitude value
		:return:                List of viewports
		"""

		p1 = (lat1, lon1)
		p2 = (lat2, lon2)
		viewport = {
			"lat1": p1[0],
			"lat2": p2[0],
			"lon1": p1[1],
			"lon2": p2[1]
		}

		# If 1st position difference is bigger than 0th position then 1, else 0:
		position_type = {0: "lat", 1: "lon"}
		position_int = int(np.absolute(p1[1] - p2[1]) > np.absolute(p1[0] - p2[0]))
		position = position_type[position_int]
		midpoint = (p1[position_int] + p2[position_int]) / 2

		viewports = []
		for i in range(2):
			new_coords = viewport.copy()
			new_coords[f"{position}{i + 1}"] = midpoint
			viewports.append(new_coords)

		return viewports

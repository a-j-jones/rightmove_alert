from functools import lru_cache
from json import JSONDecodeError
from textwrap import wrap
from typing import Optional

import httpx
import requests
from tqdm.asyncio import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


class Rightmove:
    def __init__(self, database):
        self.database = database

    async def __aenter__(self):
        """
        Asynchronous enter function which assigns the async httpx client
        """
        self.client = httpx.AsyncClient()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Asynchronous exit function which closes the async httpx client
        """
        await self.client.aclose()

    @lru_cache(maxsize=10)
    def get_region(self, region_search: str) -> str:
        """
        Gets the Rightmove region code for a given search term.

        :param region_search:   String to be searched (e.g. LONDON)
        :return:                Region code to use in map searches.
        """
        region_search = region_search.upper()
        url = f'https://www.rightmove.co.uk/typeAhead/uknostreet/{"/".join(wrap(region_search, 2))}/'
        r = requests.get(url, headers=HEADERS)
        region_data = r.json()

        return region_data["typeAheadLocations"][0]["locationIdentifier"]

    async def get_properties(
        self,
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
        include: Optional[list] = None,
    ) -> dict:
        """
        Sends a request to the Rightmove servers to get the Property IDs which appear within the given
        map coordinates.

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

        :return:                Dictionary object containing Property IDs
        """

        # Parameter checks:
        if type(region_search) != str:
            raise ValueError(
                f"Expected string value for region_search, got: {region_search}"
            )

        for parameter, value in {
            "lat1": lat1,
            "lat2": lat2,
            "lon1": lon1,
            "lon2": lon2,
        }.items():
            if type(value) != float:
                raise ValueError(f"Expected float value for {parameter}, got: {value}")

        if type(channel) != str or channel.upper() not in ["BUY", "RENT"]:
            raise ValueError(
                f"Expected string value of either 'BUY'/'RENT' for channel, got: {channel}"
            )

        if type(index) != int or index < 0:
            raise ValueError(f"Expected positive integer value for index, got: {index}")

        if type(radius) != int or radius < 0 or radius > 200:
            raise ValueError(
                f"Expected integer value between 0-200 for radius, got: {radius}"
            )

        if type(sstc) != bool:
            raise ValueError(f"Expected boolean value for sstc, got: {sstc}")

        # Create extra parameters:
        region = self.get_region(region_search)

        # Create params dictionary:
        params = {
            "locationIdentifier": region,
            "numberOfPropertiesPerPage": "499",
            "radius": f"{radius:.1f}",
            "sortType": "2",
            "index": str(index),
            "includeSSTC": str(sstc).lower(),
            "viewType": "MAP",
            "channel": channel.upper(),
            "areaSizeUnit": "sqft",
            "currencyCode": "GBP",
            "viewport": f"{lon1:.6f},{lon2:.6f},{lat1:.6f},{lat2:.6f}",
            "isFetching": "false",
        }

        if exclude:
            for item in exclude:
                valid_exclusions = ["newHome", "retirement", "sharedOwnership"]
                if item not in valid_exclusions:
                    raise ValueError(
                        f"Valid options for exclude are {valid_exclusions}, got: {item}"
                    )
            params["dontShow"] = ",".join(exclude)

        if include:
            valid_inclusions = [
                "garden",
                "parking",
                "newHome",
                "retirement",
                "sharedOwnership",
                "auction",
            ]
            for item in include:
                if item not in valid_inclusions:
                    raise ValueError(
                        f"Valid options for include are {valid_inclusions}, got: {item}"
                    )

            params["dontShow"] = ",".join(include)

        r = await self.client.get(
            "https://www.rightmove.co.uk/api/_mapSearch", params=params, headers=HEADERS
        )
        data = r.json()

        if load_sql:
            self.database.load_map_properties(data, channel=channel)

        return r.json()

    async def get_property_data(
        self, channel: str, ids: list[int], progress: tqdm = None
    ) -> dict:
        """
        Sends a request to the Rightmove API to get property data from each Property ID given.
        :param channel:     str RENT or BUY channel
        :param ids:         List of integer Rightmove Property IDs
        :param progress:    Optionally add progress bar object.
        :return:            JSON response from the Rightmove API
        """

        if type(channel) != str or channel.upper() not in ["BUY", "RENT"]:
            raise ValueError(
                f"Expected string value of either 'BUY'/'RENT' for channel, got: {channel}"
            )

        params = {"channel": channel.upper(), "propertyIds": ids, "viewType": "MAP"}
        r = await self.client.get(
            "https://www.rightmove.co.uk/api/_searchByIds",
            params=params,
            headers=HEADERS,
        )

        try:
            data = r.json()["properties"]
            self.database.load_property_data(data, ids)
        except JSONDecodeError:
            data = None

        if progress is not None:
            progress.update(len(ids))

        return data

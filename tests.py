import asyncio

from rightmove.api_wrapper import Rightmove
from rightmove.database import RightmoveDatabase
from rightmove.models import database_uri


async def test_get_region():
    database = RightmoveDatabase(database_uri)
    async with Rightmove(database) as rightmove:
        region = rightmove.get_region("LONDON")
        assert region == "REGION^87490"


async def test_get_properties():
    database = RightmoveDatabase(database_uri)
    async with Rightmove(database) as rightmove:
        properties = await rightmove.get_properties(
            region_search="LONDON",
            load_sql=False,
            lat1=51.313447,
            lat2=51.720223,
            lon1=-0.5245971,
            lon2=0.36117554,
            channel="BUY",
        )
        assert len(properties["properties"]) > 100


async def test_get_property_data():
    database = RightmoveDatabase(database_uri)
    async with Rightmove(database) as rightmove:
        property_data = await rightmove.get_property_data("BUY", [143206301])
        assert len(property_data) == 1


asyncio.run(test_get_region())
asyncio.run(test_get_properties())
asyncio.run(test_get_property_data())

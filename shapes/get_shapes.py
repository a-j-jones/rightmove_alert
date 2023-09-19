import asyncio
import datetime as dt
import json
from typing import Tuple

from traveltimepy import Coordinates, PublicTransport, TravelTimeSdk
from traveltimepy.dto.responses.time_map import TimeMapResult

LAT = 51.5038879
LON = -0.0182073
ARRIVAL_TIME = dt.datetime(2023, 9, 25, 7, 30, 0)

sdk = TravelTimeSdk("4173bea0", "b256925da6ea61e020bea32f8753db0f")


async def get_results(minutes: int) -> Tuple[int, TimeMapResult]:
    """
    This function returns the results of a time map request.
    """
    seconds = minutes * 60
    results = await sdk.time_map_async(
        coordinates=[Coordinates(lat=LAT, lng=LON)],
        departure_time=ARRIVAL_TIME,
        travel_time=seconds,
        transportation=PublicTransport(type="public_transport")
    )
    return minutes, results[0]


async def main():
    """
    This example shows how to use the SDK asynchronously.
    """

    results = await asyncio.gather(*[get_results(m) for m in range(10, 51, 1)])

    for minutes, result in results:
        with open(f"sub_{minutes}m.json", "w") as f:
            data = json.loads(result.json())
            json.dump(data, f, indent=4)


asyncio.run(main())

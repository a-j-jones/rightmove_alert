import datetime as dt
from typing import AsyncIterable, List, Set

import asyncpg
import pandas as pd
from asyncpg.pool import Pool
from pydantic import BaseModel

from config import DATABASE_URI
from rightmove.database import parse_added_or_reduced, parse_area
from rightmove.models import PropertyData


async def get_database_pool() -> Pool:
    return await asyncpg.create_pool(DATABASE_URI, min_size=50, max_size=50)


async def async_model_executemany(conn, table_name: str, values: List[BaseModel]):
    """
    Insert a list of pydantic models into a database table using executemany.

    Args:
        conn: The database connection.
        table_name (str): The name of the table in the database.
        values (List[BaseModel]): The list of pydantic models to be inserted into the database.
    """
    if len(values) == 0:
        return

    # Get the model fields
    model_field_names = [field for field in values[0].model_fields]

    # Construct the insert query
    placeholders = ",".join([f"${i + 1}" for i in range(len(model_field_names))])
    insert_query = f"""
        INSERT INTO {table_name} ({','.join(model_field_names)})
        VALUES ({placeholders})
    """

    # Insert the values using executemany
    await conn.executemany(insert_query, [tuple(model.model_dump().values()) for model in values])


async def insert_property_images(conn, property_images):
    """
    Insert property images into the database using executemany.

    Args:
        cursor: The database cursor.
        property_images: The property images to be inserted into the database.
    """

    # Insert property images into the database using executemany
    insert_query = """
        INSERT INTO property_images (property_id, image_url, image_caption)
        VALUES ($1, $2, $3)
        ON CONFLICT (property_id, image_url) DO NOTHING
    """
    await conn.executemany(insert_query, property_images)


class RightmoveDatabase:
    def __init__(self):
        return

    async def __aenter__(self):
        self.pool: Pool = await get_database_pool()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.pool.close()

    async def _close_missing_properties(self, missing_ids: Set[int]) -> None:
        """
        Closes the validto variable for properties which are no longer on the Rightmove website.

        Args:
            missing_ids (Set[int]): A set of IDs for the properties which are no longer on the Rightmove website.
        """
        async with self.pool.acquire() as conn:
            current_time: dt.datetime = dt.datetime.now()
            await conn.execute(f"""
                UPDATE property_data
                SET property_validto = '{current_time}'
                WHERE property_id IN ({','.join([str(id) for id in missing_ids])})
            """)

    async def get_id_len(self, update, channel, update_cutoff=None):
        """
        Returns the number of property IDs that would be returned in the get_id_list() function.

        Args:
            update (bool): If True then the list will not filter for only those properties with no existing data.
            update_cutoff (dt.datetime): If update=True then a cutoff for last update can be used.
            channel (str): The channel which should be searched (RENT/BUY).

        Returns:
            int: Number of properties which would be in the list.
        """

        async with self.pool.acquire() as conn:
            current_time = dt.datetime.now()
            sql = f"""
                    SELECT COUNT(DISTINCT pl.property_id)
                    FROM property_location pl
                    LEFT JOIN property_data pd ON pl.property_id = pd.property_id
                    WHERE pl.property_channel = '{channel}'
                """
            if update:
                if update_cutoff:
                    sql += f"""
                                    AND (
                                        (pd.last_update < '{update_cutoff}' OR pd.last_update IS NULL)
                                        AND pd.property_validto >= '{current_time}'
                                        OR pd.property_id IS NULL
                                    )
                                """
            else:
                sql += "AND pd.property_id IS NULL"

            result = await conn.fetchrow(sql)

            return result[0]

    async def get_id_list(self, update: bool, channel: str, update_cutoff=None) -> AsyncIterable[List[int]]:
        """
        Generator for a list of IDs which can be used to search the Rightmove API, this list will be a
        maximum size of 25, and the generator will stop once all IDs have been yielded.

        Args:
            update (bool): If True then the list will not filter for only those properties with no existing data.
            update_cutoff (dt.datetime): If update=True then a cutoff for last update can be used.
            channel (str): The channel which should be searched (RENT/BUY).

        Returns:
            List[List[int]]: A list of Property ID integers.
        """

        async with self.pool.acquire() as conn:
            current_time = dt.datetime.now()

            sql = f"""
                SELECT pl.property_id
                FROM property_location pl
                LEFT JOIN property_data pd ON pl.property_id = pd.property_id
                WHERE pl.property_channel = '{channel}'
            """

            if update:
                if update_cutoff:
                    sql += f"""
                        AND (
                            (pd.last_update < '{update_cutoff}' OR pd.last_update IS NULL)
                            AND pd.property_validto >= '{current_time}'
                            OR pd.property_id IS NULL
                        )
                    """

            else:
                sql += "AND pd.property_id IS NULL"

            ids = []
            results_raw = await conn.fetch(sql)
            results = set([x[0] for x in results_raw])

        for result in results:
            ids.append(result)
            if len(ids) == 25:
                yield ids
                ids = []
        if len(ids) > 0:
            yield ids

    async def load_map_properties(self, properties: dict, channel: str) -> None:
        """
        Loads the data obtained from the Rightmove API into the database.
        :param properties:      Dictionary      JSON response from the Rightmove API.
        :param channel          String          The channel which searched for in the API.
        """
        async with self.pool.acquire() as conn:
            current_time = dt.datetime.now()
            channel = channel.upper()

            # Check for existing IDs in the database:
            if len(properties) == 0:
                return

            await conn.execute(f"""
                SELECT property_id 
                FROM property_location 
                WHERE property_id IN ({','.join([str(p) for p in properties.keys()])})""")

            ids_raw = await conn.fetch()
            existing_ids: set = {r[0] for r in ids_raw}

            insert_values = []
            for property_data in properties.values():
                if property_data["id"] in existing_ids:
                    continue

                insert_values.append((
                    property_data["id"],
                    current_time,
                    channel,
                    property_data["location"]["latitude"],
                    property_data["location"]["longitude"],
                ))

            if len(insert_values) > 0:
                sql = """
                    INSERT INTO property_location (
                        property_id,
                        property_asatdt,
                        property_channel,
                        property_latitude,
                        property_longitude
                    ) VALUES ($1, $2, $3, $4, $5)
                    """
                await conn.executemany(sql, insert_values)

    async def load_property_data(self, data: dict, ids: list[int]) -> None:

        async with self.pool.acquire() as conn:
            try:
                # Retrieve existing property IDs from the database
                ids_raw = await conn.fetch("SELECT property_id FROM property_data")
                existing_ids = {row["property_id"] for row in ids_raw}

                # Set validto for properties which are no longer on the Rightmove website:
                missing_ids = set(ids) - existing_ids
                if missing_ids:
                    await self._close_missing_properties(missing_ids)

                current_time = dt.datetime.now()

                for prop in data:
                    property_id = prop["id"]

                    # Check for an existing record which is currently valid:
                    existing_record = await conn.fetchrow(
                        """
                        SELECT * FROM property_data
                        WHERE property_id = $1 AND property_validto >= $2
                        """,
                        property_id,
                        current_time,
                    )

                    # Parse the Area of the property:
                    area_str = prop.get("displaySize")
                    area = parse_area(area_str)

                    # Get the 'display update date':
                    added_or_reduced = parse_added_or_reduced(prop.get("addedOrReduced"))

                    # Construct the property data dictionary
                    property_data = PropertyData(
                        property_id=property_id,
                        property_validfrom=current_time,
                        bedrooms=prop["bedrooms"],
                        bathrooms=prop.get("bathrooms"),
                        area=area,
                        summary=prop.get("summary"),
                        address=prop["displayAddress"],
                        property_subtype=prop["propertySubType"],
                        property_description=prop["propertyTypeFullDescription"],
                        premium_listing=prop["premiumListing"],
                        price_amount=prop["price"]["amount"],
                        price_frequency=prop["price"]["frequency"],
                        price_qualifier=prop["price"]["displayPrices"][0].get("displayPriceQualifier"),
                        lettings_agent=prop["customer"]["brandTradingName"],
                        lettings_agent_branch=prop["customer"]["branchName"],
                        development=prop["development"],
                        commercial=prop["commercial"],
                        enhanced_listing=prop["enhancedListing"],
                        students=prop["students"],
                        auction=prop["auction"],
                        last_update=current_time,
                        first_visible=pd.to_datetime(prop["firstVisibleDate"]).tz_localize(None),
                        last_displayed_update=added_or_reduced,
                    )

                    insert_list = []
                    # Check for changes in property data
                    if existing_record and self.has_changes(existing_record, property_data):
                        # Mark the existing record as no longer valid
                        await conn.execute(
                            """
                            UPDATE property_data
                            SET property_validto = $1
                            WHERE property_id = $2 AND property_validto >= $3
                            """,
                            current_time,
                            property_id,
                            current_time,
                        )
                        # Insert a new record with updated data
                        insert_list.append(property_data)
                    elif not existing_record:
                        # Insert a new record if no existing record is found
                        insert_list.append(property_data)

                    if insert_list:
                        await async_model_executemany(conn, "property_data", insert_list)

                    # Insert property images using executemany
                    property_images = [
                        (property_id, img_data["srcUrl"], img_data["caption"])
                        for img_data in prop["propertyImages"]["images"]
                    ]
                    if property_images:
                        await insert_property_images(conn, property_images)

            except Exception as e:
                # Handle exceptions and log if needed
                print(f"Error: {e}")

    def has_changes(self, existing_record, data):
        """
        Check if there are changes between the existing record and new data.

        Parameters:
        - existing_record: Dictionary representing the existing record in the database.
        - new_data: Dictionary representing the new data to be compared.

        Returns:
        - True if there are changes, False otherwise.
        """
        new_data = data.model_dump()
        for key, value in new_data.items():
            if key in ["property_validfrom", "first_visible", "last_update"]:
                continue  # Skip these keys as they are not considered for changes

            existing_value = existing_record.get(key)
            if existing_value != value:
                return True  # Changes found

        return False  # No changes

import datetime as dt
import re
from typing import List, Set

import pandas as pd
import psycopg2
from sqlmodel import create_engine, select, Session

from rightmove.models import PropertyData, PropertyImages


class RightmoveDatabase:
    def __init__(self, sqlite_url):
        self.engine = create_engine(sqlite_url, echo=False)
        self.conn = psycopg2.connect(sqlite_url)

    def _close_missing_properties(self, missing_ids: Set[int]) -> None:
        """
        Closes the validto variable for properties which are no longer on the Rightmove website.
        :param ids:     List            A list of expected IDs which were sent in the API request.
        """
        cursor = self.conn.cursor()
        current_time = dt.datetime.now()

        cursor.execute(
            f"""
            UPDATE propertydata
            SET property_validto = '{current_time}'
            WHERE property_id IN ({','.join([str(id) for id in missing_ids])})
        """
        )

    def get_id_len(self, update, channel, update_cutoff=None):
        """
        Will return the number of property IDs that would be returned in the get_id_list() function.

        :param update:      bool        If True then the list will not filter for only those properties
                                        with no existing data.
        :param update_cutoff:   dt.datetime     If update=True then a cutoff for last update can be used.
        :param channel:     string      The channel which should be searched (RENT/BUY)
        :return:            int         Number of properties which would be in the list.
        """
        with Session(self.engine) as session:
            current_time = dt.datetime.now()
            sql = f"""
                    SELECT COUNT(DISTINCT pl.property_id)
                    FROM propertylocation pl
                    LEFT JOIN propertydata pd ON pl.property_id = pd.property_id
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

            results = session.exec(sql)
            return results.first()[0]

    def get_id_list(self, update: bool, channel: str, update_cutoff=None) -> List[int]:
        """
        Generator for a list of IDs which can be used to search the Rightmove API, this list will be a
        maximum size of 25, and the generator will stop once all IDs have been yielded.

        :param update:      bool        If True then the list will not filter for only those properties
                                        with no existing data.
        :param update_cutoff:   dt.datetime     If update=True then a cutoff for last update can be used.
        :param channel:     string      The channel which should be searched (RENT/BUY)
        :return:            list        A list of Property ID integers.
        """
        with Session(self.engine) as session:
            current_time = dt.datetime.now()

            sql = f"""
                SELECT pl.property_id
                FROM propertylocation pl
                LEFT JOIN propertydata pd ON pl.property_id = pd.property_id
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

            results = session.exec(sql)
            ids = []
            for result in results.unique():
                ids.append(result[0])
                if len(ids) == 25:
                    yield ids
                    ids = []
            if len(ids) > 0:
                yield ids

    def load_map_properties(self, data: dict, channel: str) -> None:
        """
        Loads the data obtained from the Rightmove API into the database.
        :param data:    Dictionary      JSON response from the Rightmove API.
        :param channel  String          The channel which searched for in the API.
        """
        cursor = self.conn.cursor()

        current_time = dt.datetime.now()
        channel = channel.upper()
        properties = data["properties"]

        # Check for existing IDs in the database:
        ids = [p["id"] for p in properties]
        if len(ids) == 0:
            cursor.close()
            return

        cursor.execute(
            f"""
            SELECT property_id 
            FROM propertylocation 
            WHERE property_id IN ({','.join([str(p['id']) for p in properties])})"""
        )
        existing_ids = [r[0] for r in cursor.fetchall()]

        insert_values = []
        for property_data in properties:
            if property_data["id"] in existing_ids:
                continue

            insert_values.append(
                (
                    property_data["id"],
                    current_time,
                    channel,
                    property_data["location"]["latitude"],
                    property_data["location"]["longitude"],
                )
            )

        if len(insert_values) > 0:
            cursor.executemany(
                """
                INSERT INTO propertylocation (
                    property_id,
                    property_asatdt,
                    property_channel,
                    property_latitude,
                    property_longitude
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                insert_values,
            )
            self.conn.commit()
            cursor.close()

    def load_property_data(self, data: dict, ids: list[int]) -> None:
        """
        Loads the data obtained from the Rightmove API into the database.
        :param data:    Dictionary      JSON response from the Rightmove API.
        :param ids:     List            A list of expected IDs which were sent in the API request.
        """
        with Session(self.engine) as session:
            found_ids = set([p["id"] for p in data])
            searched_ids = set(ids)

            # Set validto for properties which are no longer on the Rightmove website:
            missing_ids = searched_ids - found_ids
            if len(missing_ids) > 0:
                self._close_missing_properties(missing_ids)

            # Loop through each property which was returned by the request:
            for prop in data:
                # Check for an existing record which is currently valid:
                current_time = dt.datetime.now()
                statement = (
                    select(PropertyData)
                    .where(PropertyData.property_id == prop["id"])
                    .where(PropertyData.property_validto >= dt.datetime.now())
                )
                results = session.exec(statement)
                existing_record = results.first()

                # Parse the Area of the property:
                area_str = prop.get("displaySize")
                if "sq" in area_str:
                    area = float(
                        re.match(r"\d{1,3}(,\d{3})*(\.\d+)?", area_str)
                        .group(0)
                        .replace(",", "")
                    )
                else:
                    area = None

                # Get the 'display update date':
                try:
                    added_or_reduced = pd.to_datetime(
                        prop.get("addedOrReduced").split(" ")[-1], dayfirst=True
                    )
                    if str(added_or_reduced) == "NaT":
                        added_or_reduced = None
                except Exception:
                    added_or_reduced = None

                p = PropertyData(
                    property_id=prop["id"],
                    property_validfrom=current_time,
                    bedrooms=prop["bedrooms"],
                    bathrooms=prop.get("bathrooms"),
                    area=area,
                    summary=prop["summary"],
                    address=prop["displayAddress"],
                    property_subtype=prop["propertySubType"],
                    property_description=prop["propertyTypeFullDescription"],
                    premium_listing=prop["premiumListing"],
                    price_amount=prop["price"]["amount"],
                    price_frequency=prop["price"]["frequency"],
                    price_qualifier=prop["price"]["displayPrices"][0].get(
                        "displayPriceQualifier"
                    ),
                    lettings_agent=prop["customer"]["brandTradingName"],
                    lettings_agent_branch=prop["customer"]["branchName"],
                    development=prop["development"],
                    commercial=prop["commercial"],
                    enhanced_listing=prop["enhancedListing"],
                    students=prop["students"],
                    auction=prop["auction"],
                    last_update=current_time,
                    first_visible=pd.to_datetime(prop["firstVisibleDate"]),
                    last_displayed_update=added_or_reduced,
                )

                # Otherwise we need to check if there are any changes to the data, if so we will mark the latest
                # record as no longer valid, and create a new record which is valid from the current moment.
                for img_data in prop["propertyImages"]["images"]:
                    property_id = prop["id"]
                    image_url = img_data["srcUrl"]
                    statement = (
                        select(PropertyImages)
                        .where(PropertyImages.property_id == property_id)
                        .where(PropertyImages.image_url == image_url)
                    )
                    results = session.exec(statement)
                    existing_image = results.first()

                    if not existing_image:
                        img = PropertyImages(
                            property_id=property_id,
                            image_caption=img_data["caption"],
                            image_url=image_url,
                        )
                        session.add(img)

                # If an existing record was not found we can add it the DB transaction and move to the next
                # property.
                lookup = p.dict()
                if not existing_record:
                    session.add(p)
                    continue

                difference = False
                for key, value in existing_record.dict().items():
                    if key in ["property_validfrom", "first_visible", "last_update"]:
                        continue
                    elif lookup.get(key) != value:
                        difference = True
                        break

                if difference:
                    session.add(p)
                    session.commit()
                    existing_record.property_validto = current_time
                else:
                    existing_record.last_update = current_time

                session.add(existing_record)
                session.commit()

            session.commit()

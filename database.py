import datetime as dt
from typing import List

import pandas as pd
from sqlmodel import create_engine, Session, select, func, distinct, or_

from models import Property_Location, Property_Data


class RightmoveDatabase:
    def __init__(self, sqlite_file_name):
        self.sqlite_file_name = sqlite_file_name
        self.sqlite_url = f"sqlite:///{self.sqlite_file_name}"
        self.engine = create_engine(self.sqlite_url, echo=False)

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
            statement = (select(func.count(distinct(Property_Location.property_id))).join(Property_Data, isouter=True)
                         .where(Property_Location.property_channel == channel))
            if update:
                if update_cutoff:
                    statement = (statement
                                 .where(
                        or_(Property_Data.last_update < update_cutoff, Property_Data.last_update == None))
                                 .where(Property_Data.property_validto >= current_time)
                                 )
            else:
                statement = statement.where(Property_Data.property_id == None)

            results = session.exec(statement)
            return results.first()

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
            statement = (select(Property_Location.property_id).join(Property_Data, isouter=True)
                         .where(Property_Location.property_channel == channel))
            if update:
                if update_cutoff:
                    statement = (statement
                                 .where(
                        or_(Property_Data.last_update < update_cutoff, Property_Data.last_update == None))
                                 .where(Property_Data.property_validto >= current_time)
                                 )
            else:
                statement = statement.where(Property_Data.property_id == None)

            results = session.exec(statement)
            ids = []
            for result in results.unique():
                ids.append(result)
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
        with Session(self.engine) as session:
            properties = data["properties"]
            for property_data in properties:
                if not session.get(Property_Location, property_data["id"]):
                    p = Property_Location(
                        property_id=property_data["id"],
                        property_asatdt=dt.datetime.now(),
                        property_channel=channel.upper(),
                        property_latitude=property_data["location"]["latitude"],
                        property_longitude=property_data["location"]["longitude"]
                    )
                    session.add(p)

            session.commit()

    def load_property_data(self, data: dict, ids: list[int]) -> None:
        """
        Loads the data obtained from the Rightmove API into the database.
        :param data:    Dictionary      JSON response from the Rightmove API.
        :param ids:     List            A list of expected IDs which were sent in the API request.
        """
        with Session(self.engine) as session:
            found_ids = [p["id"] for p in data]
            for id in ids:
                if id not in found_ids:
                    current_time = dt.datetime.now()
                    statement = (select(Property_Data)
                                 .where(Property_Data.property_id == id)
                                 .where(Property_Data.property_validto >= dt.datetime.now())
                                 )
                    results = session.exec(statement)
                    existing_record = results.first()
                    if existing_record:
                        existing_record.property_validto = current_time
                        session.add(existing_record)
                        session.commit()

            for prop in data:
                current_time = dt.datetime.now()
                statement = (select(Property_Data)
                             .where(Property_Data.property_id == prop["id"])
                             .where(Property_Data.property_validto >= dt.datetime.now())
                             )
                results = session.exec(statement)
                existing_record = results.first()

                p = Property_Data(
                    property_id=prop["id"],
                    property_validfrom=current_time,
                    bedrooms=prop["bedrooms"],
                    bathrooms=prop.get("bathrooms"),
                    summary=prop["summary"],
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
                    first_visible=pd.to_datetime(prop["firstVisibleDate"])
                )

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

import datetime as dt
import re
from typing import List, Set

import pandas as pd
import psycopg2
from psycopg2 import extras
from pydantic import BaseModel

from config import DATABASE_URI
from rightmove.models import EmailAddress, PropertyData, ReviewDates, ReviewedProperties


def get_database_connection():
    """
    Establish a connection to the database.

    Returns:
        conn: A connection object to the database.
    """
    conn = psycopg2.connect(DATABASE_URI)
    return conn


def get_email_addresses() -> List[str]:
    """
    Retrieve all email addresses from the database.

    Returns:
        List[str]: A list of email addresses.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT email_address FROM email_details")
            return [row[0] for row in cursor.fetchall()]


def set_email_addresses(email_addresses: List[EmailAddress]) -> None:
    """
    Set the list of email addresses in the database that will be sent an email by the
    tool.

    Args:
        email_addresses (List[EmailAddress]): A list of EmailAddress objects to be set in the database.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM email_details")
            model_executemany(cursor, "email_details", email_addresses)


def get_property_reviews() -> List[dict]:
    """
    Property review IDs and dates from the database.

    Returns:
        List[dict]: A list of dictionaries where each dictionary represents a property review.
    """
    # Get review dates:
    sql = "select distinct email_id, str_date from review_dates order by email_id desc"
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return [{"email_id": row[0], "str_date": row[1]} for row in cursor.fetchall()]


def delete_property_review(review_id: str) -> None:
    """
    Delete a property review from the database.

    Args:
        review_id (str): The ID of the review to be deleted.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"select reviewed_date from review_dates where email_id={review_id}")
            date = cursor.fetchone()[0]

            cursor.execute(f"delete from review_dates where email_id={review_id}")
            cursor.execute(f"delete from reviewed_properties where reviewed_date='{date}'")

            conn.commit()


def get_new_property_count() -> int:
    """
    Get the count of new properties from the database.

    This function queries the 'alert_properties' table in the database and counts the number of properties
    where the 'review_id' is NULL, indicating that these properties are new and have not been reviewed yet.

    Returns:
        int: The count of new properties.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM alert_properties WHERE review_id IS NULL")
            return cursor.fetchone()[0]


def get_enhancement_properties() -> List[int]:
    """
    Function to get a list of property IDs which require enhanced data from the Rightmove property page.

    Returns:
        List[int]: A list of property IDs.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT ap.property_id
                FROM alert_properties ap
                LEFT JOIN property_floorplan pf using (property_id)
                WHERE pf.property_id IS NULL and ap.area is null
                """)
            return [row[0] for row in cursor.fetchall()]


def insert_models(models: List[BaseModel], table: str) -> None:
    """
    Function to insert a list of floorplans into the database.

    Args:
        models (List[BaseModel]): A list of BaseModel objects to be inserted into the database.
        table (str): The name of the table in the database.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            model_executemany(cursor, table, models)


def get_location_dataframe(ids: List[int] = None) -> pd.DataFrame:
    """
    Function to get the details of properties which require a travel time calculation.

    Returns:
        pd.DataFrame: A DataFrame containing the details of properties which require a travel time calculation.
    """

    if ids is None:
        sql = "SELECT property_id, longitude, latitude FROM alert_properties where travel_reviewed = 0"

    else:
        sql = (
            "SELECT property_id, longitude, latitude FROM alert_properties where"
            f" property_id in ({','.join([str(id) for id in ids])})"
        )

    df = pd.read_sql(sql, DATABASE_URI)

    return df


def model_execute(cursor, table_name: str, value: BaseModel):
    """
    Insert a pydantic model into a database table using execute.

    Args:
        cursor: The database cursor.
        table_name (str): The name of the table in the database.
        value (BaseModel): The pydantic model to be inserted into the database.
    """
    # Get the model fields
    model_field_names = [field for field in value.model_fields]

    # Construct the insert query
    insert_query = f"""
        INSERT INTO {table_name} ({','.join(model_field_names)})
        VALUES ({','.join(['%s' for _ in model_field_names])})
    """

    # Insert the values using execute
    cursor.execute(insert_query, tuple(value.model_dump().values()))


def model_executemany(cursor, table_name: str, values: List[BaseModel]):
    """
    Insert a list of pydantic models into a database table using executemany.

    Args:
        cursor: The database cursor.
        table_name (str): The name of the table in the database.
        values (List[BaseModel]): The list of pydantic models to be inserted into the database.
    """
    if len(values) == 0:
        return

    # Get the model fields
    model_field_names = [field for field in values[0].model_fields]

    # Construct the insert query
    insert_query = f"""
        INSERT INTO {table_name} ({','.join(model_field_names)})
        VALUES ({','.join(['%s' for _ in model_field_names])})
    """

    # Insert the values using executemany
    cursor.executemany(insert_query, [tuple(model.model_dump().values()) for model in values])


def parse_area(area_str):
    """
    Parse the area from a string.

    Args:
        area_str (str): The string containing the area.

    Returns:
        float: The parsed area as a float, or None if the area could not be parsed.
    """

    if "sq" in area_str:
        return float(re.match(r"\d{1,3}(,\d{3})*(\.\d+)?", area_str).group(0).replace(",", ""))
    else:
        return None


def parse_added_or_reduced(added_or_reduced_str):
    """
    Parse the added or reduced date from a string.

    Args:
        added_or_reduced_str (str): The string containing the added or reduced date.

    Returns:
        dt.datetime: The parsed date as a datetime object, or None if the date could not be parsed.
    """
    try:
        added_or_reduced = pd.to_datetime(added_or_reduced_str.split(" ")[-1], dayfirst=True)
        if str(added_or_reduced) == "NaT":
            added_or_reduced = None

    except Exception:
        added_or_reduced = None

    return added_or_reduced


def insert_property_images(cursor, property_images):
    """
    Insert property images into the database using executemany.

    Args:
        cursor: The database cursor.
        property_images: The property images to be inserted into the database.
    """

    # Insert property images into the database using executemany
    insert_query = """
        INSERT INTO property_images (property_id, image_url, image_caption)
        VALUES (%s, %s, %s)
        ON CONFLICT (property_id, image_url) DO NOTHING
    """
    cursor.executemany(insert_query, property_images)


class RightmoveDatabase:
    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URI)
        self.conn.autocommit = False

    def _close_missing_properties(self, missing_ids: Set[int]) -> None:
        """
        Closes the validto variable for properties which are no longer on the Rightmove website.

        Args:
            missing_ids (Set[int]): A set of IDs for the properties which are no longer on the Rightmove website.
        """
        with self.conn:
            with self.conn.cursor() as cursor:
                current_time = dt.datetime.now()
                cursor.execute(f"""
                    UPDATE property_data
                    SET property_validto = '{current_time}'
                    WHERE property_id IN ({','.join([str(id) for id in missing_ids])})
                """)

    def get_id_len(self, update, channel, update_cutoff=None):
        """
        Returns the number of property IDs that would be returned in the get_id_list() function.

        Args:
            update (bool): If True then the list will not filter for only those properties with no existing data.
            update_cutoff (dt.datetime): If update=True then a cutoff for last update can be used.
            channel (str): The channel which should be searched (RENT/BUY).

        Returns:
            int: Number of properties which would be in the list.
        """

        with self.conn:
            with self.conn.cursor() as cursor:
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

                cursor.execute(sql)
                result = cursor.fetchone()[0]

                return result

    def get_id_list(self, update: bool, channel: str, update_cutoff=None) -> List[List[int]]:
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

        with self.conn:
            with self.conn.cursor() as cursor:
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

                cursor.execute(sql)
                ids = []

                results = set([x[0] for x in cursor.fetchall()])

        for result in results:
            ids.append(result)
            if len(ids) == 25:
                yield ids
                ids = []
        if len(ids) > 0:
            yield ids

    def load_map_properties(self, properties: dict, channel: str) -> None:
        """
        Loads the data obtained from the Rightmove API into the database.
        :param properties:      Dictionary      JSON response from the Rightmove API.
        :param channel          String          The channel which searched for in the API.
        """
        with self.conn:
            with self.conn.cursor() as cursor:
                current_time = dt.datetime.now()
                channel = channel.upper()

                # Check for existing IDs in the database:
                if len(properties) == 0:
                    cursor.close()
                    return

                cursor.execute(f"""
                    SELECT property_id 
                    FROM property_location 
                    WHERE property_id IN ({','.join([str(p) for p in properties.keys()])})""")
                existing_ids: set = {r[0] for r in cursor.fetchall()}

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
                        ) VALUES (%s, %s, %s, %s, %s)
                        """
                    extras.execute_batch(cursor, sql, insert_values)

    def load_property_data(self, data: dict, ids: list[int]) -> None:
        cursor = self.conn.cursor(cursor_factory=extras.DictCursor)
        try:
            # Retrieve existing property IDs from the database
            cursor.execute("SELECT property_id FROM property_data")
            existing_ids = {row["property_id"] for row in cursor.fetchall()}

            # Set validto for properties which are no longer on the Rightmove website:
            missing_ids = set(ids) - existing_ids
            if missing_ids:
                self._close_missing_properties(missing_ids)

            current_time = dt.datetime.now()

            for prop in data:
                property_id = prop["id"]

                # Check for an existing record which is currently valid:
                cursor.execute(
                    """
                    SELECT * FROM property_data
                    WHERE property_id = %s AND property_validto >= %s
                    """,
                    (property_id, current_time),
                )
                existing_record = cursor.fetchone()

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
                    first_visible=pd.to_datetime(prop["firstVisibleDate"]),
                    last_displayed_update=added_or_reduced,
                )

                insert_list = []
                # Check for changes in property data
                if existing_record and self.has_changes(existing_record, property_data):
                    # Mark the existing record as no longer valid
                    cursor.execute(
                        """
                        UPDATE property_data
                        SET property_validto = %s
                        WHERE property_id = %s AND property_validto >= %s
                        """,
                        (current_time, property_id, current_time),
                    )
                    # Insert a new record with updated data
                    insert_list.append(property_data)
                elif not existing_record:
                    # Insert a new record if no existing record is found
                    insert_list.append(property_data)

                if insert_list:
                    model_executemany(cursor, "property_data", insert_list)

                # Insert property images using executemany
                property_images = [
                    (property_id, img_data["srcUrl"], img_data["caption"])
                    for img_data in prop["propertyImages"]["images"]
                ]
                if property_images:
                    insert_property_images(cursor, property_images)

            # Commit the transaction
            self.conn.commit()

        except Exception as e:
            # Handle exceptions and log if needed
            print(f"Error: {e}")

        finally:
            # Close the database connection
            if cursor:
                cursor.close()

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


def mark_properties_reviewed() -> int | None:
    """
    Mark properties as reviewed in the database.

    Returns:
        int: The new review ID, if there are properties to review.
        None: If there are no properties to review.
    """
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("select distinct property_id from alert_properties where property_reviewed = 0")
            property_ids = cursor.fetchall()

            cursor.execute("select coalesce(max(email_id), 0) as last_id from review_dates")
            review_id = cursor.fetchone()[0] + 1

            if len(property_ids) == 0:
                return None

            review_date = dt.datetime.now()
            review = ReviewDates(
                email_id=review_id,
                reviewed_date=review_date,
                str_date=review_date.strftime("%d-%b-%Y"),
            )
            model_execute(cursor, table_name="review_dates", value=review)

            values = [
                ReviewedProperties(property_id=property_id[0], reviewed_date=review_date, emailed=False)
                for property_id in property_ids
            ]
            model_executemany(cursor, table_name="reviewed_properties", values=values)

            return review_id


def get_properties(sql_filter: str) -> List[dict]:
    """
    Get property data from the database based on a provided SQL filter.

    Args:
        sql_filter (str): The SQL filter to apply when retrieving the properties.

    Returns:
        List[dict]: A list of dictionaries where each dictionary represents a property.
    """
    sql = f"""
    select * from alert_properties
    where {sql_filter}
    """

    # Reading data from CSV
    df = pd.read_sql(sql, DATABASE_URI)

    # Formatting changes:
    df["garden"] = df["garden"].apply(lambda x: "Private" if x == "private" else "Unknown")
    df["area"] = df["area"].fillna(0).apply(lambda x: f"{x:,.0f} ft\u00b2" if x != 0 else "Unavailable")

    properties = []
    for index, property in df.iterrows():
        travel_time = f"About {property.travel_time} minutes"

        data = {
            "link": f"https://www.rightmove.co.uk/properties/{property.property_id}",
            "title": property.property_description,
            "address": property.address,
            "status": f"Last update {property.last_update}",
            "description": property.summary,
            "garden": property.garden,
            "area": property.area,
            "price": f"£{property.price_amount:,.0f}",
            "travel_time": travel_time,
            "longitude": property.longitude,
            "latitude": property.latitude,
        }

        if type(property["images"]) == str:
            data["images"] = [
                {"url": img.strip().replace("171x162", "476x317"), "alt": "Property"}
                for img in property["images"].split(",")
            ][:2]
        else:
            data["images"] = []

        properties.append(data)

    return properties

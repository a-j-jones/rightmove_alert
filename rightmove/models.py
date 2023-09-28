import datetime as dt
from typing import Optional

from pydantic import validator
from sqlmodel import create_engine, Field, SQLModel

from config import SQL_PATH

sqlite_url = f"sqlite:///{SQL_PATH}"


class PropertyLocation(SQLModel, table=True):
    """
    Model to store Property location and channel information which is obtained via the
    map search Rightmove API.
    """
    property_id: int = Field(default=None, primary_key=True, foreign_key="propertydata.property_id")
    property_asatdt: dt.datetime = Field(default=None)
    property_channel: str
    property_longitude: float
    property_latitude: float


class PropertyData(SQLModel, table=True):
    """
    Model to store all Property data provided by the Rightmove API, such as property type, bedrooms, bathrooms etc.
    """
    property_id: int = Field(default=None, primary_key=True)
    property_validfrom: dt.datetime = Field(default=None, primary_key=True)
    property_validto: dt.datetime = Field(default=dt.datetime(9999, 12, 31))
    bedrooms: Optional[int] = Field(default=0)
    bathrooms: Optional[int] = Field(default=0)
    area: Optional[float]
    summary: str
    address: str
    property_subtype: Optional[str | None]
    property_description: str
    premium_listing: bool
    price_amount: float
    price_frequency: str
    price_qualifier: Optional[str]
    lettings_agent: str
    lettings_agent_branch: str
    development: bool
    commercial: bool
    enhanced_listing: bool
    students: bool
    auction: bool
    first_visible: Optional[dt.datetime]
    last_update: Optional[dt.datetime]
    last_displayed_update: Optional[dt.datetime]

    class Config:
        validate_assignment = True

    @validator("bedrooms", "bathrooms")
    def integer_conversion(cls, v):
        return v or 0


class PropertyImages(SQLModel, table=True):
    """
    Model to store Property location and channel information which is obtained via the
    map search Rightmove API.
    """
    property_id: int = Field(default=None, primary_key=True, foreign_key="propertydata.property_id")
    image_url: str = Field(default=None, primary_key=True)
    image_caption: Optional[str]


class ReviewedProperties(SQLModel, table=True):
    """
    Model to store properties that have already been considered / emailed to the customer
    """
    property_id: int = Field(default=None, primary_key=True, foreign_key="propertydata.property_id")
    reviewed_date: dt.datetime = Field(default=dt.datetime.now())
    emailed: bool = Field(default=False)


class ReviewDates(SQLModel, table=True):
    """
    Model to store properties that have already been considered / emailed to the customer
    """
    reviewed_date: dt.datetime = Field(
        default=dt.datetime.now(), primary_key=True, foreign_key="reviewedproperties.reviewed_date"
    )
    email_id: int = Field(default=None)
    str_date: Optional[str] = Field(default=None)


class TravelTime(SQLModel, table=True):
    property_id: int = Field(default=None, primary_key=True, foreign_key="propertydata.property_id")
    sub_35m: bool = Field(default=False)
    sub_40m: bool = Field(default=False)
    sub_45m: bool = Field(default=False)


class TravelTimePrecise(SQLModel, table=True):
    property_id: int = Field(default=None, primary_key=True, foreign_key="propertydata.property_id")
    travel_time: int = Field(default=None)


if __name__ == "__main__":
    engine = create_engine(sqlite_url, echo=False)
    # SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

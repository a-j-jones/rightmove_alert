import datetime as dt
from typing import Optional

from pydantic import validator
from sqlmodel import Field, SQLModel, create_engine


class Property_Location(SQLModel, table=True):
    """
    Model to store Property location and channel information which is obtained via the
    map search Rightmove API.
    """
    property_id: int = Field(default=None, primary_key=True, foreign_key="property_data.property_id")
    property_asatdt: dt.datetime = Field(default=None)
    property_channel: str
    property_longitude: float
    property_latitude: float


class Property_Data(SQLModel, table=True):
    """
    Model to store all Property data provided by the Rightmove API, such as property type, bedrooms, bathrooms etc.
    """
    property_id: int = Field(default=None, primary_key=True)
    property_validfrom: dt.datetime = Field(default=None, primary_key=True)
    property_validto: dt.datetime = Field(default=dt.datetime(9999, 12, 31))
    bedrooms: Optional[int] = Field(default=0)
    bathrooms: Optional[int] = Field(default=0)
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

    class Config:
        validate_assignment = True

    @validator("bedrooms", "bathrooms")
    def integer_conversion(cls, v):
        return v or 0


if __name__ == "__main__":
    db_filename = "properties.db"
    engine = create_engine(f"sqlite:///{db_filename}", echo=True)
    SQLModel.metadata.create_all(engine)

import asyncio
import logging
import os
import sqlite3

from sqlmodel import create_engine, select, Session

from app import count_new_properties
from config import DATA, SQL_PATH
from config.logging import logging_setup
from email_data.send_email import prepare_email_html, send_email
from rightmove.geolocation import update_locations
from rightmove.models import ReviewDates, database_uri, create_models
from rightmove.run import (
    download_property_data,
    mark_properties_reviewed,
)

logger = logging.getLogger(__name__)
logger = logging_setup(logger)


def create_database():
    create_models()
    with open(os.path.join(DATA, "views.sql")) as f:
        sql = f.read()

    conn = sqlite3.connect(SQL_PATH)
    c = conn.cursor()
    c.execute(sql)
    conn.commit()
    conn.close()


def main():
    # if not os.path.exists(SQL_PATH):
    #     logger.info("Creating database...")
    #     create_database()

    # Download the latest properties and data:
    logger.info("Downloading properties and data...")
    # asyncio.run(download_properties("BUY"))
    asyncio.run(download_property_data(update=False))

    # Update geolocation data:
    logger.info("Updating geolocation data...")
    update_locations()

    logger.info("Getting number of new properties...")
    count = count_new_properties()
    if count == 0:
        logger.warning("No new properties found.")
        return

    # Mark properties as reviewed:
    logger.info("Marking properties as reviewed...")
    mark_properties_reviewed()

    # Send email:
    logger.info("Creating email...")
    engine = create_engine(database_uri, echo=False)
    query = (
        select([ReviewDates.email_id]).order_by(ReviewDates.email_id.desc()).limit(1)
    )
    with Session(engine) as session:
        email_id = session.exec(query).first()

    if email_id:
        if prepare_email_html(email_id):
            logger.info("Sending email...")
            send_email()


if __name__ == "__main__":
    main()

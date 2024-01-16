import asyncio
import logging

import psycopg2

from app import count_new_properties
from config import DATABASE_URI
from config.logging import logging_setup
from email_data.send_email import prepare_email_html
from rightmove.geolocation import update_locations
from rightmove.run import (
    download_property_data,
    mark_properties_reviewed,
    download_properties,
)

logger = logging.getLogger(__name__)
logger = logging_setup(logger)


def main():
    # Download the latest properties and data:
    logger.info("Downloading properties and data...")
    asyncio.run(download_properties("BUY"))
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

    sql = "SELECT email_id FROM reviewdates ORDER BY email_id DESC LIMIT 1"
    conn = psycopg2.connect(DATABASE_URI)
    cursor = conn.cursor()
    cursor.execute(sql)
    email_id = cursor.fetchone()[0]

    if email_id:
        if prepare_email_html(email_id):
            logger.info("Sending email...")
            # send_email()


if __name__ == "__main__":
    main()

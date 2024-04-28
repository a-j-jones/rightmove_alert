import asyncio
import logging

from app import count_new_properties
from config.logging import logging_setup
from email_data.send_email import prepare_email_html, send_email
from rightmove.database import mark_properties_reviewed
from rightmove.enhancements import update_enhanced_data
from rightmove.geolocation import update_locations
from rightmove.run import (
    download_property_data,
)

logger = logging.getLogger(__name__)
logger = logging_setup(logger)


def main():
    # Download the latest properties and data:
    logger.info("Downloading properties and data...")
    # asyncio.run(download_properties("BUY"))
    asyncio.run(download_property_data(update=True))

    # Update geolocation data:
    logger.info("Updating geolocation data...")
    update_locations()

    # Getting Floorplan data:
    logger.info("Getting Floorplan data...")
    update_enhanced_data()

    logger.info("Getting number of new properties...")
    count = count_new_properties()
    if count == 0:
        logger.warning("No new properties found.")
        return

    # Mark properties as reviewed:
    logger.info("Marking properties as reviewed...")
    email_id = mark_properties_reviewed()

    # Send email:
    if email_id:
        logger.info("Creating email...")
        if prepare_email_html(email_id):
            logger.info("Sending email...")
            send_email()
    else:
        logger.info("No properties found in latest review.")


if __name__ == "__main__":
    main()

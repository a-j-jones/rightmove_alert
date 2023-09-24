import asyncio
import logging
from sqlmodel import create_engine, select, Session

from email_data.send_email import prepare_email_html, send_email
from rightmove.geolocation import update_locations
from rightmove.models import ReviewDates, sqlite_url
from rightmove.run import download_properties, download_property_data, mark_properties_reviewed


logger = logging.getLogger(__name__)
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sh.setFormatter(formatter)
logger.addHandler(sh)


if __name__ == "__main__":
    # Download latest properties and data:
    print("Downloading properties and data...")
    asyncio.run(download_properties("BUY"))
    asyncio.run(download_property_data(update=False))

    # Update geolocation data:
    print("Updating geolocation data...")
    update_locations()

    # Mark properties as reviewed:
    print("Marking properties as reviewed...")
    mark_properties_reviewed()

    # Send email:
    print("Creating email...")
    engine = create_engine(sqlite_url, echo=False)
    query = select([ReviewDates.email_id]).order_by(ReviewDates.email_id.desc()).limit(1)
    with Session(engine) as session:
        email_id = session.exec(query).first()

    if email_id:
        if prepare_email_html(email_id):
            print("Sending email...")
            send_email()

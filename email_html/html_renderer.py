import asyncio
import datetime as dt
import logging

import pandas as pd
import waitress
from flask import Flask, redirect, render_template, request, url_for
from sqlmodel import create_engine, Session

from rightmove.geolocation import update_locations
from rightmove.models import ReviewDates, ReviewedProperties, sqlite_url
from rightmove.run import download_properties, download_property_data

app = Flask(__name__)

logger = logging.getLogger('waitress')
logger.setLevel(logging.INFO)


@app.route('/')
def index():
    engine = create_engine(sqlite_url, echo=False)

    # Get review dates:
    sql = "select distinct email_id, str_date from reviewdates order by email_id desc"
    items = pd.read_sql(sql, engine).to_records()

    # Get count of new properties:
    sql = "select count(*) from alert_properties where travel_time < 45 and review_id is null"
    count_props = pd.read_sql(sql, engine).values[0][0]

    new_properties = ""
    if count_props > 0:
        new_properties = f" - {count_props} new"

    logger.info(f"New properties: {count_props}")

    return render_template('index.html', title="Home", items=items, new_properties=new_properties)


@app.route('/email_template', methods=["GET"])
def email_template():
    data = request.args.to_dict()
    review_id = data.get("id")
    include_nav = False
    match review_id:
        case None:
            review_filter = "latest_reviewed"
            include_nav = True
        case "latest":
            review_filter = "review_id is null"
        case _:
            review_filter = f"review_id = {review_id}"

    sql = f"""
    select * from alert_properties
    where 
        travel_time < 45
        and {review_filter}
    """

    # Reading data from CSV
    engine = create_engine(sqlite_url, echo=False)
    df = pd.read_sql(sql, engine)

    properties = []
    for index, property in df.iterrows():

        travel_time = f"About {property.travel_time} minutes"

        data = {
            "link": f"https://www.rightmove.co.uk/properties/{property.property_id}",
            "title": property.property_description,
            "address": property.address,
            "status": f"Last update {property.last_update}",
            "description": property.summary,
            "price": f"£{property.price_amount:,.0f}",
            "travel_time": travel_time
        }

        if type(property["images"]) == str:
            data["images"] = [{'url': img.strip().replace("171x162", "476x317"), 'alt': 'Property'} for img in
                              property['images'].split(',')][:2]
        else:
            data["images"] = []

        properties.append(data)

    return render_template('template.html', title="View properties", properties=properties, review_id=review_id, include_nav=include_nav)


@app.route('/review_latest')
def review_latest():
    engine = create_engine(sqlite_url, echo=False)
    property_ids = pd.read_sql("SELECT property_id FROM alert_properties where not property_reviewed", engine)
    review_id = pd.read_sql("select max(email_id) as last_id from reviewdates", engine).last_id[0] + 1

    with Session(engine) as session:
        review_date = dt.datetime.now()
        if len(property_ids) > 0:
            session.add(
                ReviewDates(
                    email_id=review_id,
                    reviewed_date=review_date,
                    str_date=review_date.strftime("%d-%b-%Y")
                )
            )

        for id in property_ids.property_id.unique():
            session.add(ReviewedProperties(property_id=id, reviewed_date=review_date, emailed=False))

        session.commit()

    return redirect(url_for('index'))


@app.route('/download')
def download():
    asyncio.run(download_properties("BUY"))
    asyncio.run(download_property_data(update=False))
    update_locations()

    return redirect(url_for('index'))


if __name__ == '__main__':
    port = 5000
    host = '127.0.0.1'

    logger.info("Starting server...")
    waitress.serve(app, port=port, host=host)

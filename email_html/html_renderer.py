import datetime as dt

import pandas as pd
from flask import Flask, render_template
from sqlmodel import create_engine, Session

from rightmove.models import ReviewedProperties, sqlite_url

app = Flask(__name__)


@app.route('/')
def index():
    # Reading data from CSV
    engine = create_engine(sqlite_url, echo=False)
    df = pd.read_sql("SELECT * FROM alert_properties where sub_45m and latest_reviewed", engine)

    properties = []
    for index, property in df.iterrows():
        data = {
            "link": f"https://www.rightmove.co.uk/properties/{property.property_id}",
            "title": property.property_description,
            "address": property.address,
            "status": f"Last update {property.last_update}",
            "description": property.summary,
            "price": f"£{property.price_amount:,.0f}"
        }

        if type(property["images"]) == str:
            data["images"] = [{'url': img.strip().replace("171x162", "476x317"), 'alt': 'Property'} for img in
                              property['images'].split(',')][:2]
        else:
            data["images"] = []

        properties.append(data)

    return render_template('template.html', properties=properties, style="static/styles.css")


def run_app():
    engine = create_engine(sqlite_url, echo=False)
    property_ids = pd.read_sql("SELECT property_id FROM alert_properties where not property_reviewed", engine)

    with Session(engine) as session:
        review_date = dt.datetime.now()
        for id in property_ids.property_id.unique():
            session.add(ReviewedProperties(property_id=id, reviewed_date=review_date, emailed=False))

        session.commit()

    app.run(debug=False)

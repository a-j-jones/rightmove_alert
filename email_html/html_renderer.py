import datetime as dt

import pandas as pd
from flask import Flask, redirect, render_template, request, url_for
from sqlmodel import create_engine, select, Session

from rightmove.models import ReviewDates, ReviewedProperties, sqlite_url

app = Flask(__name__)


@app.route('/')
def index():
    engine = create_engine(sqlite_url, echo=False)
    with Session(engine) as session:
        items = list(session.exec(select(ReviewDates)))

    return render_template('index.html', items=items)


@app.route('/review')
def review():
    engine = create_engine(sqlite_url, echo=False)
    sql = f"""
     select * from alert_properties
     where 
         travel_time < 45
         and review_id is null
     """


@app.route('/email_template', methods=["GET"])
def email_template():
    data = request.args.to_dict()
    review_id = data.get("id")
    match review_id:
        case None:
            review_filter = "latest_reviewed"
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

    return render_template('template.html', properties=properties, review_id=review_id)


@app.route('/review_latest')
def review_latest():
    engine = create_engine(sqlite_url, echo=False)
    property_ids = pd.read_sql("SELECT property_id FROM alert_properties where not property_reviewed", engine)
    review_id = pd.read_sql("select max(email_id) as last_id from reviewdates", engine).last_id[0] + 1

    with Session(engine) as session:
        review_date = dt.datetime.now()
        if len(property_ids) > 0:
            session.add(ReviewDates(
                email_id=review_id,
                reviewed_date=review_date,
                str_date=review_date.strftime("%d-%b-%Y")
            ))

        for id in property_ids.property_id.unique():
            session.add(ReviewedProperties(property_id=id, reviewed_date=review_date, emailed=False))

        session.commit()

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=False)

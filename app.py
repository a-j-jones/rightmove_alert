import asyncio
import logging
import os

import pandas as pd
import psycopg2
import waitress
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from config import IS_WINDOWS, DATABASE_URI
from config.logging import logging_setup
from email_data.send_email import prepare_email_html, send_email
from rightmove.database import get_email_addresses, set_email_addresses
from rightmove.geolocation import update_locations
from rightmove.models import EmailAddress
from rightmove.run import (
    download_properties,
    download_property_data,
    get_properties,
    mark_properties_reviewed,
)

app = Flask(__name__)

wlogger = logging.getLogger("waitress")
wlogger = logging_setup(wlogger)

logger = logging.getLogger(__name__)
logger = logging_setup(logger)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/")
def index():
    # Get review dates:
    sql = "select distinct email_id, str_date from reviewdates order by email_id desc"
    items = pd.read_sql(sql, DATABASE_URI).to_records()

    new_properties = count_new_properties()

    return render_template(
        "index.html", title="Home", items=items, new_properties=new_properties
    )


@app.route("/email_template", methods=["GET"])
def email_template():
    data = request.args.to_dict()
    review_id = data.get("id")
    match review_id:
        case "latest":
            review_filter = "review_id is null"
        case _:
            review_filter = f"review_id = {review_id}"

    new_properties = count_new_properties()
    properties = get_properties(review_filter)

    return render_template(
        "template.html",
        title="View properties",
        properties=properties,
        review_id=review_id,
        new_properties=new_properties,
    )


@app.route("/review_latest")
def review_latest():
    mark_properties_reviewed()

    return redirect(url_for("index"))


@app.route("/download")
def download():
    asyncio.run(download_properties("BUY"))
    asyncio.run(download_property_data(update=False))
    update_locations()

    return redirect(url_for("index"))


@app.route("/send_email")
def send():
    data = request.args.to_dict()
    review_id = data.get("id")

    if prepare_email_html(review_id):
        send_email()

    return redirect(url_for("index"))


@app.route("/delete_review")
def delete_review():
    data = request.args.to_dict()
    review_id = data.get("id")

    conn = psycopg2.connect(DATABASE_URI)
    cursor = conn.cursor()

    cursor.exec(f"select reviewed_date from reviewdates where email_id={review_id}")
    date = cursor.fetchone()[0]

    cursor.exec(f"delete from reviewdates where email_id={review_id}")
    cursor.exec(f"delete from reviewedproperties where reviewed_date='{date}'")

    conn.commit()

    return redirect(url_for("index"))


@app.route("/settings", methods=["GET"])
def settings():
    email_recipients = get_email_addresses()
    return render_template("settings.html", email_recipients=email_recipients)


@app.route("/settings", methods=["POST"])
def update_settings():
    form_data = request.form
    recipients = form_data.getlist("recipients[]")

    if recipients:
        set_email_addresses([EmailAddress(email_address=email) for email in recipients])

    return redirect("/")


def count_new_properties() -> str:
    # Get count of new properties:
    sql = "select count(*) from alert_properties where travel_time < 45 and review_id is null"
    count_props = pd.read_sql(sql, DATABASE_URI).values[0][0]

    new_properties = ""
    if count_props > 0:
        new_properties = f" - {count_props} new"

    return new_properties


if __name__ == "__main__":
    if IS_WINDOWS:
        host = "127.0.0.1"
        port = 5002
    else:
        host = "0.0.0.0"
        port = 5009

    logger.info("Starting server...")
    waitress.serve(app, port=port, host=host)

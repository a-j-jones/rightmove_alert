import asyncio
import logging
import os

import waitress
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from config import IS_WINDOWS
from config.logging import logging_setup
from email_data.send_email import prepare_email_html, send_email
from rightmove.database import (
    get_email_addresses,
    set_email_addresses,
    get_property_reviews,
    delete_property_review,
    get_new_property_count,
    mark_properties_reviewed,
    get_properties,
)
from rightmove.enhancements import update_enhanced_data
from rightmove.geolocation import update_locations
from rightmove.models import EmailAddress
from rightmove.plotting import create_mapbox
from rightmove.run import (
    download_properties,
    download_property_data,
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
    reviews = get_property_reviews()
    new_properties = count_new_properties()

    return render_template(
        "index.html", title="Home", items=reviews, new_properties=new_properties
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
    graph = create_mapbox(properties) if properties else None

    return render_template(
        "template.html",
        title="View properties",
        properties=properties,
        review_id=review_id,
        new_properties=new_properties,
        graph=graph,
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
    update_enhanced_data()
    logger.info("Download complete")

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
    delete_property_review(review_id)
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
    count_props = get_new_property_count()
    new_properties = f" - {count_props} new" if count_props > 0 else ""

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

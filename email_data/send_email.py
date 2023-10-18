import base64
import json
import logging
import os
import pickle
import shutil
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from jinja2 import Environment, FileSystemLoader
from requests import HTTPError

from config import BASE_DIR, BOOTSTRAP_UTIL, DATA, TEMPLATES
from config.logging import logging_setup
from rightmove.run import get_properties

logger = logging.getLogger(__name__)
logger = logging_setup(logger)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_service():
    logger.info("Getting gmail credentials")

    creds = None
    token_path = os.path.join(DATA, "token.pickle")
    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds: Credentials = pickle.load(token)

    try:
        logger.info("Attempting to refresh credentials")
        http = httplib2.Http()
        creds.refresh(Request(http))
    except Exception as e:
        logger.warning(f"Login required {e}")
        flow = InstalledAppFlow.from_client_secrets_file(
            "email_data/credentials.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

    with open(token_path, "wb") as token:
        pickle.dump(creds, token)

    return build("gmail", "v1", credentials=creds)


def create_email():
    logger.info("Creating email")

    with open(os.path.join(DATA, "email_details.json"), "r") as f:
        data = json.load(f)
        logger.info(f"Recipients: {data['recipients']}")

    msg = MIMEMultipart("alternative")
    msg["From"] = data["from"]
    msg["To"] = ",".join(data["recipients"])
    msg["Subject"] = "Property update"

    # HTML Email Content
    with open("email_data/bootstrap.html", "r") as f:
        html_content = f.read()

    # Attach HTML Content
    msg.attach(MIMEText(html_content, "html"))

    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def prepare_email_html(review_id) -> bool:
    review_filter = f"review_id = {review_id}"
    properties = get_properties(review_filter)

    infile = Path(BASE_DIR, "email_data", "jinja.html")
    outfile = Path(BASE_DIR, "email_data", "bootstrap.html")

    # Render jinja2 template:
    logger.info("Rendering template")

    env = Environment(loader=FileSystemLoader(TEMPLATES))
    bootstrap_email_path = shutil.which(BOOTSTRAP_UTIL)

    template = env.get_template("send_email_template.html")
    with open(infile, "w", encoding="utf-8") as f:
        f.write(template.render(properties=properties))

    if bootstrap_email_path:
        logger.info(f"Creating output file: {outfile}")
        cmd = rf'"{bootstrap_email_path}" "{infile}" > "{outfile}"'
        subprocess.run(cmd, text=True, shell=True)
    else:
        logger.error(f"'{BOOTSTRAP_UTIL}' was not found in path:")
        for path in os.environ["PATH"].split(os.pathsep):
            logger.error(f"{path}")
        return False

    return True


def send_email():
    service = get_service()
    create_message = create_email()

    try:
        message = (
            service.users().messages().send(userId="me", body=create_message).execute()
        )
        logger.info(f'sent message to {message} Message Id: {message["id"]}')
    except HTTPError as error:
        logger.info(f"An error occurred: {error}")


if __name__ == "__main__":
    send_email()

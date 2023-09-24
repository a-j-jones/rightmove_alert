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
from google_auth_httplib2 import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from jinja2 import Environment, FileSystemLoader
from requests import HTTPError

from rightmove.run import get_properties

logger = logging.getLogger('waitress')

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


def get_service():
    logger.info("Getting gmail credentials...")
    creds = None
    if os.path.exists('email_data/token.pickle'):
        with open('email_data/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            http = httplib2.Http()
            creds.refresh(Request(http))
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'email_data/credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('email_data/token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


def create_email():
    logger.info("Creating email...")
    with open("email_data/email_details.json", "r") as f:
        data = json.load(f)
        logger.info(f"Recipients: {data['recipients']}")

    msg = MIMEMultipart('alternative')
    msg['From'] = data["from"]
    msg['To'] = ",".join(data["recipients"])
    msg['Subject'] = "Property update"

    # HTML Email Content
    with open("email_data/bootstrap.html", "r") as f:
        html_content = f.read()

    # Attach HTML Content
    msg.attach(MIMEText(html_content, 'html'))

    return {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def prepare_email_html(review_id) -> bool:
    review_filter = f"review_id = {review_id}"
    properties = get_properties(review_filter)

    infile = Path(os.path.abspath(os.path.dirname(__file__)), "jinja.html")
    outfile = Path(os.path.abspath(os.path.dirname(__file__)), "bootstrap.html")

    # Render jinja2 template:
    logger.info("Rendering template...")
    
    if os.name == 'nt':
        env = Environment(loader=FileSystemLoader('templates'))
    else:
        env = Environment(loader=FileSystemLoader('/app/email_data/templates'))

    template = env.get_template('send_email_template.html')
    with open(infile, "w", encoding="utf-8") as f:
        f.write(template.render(properties=properties))

    executable_name = "bootstrap-email.bat" if os.name == 'nt' else "bootstrap-email"
    bootstrap_email_path = shutil.which(executable_name)
    if bootstrap_email_path:
        print(f"Creating output file: {outfile}")
        cmd = rf'"{bootstrap_email_path}" "{infile}" > "{outfile}"'
        subprocess.run(cmd, text=True, shell=True)
    else:
        print("bootstrap-email.bat was not found.")
        logger.error("bootstrap-email.bat was not found.")
        return False

    return True


def send_email():
    service = get_service()
    create_message = create_email()

    try:
        message = (service.users().messages().send(userId="me", body=create_message).execute())
        logger.info(F'sent message to {message} Message Id: {message["id"]}')
    except HTTPError as error:
        logger.info(F'An error occurred: {error}')

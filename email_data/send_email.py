import base64
import json
import logging
import os
import pickle
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httplib2
from google_auth_httplib2 import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests import HTTPError

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


def send_email():
    service = get_service()
    create_message = create_email()

    try:
        message = (service.users().messages().send(userId="me", body=create_message).execute())
        logger.info(F'sent message to {message} Message Id: {message["id"]}')
    except HTTPError as error:
        logger.info(F'An error occurred: {error}')

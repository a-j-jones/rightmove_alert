import json
import logging
import os
import shutil
import smtplib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader
from requests import HTTPError

from config import BASE_DIR, BOOTSTRAP_UTIL, DATA, TEMPLATES
from config.logging import logging_setup
from rightmove.database import get_email_addresses, get_properties

# Setting up logger
logger = logging.getLogger(__name__)
logger = logging_setup(logger)

# Defining paths for bootstrap and jinja templates
BOOTSTRAP_TEMPLATE = Path(BASE_DIR, "email_data", "bootstrap.html")
JINJA_TEMPLATE = Path(BASE_DIR, "email_data", "jinja.html")


def cleanup_files():
    """
    Clean up temporary files created for the email.
    """
    logger.info("Cleaning up temporary files")
    os.remove(BOOTSTRAP_TEMPLATE)
    os.remove(JINJA_TEMPLATE)


def create_email(from_email: str, recipients: List[str]) -> MIMEMultipart:
    """
    Creates email message using MIME.

    Args:
        from_email (str): Sender's email address
        recipients (List[str]): List of recipient email addresses

    Returns:
        MIMEMultipart: Email message
    """
    logger.info("Creating email")

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = ",".join(recipients)
    msg["Subject"] = "Property update"

    # HTML Email Content
    with open(BOOTSTRAP_TEMPLATE, "r") as f:
        html_content = f.read()

    # Attach HTML Content
    msg.attach(MIMEText(html_content, "html"))

    return msg


def prepare_email_html(review_id) -> bool:
    """
    Prepare HTML file to be sent in an email using jinja2 templating and bootstrap.

    Args:
        review_id (int): Review ID to filter properties

    Returns:
        bool: True if successful, False otherwise
    """
    review_filter = f"review_id = {review_id}"
    properties = get_properties(review_filter)

    # Render jinja2 template:
    logger.info("Rendering template")

    env = Environment(loader=FileSystemLoader(TEMPLATES))
    bootstrap_email_path = shutil.which(BOOTSTRAP_UTIL)

    template = env.get_template("send_email_template.html")
    with open(JINJA_TEMPLATE, "w", encoding="utf-8") as f:
        f.write(template.render(properties=properties))

    if bootstrap_email_path:
        logger.info(f"Creating output file: {BOOTSTRAP_TEMPLATE}")
        cmd = rf'"{bootstrap_email_path}" "{JINJA_TEMPLATE}" > "{BOOTSTRAP_TEMPLATE}"'
        subprocess.run(cmd, text=True, shell=True)
    else:
        logger.error(f"'{BOOTSTRAP_UTIL}' was not found in path:")
        for path in os.environ["PATH"].split(os.pathsep):
            logger.error(f"{path}")
        return False

    return True


def send_email():
    """
    Sends email to the recipients in the database, from the email in secrets JSON.
    """
    with open(os.path.join(DATA, "secrets.json"), "r") as f:
        secrets = json.load(f)
        email = secrets["email"]
        password = secrets["password"]

    recipients = get_email_addresses()

    message = create_email(email, recipients)

    try:
        smtp_server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp_server.login(email, password)
        smtp_server.sendmail(email, recipients, message.as_string())
        logger.info(f'Sent message to email(s): {", ".join(recipients)}')
    except HTTPError as error:
        logger.info(f"An error occurred: {error}")
    finally:
        cleanup_files()


if __name__ == "__main__":
    send_email()

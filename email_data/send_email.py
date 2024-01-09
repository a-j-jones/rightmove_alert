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
from rightmove.run import get_properties

logger = logging.getLogger(__name__)
logger = logging_setup(logger)


def create_email(from_email: str, recipients: List[str]) -> MIMEMultipart:
    logger.info("Creating email")

    msg = MIMEMultipart("alternative")
    msg["From"] = from_email
    msg["To"] = ",".join(recipients)
    msg["Subject"] = "Property update"

    # HTML Email Content
    with open(os.path.join(BASE_DIR, "email_data", "bootstrap.html"), "r") as f:
        html_content = f.read()

    # Attach HTML Content
    msg.attach(MIMEText(html_content, "html"))

    return msg


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
    with open(os.path.join(DATA, "secrets.json"), "r") as f:
        secrets = json.load(f)
        email = secrets["email"]
        password = secrets["password"]

    with open(os.path.join(DATA, "email_details.json"), "r") as f:
        data = json.load(f)
        recipients = data["recipients"]

    message = create_email(email, recipients)

    try:
        smtp_server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp_server.login(email, password)
        smtp_server.sendmail(email, recipients, message.as_string())
        logger.info(f'Sent message to email(s): {", ".join(recipients)}')
    except HTTPError as error:
        logger.info(f"An error occurred: {error}")


if __name__ == "__main__":
    send_email()

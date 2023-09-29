# Rightmove Alerts

## Description

This project wraps the Rightmove API, implemented in their website to populate their map search page, as well as the
data displayed to the user on the website.
This tool is built to obtain results from the API and build an automated email system to send desired properties to
their email when it meets their requirements.

## Features

- Obtain all properties from the Rightmove API within a given search area, in both Rent and Buy channels as required.
- Compare the location of the properties to travel time shape files, to determine whether the property is within the
  requirements
- Interact with the properties which were added/reviewed on specific days using a web interface.
- Send an email to the user with the new properties, ad hoc or on a schedule using docker cron jobs.

## Installation

### Windows

```cmd
git clone https://github.com/a-j-jones/rightmove_api_v2.git
cd rightmove_api_v2
pip install -r requirements.txt
```

### Docker

```cmd
git clone https://github.com/a-j-jones/rightmove_api_v2.git
cd rightmove_api_v2
docker-compose up --build
```

## Usage

Navigate to the locally hosted webpage, by default this is http://localhost:5001

- Download new properties with "Download properties"
- View latest, non-reviewed properties with "Review properties"
    - When reviewing properties, you may click "Mark reviewed" to set the unreviewed properties to reviewed.
- View any day of reviewed properties in the list.
    - When reviewing the selected day, you may click "Send email" to send the properties to the user.
- Settings, update the email address for the recipients.

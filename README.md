# Rightmove API v2

## Description

The "Rightmove Scraper" is a Python project that provides a set of tools to scrape property data from the Rightmove website and perform various analysis on the scraped data. The project includes modules for interacting with the Rightmove API, managing a SQLite database to store the scraped data, performing geolocation analysis, rendering HTML email templates, and running the main application.

## Features

- Scraping property data: The project includes a module `api_wrapper.py` that interacts with the Rightmove API to download property data. It provides functions to search for properties within a specific region and geographic coordinates, download property data for a list of property IDs, and store the downloaded data in a SQLite database.

- Database management: The `database.py` module provides a set of functions for managing the SQLite database. It includes functions to retrieve property IDs, retrieve the number of properties in the database, load map properties into the database, load property data into the database, update property locations based on travel time shapes, etc.

- Geolocation analysis: The `geolocation.py` module includes functions to perform geolocation analysis on the property data. It uses travel time shape files to determine the proximity of properties to certain locations. The module can update the property locations in the database based on the travel time shapes.

- HTML email rendering: The `html_renderer.py` module provides a Flask application that renders HTML templates for sending property information to customers via email. It reads property data from the database and generates HTML templates that can be sent as emails.

- Main application: The `main.py` file is the entry point of the application. It includes functions to download and update properties, perform geolocation analysis, and display the properties using the HTML renderer.

- Testing: The `tests.py` file includes test functions for testing different modules of the project.

## Installation

1. Clone the project repository:

```bash
git clone https://github.com/a-j-jones/rightmove_api_v2.git
```

2. Install the required Python packages:

```cmd
pip install -r requirements.txt
```

## Usage

1. Run rightmove.models.py to create the database:
```cmd
python rightmove/models.py
```
2. Run the main application:

```cmd
python main.py
```

This will download and update the properties, perform geolocation analysis, and display the properties using the HTML renderer.

3. To run the tests:

```cmd
python tests.py
```

## Contributing

Contributions to the project are always welcome. Here's how you can contribute:

1. Fork the project repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them.
4. Push your changes to your forked repository.
5. Submit a pull request explaining your changes.

## Credits

The project is developed and maintained by Adam Jones.

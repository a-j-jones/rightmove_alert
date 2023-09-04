import pandas as pd
from flask import Flask, render_template
from rightmove.models import sqlite_file_name

app = Flask(__name__)

wanted = [
    135811319,
    139253411,
    139349150,
    139259135,
    138446930,
    138966491,
    139257416
]


@app.route('/')
def index():
    # Reading data from CSV
    df = pd.read_csv("40mins.csv")

    properties = []
    for index, property in df.iterrows():
        if property.property_id not in wanted:
            continue

        data = {
            "link": f"https://www.rightmove.co.uk/properties/{property.property_id}",
            "title": property.property_description,
            "address": property.address,
            "status": f"Last update {property.last_update}",
            "description": property.summary,
            "price": f"£{property.price_amount:,.0f}"
        }

        if type(property["images"]) == str:
            data["images"] = [{'url': img.strip().replace("171x162", "476x317"), 'alt': 'Property'} for img in
                              property['images'].split(',')][:2]
        else:
            data["images"] = []

        properties.append(data)

    return render_template('template.html', properties=properties, style="static/styles.css")


if __name__ == '__main__':
    app.run(debug=True)

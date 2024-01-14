import os
import sqlite3

from config import SQL_PATH
from rightmove.models import create_models


def create_database():
    print(SQL_PATH)
    create_models()
    with open("views.sql") as f:
        sql = f.read()

    conn = sqlite3.connect(SQL_PATH)
    c = conn.cursor()

    print(sql)
    c.execute(sql)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    if not os.path.exists(SQL_PATH):
        create_database()

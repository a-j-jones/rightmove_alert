import os

IS_WINDOWS = os.name == "nt"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if IS_WINDOWS:
    DATA = os.path.join(BASE_DIR, "data")
    DB_HOST = "localhost"
    TEMPLATES = os.path.join(BASE_DIR, "templates")
    STATIC = os.path.join(BASE_DIR, "static")
    BOOTSTRAP_UTIL = "bootstrap-email.bat"
else:
    DATA = "/app/data"
    DB_HOST = "pgvector"
    TEMPLATES = "/app/templates"
    STATIC = "/app/static"
    BOOTSTRAP_UTIL = "bootstrap-email"

DATABASE_URI = f"postgresql://root:root@{DB_HOST}:5432/rightmove_test"

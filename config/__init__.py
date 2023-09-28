import os

IS_WINDOWS = os.name == 'nt'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if IS_WINDOWS:
    DATA = os.path.join(BASE_DIR, "data")
    SQL_PATH = os.path.join(BASE_DIR, "data", "database.db")
    TEMPLATES = os.path.join(BASE_DIR, "templates")
    STATIC = os.path.join(BASE_DIR, "static")
    BOOTSTRAP_UTIL = "bootstrap-email.bat"
else:
    DATA = "/data"
    SQL_PATH = "/data/database.db"
    TEMPLATES = "/app/templates"
    STATIC = "/app/static"
    BOOTSTRAP_UTIL = "bootstrap-email"

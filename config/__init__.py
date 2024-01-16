import os

IS_WINDOWS = os.name == "nt"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if IS_WINDOWS:
    DATA = os.path.join(BASE_DIR, "data")
    DATABASE_URI = "postgresql://root:root@localhost:5432/rightmove"
    TEMPLATES = os.path.join(BASE_DIR, "templates")
    STATIC = os.path.join(BASE_DIR, "static")
    BOOTSTRAP_UTIL = "bootstrap-email.bat"
else:
    DATA = "/data"
    DATABASE_URI = "postgresql://root:root@pgvector:5432/rightmove"
    TEMPLATES = "/app/templates"
    STATIC = "/app/static"
    BOOTSTRAP_UTIL = "bootstrap-email"

from sqlmodel import create_engine, SQLModel
from models import PropertyLocation, PropertyData, PropertyImages

models = [PropertyLocation, PropertyData, PropertyImages]

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=False)

SQLModel.metadata.create_all(engine)

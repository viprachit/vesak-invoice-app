"""
Import clients from CSV or Excel into PostgreSQL.

Usage:
python -m backend.import_clients path/to/clients.csv
or
python -m backend.import_clients path/to/clients.xlsx
"""

import sys
import pandas as pd
from .db import SessionLocal, engine
from . import models

# Create tables if they do not exist
models.Base.metadata.create_all(bind=engine)

def import_file(file_path: str):
    if file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
    elif file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        raise ValueError("Only CSV or XLSX files are supported")

    df = df.fillna("")

    db = SessionLocal()

    for _, row in df.iterrows():
        client = models.Client(
            name=str(row.get("name") or row.get("Name") or "").strip(),
            phone=str(row.get("phone") or row.get("Phone") or "").strip(),
            email=str(row.get("email") or row.get("Email") or "").strip(),
            address=str(row.get("address") or row.get("Address") or "").strip(),
            notes=str(row.get("notes") or row.get("Notes") or "").strip(),
        )

        if client.name:  # skip empty rows
            db.add(client)

    db.commit()
    db.close()

    print("✅ Import completed successfully")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("❌ Usage: python -m app.import_clients path/to/file.csv")
        sys.exit(1)

    import_file(sys.argv[1])

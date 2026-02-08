from sqlalchemy.orm import Session
from . import models, schemas

def get_clients(db: Session, skip: int = 0, limit: int = 1000):
    return db.query(models.Client).offset(skip).limit(limit).all()

def get_client(db: Session, client_id: int):
    return db.query(models.Client).filter(models.Client.id == client_id).first()

def create_client(db: Session, client: schemas.ClientCreate):
    db_client = models.Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

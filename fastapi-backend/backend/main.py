from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .db import SessionLocal, engine
from . import models, crud

# Create DB tables (safe to call multiple times)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Vesak Invoice App")

templates = Jinja2Templates(directory="backend/templates")

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    clients = crud.get_clients(db)
    return templates.TemplateResponse(
        "base.html",
        {
            "request": request,
            "clients": clients
        }
    )

@app.get("/client/{client_id}", response_class=HTMLResponse)
def view_client(client_id: int, request: Request, db: Session = Depends(get_db)):
    client = crud.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return templates.TemplateResponse(
        "invoice.html",
        {
            "request": request,
            "client": client
        }
    )

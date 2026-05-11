from __future__ import annotations

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import models
from backend.database import Base, engine
from backend.init_data import inicializar_datos
from backend.routers import categorias, compras, gasolina, productos, reportes, tasas, ventas


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("BODEGA_AUTO_INIT", "1") == "1":
        inicializar_datos()
    yield


app = FastAPI(
    title="Bodega Inventario API",
    version="1.0.0",
    description="Sistema de inventario para bodega con FastAPI, SQLite y JavaScript vanilla.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "service": "bodega-api"}


app.include_router(tasas.router, prefix="/api")
app.include_router(categorias.router, prefix="/api")
app.include_router(productos.router, prefix="/api")
app.include_router(compras.router, prefix="/api")
app.include_router(ventas.router, prefix="/api")
app.include_router(gasolina.router, prefix="/api")
app.include_router(reportes.router, prefix="/api")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

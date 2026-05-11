import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Asegurar que backend/ está en el path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from init_data import inicializar_datos
from routers import categorias, compras, gasolina, productos, reportes, tasas, ventas
from routers import compras_oro

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    inicializar_datos()
    yield


app = FastAPI(
    title="Bodega Inventario",
    version="2.0.0",
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
    return {"status": "ok", "service": "bodega-api", "version": "2.0.0"}

app.include_router(productos.router, prefix="/api")
app.include_router(categorias.router, prefix="/api")
app.include_router(compras.router, prefix="/api")
app.include_router(ventas.router, prefix="/api")
app.include_router(gasolina.router, prefix="/api")
app.include_router(reportes.router, prefix="/api")
app.include_router(tasas.router, prefix="/api")
app.include_router(compras_oro.router, prefix="/api")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

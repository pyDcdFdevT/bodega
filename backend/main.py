from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import Base, apply_schema_patches, engine
from init_data import inicializar_datos
from routers import (
    activos,
    apertura,
    auth,
    categorias,
    cierre,
    cobros,
    compras,
    compras_oro,
    fundicion,
    gasolina,
    gastos,
    productos,
    reportes,
    salidas,
    tasas,
    transacciones,
    ventas,
)


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    apply_schema_patches()
    if os.getenv("BODEGA_AUTO_INIT", "1") == "1":
        inicializar_datos()
    yield


app = FastAPI(
    title="Bodega POS",
    version="3.0.0",
    description="Punto de venta e inventario: bodega, gasolina, oro, gastos y cierre.",
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


app.include_router(auth.router, prefix="/api")
app.include_router(productos.router, prefix="/api")
app.include_router(categorias.router, prefix="/api")
app.include_router(compras.router, prefix="/api")
app.include_router(compras_oro.router, prefix="/api")
app.include_router(ventas.router, prefix="/api")
app.include_router(cobros.router, prefix="/api")
app.include_router(salidas.router, prefix="/api")
app.include_router(gasolina.router, prefix="/api")
app.include_router(gastos.router, prefix="/api")
app.include_router(activos.router, prefix="/api")
app.include_router(cierre.router, prefix="/api")
app.include_router(apertura.router, prefix="/api")
app.include_router(fundicion.router, prefix="/api")
app.include_router(reportes.router, prefix="/api")
app.include_router(tasas.router, prefix="/api")
app.include_router(transacciones.router, prefix="/api")

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

# test persistence
# force deploy Thu May 14 19:35:47 CEST 2026

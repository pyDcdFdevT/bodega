from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine
from models import Base
from init_data import inicializar_datos
from routers import productos, categorias, compras, ventas, gasolina, reportes, tasas

# Crear tablas
Base.metadata.create_all(bind=engine)

# Inicializar datos
inicializar_datos()

# App
app = FastAPI(title="🏪 Bodega Inventario", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers API
app.include_router(productos.router, prefix="/api")
app.include_router(categorias.router, prefix="/api")
app.include_router(compras.router, prefix="/api")
app.include_router(ventas.router, prefix="/api")
app.include_router(gasolina.router, prefix="/api")
app.include_router(reportes.router, prefix="/api")
app.include_router(tasas.router, prefix="/api")

# Frontend estático
import os
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "bodega-api"}

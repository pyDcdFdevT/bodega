from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _texto_requerido(valor: str) -> str:
    limpio = " ".join(valor.strip().split())
    if not limpio:
        raise ValueError("El valor no puede estar vacio")
    return limpio


class PinVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4)

    _pin = field_validator("pin")(_texto_requerido)


class TasasConfigUpdate(BaseModel):
    araparita: float = Field(..., gt=0)
    uruman: float = Field(..., gt=0)
    santa_elena_minero: float = Field(..., gt=0)
    santa_elena_fundido: float = Field(..., gt=0)


class TasaCambioOut(ORMModel):
    id: int
    nombre: str
    tasa_reales: float
    actualizado_en: datetime


class CategoriaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    icono: str = Field(default="BOX", max_length=20)
    color: str = Field(default="#D5E6F7", max_length=20)

    _nombre = field_validator("nombre")(_texto_requerido)


class CategoriaOut(ORMModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    icono: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime


class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    categoria_nombre: str = Field(..., min_length=2, max_length=100)
    presentacion: str = Field(default="unidad", min_length=2, max_length=20)
    unidades_por_bulto: float = Field(default=1, gt=0)
    stock_actual: float = Field(default=0, ge=0)
    stock_minimo: float = Field(default=5, ge=0)
    precio_venta_oro: float = Field(..., ge=0)

    _nombre = field_validator("nombre")(_texto_requerido)
    _categoria = field_validator("categoria_nombre")(_texto_requerido)
    _presentacion = field_validator("presentacion")(_texto_requerido)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    categoria_nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    presentacion: Optional[str] = Field(default=None, min_length=2, max_length=20)
    unidades_por_bulto: Optional[float] = Field(default=None, gt=0)
    stock_actual: Optional[float] = Field(default=None, ge=0)
    stock_minimo: Optional[float] = Field(default=None, ge=0)
    precio_venta_oro: Optional[float] = Field(default=None, ge=0)
    activo: Optional[bool] = None

    @field_validator("nombre", "categoria_nombre", "presentacion")
    @classmethod
    def limpiar_opcionales(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return valor
        return _texto_requerido(valor)


class ItemVenta(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)


class VentaCreate(BaseModel):
    items: List[ItemVenta] = Field(..., min_length=1)
    tasa_cambio_id: int = Field(..., gt=0)
    tipo_pago: str = Field(..., min_length=3, max_length=20)
    cliente: str = Field(default="Mostrador", max_length=100)
    monto_recibido_oro: float = Field(default=0, ge=0)
    monto_recibido_reales: float = Field(default=0, ge=0)

    _tipo_pago = field_validator("tipo_pago")(_texto_requerido)
    _cliente = field_validator("cliente")(_texto_requerido)


class CompraCreate(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)
    tipo_cantidad: str = Field(default="bulto", min_length=4, max_length=20)
    precio_reales: float = Field(..., gt=0)
    proveedor: str = Field(default="Proveedor", max_length=100)
    observaciones: Optional[str] = Field(default=None, max_length=500)

    _tipo_cantidad = field_validator("tipo_cantidad")(_texto_requerido)
    _proveedor = field_validator("proveedor")(_texto_requerido)


class GasolinaVenta(BaseModel):
    litros: float = Field(..., gt=0)
    tasa_cambio_id: int = Field(..., gt=0)
    tipo_pago: str = Field(default="oro", min_length=3, max_length=20)
    monto_recibido_oro: float = Field(default=0, ge=0)
    monto_recibido_reales: float = Field(default=0, ge=0)

    _tipo_pago = field_validator("tipo_pago")(_texto_requerido)


class GasolinaConfigUpdate(BaseModel):
    tipo: str = Field(default="Gasolina", min_length=3, max_length=50)
    litros_disponibles: Optional[float] = Field(default=None, ge=0)
    precio_por_litro_oro: Optional[float] = Field(default=None, ge=0)

    _tipo = field_validator("tipo")(_texto_requerido)


class CompraOroCreate(BaseModel):
    tipo_oro: str = Field(..., min_length=3, max_length=50)
    gramos: float = Field(..., gt=0)
    tasa_compra_reales: float = Field(..., gt=0)

    _tipo_oro = field_validator("tipo_oro")(_texto_requerido)


class CompraOroOut(ORMModel):
    id: int
    tipo_oro: str
    gramos: float
    tasa_compra_reales: float
    total_reales: float
    fecha: datetime


class SalidaCreate(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)
    motivo: str = Field(..., min_length=3, max_length=50)

    _motivo = field_validator("motivo")(_texto_requerido)


class SalidaOut(ORMModel):
    id: int
    producto_id: int
    cantidad: float
    valor_oro: float
    motivo: str
    fecha: datetime

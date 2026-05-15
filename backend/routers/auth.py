from fastapi import APIRouter, Depends, HTTPException

from routers.deps import require_admin
from schemas import PinCambioRequest, PinVerifyRequest
from services.pin_store import guardar_pins, obtener_pins

router = APIRouter(prefix="/auth", tags=["Auth"])


def _verificar_rol_pin(pin: str) -> str | None:
    pins = obtener_pins()
    if pin == pins["admin"]:
        return "admin"
    if pin == pins["vendedor"]:
        return "vendedor"
    return None


@router.post("/verificar-pin")
def verificar_pin(data: PinVerifyRequest):
    pin = data.pin.strip()
    rol = _verificar_rol_pin(pin)
    if rol:
        return {"acceso": True, "rol": rol}
    return {"acceso": False}


@router.post("/cambiar-pines")
def cambiar_pines(
    data: PinCambioRequest,
    _rol: str = Depends(require_admin),
):
    pins = obtener_pins()
    if data.pin_admin_actual != pins["admin"]:
        raise HTTPException(status_code=400, detail="PIN Admin actual incorrecto")
    if data.pin_vendedor_actual != pins["vendedor"]:
        raise HTTPException(status_code=400, detail="PIN Vendedor actual incorrecto")
    if data.pin_admin_nuevo == data.pin_vendedor_nuevo:
        raise HTTPException(status_code=400, detail="Los PIN Admin y Vendedor deben ser distintos")
    guardar_pins(data.pin_admin_nuevo, data.pin_vendedor_nuevo)
    return {"status": "success", "message": "PINs actualizados correctamente"}

from fastapi import APIRouter

from schemas import PinVerifyRequest

router = APIRouter(prefix="/auth", tags=["Auth"])

PIN_ADMIN = "1696"
PIN_VENDEDOR = "1111"


@router.post("/verificar-pin")
def verificar_pin(data: PinVerifyRequest):
    pin = data.pin.strip()
    if pin == PIN_ADMIN:
        return {"acceso": True, "rol": "admin"}
    if pin == PIN_VENDEDOR:
        return {"acceso": True, "rol": "vendedor"}
    return {"acceso": False}

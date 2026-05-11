from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import PinVerifyRequest


router = APIRouter(prefix="/auth", tags=["Auth"])

PIN_SISTEMA = "1696"


@router.post("/verificar-pin")
def verificar_pin(data: PinVerifyRequest, db: Session = Depends(get_db)):
    _ = db
    return {"acceso": data.pin == PIN_SISTEMA}

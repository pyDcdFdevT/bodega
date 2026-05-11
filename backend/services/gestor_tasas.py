from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from backend.models import LogTasaCambio, TasaCambio


class GestorTasas:
    def __init__(self, db: Session):
        self.db = db

    def obtener_actual(self) -> TasaCambio | None:
        return (
            self.db.query(TasaCambio)
            .filter(TasaCambio.activo.is_(True))
            .order_by(TasaCambio.created_at.desc(), TasaCambio.id.desc())
            .first()
        )

    def establecer_inicial(self, tasa_reales: float, motivo: str = "Inicio del dia") -> TasaCambio:
        if tasa_reales <= 0:
            raise ValueError("La tasa debe ser positiva")
        if tasa_reales < 10 or tasa_reales > 100:
            raise ValueError(f"Tasa sospechosa: {tasa_reales}")

        actual = self.obtener_actual()
        if actual:
            actual.activo = False
            self.db.add(
                LogTasaCambio(
                    tasa_anterior=actual.tasa_reales,
                    tasa_nueva=tasa_reales,
                    variacion_porcentaje=round(((tasa_reales - actual.tasa_reales) / actual.tasa_reales) * 100, 2),
                    motivo=motivo,
                )
            )

        nueva = TasaCambio(fecha=date.today(), tasa_reales=tasa_reales, activo=True)
        self.db.add(nueva)
        self.db.flush()
        return nueva

    def actualizar(self, nueva_tasa: float, motivo: str = "Actualizacion manual") -> dict:
        if nueva_tasa <= 0:
            raise ValueError("La tasa debe ser positiva")

        anterior = self.obtener_actual()
        if not anterior:
            raise ValueError("Configure una tasa inicial primero")
        if anterior.tasa_reales == nueva_tasa:
            raise ValueError("La tasa nueva es igual a la actual")
        if nueva_tasa < 10 or nueva_tasa > 100:
            raise ValueError(f"Tasa sospechosa: {nueva_tasa}")

        variacion = round(((nueva_tasa - anterior.tasa_reales) / anterior.tasa_reales) * 100, 2)
        self.db.add(
            LogTasaCambio(
                tasa_anterior=anterior.tasa_reales,
                tasa_nueva=nueva_tasa,
                variacion_porcentaje=variacion,
                motivo=motivo,
            )
        )

        anterior.activo = False
        nueva = TasaCambio(fecha=date.today(), tasa_reales=nueva_tasa, activo=True)
        self.db.add(nueva)
        self.db.flush()

        return {
            "tasa_anterior": anterior.tasa_reales,
            "tasa_nueva": nueva_tasa,
            "variacion": variacion,
            "fecha": nueva.fecha.isoformat(),
        }

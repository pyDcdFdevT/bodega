from __future__ import annotations

from sqlalchemy.orm import Session

from models import LogTasaCambio, TasaCambio
from services.calculos import CalculosMonetarios


class GestorTasas:
    def __init__(self, db: Session):
        self.db = db

    def listar(self) -> list[TasaCambio]:
        return CalculosMonetarios.listar_tasas(self.db)

    def actualizar_bloque(self, nuevas_tasas: dict[str, float]) -> list[TasaCambio]:
        tasas = {tasa.nombre: tasa for tasa in self.listar()}

        for nombre, tasa_nueva in nuevas_tasas.items():
            if nombre not in tasas:
                self.db.add(TasaCambio(nombre=nombre, tasa_reales=tasa_nueva))
                continue

            tasa_actual = tasas[nombre]
            if tasa_actual.tasa_reales != tasa_nueva:
                variacion = round(((tasa_nueva - tasa_actual.tasa_reales) / tasa_actual.tasa_reales) * 100, 2)
                self.db.add(
                    LogTasaCambio(
                        nombre_tasa=nombre,
                        tasa_anterior=tasa_actual.tasa_reales,
                        tasa_nueva=tasa_nueva,
                        variacion_porcentaje=variacion,
                        motivo="Actualizacion masiva",
                    )
                )
                tasa_actual.tasa_reales = tasa_nueva

        self.db.flush()
        return self.listar()

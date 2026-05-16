"""Rango de fechas para listados de historial (día / mes / año)."""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta


def rango_filtro_historial(
    anio: int | None,
    mes: int | None,
    dia: int | None,
) -> tuple[datetime, datetime]:
    """
    Devuelve [inicio, fin) en UTC naive (coherente con fechas almacenadas).
    - Solo año: todo el año.
    - Año + mes: todo el mes.
    - Año + mes + día: ese día calendario UTC.
  """
    hoy = datetime.now(UTC).replace(tzinfo=None)
    y = int(anio if anio is not None else hoy.year)
    if mes is None and dia is None:
        inicio = datetime(y, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        fin = datetime(y + 1, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        return inicio, fin
    m = int(mes if mes is not None else hoy.month)
    if dia is None:
        inicio = datetime(y, m, 1, tzinfo=UTC).replace(tzinfo=None)
        if m == 12:
            fin = datetime(y + 1, 1, 1, tzinfo=UTC).replace(tzinfo=None)
        else:
            fin = datetime(y, m + 1, 1, tzinfo=UTC).replace(tzinfo=None)
        return inicio, fin
    d = int(dia)
    max_d = monthrange(y, m)[1]
    d = min(max(d, 1), max_d)
    inicio = datetime(y, m, d, tzinfo=UTC).replace(tzinfo=None)
    fin = inicio + timedelta(days=1)
    return inicio, fin

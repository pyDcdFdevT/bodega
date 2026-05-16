from datetime import timedelta

ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def _abrir_caja(client):
    return client.post(
        "/api/apertura/",
        headers=ADMIN_HEADERS,
        json={
            "caja_inicial_reales": 500.0,
            "oro_operativo_inicial": 10.0,
            "abierto_por": "Cierre test",
        },
    )


def test_get_cierre_dia_devuelve_payload(client):
    r = client.get("/api/cierre/dia")
    assert r.status_code == 200
    data = r.json()
    assert "fecha" in data
    assert "bodega" in data
    assert "conciliacion" in data
    assert "cierre_guardado" in data


def test_get_cierre_apertura_misma_estructura_que_apertura(client):
    r = client.get("/api/cierre/apertura")
    assert r.status_code == 200
    data = r.json()
    assert "fecha_operativa" in data
    assert "apertura_hoy" in data


def test_post_generar_cierre_sin_admin_devuelve_403(client):
    r = client.post(
        "/api/cierre/generar",
        json={
            "cerrado_por": "X",
            "reales_contados": 0,
            "oro_contado": 0,
        },
    )
    assert r.status_code == 403


def test_post_generar_cierre_sin_apertura_devuelve_400(client):
    r = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Tester",
            "reales_contados": 500.0,
            "oro_contado": 10.0,
        },
    )
    assert r.status_code == 400


def test_post_generar_cierre_con_apertura_usa_conciliacion(client):
    assert _abrir_caja(client).status_code == 200
    dia = client.get("/api/cierre/dia").json()
    conc = dia["conciliacion"]
    r = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Tester cierre",
            "reales_contados": float(conc["reales_esperados"]),
            "oro_contado": float(conc["oro_esperado"]),
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "success"
    assert "cierre_id" in out
    assert out["cierre"]["reales_contados"] == float(conc["reales_esperados"])

    dup = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Otro",
            "reales_contados": 1.0,
            "oro_contado": 1.0,
        },
    )
    assert dup.status_code == 400


def test_generar_cierre_retiro_fundicion_crea_lote(client):
    assert _abrir_caja(client).status_code == 200
    if client.get("/api/cierre/dia").json().get("cierre_guardado"):
        client.post("/api/cierre/reabrir", headers=ADMIN_HEADERS)
    dia = client.get("/api/cierre/dia").json()
    conc = dia["conciliacion"]
    bruto = float(dia["oro_recolectado"]["bruto_total_gramos"])
    r = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Tester fundicion",
            "reales_contados": float(conc["reales_esperados"]),
            "oro_contado": float(conc["oro_esperado"]),
            "retirar_oro_para_fundicion": True,
        },
    )
    if bruto <= 0:
        assert r.status_code == 400
        return
    assert r.status_code == 200
    out = r.json()
    assert out.get("lote_fundicion_id")
    lotes = client.get("/api/fundicion/lotes").json()
    lote = next((x for x in lotes if x["id"] == out["lote_fundicion_id"]), None)
    assert lote is not None
    assert lote["estado"] == "ACUMULANDO"
    assert float(lote["gramos_brutos"]) == bruto
    assert "Cierre del" in lote["origen"]


def test_cierre_retiro_ignora_lotes_de_dias_anteriores(client):
    from database import SessionLocal
    from models import LoteOro
    from services.operativa import _inicio_dia_hoy

    assert _abrir_caja(client).status_code == 200
    if client.get("/api/cierre/dia").json().get("cierre_guardado"):
        client.post("/api/cierre/reabrir", headers=ADMIN_HEADERS)

    ayer = _inicio_dia_hoy() - timedelta(days=1)
    db = SessionLocal()
    try:
        db.add(
            LoteOro(
                gramos_brutos=5.49,
                origen="Lote dia anterior",
                estado="ACUMULANDO",
                fecha=ayer,
            )
        )
        db.commit()
    finally:
        db.close()

    dia = client.get("/api/cierre/dia").json()
    bruto = float(dia["oro_recolectado"]["bruto_total_gramos"])
    if bruto <= 0:
        return
    conc = dia["conciliacion"]
    r = client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Tester lotes viejos",
            "reales_contados": float(conc["reales_esperados"]),
            "oro_contado": float(conc["oro_esperado"]),
            "retirar_oro_para_fundicion": True,
        },
    )
    assert r.status_code == 200, r.text


def test_oro_disponible_recolectado_solo_resta_lotes_hoy():
    from datetime import date, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from database import Base
    from models import LoteOro
    from services.oro_lotes import gramos_oro_en_lotes, oro_disponible_recolectado

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    hoy = date(2026, 5, 15)
    ayer_dt = datetime(2026, 5, 14, 12, 0, 0)
    hoy_dt = datetime(2026, 5, 15, 10, 0, 0)
    db.add(LoteOro(gramos_brutos=5.49, origen="viejo", estado="ACUMULANDO", fecha=ayer_dt))
    db.add(LoteOro(gramos_brutos=1.0, origen="hoy", estado="ACUMULANDO", fecha=hoy_dt))
    db.commit()
    assert gramos_oro_en_lotes(db, hoy) == 1.0
    assert gramos_oro_en_lotes(db) == round(6.49, 4)
    assert oro_disponible_recolectado(db, hoy, 3.55) == 2.55
    db.close()
    engine.dispose()


def test_balance_excluye_oro_en_lotes(client):
    from services.balance import build_balance_general
    from database import SessionLocal

    assert _abrir_caja(client).status_code == 200
    dia = client.get("/api/cierre/dia").json()
    bruto = float(dia["oro_recolectado"]["bruto_total_gramos"])
    if bruto <= 0:
        return
    conc = dia["conciliacion"]
    client.post(
        "/api/fundicion/lotes",
        headers=ADMIN_HEADERS,
        json={"gramos_brutos": min(bruto, 1.0), "origen": "Test balance", "estado": "ACUMULANDO"},
    )
    db = SessionLocal()
    try:
        bal = build_balance_general(db)
        oro = bal["activos"]["oro"]
        assert float(oro["gramos_en_lotes"]) >= min(bruto, 1.0) - 0.0001
        assert float(oro["gramos"]) <= float(oro["gramos_operativo"]) + 0.0001
    finally:
        db.close()

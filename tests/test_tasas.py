def test_actualizar_tasas_modifica_valores(client):
    body = {
        "araparita": 37.5,
        "uruman": 38.0,
        "santa_elena_minero": 35.0,
        "santa_elena_fundido": 39.0,
    }
    response = client.put("/api/tasas", json=body)
    assert response.status_code == 200
    tasas = {item["nombre"]: item["tasa_reales"] for item in client.get("/api/tasas").json()}
    assert tasas["araparita"] == 37.5
    assert tasas["uruman"] == 38.0


def test_listar_tasas_devuelve_cuatro(client):
    tasas = client.get("/api/tasas").json()
    assert len(tasas) == 4
    nombres = {t["nombre"] for t in tasas}
    assert nombres == {"araparita", "uruman", "santa_elena_minero", "santa_elena_fundido"}

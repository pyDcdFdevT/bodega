def test_actualizar_tasa_modifica_tasa_actual(client):
    response = client.put(
        "/api/tasas/actualizar",
        json={"tasa_reales": 38.5, "motivo": "Ajuste de mercado"},
    )

    assert response.status_code == 200
    actual = client.get("/api/tasas/actual").json()
    assert actual["configurado"] is True
    assert actual["tasa"] == 38.5


def test_actualizar_tasa_igual_devuelve_error_y_conserva_tasa(client):
    first = client.put(
        "/api/tasas/actualizar",
        json={"tasa_reales": 39.0, "motivo": "Primer ajuste"},
    )
    second = client.put(
        "/api/tasas/actualizar",
        json={"tasa_reales": 39.0, "motivo": "Repetida"},
    )
    actual = client.get("/api/tasas/actual").json()

    assert first.status_code == 200
    assert second.status_code == 400
    assert actual["tasa"] == 39.0

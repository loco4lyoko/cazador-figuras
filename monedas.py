"""Tipos de cambio (gratis, sin clave) con respaldo guardado."""
from __future__ import annotations

import time

import requests

URL = "https://open.er-api.com/v6/latest/JPY"
# Respaldo aproximado por si la API falla el primer día (1 JPY = X)
RESPALDO = {"JPY": 1.0, "CLP": 6.3, "USD": 0.0066, "CNY": 0.047, "EUR": 0.0061}


def actualizar(guardadas: dict | None) -> dict:
    """Devuelve {'base': 'JPY', 'tasas': {...}, 'fecha': ts}. Refresca cada 12 h."""
    if guardadas and time.time() - guardadas.get("fecha", 0) < 12 * 3600:
        return guardadas
    try:
        r = requests.get(URL, timeout=15)
        d = r.json()
        if d.get("result") == "success":
            return {"base": "JPY", "tasas": d["rates"], "fecha": time.time()}
    except Exception:
        pass
    return guardadas or {"base": "JPY", "tasas": RESPALDO, "fecha": 0}


def convertir(monto: float | None, de: str, a: str, tasas: dict) -> float | None:
    if monto is None:
        return None
    t = tasas["tasas"]
    if de not in t or a not in t:
        return None
    return monto / t[de] * t[a]


def formato(monto: float | None, moneda: str) -> str:
    if monto is None:
        return "?"
    if moneda == "JPY":
        return f"¥{monto:,.0f}"
    if moneda == "CLP":
        return f"${monto:,.0f} CLP".replace(",", ".")
    if moneda == "USD":
        return f"US${monto:,.2f}"
    return f"{monto:,.2f} {moneda}"

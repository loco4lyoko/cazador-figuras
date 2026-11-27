"""Escucha tu Telegram: cuando escribes "ps5", rastrea en ese momento y responde."""
from __future__ import annotations

import html
import os
import time

import requests

from .avisos import _telegram
from .ps5 import BUSQUEDAS, EXCLUIR, MINIMOS, buscar, tipo

NOMBRES = {"disco": "💿 PS5 con disco / lector", "digital": "📱 PS5 digital", "lector": "🔌 Lector suelto"}
DURACION = 5.7 * 3600  # GitHub corta los trabajos a las 6 horas


def clp(n: float) -> str:
    return "$" + f"{n:,.0f}".replace(",", ".")


def rastrear() -> str:
    grupos, errores, vistos, total = {}, [], set(), 0
    for q, minimo, maximo in BUSQUEDAS:
        try:
            res = buscar(q, minimo, maximo)
        except Exception as e:
            errores.append(str(e))
            continue
        total += len(res)
        for l in res:
            tp = tipo(l.titulo)
            if (not tp or l.id in vistos or not l.precio or l.precio < MINIMOS[tp]
                    or EXCLUIR.search(l.titulo)):
                continue
            vistos.add(l.id)
            grupos.setdefault(tp, []).append(l)
    partes = [f"📊 Rastreo {time.strftime('%H:%M:%S')} (Mercado Libre, {total} resultados)"]
    for tp, nombre in NOMBRES.items():
        if tp in grupos:
            partes.append(f"\n<b>{nombre}</b>")
            for l in sorted(grupos[tp], key=lambda x: x.precio)[:3]:
                partes.append(f'<b>{clp(l.precio)}</b> <a href="{html.escape(l.url)}">'
                              f"{html.escape(l.titulo[:70])}</a>")
    if not grupos:
        partes.append("Sin resultados válidos.")
    if errores:
        partes.append("⚠️ Falló: " + html.escape(errores[0][:150]))
    return "\n".join(partes)


def main() -> None:
    token, chat = os.environ["TELEGRAM_TOKEN"], str(os.environ["TELEGRAM_CHAT_ID"])
    api = f"https://api.telegram.org/bot{token}/getUpdates"
    # Ignora mensajes antiguos
    r = requests.get(api, params={"offset": -1}, timeout=30).json()
    if not r.get("ok"):
        raise SystemExit(f"Telegram: {r.get('description')}")
    offset = r["result"][-1]["update_id"] + 1 if r["result"] else 0
    _telegram("sendMessage", {"text": "🟢 Listo. Escribe <b>ps5</b> y rastreo al tiro."})
    fin = time.time() + DURACION
    while time.time() < fin:
        try:
            data = requests.get(api, params={"offset": offset, "timeout": 25}, timeout=40).json()
        except (requests.RequestException, ValueError):
            time.sleep(3)
            continue
        pedido = False
        for u in data.get("result", []):
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if str(m.get("chat", {}).get("id")) == chat and "ps5" in m.get("text", "").lower():
                pedido = True
        if pedido:
            _telegram("sendMessage", {"text": "🔎 Buscando..."})
            _telegram("sendMessage", {"text": rastrear(), "disable_web_page_preview": "true"})
        if not data.get("ok"):
            time.sleep(5)
    _telegram("sendMessage", {"text": "🔴 Se apagó el rastreo a pedido. Vuelve a activarlo en GitHub Actions."})


if __name__ == "__main__":
    main()

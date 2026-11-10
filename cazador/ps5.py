"""Monitor de PS5 en Chile: avisa por Telegram cuando baja de tus precios objetivo.

Uso: python -m cazador.ps5
Guarda lo ya avisado en docs/ps5_vistos.json para no repetir alertas.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .avisos import _telegram
from .fuentes.tiendas import mercadolibre_cl

# ---- Configura aquí ----
OBJETIVOS = {
    "disco": 650_000,     # PS5 con lectora (o bundle con lector)
    "digital": 560_000,   # PS5 digital sola (necesitarías comprar lector aparte)
    "lector": 90_000,     # lector de disco suelto para PS5 digital
}
BUSQUEDAS = ["ps5 slim", "playstation 5 slim", "ps5 lector disco"]
# Palabras que descartan el aviso (accesorios, usados, importados, etc.)
EXCLUIR = re.compile(
    r"control|dualsense|joystick|carcasa|cover|funda|base|soporte|cargador|juego|game|"
    r"usad|reacondicionad|repuesto|ventilador|skin|cable|pro\b|portal|vr|audifono|"
    r"estados unidos|importad", re.I)
# -------------------------

VISTOS = Path("docs/ps5_vistos.json")


def tipo(titulo: str) -> str | None:
    t = titulo.lower()
    if "lector" in t and ("consola" not in t):
        return "lector"
    if "digital" in t:
        return "digital"
    if "ps5" in t or "playstation 5" in t:
        return "disco"
    return None


def main() -> None:
    vistos = json.loads(VISTOS.read_text()) if VISTOS.exists() else {}
    nuevos = []
    for q in BUSQUEDAS:
        try:
            resultados = mercadolibre_cl(q)
        except Exception as e:  # una búsqueda caída no frena las demás
            print("[ps5] error en", q, e)
            continue
        for l in resultados:
            if not l.precio:
                continue
            tp = tipo(l.titulo)
            ok_excluir = tp == "lector" or not EXCLUIR.search(l.titulo)
            if tp and ok_excluir and l.precio <= OBJETIVOS[tp]:
                # Vuelve a avisar solo si el precio bajó respecto al último aviso
                if l.id in vistos and vistos[l.id] <= l.precio:
                    continue
                vistos[l.id] = l.precio
                nuevos.append((tp, l))
    for tp, l in sorted(nuevos, key=lambda x: x[1].precio):
        _telegram("sendMessage", {
            "text": f"🎮 <b>PS5 {tp} bajo tu objetivo</b>\n{l.titulo}\n"
                    f"<b>${l.precio:,.0f}</b> (objetivo ${OBJETIVOS[tp]:,.0f})\n{l.url}".replace(",", "."),
            "disable_web_page_preview": "false",
        })
    print(f"[ps5] {len(nuevos)} avisos nuevos")
    VISTOS.parent.mkdir(exist_ok=True)
    VISTOS.write_text(json.dumps(vistos, indent=1))


if __name__ == "__main__":
    main()

"""Monitor de PS5 en Chile: avisa por Telegram cuando baja de tus precios objetivo.

Uso: python -m cazador.ps5
Guarda lo ya avisado en docs/ps5_vistos.json para no repetir alertas.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

from .avisos import _telegram
from .fuentes.tiendas import _armar, _slug, descargar, tarjetas

# ---- Configura aquí ----
OBJETIVOS = {
    "disco": 650_000,     # PS5 con lectora (o bundle con lector)
    "digital": 560_000,   # PS5 digital sola (necesitarías comprar lector aparte)
    "lector": 90_000,     # lector de disco suelto para PS5 digital
}
# (búsqueda, precio mínimo, precio máximo): el rango deja fuera los accesorios
BUSQUEDAS = [
    ("ps5 slim", 350_000, 750_000),
    ("consola playstation 5", 350_000, 750_000),
    ("lector de disco ps5 slim", 50_000, 130_000),
]
MINIMOS = {"disco": 350_000, "digital": 350_000, "lector": 50_000}
# Descarta consolas usadas, Pro, Portal e importadas (los packs con juegos o control SÍ valen)
EXCLUIR = re.compile(
    r"usad|reacondicionad|seminuev|open box|caja abierta|repuesto|\bpro\b|portal|ps4|"
    r"estados unidos|importad", re.I)
# -------------------------

VISTOS = Path("docs/ps5_vistos.json")


def tipo(titulo: str) -> str | None:
    t = titulo.lower()
    es_lector = re.search(r"lector|unidad de disco", t)
    if es_lector and not re.search(r"consola|digital \+|\+ lector", t):
        return "lector"
    if not re.search(r"ps ?5|playstation ?5", t):
        return None
    if "digital" in t and not es_lector:
        return "digital"
    return "disco"


def buscar(consulta: str, minimo: int, maximo: int) -> list:
    url = (f"https://listado.mercadolibre.cl/{_slug(consulta)}"
           f"_PriceRange_{minimo}CLP-{maximo}CLP_NoIndex_True")
    html = descargar(url, headers={"Accept-Language": "es-CL,es;q=0.9"})
    out = []
    for t in tarjetas(html, "https://www.mercadolibre.cl", r"(MLC-?\d{6,})"):
        t["id"] = t["id"].replace("-", "")
        # El primer monto no tachado es el precio actual
        precio = None
        for frac in t["nodo"].find_all(class_=re.compile("andes-money-amount__fraction")):
            if not frac.find_parent("s"):
                precio = frac.get_text(strip=True)
                break
        l = _armar("mercadolibre_cl", t, precio, "CLP")
        if l:
            usado = re.search(r"\busado\b|reacondicionado|internacional", t["texto"], re.I)
            if not usado:
                out.append(l)
    return out


def main() -> None:
    vistos = json.loads(VISTOS.read_text()) if VISTOS.exists() else {}
    nuevos = []
    mejores = {}
    total = 0
    for q, minimo, maximo in BUSQUEDAS:
        try:
            resultados = buscar(q, minimo, maximo)
        except Exception as e:  # una búsqueda caída no frena las demás
            print("[ps5] error en", q, e)
            continue
        total += len(resultados)
        print(f"[ps5] {q}: {len(resultados)} resultados")
        for l in resultados:
            tp = tipo(l.titulo)
            if not tp or not l.precio or l.precio < MINIMOS[tp] or EXCLUIR.search(l.titulo):
                continue
            if tp not in mejores or l.precio < mejores[tp].precio:
                mejores[tp] = l
            if l.precio <= OBJETIVOS[tp]:
                # Vuelve a avisar solo si el precio bajó respecto al último aviso
                if l.id in vistos and vistos[l.id] <= l.precio:
                    continue
                vistos[l.id] = l.precio
                nuevos.append((tp, l))
    for tp, l in mejores.items():
        print(f"[ps5] mejor {tp}: {l.precio:,.0f} | {l.titulo} | {l.url}")
    if os.getenv("RESUMEN") == "1":
        lineas = [f"• {tp}: <b>${l.precio:,.0f}</b>".replace(",", ".") + f"\n{html.escape(l.titulo)}\n{l.url}"
                  for tp, l in mejores.items()]
        _telegram("sendMessage", {"text": f"📊 PS5: {total} resultados revisados\n" +
                  ("\n".join(lineas) or "Sin resultados: puede que Mercado Libre esté bloqueando.")})
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

"""Monitor de preventas: avisa por Telegram apenas una tienda abre la reserva de una figura.

Uso: python -m cazador.preventas
Guarda lo ya avisado en docs/preventas_vistos.json para no repetir alertas.
Primer objetivo: OPAPA TOYS x M9 Studio 1/6 "Hot Explorer" (Lara) — versión Deluxe (G2026018),
la que trae el traje de buceo + el de jungla.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from .avisos import telegram_texto
from .fuentes.base import _contenedor, sesion

# ---------------- Configura aquí ----------------
FIGURA = "OPAPA x M9 Studio 1/6 Lara \"Hot Explorer\" — Deluxe (buceo + jungla)"

# Un link cuenta como "la figura" si su texto/URL calza con esto…
RX_FIGURA = re.compile(r"hot[\s\-_]*explorer|lara[\s\-_]*hot|p?g[\s\-_]*2026[\s\-_]*0?1[678]\b", re.I)
# …y, en sitios que venden de todo (eBay, buscadores), además debe mencionar la marca
RX_MARCA = re.compile(r"opapa|opa[\s\-]*toys|m9[\s\-]*studio", re.I)

# Versión de cada listado (el código 018 es la Deluxe; ojo: 017 es la Jungla)
VERSIONES = [
    ("deluxe", re.compile(r"deluxe|luxury|豪华|p?g[\s\-_]*2026[\s\-_]*0?18\b", re.I)),
    ("buceo", re.compile(r"diving|scuba|潜水|p?g[\s\-_]*2026[\s\-_]*0?16\b", re.I)),
    ("jungla", re.compile(r"jungle|丛林|p?g[\s\-_]*2026[\s\-_]*0?17\b", re.I)),
]
RX_AGOTADO = re.compile(r"sold[\s\-]*out|out of stock|agotad|no disponible|unavailable|已售罄|缺货", re.I)
RX_PRECIO = re.compile(r"(?:US\s*)?(?:\$|USD|S\$|HK\$|€|£|CLP)\s*[\d.,]+(?:\s*(?:USD|CLP))?", re.I)

# Páginas de producto ya conocidas (GunDamit las publicó y luego las ocultó: hoy redirigen al inicio)
PRODUCTOS_DIRECTOS = [
    ("GunDamit", "deluxe", "https://gundamit.com/opapa-toys-x-m9-studio-1-6-pg2026018-lara-hot-explorer-deluxe-version_p11619.html"),
    ("GunDamit", "jungla", "https://gundamit.com/opapa-toys-x-m9-studio-1-6-pg2026017-lara-hot-explorer-jungle-version_p11617.html"),
    ("GunDamit", "buceo", "https://gundamit.com/opapa-toys-x-m9-studio-1-6-pg2026016-lara-hot-explorer-diving-version_p11618.html"),
]

# Sitios que bloquean a los servidores de GitHub (HTTP 403): se revisan desde el notebook
BLOQUEADOS_EN_GITHUB = {"GunDamit", "eBay", "Oh My Primus"}

# Páginas de tiendas/listados donde aparecerá la preventa: (tienda, url, exige_marca)
PAGINAS = [
    ("GunDamit", "https://gundamit.com/c/opapa-toys_1083", False),
    ("HobbyGalaxy", "https://www.hobbygalaxy.com/opapa-toys/", False),
    ("Onesixthkit", "https://onesixthkit.com/index.php?route=product/search&search=opapa", False),
    ("Bombusbee", "https://www.bombusbee.net/?s=opapa&post_type=product", False),
    ("GianToy", "https://giantoy.com/search?q=opapa&type=product", False),
    ("Oh My Primus", "https://ohmyprimus.com/catalogsearch/result/?q=opapa", False),
    ("Pop Culture Art", "https://popculture-art.com/product-category/opapa-toys/", False),
] + [
    ("eBay", f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(q)}&_sop=10&_ipg=120", True)
    for q in ("opapa lara 1/6", "opapa hot explorer", "opapa m9 studio")
]
# --------------------------------------------------

NOTEBOOK = "--notebook" in sys.argv
VISTOS = Path("notebook/preventas_vistos.json" if NOTEBOOK else "docs/preventas_vistos.json")


def toca(tienda: str) -> bool:
    """En GitHub revisa los sitios que lo dejan; en el notebook, solo los que bloquean a GitHub."""
    return (tienda in BLOQUEADOS_EN_GITHUB) == NOTEBOOK


def version(texto: str) -> str:
    for nombre, rx in VERSIONES:
        if rx.search(texto):
            return nombre
    return "?"


def precios(texto: str) -> str:
    vistos = []
    for p in RX_PRECIO.findall(texto):
        p = p.strip()
        if p not in vistos:
            vistos.append(p)
    return " / ".join(vistos[:3])


def listados(html_txt: str, base: str, exige_marca: bool) -> list[dict]:
    """Links de una página que corresponden a la figura, con versión, precio y si está agotada."""
    sopa = BeautifulSoup(html_txt, "lxml")
    out: dict[str, dict] = {}
    for a in sopa.find_all("a", href=True):
        url = urljoin(base, a["href"]).split("#")[0]
        titulo = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
        if not titulo:
            img = a.find("img")
            titulo = (img.get("alt") if img else "") or ""
        clave = f"{titulo} {url}"
        if not RX_FIGURA.search(clave) or (exige_marca and not RX_MARCA.search(clave)):
            continue
        if "ebay.com" in url:
            url = url.split("?")[0]
        texto = _contenedor(a).get_text(" ", strip=True)
        previo = out.get(url)
        if previo and len(previo["titulo"]) >= len(titulo):
            continue
        out[url] = {"url": url, "titulo": titulo[:200], "version": version(clave),
                    "agotado": bool(RX_AGOTADO.search(texto)), "precio": precios(texto)}
    return list(out.values())


def revisar_producto(tienda: str, ver: str, url: str) -> dict | None:
    """Una página de producto concreta: ¿está publicada (no redirige) y sin agotar?"""
    r = sesion().get(url, timeout=25, allow_redirects=True)
    pid = re.search(r"_p(\d+)\.html", url)
    if r.status_code in (401, 403, 429) or r.status_code >= 500:
        raise RuntimeError(f"HTTP {r.status_code}")  # bloqueado: no confundir con "oculta"
    if r.status_code != 200 or (pid and pid.group(0) not in r.url):
        return None  # sigue oculta
    sopa = BeautifulSoup(r.text, "lxml")
    titulo = (sopa.find("h1").get_text(" ", strip=True) if sopa.find("h1") else "") or url
    cuerpo = sopa.get_text(" ", strip=True)
    agotado = bool(re.search(r"\bsold\s*out\b|out of stock", cuerpo[:20000], re.I)) and \
        not re.search(r"add to cart|pre-?order now|buy now", cuerpo, re.I)
    return {"url": url, "titulo": titulo[:200], "version": ver, "agotado": agotado,
            "precio": precios(cuerpo[:20000]), "tienda": tienda}


def mensaje(l: dict, cambio: str) -> tuple[str, bool]:
    e = html.escape
    es_deluxe = l["version"] == "deluxe"
    if es_deluxe:
        cab = "🚨🚨 <b>¡PREVENTA ABIERTA — LARA DELUXE (buceo + jungla)!</b>"
    elif l["version"] == "?":
        cab = "👀 <b>Apareció la Lara Hot Explorer (revisa qué versión es)</b>"
    else:
        cab = f"ℹ️ Preventa de la versión <b>{l['version']}</b> (no es la Deluxe)"
    lineas = [cab]
    if cambio == "volvio":
        lineas.append("🔁 Estaba agotada y volvió a estar disponible")
    lineas += [f"🏪 {e(l['tienda'])}", f"📝 {e(l['titulo'])}"]
    if l.get("precio"):
        lineas.append(f"💵 {e(l['precio'])}")
    if es_deluxe:
        lineas.append("✅ Revisa que diga Deluxe / 018 antes de pagar (017 es la de jungla).")
    lineas.append(f'\n<a href="{e(l["url"])}">👉 Abrir y reservar</a>')
    return "\n".join(lineas), not (es_deluxe or l["version"] == "?")


def main() -> None:
    if NOTEBOOK:
        from .main import cargar_env
        cargar_env()  # en el notebook las claves de Telegram están en .env
    vistos = json.loads(VISTOS.read_text()) if VISTOS.exists() else {}
    primera_vez = not vistos.get("_iniciado")
    encontrados: list[dict] = []
    estado_sitios = []

    for tienda, ver, url in PRODUCTOS_DIRECTOS:
        if not toca(tienda):
            continue
        try:
            l = revisar_producto(tienda, ver, url)
            estado_sitios.append(f"✅ {tienda} ficha {ver}: {'publicada' if l else 'aún oculta'}")
            if l:
                encontrados.append(l)
        except Exception as ex:
            estado_sitios.append(f"⚠️ {tienda} ficha {ver}: {type(ex).__name__}")
            print("[preventas]", tienda, url, ex)

    for tienda, url, exige in PAGINAS:
        if not toca(tienda):
            continue
        try:
            r = sesion().get(url, timeout=25)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            ls = listados(r.text, url, exige)
            for l in ls:
                l["tienda"] = tienda
            encontrados += ls
            estado_sitios.append(f"✅ {tienda}: {len(ls)} listado(s)")
        except Exception as ex:
            estado_sitios.append(f"⚠️ {tienda}: no se pudo revisar ({ex})"[:120])
            print("[preventas]", tienda, url, ex)

    avisos = 0
    for l in encontrados:
        antes = vistos.get(l["url"])
        ahora = "agotado" if l["agotado"] else "disponible"
        vistos[l["url"]] = ahora
        if ahora != "disponible" or antes == "disponible":
            continue
        texto, silencioso = mensaje(l, "volvio" if antes == "agotado" else "nuevo")
        telegram_texto(texto, silencioso=silencioso)
        avisos += 1

    if primera_vez:
        telegram_texto(
            f"🛰️ <b>Monitor de preventa activado{' (notebook)' if NOTEBOOK else ''}</b>\n{html.escape(FIGURA)}\n"
            + ("Reviso GunDamit y eBay cada 30 min mientras el notebook esté encendido.\n\n" if NOTEBOOK else
               "Reviso cada 20 minutos y te aviso apenas abra la reserva.\n\n")
            + "\n".join(html.escape(s) for s in estado_sitios), silencioso=True)
        vistos["_iniciado"] = datetime.now(timezone.utc).isoformat(timespec="minutes")

    print(f"[preventas] {len(encontrados)} listados, {avisos} avisos")
    print("\n".join(estado_sitios))
    VISTOS.parent.mkdir(exist_ok=True)
    VISTOS.write_text(json.dumps(vistos, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()

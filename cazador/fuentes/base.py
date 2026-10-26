"""Herramientas compartidas por todas las fuentes (descarga y lectura de HTML)."""
from __future__ import annotations

import re
import time
from typing import Callable, Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
)

_sesion: Optional[requests.Session] = None
# Última respuesta de cada sitio (para el modo diagnóstico: guarda lo que realmente se recibió)
ULTIMA: dict[str, dict] = {}


def sesion() -> requests.Session:
    global _sesion
    if _sesion is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.8,en;q=0.6,es;q=0.5",
        })
        _sesion = s
    return _sesion


def descargar(url: str, intentos: int = 2, **kw) -> str:
    ultimo = None
    for i in range(intentos):
        try:
            r = sesion().get(url, timeout=25, **kw)
            ULTIMA[urlparse(url).netloc] = {"url": r.url, "status": r.status_code, "texto": r.text[:500_000]}
            if r.status_code == 200:
                r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
                return r.text
            ultimo = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as e:  # red caída, timeout...
            ultimo = e
        time.sleep(2 * (i + 1))
    motivo = str(ultimo)
    if "403" in motivo:
        motivo = "bloqueado (HTTP 403)"
    elif "timed out" in motivo.lower() or "timeout" in motivo.lower():
        motivo = "no respondió a tiempo"
    elif len(motivo) > 120:
        motivo = type(ultimo).__name__
    raise RuntimeError(f"{motivo} — {urlparse(url).netloc}")


def _img(cont) -> str:
    for img in cont.find_all("img"):
        for attr in ("data-src", "data-original", "data-lazy", "src", "data-srcset", "srcset"):
            v = img.get(attr)
            if v and not v.startswith("data:") and "spacer" not in v and "blank" not in v:
                return v.split(",")[0].split(" ")[0]
    return ""


def _contenedor(a, max_niveles: int = 6):
    """Sube desde el link hasta el bloque que representa una 'tarjeta' de producto."""
    nodo = a
    for _ in range(max_niveles):
        padre = nodo.parent
        if padre is None or padre.name in ("body", "html", "ul", "ol", "main"):
            break
        nodo = padre
        if nodo.name in ("li", "article"):
            break
        clases = " ".join(nodo.get("class", [])).lower()
        if any(k in clases for k in ("item", "product", "card", "result", "box")) and len(nodo.find_all("a")) >= 1:
            # si ya contiene un precio, este es el bloque
            if re.search(r"[¥￥$円]|\d{1,3}(,\d{3})", nodo.get_text(" ")):
                break
    return nodo


def tarjetas(html: str, base: str, patron_link: str) -> Iterable[dict]:
    """Encuentra todos los productos de una página de resultados.

    Devuelve dicts con id, url, titulo, texto (todo el texto de la tarjeta), foto, nodo.
    Funciona aunque el sitio cambie sus clases CSS, porque se guía por la forma de los links.
    """
    sopa = BeautifulSoup(html, "lxml")
    rx = re.compile(patron_link)
    vistos: dict[str, dict] = {}
    for a in sopa.find_all("a", href=True):
        href = urljoin(base, a["href"])
        m = rx.search(href)
        if not m:
            continue
        pid = m.group(1)
        cont = _contenedor(a)
        titulo = (a.get("title") or a.get("data-auction-title") or a.get_text(" ", strip=True) or "").strip()
        if not titulo:
            img = a.find("img")
            titulo = (img.get("alt") if img else "") or ""
        previo = vistos.get(pid)
        tarjeta = {
            "id": pid,
            "url": href,
            "titulo": titulo,
            "texto": cont.get_text(" ", strip=True),
            "foto": _img(cont) or (previo or {}).get("foto", ""),
            "nodo": cont,
            "a": a,
        }
        if previo:
            # quedarse con el título más largo/útil y la tarjeta más completa
            if len(titulo) > len(previo["titulo"]):
                previo["titulo"] = titulo
            if not previo["foto"]:
                previo["foto"] = tarjeta["foto"]
            if len(tarjeta["texto"]) > len(previo["texto"]):
                previo["texto"], previo["nodo"] = tarjeta["texto"], cont
        else:
            vistos[pid] = tarjeta
    return list(vistos.values())


def primer_precio(texto: str, patrones: Iterable[str]) -> Optional[str]:
    for p in patrones:
        m = re.search(p, texto)
        if m:
            return m.group(1)
    return None


Buscador = Callable[[str], list]


def json_embebido(html: str, id_script: str = "__NEXT_DATA__"):
    """Datos JSON que las páginas modernas (Next.js) traen dentro de un <script id=...>."""
    import json
    m = re.search(rf'<script[^>]*id="{id_script}"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def buscar_dicts(obj, clave: str):
    """Recorre un JSON y devuelve todos los diccionarios que tengan `clave`."""
    out = []
    pila = [obj]
    while pila:
        o = pila.pop()
        if isinstance(o, dict):
            if clave in o:
                out.append(o)
            pila.extend(o.values())
        elif isinstance(o, list):
            pila.extend(o)
    return out


def productos_ldjson(html: str) -> list[dict]:
    """Productos del bloque estándar schema.org (ld+json) que muchas tiendas incluyen.

    Devuelve dicts con titulo, url, foto, precio, moneda."""
    import json
    out = []
    for bloque in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(bloque.strip())
        except ValueError:
            continue
        for p in buscar_dicts(data, "offers"):
            if not isinstance(p, dict) or not p.get("name"):
                continue
            ofertas = p["offers"]
            if isinstance(ofertas, list):
                ofertas = ofertas[0] if ofertas else {}
            precio = ofertas.get("price") or ofertas.get("lowPrice")
            img = p.get("image")
            if isinstance(img, list):
                img = img[0] if img else ""
            if isinstance(img, dict):
                img = img.get("url", "")
            out.append({"titulo": p["name"], "url": p.get("url") or ofertas.get("url") or "",
                        "foto": img or "", "precio": precio,
                        "moneda": ofertas.get("priceCurrency") or "JPY",
                        "agotado": "OutOfStock" in str(ofertas.get("availability", ""))})
    return [x for x in out if x["url"] and x["precio"] not in (None, "")]

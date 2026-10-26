"""Yahoo! Auctions Japón (incluye listados de Yahoo! Flea / PayPay Flea que aparecen ahí)."""
from __future__ import annotations

import re
from urllib.parse import quote

from .base import descargar, tarjetas, primer_precio
from ..modelos import Listado, parse_precio

BASE = "https://auctions.yahoo.co.jp"
PATRON = r"(?:auctions\.yahoo\.co\.jp/jp/auction/|page\.auctions\.yahoo\.co\.jp/jp/auction/|paypayfleamarket\.yahoo\.co\.jp/item/)([A-Za-z0-9]+)"


def _listados(html: str, cerrados: bool) -> list[Listado]:
    salida = []
    for t in tarjetas(html, BASE, PATRON):
        texto, a, nodo = t["texto"], t["a"], t["nodo"]
        es_flea = "paypayfleamarket" in t["url"]
        # 1) atributos data-* (diseño clásico de Yahoo)
        attrs = {}
        for el in [a] + nodo.find_all(attrs={"data-auction-id": True}):
            for k, v in el.attrs.items():
                if k.startswith("data-auction-"):
                    attrs.setdefault(k, v)
        titulo = attrs.get("data-auction-title") or t["titulo"]
        foto = attrs.get("data-auction-img") or t["foto"]
        if cerrados:
            p = primer_precio(texto, [r"落札\s*([\d,]+)\s*円", r"([\d,]+)\s*円"])
        else:
            p = attrs.get("data-auction-price") or primer_precio(
                texto, [r"現在\s*([\d,]+)\s*円", r"([\d,]+)\s*円"])
        precio = parse_precio(p)
        inmediata = attrs.get("data-auction-buynowprice") or primer_precio(texto, [r"即決\s*([\d,]+)\s*円"])
        inmediata = parse_precio(inmediata) if inmediata else None
        if inmediata == 0:
            inmediata = None
        pujas = primer_precio(texto, [r"入札\s*(\d+)", r"(\d+)\s*件?の?入札"])
        termina = primer_precio(texto, [r"(\d{1,2}/\d{1,2}\s*\d{1,2}:\d{2})\s*終了", r"残り\s*([^\s]+)"]) or ""
        if not titulo or precio is None:
            continue
        salida.append(Listado(
            fuente="yahoo",
            id=t["id"],
            titulo=titulo,
            precio=precio,
            moneda="JPY",
            url=t["url"],
            foto=foto,
            vendido=cerrados,
            subasta=not es_flea and not (inmediata and inmediata == precio),
            compra_inmediata=inmediata,
            termina=termina if not cerrados else "",
            pujas=int(pujas) if pujas and pujas.isdigit() else None,
            fecha_venta=termina if cerrados else "",
        ))
    return salida


def buscar(consulta: str) -> list[Listado]:
    q = quote(consulta)
    # s1=new&o1=d -> los más nuevos primero
    url = f"{BASE}/search/search?p={q}&va={q}&b=1&n=50&s1=new&o1=d"
    return _listados(descargar(url), cerrados=False)


def vendidos(consulta: str) -> list[Listado]:
    q = quote(consulta)
    url = f"{BASE}/closedsearch/closedsearch?p={q}&va={q}&b=1&n=100"
    return _listados(descargar(url), cerrados=True)

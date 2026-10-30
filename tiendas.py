"""Rakuma, Suruga-ya, Mandarake, eBay y MercadoLibre Chile (lectura de páginas de resultados)."""
from __future__ import annotations

import re
from urllib.parse import quote, quote_plus

from .base import descargar, tarjetas, primer_precio, productos_ldjson
from ..modelos import Listado, parse_precio

YEN = [r"[¥￥]\s*([\d,]+)", r"([\d,]+)\s*円"]


def _armar(fuente, t, precio_txt, moneda, vendido=False, subasta=False) -> Listado | None:
    precio = parse_precio(precio_txt)
    if not t["titulo"] or precio is None:
        return None
    return Listado(fuente=fuente, id=t["id"], titulo=t["titulo"], precio=precio, moneda=moneda,
                   url=t["url"], foto=t["foto"], vendido=vendido, subasta=subasta)


# ---------------- Rakuma (Rakuten) ----------------
def rakuma(consulta: str) -> list[Listado]:
    url = f"https://fril.jp/s?query={quote(consulta)}&sort=created_at&order=desc"
    html = descargar(url)
    out = []
    for t in tarjetas(html, "https://fril.jp", r"item\.fril\.jp/([0-9a-f]{16,})"):
        vendido = bool(re.search(r"sold\s*out|売り切れ|売切", t["texto"], re.I))
        l = _armar("rakuma", t, primer_precio(t["texto"], YEN), "JPY", vendido)
        if l:
            out.append(l)
    return out


# ---------------- Suruga-ya ----------------
def surugaya(consulta: str) -> list[Listado]:
    url = f"https://www.suruga-ya.jp/search?category=&search_word={quote(consulta)}&rankBy=modificationTime%3Adescending"
    html = descargar(url)
    out = []
    for t in tarjetas(html, "https://www.suruga-ya.jp", r"suruga-ya\.jp/product/(?:detail|other)/([A-Za-z0-9]+)"):
        if re.search(r"品切れ|在庫なし", t["texto"]) and not re.search(r"[¥￥]\s*[\d,]+", t["texto"]):
            continue
        # Suruga-ya muestra varios precios (nuevo/usado); el más bajo es el relevante
        precios = []
        for grupo in re.findall(r"[¥￥]\s*([\d,]+)|([\d,]+)\s*円", t["texto"]):
            p = parse_precio(grupo[0] or grupo[1])
            if p and p > 100:
                precios.append(p)
        if not precios:
            continue
        l = _armar("surugaya", t, str(min(precios)), "JPY")
        if l:
            out.append(l)
    return out


# ---------------- Mandarake ----------------
def mandarake(consulta: str) -> list[Listado]:
    url = (f"https://order.mandarake.co.jp/order/listPage/list?keyword={quote(consulta)}"
           f"&lang=ja&sort=arrival&sortOrder=1&dispCount=48&soldOut=1")
    html = descargar(url, cookies={"tr_mndrk_user": "1"})
    out = []
    for t in tarjetas(html, "https://order.mandarake.co.jp", r"itemCode=(\d+)"):
        vendido = bool(re.search(r"売り切れ|sold\s*out", t["texto"], re.I))
        l = _armar("mandarake", t, primer_precio(t["texto"], YEN), "JPY", vendido)
        if l:
            out.append(l)
    return out


# ---------------- eBay ----------------
def ebay(consulta: str, vendidos: bool = False) -> list[Listado]:
    url = f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(consulta)}&_sop=10&_ipg=120"
    if vendidos:
        url += "&LH_Sold=1&LH_Complete=1"
    html = descargar(url, headers={"Accept-Language": "en-US,en;q=0.9"})
    out = []
    for t in tarjetas(html, "https://www.ebay.com", r"ebay\.com/itm/(?:[^/?]+/)?(\d{9,})"):
        if t["id"] == "123456":  # tarjeta fantasma "Shop on eBay"
            continue
        t["titulo"] = re.sub(r"^(New Listing|Nuevo anuncio)\s*", "", t["titulo"]).replace("Opens in a new window or tab", "").strip()
        precio = primer_precio(t["texto"], [r"(?:US\s*)?\$\s*([\d,]+\.?\d*)"])
        subasta = bool(re.search(r"\d+\s+bids?", t["texto"], re.I))
        l = _armar("ebay", t, precio, "USD", vendido=vendidos, subasta=subasta)
        if l:
            if re.search(r"free\s+(international\s+)?shipping|envío gratis", t["texto"], re.I):
                l.envio = 0.0
            else:
                env = primer_precio(t["texto"], [r"\+\s*(?:US\s*)?\$\s*([\d,]+\.?\d*)\s*(?:shipping|envío|delivery)"])
                l.envio = parse_precio(env) if env else None
            out.append(l)
    return out


def ebay_vendidos(consulta: str) -> list[Listado]:
    return ebay(consulta, vendidos=True)


# ---------------- MercadoLibre Chile ----------------
def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9ñáéíóú]+", "-", texto.lower()).strip("-")


def mercadolibre_cl(consulta: str) -> list[Listado]:
    url = f"https://listado.mercadolibre.cl/{_slug(consulta)}_OrderId_PRICE_NoIndex_True"
    html = descargar(url, headers={"Accept-Language": "es-CL,es;q=0.9"})
    out = []
    for t in tarjetas(html, "https://www.mercadolibre.cl", r"(MLC-?\d{6,})"):
        t["id"] = t["id"].replace("-", "")
        frac = t["nodo"].find(class_=re.compile("andes-money-amount__fraction|price-tag-fraction"))
        precio = frac.get_text(strip=True) if frac else primer_precio(t["texto"], [r"\$\s*([\d\.]+)"])
        l = _armar("mercadolibre_cl", t, precio, "CLP")
        if l:
            out.append(l)
    return out


# ---------------- Rakuten Ichiba (muchas tiendas de usados) ----------------
def rakuten(consulta: str) -> list[Listado]:
    url = f"https://search.rakuten.co.jp/search/mall/{quote(consulta)}/?s=4"  # s=4: más nuevos
    html = descargar(url)
    out = []
    for p in productos_ldjson(html):
        m = re.search(r"item\.rakuten\.co\.jp/([^/?#]+/[^/?#]+)", p["url"])
        if not m or p["agotado"]:
            continue
        out.append(Listado(fuente="rakuten", id=m.group(1).replace("/", "_"), titulo=p["titulo"],
                           precio=parse_precio(str(p["precio"])), moneda=p["moneda"],
                           url=p["url"].split("?")[0], foto=p["foto"]))
    if out:
        return [l for l in out if l.precio]
    for t in tarjetas(html, "https://search.rakuten.co.jp", r"item\.rakuten\.co\.jp/([^/?#]+/[^/?#]+)"):
        t["id"] = t["id"].replace("/", "_")
        if re.search(r"売り切れ|在庫なし", t["texto"]):
            continue
        l = _armar("rakuten", t, primer_precio(t["texto"], YEN), "JPY")
        if l:
            out.append(l)
    return out


# ---------------- Yahoo! Shopping ----------------
def yahoo_shopping(consulta: str) -> list[Listado]:
    url = f"https://shopping.yahoo.co.jp/search?p={quote(consulta)}&X=4&used=2"  # X=4 nuevos; used=2 incluye usados
    html = descargar(url)
    out = []
    for t in tarjetas(html, "https://shopping.yahoo.co.jp",
                      r"store\.shopping\.yahoo\.co\.jp/([^/?#]+/[^/?#]+?)(?:\.html|[/?#]|$)"):
        t["id"] = t["id"].replace("/", "_")
        l = _armar("yahoo_shopping", t, primer_precio(t["texto"], YEN), "JPY")
        if l:
            out.append(l)
    return out


# ---------------- Off Mall (Hard Off / Hobby Off) ----------------
def offmall(consulta: str) -> list[Listado]:
    url = f"https://netmall.hardoff.co.jp/search/?q={quote(consulta)}&s=1"
    html = descargar(url)
    out = []
    for t in tarjetas(html, "https://netmall.hardoff.co.jp", r"netmall\.hardoff\.co\.jp/product/(\d+)"):
        if re.search(r"SOLD\s*OUT|売り切れ", t["texto"], re.I):
            continue
        l = _armar("offmall", t, primer_precio(t["texto"], YEN), "JPY")
        if l:
            out.append(l)
    return out


# ---------------- Lashinbang (らしんばん) ----------------
def lashinbang(consulta: str) -> list[Listado]:
    url = f"https://shop.lashinbang.com/products/list?keyword={quote(consulta)}&orderby=new"
    html = descargar(url)
    out = []
    for t in tarjetas(html, "https://shop.lashinbang.com", r"shop\.lashinbang\.com/products/detail/(\d+)"):
        if re.search(r"売り切れ|在庫なし|SOLD", t["texto"], re.I):
            continue
        l = _armar("lashinbang", t, primer_precio(t["texto"], YEN), "JPY")
        if l:
            out.append(l)
    return out


# ---------------- AmiAmi (sección usados / pre-owned) ----------------
def amiami(consulta: str) -> list[Listado]:
    from .base import sesion
    r = sesion().get(
        "https://api.amiami.com/api/v1.0/items",
        params={"pagemax": 50, "lang": "eng", "s_keywords": consulta, "s_st_condition_flg": 1},
        headers={"X-User-Key": "amiami_dev", "Accept": "application/json"},
        timeout=25,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} — AmiAmi")
    out = []
    for it in (r.json().get("items") or []):
        if not it.get("instock_flg"):
            continue
        codigo = it.get("scode") or it.get("gcode")
        if not codigo:
            continue
        param = "scode" if it.get("scode") else "gcode"
        thumb = it.get("thumb_url") or ""
        out.append(Listado(
            fuente="amiami", id=str(codigo), titulo=it.get("gname") or "",
            precio=float(it.get("min_price") or it.get("c_price_taxed") or 0) or None, moneda="JPY",
            url=f"https://www.amiami.com/eng/detail/?{param}={codigo}",
            foto=("https://img.amiami.com" + thumb) if thumb.startswith("/") else thumb,
        ))
    return [l for l in out if l.precio]

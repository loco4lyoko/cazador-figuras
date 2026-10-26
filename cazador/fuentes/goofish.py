"""Goofish / 闲鱼 (Xianyu), segunda mano en China. EXPERIMENTAL.

Usa la misma API pública que la web (mtop, firmada con md5). Goofish suele bloquear
servidores en la nube (como GitHub), así que lo más confiable es correr esta fuente
desde tu notebook (ver LEEME: "Goofish desde el notebook").

Opcional: GOOFISH_COOKIES = las cookies de tu navegador con sesión iniciada en goofish.com
(texto tipo "cookie2=...; _m_h5_tk=...; ..."), mejora mucho la tasa de éxito.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import requests

from ..modelos import Listado, parse_precio
from .base import UA

APP_KEY = "34839810"
BASE = "https://h5api.m.goofish.com/h5/{api}/1.0/"
API_BUSCAR = "mtop.taobao.idlemtopsearch.pc.search"
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Origin": "https://www.goofish.com",
    "Referer": "https://www.goofish.com/",
    "Content-Type": "application/x-www-form-urlencoded",
}

_sesion: requests.Session | None = None


def firmar(token: str, t: str, data: str) -> str:
    return hashlib.md5(f"{token}&{t}&{APP_KEY}&{data}".encode()).hexdigest()


def _params(api: str, t: str, sign: str) -> dict:
    return {"jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign, "v": "1.0",
            "type": "originaljson", "accountSite": "xianyu", "dataType": "json",
            "timeout": "20000", "api": api, "sessionOption": "AutoLoginOnly",
            "spm_cnt": "a21ybx.search.0.0"}


def _llamar(s: requests.Session, api: str, data: dict) -> dict:
    data_txt = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    token = (s.cookies.get("_m_h5_tk") or "").split("_")[0]
    t = str(int(time.time() * 1000))
    r = s.post(BASE.format(api=api), params=_params(api, t, firmar(token, t, data_txt)),
               data={"data": data_txt}, headers=HEADERS, timeout=20)
    return r.json()


def _preparar() -> requests.Session:
    global _sesion
    if _sesion is not None:
        return _sesion
    s = requests.Session()
    cookies = os.getenv("GOOFISH_COOKIES", "")
    for parte in cookies.split(";"):
        if "=" in parte:
            k, v = parte.strip().split("=", 1)
            s.cookies.set(k, v, domain=".goofish.com")
    try:
        s.get("https://www.goofish.com/", headers={"User-Agent": UA}, timeout=15)
    except requests.RequestException:
        pass
    if not s.cookies.get("_m_h5_tk"):
        # la primera llamada "vacía" entrega el token _m_h5_tk en las cookies
        try:
            _llamar(s, "mtop.taobao.idlehome.home.webpc.feed", {})
        except Exception:
            pass
    _sesion = s
    return s


def interpretar(resp: dict) -> list[Listado]:
    """Convierte la respuesta JSON de búsqueda en listados."""
    out = []
    for item in (resp.get("data") or {}).get("resultList") or []:
        main = (((item.get("data") or {}).get("item") or {}).get("main") or {})
        ex = main.get("exContent") or {}
        iid = ex.get("itemId") or (main.get("clickParam") or {}).get("args", {}).get("item_id")
        if not iid:
            continue
        partes = ex.get("price") or []
        txt = "".join(str(p.get("text", "")) for p in partes if isinstance(p, dict)) if isinstance(partes, list) else str(partes)
        txt = txt.replace("当前价", "").replace("¥", "").strip()
        precio = None
        if "万" in txt:
            try:
                precio = float(txt.replace("万", "")) * 10000
            except ValueError:
                pass
        else:
            precio = parse_precio(txt)
        foto = ex.get("picUrl") or ""
        if foto.startswith("//"):
            foto = "https:" + foto
        out.append(Listado(
            fuente="goofish", id=str(iid), titulo=ex.get("title") or ex.get("detailParams", {}).get("title", ""),
            precio=precio, moneda="CNY", url=f"https://www.goofish.com/item?id={iid}", foto=foto,
        ))
    return [l for l in out if l.titulo and l.precio]


def buscar(consulta: str) -> list[Listado]:
    s = _preparar()
    data = {"pageNumber": 1, "keyword": consulta, "fromFilter": False, "rowsPerPage": 30,
            "sortValue": "desc", "sortField": "create", "customDistance": "", "gps": "",
            "propValueStr": {}, "customGps": "", "searchReqFromPage": "pcSearch",
            "extraFilterValue": "{}", "userPositionJson": "{}"}
    resp = _llamar(s, API_BUSCAR, data)
    ret = " ".join(resp.get("ret") or [])
    if "TOKEN" in ret:  # token vencido: se renueva solo y se reintenta una vez
        resp = _llamar(s, API_BUSCAR, data)
        ret = " ".join(resp.get("ret") or [])
    if "SUCCESS" not in ret:
        raise RuntimeError(f"Goofish rechazó la búsqueda ({ret[:80] or 'sin respuesta'}). "
                           "Probablemente bloquea esta IP; usa el modo notebook.")
    return interpretar(resp)

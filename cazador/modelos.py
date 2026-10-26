"""Estructuras de datos y utilidades comunes."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Optional

# País de cada fuente (para el filtro por país)
PAIS_FUENTE = {
    "mercari": "JP", "yahoo": "JP", "rakuma": "JP", "surugaya": "JP", "mandarake": "JP",
    "rakuten": "JP", "yahoo_shopping": "JP", "offmall": "JP", "lashinbang": "JP", "amiami": "JP",
    "goofish": "CN",
    "ebay": "INT",
    "mercadolibre_cl": "CL",
}

# Idioma de las consultas que usa cada fuente
IDIOMA_FUENTE = {
    **{f: "jp" for f in ("mercari", "yahoo", "rakuma", "surugaya", "mandarake", "rakuten",
                         "yahoo_shopping", "offmall", "lashinbang")},
    "amiami": "en",
    "goofish": "zh",
    "ebay": "en",
    "mercadolibre_cl": "es",
}

NOMBRE_FUENTE = {
    "mercari": "Mercari JP",
    "yahoo": "Yahoo Auctions / Yahoo Flea",
    "rakuma": "Rakuma",
    "surugaya": "Suruga-ya",
    "mandarake": "Mandarake",
    "ebay": "eBay",
    "mercadolibre_cl": "MercadoLibre Chile",
    "rakuten": "Rakuten Ichiba",
    "yahoo_shopping": "Yahoo! Shopping",
    "offmall": "Off Mall (Hard Off/Hobby Off)",
    "lashinbang": "Lashinbang",
    "amiami": "AmiAmi (usados)",
    "goofish": "Goofish 闲鱼",
}

# Cada cuántos minutos revisar cada fuente: los mercados de segunda mano (donde las
# gangas duran minutos) en cada pasada; las tiendas, que cambian lento, cada hora.
MINUTOS_FUENTE = {
    "mercari": 0, "yahoo": 0, "rakuma": 0, "goofish": 30, "mercadolibre_cl": 30, "ebay": 30,
    "surugaya": 60, "mandarake": 60, "rakuten": 60, "yahoo_shopping": 60, "offmall": 60,
    "lashinbang": 60, "amiami": 120,
}

# Búsqueda genérica para comprobar 1 vez al día que el lector de cada sitio sigue funcionando
CONSULTA_DIAGNOSTICO = {"jp": "フィギュア", "en": "figure", "es": "figura", "zh": "手办"}


@dataclass
class Listado:
    fuente: str
    id: str
    titulo: str
    precio: Optional[float]
    moneda: str
    url: str
    foto: str = ""
    vendido: bool = False
    subasta: bool = False
    compra_inmediata: Optional[float] = None  # precio "即決" en subastas
    termina: str = ""                         # fin de subasta (texto/ISO) si se conoce
    pujas: Optional[int] = None
    fecha_venta: str = ""
    envio: Optional[float] = None             # costo de envío que indica el listado (misma moneda)

    @property
    def clave(self) -> str:
        return f"{self.fuente}:{self.id}"

    def dict(self):
        return asdict(self)


_KATA_INICIO, _KATA_FIN = 0x30A1, 0x30F6


def normalizar(texto: str) -> str:
    """Minúsculas, ancho normal (NFKC) y katakana→hiragana, para comparar títulos."""
    t = unicodedata.normalize("NFKC", texto or "").lower()
    t = "".join(
        chr(ord(c) - 0x60) if _KATA_INICIO <= ord(c) <= _KATA_FIN else c for c in t
    )
    return re.sub(r"\s+", " ", t).strip()


def contiene(texto_norm: str, palabras) -> bool:
    return any(normalizar(p) in texto_norm for p in palabras or [])


def parse_precio(texto: str) -> Optional[float]:
    """'¥12,345' / '12,345円' / 'US $123.45' / '$ 45.990' (CLP) -> número."""
    if texto is None:
        return None
    s = unicodedata.normalize("NFKC", str(texto))
    m = re.search(r"\d[\d,\.]*", s)
    if not m:
        return None
    num = m.group(0)
    # Formato chileno 45.990 (punto de miles, sin decimales)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", num):
        return float(num.replace(".", ""))
    num = num.replace(",", "")
    try:
        return float(num)
    except ValueError:
        return None

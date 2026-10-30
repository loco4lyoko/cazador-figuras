"""Registro de fuentes: nombre -> (función buscar, función vendidos o None)."""
from . import mercari, yahoo, tiendas, goofish

FUENTES = {
    # Japón (todas compatibles con ZenMarket: pega el link si no hay botón directo)
    "mercari": (mercari.buscar, mercari.vendidos),
    "yahoo": (yahoo.buscar, yahoo.vendidos),
    "rakuma": (tiendas.rakuma, None),
    "surugaya": (tiendas.surugaya, None),
    "mandarake": (tiendas.mandarake, None),
    "rakuten": (tiendas.rakuten, None),
    "yahoo_shopping": (tiendas.yahoo_shopping, None),
    "offmall": (tiendas.offmall, None),
    "lashinbang": (tiendas.lashinbang, None),
    "amiami": (tiendas.amiami, None),
    # China (Superbuy)
    "goofish": (goofish.buscar, None),
    # Internacional / Chile
    "ebay": (tiendas.ebay, tiendas.ebay_vendidos),
    "mercadolibre_cl": (tiendas.mercadolibre_cl, None),
}

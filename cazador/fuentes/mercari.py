"""Mercari Japón, usando su API (librería mercapi). La fuente más importante."""
from __future__ import annotations

import asyncio

from ..modelos import Listado

_api = None
_loop = None


def _correr(coro):
    """Un solo event loop para todo el proceso (el cliente HTTP de mercapi queda atado a él)."""
    global _loop
    if _loop is None:
        _loop = asyncio.new_event_loop()
    return _loop.run_until_complete(coro)


async def _cliente():
    """Se crea dentro del event loop (mercapi abre su cliente HTTP al instanciarse)."""
    global _api
    if _api is None:
        from mercapi import Mercapi
        _api = Mercapi()
    return _api


def _a_listado(it) -> Listado:
    iid = it.id_
    es_tienda = not str(iid).startswith("m")
    url = (f"https://jp.mercari.com/shops/product/{iid}" if es_tienda
           else f"https://jp.mercari.com/item/{iid}")
    auction = getattr(it, "auction", None)
    estado = (it.status or "").lower()
    return Listado(
        fuente="mercari",
        id=str(iid),
        titulo=it.name or "",
        precio=None if getattr(it, "is_no_price", False) else float(it.price),
        moneda="JPY",
        url=url,
        foto=(it.thumbnails or [""])[0],
        vendido=("sold" in estado or "trading" in estado),
        subasta=bool(auction and getattr(auction, "id_", None)),
        termina=(auction.bid_deadline.isoformat() if auction and getattr(auction, "bid_deadline", None) else ""),
        pujas=(auction.total_bid if auction and getattr(auction, "id_", None) else None),
        fecha_venta=(it.updated.isoformat() if ("sold" in estado and getattr(it, "updated", None)) else ""),
    )


async def _buscar(consulta: str, vendidos: bool):
    from mercapi.requests import SearchRequestData as S
    api = await _cliente()
    estado = [S.Status.STATUS_SOLD_OUT] if vendidos else [S.Status.STATUS_ON_SALE]
    res = await api.search(
        consulta,
        sort_by=S.SortBy.SORT_CREATED_TIME,
        sort_order=S.SortOrder.ORDER_DESC,
        status=estado,
    )
    return [_a_listado(i) for i in res.items]


def buscar(consulta: str) -> list[Listado]:
    return _correr(_buscar(consulta, vendidos=False))


def vendidos(consulta: str) -> list[Listado]:
    return _correr(_buscar(consulta, vendidos=True))

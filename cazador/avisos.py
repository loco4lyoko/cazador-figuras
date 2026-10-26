"""Envío de alertas por Telegram (principal) y correo (opcional)."""
from __future__ import annotations

import html
import os
import smtplib
from email.mime.text import MIMEText

import requests

from .modelos import NOMBRE_FUENTE, PAIS_FUENTE


def link_compra(fuente: str, url: str, id_: str) -> list[tuple[str, str]]:
    """Links directos a tus intermediarios cuando se conoce el formato."""
    links = []
    if fuente == "mercari" and id_.startswith("m"):
        links.append(("ZenMarket", f"https://zenmarket.jp/en/mercariproduct.aspx?itemCode={id_}"))
        links.append(("Buyee", f"https://buyee.jp/mercari/item/{id_}"))
    elif fuente == "yahoo" and "paypayfleamarket" not in url:
        links.append(("ZenMarket", f"https://zenmarket.jp/en/auction.aspx?itemCode={id_}"))
        links.append(("Buyee", f"https://buyee.jp/item/yahoo/auction/{id_}"))
    return links


def _telegram(metodo: str, datos: dict) -> bool:
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[avisos] Telegram no configurado; mensaje:\n", datos.get("caption") or datos.get("text"))
        return False
    datos = {"chat_id": chat, "parse_mode": "HTML", **datos}
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data=datos, timeout=20)
        if r.ok:
            return True
        print("[avisos] Telegram respondió", r.status_code, r.text[:300])
    except requests.RequestException as e:
        print("[avisos] Error Telegram:", e)
    return False


def telegram_texto(texto: str, silencioso: bool = False) -> bool:
    return _telegram("sendMessage", {"text": texto[:4000], "disable_web_page_preview": "true",
                                     "disable_notification": str(silencioso).lower()})


def telegram_foto(foto: str, texto: str, silencioso: bool = False) -> bool:
    if foto and _telegram("sendPhoto", {"photo": foto, "caption": texto[:1024],
                                        "disable_notification": str(silencioso).lower()}):
        return True
    return telegram_texto(texto, silencioso)


def correo(asunto: str, cuerpo_html: str) -> bool:
    host, usuario, clave, para = (os.getenv("SMTP_HOST"), os.getenv("SMTP_USUARIO"),
                                  os.getenv("SMTP_CLAVE"), os.getenv("CORREO_DESTINO"))
    if not (host and usuario and clave and para):
        return False
    try:
        msg = MIMEText(cuerpo_html, "html", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = asunto, usuario, para
        with smtplib.SMTP(host, int(os.getenv("SMTP_PUERTO", "587")), timeout=30) as s:
            s.starttls()
            s.login(usuario, clave)
            s.send_message(msg)
        return True
    except Exception as e:
        print("[avisos] Error correo:", e)
        return False


def armar_mensaje(tipo: str, art_nombre: str, l: dict, precio_local: str, precio_orig: str,
                  ref_txt: str, descuento, junk: bool, sin_caja: bool = False, total_local: str = "") -> str:
    e = html.escape
    cabecera = {
        "bomba": "🚨🚨 <b>¡OFERTA BOMBA!</b>",
        "oferta": "🔥 <b>OFERTA</b>",
        "presupuesto": "💰 <b>DENTRO DE TU PRESUPUESTO</b>",
        "bajo_precio": "📉 <b>BAJÓ DE PRECIO</b>",
        "subasta_final": "⏰ <b>SUBASTA POR TERMINAR Y VA BARATA</b>",
        "nuevo": "🆕 Nuevo listado",
    }.get(tipo, tipo)
    lineas = [cabecera, f"<b>{e(art_nombre)}</b>", ""]
    lineas.append(f"💴 <b>{e(precio_orig)}</b>  ≈ {e(precio_local)}")
    if total_local and total_local != "?" and l.get("fuente") != "mercadolibre_cl":
        lineas.append(f"🚚 ≈ {e(total_local)} puesto en Chile (estimado)")
    if descuento is not None and ref_txt:
        signo = "más barato" if descuento >= 0 else "más caro"
        lineas.append(f"📊 {abs(descuento) * 100:.0f}% {signo} que lo normal (normal en Japón: {e(ref_txt)})")
    if l.get("subasta"):
        extra = []
        if l.get("pujas") is not None:
            extra.append(f"{l['pujas']} pujas")
        if l.get("termina"):
            extra.append(f"termina {l['termina']}")
        if l.get("compra_inmediata"):
            extra.append(f"compra inmediata ¥{l['compra_inmediata']:,.0f}")
        lineas.append("🔨 Subasta" + (": " + ", ".join(extra) if extra else " (el precio puede subir)"))
    if junk:
        lineas.append("⚠️ Junk / dañada / incompleta: revisa fotos y descripción")
    if sin_caja:
        lineas.append("📦❌ Sin caja")
    if l.get("personajes"):
        lineas.append("👧 " + ", ".join(p.capitalize() for p in l["personajes"]))
    lineas.append(f"🏪 {e(NOMBRE_FUENTE.get(l['fuente'], l['fuente']))}")
    lineas.append(f"📝 {e(l['titulo'][:180])}")
    lineas.append("")
    links = [f'<a href="{e(l["url"])}">Ver listado</a>']
    links += [f'<a href="{e(u)}">{n}</a>' for n, u in link_compra(l["fuente"], l["url"], l["id"])]
    lineas.append(" · ".join(links))
    if not link_compra(l["fuente"], l["url"], l["id"]):
        pista = {"CN": "Pega el link en Superbuy para comprarlo.",
                 "JP": "Pega el link en ZenMarket para comprarlo."}.get(PAIS_FUENTE.get(l["fuente"], ""))
        if pista:
            lineas.append(f"<i>{pista}</i>")
    return "\n".join(lineas)

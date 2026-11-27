"""Vigila una ficha de Ripley cada 30 s y avisa por Telegram cuando deja de estar sin stock."""
from __future__ import annotations

import re
import time

from .avisos import _telegram
from .fuentes.base import descargar

URL = ("https://simple.ripley.cl/consola-playstation-5-ps5-digital-juego-ratchet-clank-"
       "rift-apart-juego-returnal-2000400281915p?color_80=Blanco")
CADA = 30                # segundos entre revisiones
DURACION = 5.7 * 3600    # GitHub corta los trabajos a las 6 horas


def revisar() -> tuple[str, str]:
    html = descargar(URL)
    estado = re.search(r'\\?"availability\\?":\s*\\?"https?://schema\.org/(\w+)', html)
    precio = re.search(r'\\?"priceCurrency\\?":\s*\\?"CLP\\?",\s*\\?"price\\?":\s*\\?"?(\d+)', html)
    if not estado:
        raise ValueError("la página llegó sin el dato de disponibilidad")
    p = "$" + f"{int(precio.group(1)):,}".replace(",", ".") if precio else "precio no leído"
    return estado.group(1), p


def avisar(texto: str) -> None:
    _telegram("sendMessage", {"text": texto})


def main() -> None:
    fin = time.time() + DURACION
    anterior, fallos, primera = None, 0, True
    while time.time() < fin:
        try:
            estado, precio = revisar()
            print(time.strftime("%H:%M:%S"), estado, precio, flush=True)
            if primera:
                avisar(f"👀 Vigilando la PS5 de Ripley cada {CADA} s.\nAhora: {estado}, {precio}")
                primera = False
            if fallos >= 6:
                avisar("✅ Volví a leer la página de Ripley.")
            fallos = 0
            if estado != "OutOfStock" and estado != anterior:
                for i in range(5):  # varios mensajes para que suene fuerte
                    avisar(f"🚨🚨 ¡PS5 EN RIPLEY! Estado: {estado}, {precio}\nCORRE: {URL}")
                    time.sleep(3)
            anterior = estado
        except Exception as e:
            fallos += 1
            print(time.strftime("%H:%M:%S"), "error:", e, flush=True)
            if fallos == (1 if primera else 6):
                avisar(f"⚠️ NO estoy pudiendo leer Ripley, no confíes en este aviso.\n{str(e)[:150]}")
            if primera:
                raise SystemExit(1)
        time.sleep(CADA)
    avisar("🔴 Terminó la vigilancia de Ripley (límite de 6 horas). Hay que activarla de nuevo.")


if __name__ == "__main__":
    main()

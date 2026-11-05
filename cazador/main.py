"""Cazador de figuras — programa principal.

Modos:
  python -m cazador.main                 # rastreo normal (lo que corre cada 15 min)
  python -m cazador.main --modo historico # junta precios de VENTAS reales (1 vez al día)
  python -m cazador.main --modo prueba    # manda un mensaje de prueba a Telegram
"""
from __future__ import annotations

import argparse
import sys
import json
import os
import statistics
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from . import avisos, monedas
from .clasificador import Clasificador
from .fuentes import FUENTES
from .modelos import (Listado, PAIS_FUENTE, IDIOMA_FUENTE, NOMBRE_FUENTE, MINUTOS_FUENTE,
                      CONSULTA_DIAGNOSTICO, normalizar, contiene)

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.yaml"
DATOS = RAIZ / "docs" / "data.json"
COSTO_DEFECTO = {"JP": 9000, "CN": 7000, "INT": 7000, "CL": 0}
PAUSA = float(os.getenv("PAUSA_ENTRE_BUSQUEDAS", "1.5"))
FALLAS_PARA_AVISAR = 8          # ~2 horas seguidas fallando
MAX_POR_ARTICULO = 400
MAX_VENDIDOS = 300


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cargar_datos() -> dict:
    if DATOS.exists():
        try:
            return json.loads(DATOS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def guardar_datos(d: dict):
    DATOS.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATOS.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DATOS)


class Cazador:
    def __init__(self, config: dict, datos: dict, enviar: bool = True, solo: list | None = None,
                 forzar: bool = False):
        self.solo = solo          # limitar a ciertas fuentes (modo notebook)
        self.forzar = forzar      # ignorar la frecuencia por fuente
        self.cfg = config
        self.d = datos
        self.enviar = enviar
        self.cla = Clasificador(config)
        self.aj = config.get("ajustes", {})
        self.moneda_local = self.aj.get("moneda_local", "CLP")
        for k, v in {"listados": {}, "vendidos": {}, "salud": {}, "iniciados": [],
                     "sin_clasificar": [], "ref_aprendida": {}, "ultima_fuente": {}}.items():
            self.d.setdefault(k, v)
        self.d["tasas"] = monedas.actualizar(self.d.get("tasas"))
        self.cla.ref_aprendida = self.d["ref_aprendida"]
        self.alertas_enviadas = 0

    # ---------- utilidades ----------
    def a_jpy(self, l: Listado | dict, precio=None):
        moneda = l.moneda if isinstance(l, Listado) else l["moneda"]
        p = precio if precio is not None else (l.precio if isinstance(l, Listado) else l["precio"])
        return monedas.convertir(p, moneda, "JPY", self.d["tasas"])

    def referencia(self, busqueda: dict, art: dict, listado: Listado):
        if art.get("tipo") == "lote":
            return self.cla.referencia_lote(busqueda, listado)
        # Si hay suficientes ventas reales registradas, manda el mercado real (se actualiza cada día)
        aprendida = self.d["ref_aprendida"].get(art["id"], {})
        if self.aj.get("usar_ventas_reales", True) and aprendida.get("n", 0) >= 5:
            return aprendida["mediana"]
        return art.get("precio_referencia_jpy") or aprendida.get("mediana")

    def solo_notebook(self) -> list:
        """Sitios que bloquean a GitHub: se revisan solo desde el notebook (modo --solo)."""
        lista = list(self.aj.get("fuentes_solo_notebook") or [])
        if self.aj.get("goofish_en_nube") is False and "goofish" not in lista:
            lista.append("goofish")
        return lista

    def costo_chile(self, art: dict, l: Listado) -> float:
        """Yenes extra para que el artículo llegue a Chile (envío + intermediario)."""
        pais = PAIS_FUENTE.get(l.fuente, "JP")
        if l.envio is not None and pais in ("INT", "CL"):
            return self.a_jpy(l, l.envio) or 0.0
        tabla = {**COSTO_DEFECTO, **(self.aj.get("costo_hasta_chile_jpy") or {}),
                 **(art.get("costo_hasta_chile_jpy") or {})}
        return float(tabla.get(pais, 0))

    def costo_ref(self, art: dict) -> float:
        tabla = {**COSTO_DEFECTO, **(self.aj.get("costo_hasta_chile_jpy") or {}),
                 **(art.get("costo_hasta_chile_jpy") or {})}
        return float(tabla.get("JP", 0))

    def consultas(self, busqueda: dict, fuente: str) -> list[str]:
        c = busqueda.get("consultas", {})
        return c.get(IDIOMA_FUENTE.get(fuente, "jp")) or c.get("jp") or []

    def fuente_permitida(self, art: dict, busqueda: dict, fuente: str) -> bool:
        paises = art.get("paises") or busqueda.get("paises")
        return not paises or PAIS_FUENTE.get(fuente) in paises

    # ---------- búsqueda ----------
    def recolectar(self, busqueda: dict, vendidos: bool) -> list[tuple[str, Listado]]:
        encontrados: dict[str, Listado] = {}
        for fuente in busqueda.get("fuentes", list(FUENTES)):
            if fuente not in FUENTES:
                print(f"[aviso] fuente desconocida: {fuente}")
                continue
            fn = FUENTES[fuente][1 if vendidos else 0]
            if fn is None:
                continue
            if self.solo and fuente not in self.solo:
                continue
            if not self.solo and fuente in self.solo_notebook():
                continue
            clave_t = f"{busqueda['nombre']}|{fuente}|{'v' if vendidos else 'a'}"
            if not vendidos and not self.forzar and not self.toca(clave_t, MINUTOS_FUENTE.get(fuente, 0)):
                continue
            self.d["ultima_fuente"][clave_t] = ahora()
            total, errores = 0, []
            for q in self.consultas(busqueda, fuente):
                try:
                    res = fn(q)
                    total += len(res)
                    for l in res:
                        encontrados.setdefault(l.clave, l)
                except Exception as e:
                    errores.append(f"{q}: {e}")
                    traceback.print_exc()
                time.sleep(PAUSA)
            if len(errores) < len(self.consultas(busqueda, fuente)):
                self.fuentes_ok = getattr(self, "fuentes_ok", set()) | {fuente}
            print(f"  {NOMBRE_FUENTE.get(fuente, fuente):28s} {total:4d} resultados"
                  + (f"  ({len(errores)} errores)" if errores else ""))
            if not vendidos:
                self.registrar_salud(fuente, total, errores)
        return [(l.fuente, l) for l in encontrados.values()]

    def toca(self, clave: str, minutos: int) -> bool:
        ult = self.d["ultima_fuente"].get(clave)
        if not ult or minutos <= 0:
            return True
        # margen de 3 min porque GitHub no corre exactamente cada 15
        return datetime.now(timezone.utc) - datetime.fromisoformat(ult) >= timedelta(minutes=max(0, minutos - 3))

    def registrar_salud(self, fuente: str, total: int, errores: list[str]):
        s = self.d["salud"].setdefault(fuente, {"fallas_seguidas": 0, "avisado": False})
        if fuente == "goofish" and errores and total == 0 and not self.solo:
            s["bloqueo_nube"] = True
        s["ultima"] = ahora()
        s["resultados"] = total
        s["error"] = errores[-1][:300] if errores else ""
        if errores and total == 0:
            s["fallas_seguidas"] = s.get("fallas_seguidas", 0) + 1
        else:
            if s.get("avisado"):
                self.texto(f"✅ {NOMBRE_FUENTE.get(fuente, fuente)} volvió a funcionar.", silencioso=True)
            s["fallas_seguidas"], s["avisado"] = 0, False
            s["ultima_ok"] = ahora()
        if s["fallas_seguidas"] >= FALLAS_PARA_AVISAR and not s.get("avisado"):
            s["avisado"] = True
            self.texto(f"🛠 {NOMBRE_FUENTE.get(fuente, fuente)} lleva varias revisiones seguidas fallando."
                       f"\nÚltimo error: {s['error'] or 'ninguno (0 resultados)'}\n"
                       f"Puede que el sitio haya cambiado; pídele a Claude que lo revise.", silencioso=True)

    # ---------- envío ----------
    def texto(self, msg: str, silencioso=False):
        if self.enviar:
            avisos.telegram_texto(msg, silencioso)
        else:
            print("[sin enviar]", msg)

    def alertar(self, tipo, art, reg, ref, evaluacion, silencioso=False):
        precio_orig = monedas.formato(reg["precio"], reg["moneda"])
        precio_local = monedas.formato(
            monedas.convertir(reg["precio"], reg["moneda"], self.moneda_local, self.d["tasas"]), self.moneda_local)
        ref_txt = monedas.formato(ref, "JPY") if ref else ""
        total_local = monedas.formato(
            monedas.convertir(reg.get("total_chile_jpy"), "JPY", self.moneda_local, self.d["tasas"]), self.moneda_local)
        msg = avisos.armar_mensaje(tipo, art["nombre"], reg, precio_local, precio_orig, ref_txt,
                                   evaluacion.get("descuento"), reg.get("junk", False),
                                   reg.get("sin_caja", False), total_local)
        self.alertas_enviadas += 1
        if not self.enviar:
            print("[alerta sin enviar]\n" + msg + "\n")
            return
        avisos.telegram_foto(reg.get("foto", ""), msg, silencioso)
        if tipo in ("bomba", "oferta", "presupuesto", "bajo_precio", "subasta_final"):
            avisos.correo(f"{'🚨' if tipo == 'bomba' else '🔥'} {art['nombre']} a {precio_orig}",
                          msg.replace("\n", "<br>"))

    # ---------- rastreo normal ----------
    def rastrear(self):
        primera_vez_global = not self.d["listados"]
        nuevos_total, ofertas = 0, 0
        for busqueda in self.cfg.get("busquedas", []):
            print(f"\n=== {busqueda['nombre']} ===")
            self.fuentes_ok = set()
            iniciados = set(self.d["iniciados"])
            for fuente, l in self.recolectar(busqueda, vendidos=False):
                art = self.cla.clasificar(busqueda, l)
                if art is None:
                    self.guardar_sin_clasificar(busqueda, l)
                    continue
                if not self.fuente_permitida(art, busqueda, fuente):
                    continue
                # 1ra revisión exitosa de un sitio: no avisar "nuevo" de todo lo que ya estaba
                n, o = self.procesar(busqueda, art, l, primera=f"fuente:{fuente}" not in iniciados)
                nuevos_total += n
                ofertas += o
            for f in self.fuentes_ok:
                if f"fuente:{f}" not in self.d["iniciados"]:
                    self.d["iniciados"].append(f"fuente:{f}")
        self.podar()
        self.d["actualizado"] = ahora()
        self.d["articulos"] = self.resumen_articulos()
        self.d["solo_notebook"] = self.solo_notebook()
        self.d["fuentes_activas"] = sorted({f for b in self.cfg.get("busquedas", []) for f in b.get("fuentes", [])})
        self.d["revision_manual"] = links_manuales(self.cfg)
        self.d["ajustes_costos"] = {**COSTO_DEFECTO, **(self.aj.get("costo_hasta_chile_jpy") or {})}
        if primera_vez_global and self.d["listados"] and not self.d.get("bienvenida"):
            self.d["bienvenida"] = ahora()
            self.texto(f"🤖 <b>Cazador de figuras activo</b>\nEncontré {len(self.d['listados'])} listados "
                       f"de tus artículos ({ofertas} ofertas). Desde ahora te aviso de lo nuevo.")
        print(f"\nListados nuevos: {nuevos_total} · ofertas: {ofertas} · alertas: {self.alertas_enviadas}")

    def procesar(self, busqueda, art, l: Listado, primera: bool) -> tuple[int, int]:
        ahora_ = ahora()
        precio_jpy = self.a_jpy(l)
        # en subastas sin "compra inmediata" el precio actual no sirve para juzgar si es ganga
        precio_eval = l.compra_inmediata if (l.subasta and l.compra_inmediata) else l.precio
        precio_eval_jpy = self.a_jpy(l, precio_eval)
        ref = self.referencia(busqueda, art, l)
        # Se compara el costo TOTAL puesto en Chile (precio + envío/intermediario), así una
        # figura en Chile, una en Japón y una en eBay quedan en igualdad de condiciones.
        costo = self.costo_chile(art, l)
        total_jpy = precio_eval_jpy + costo if precio_eval_jpy is not None else None
        ref_total = ref + self.costo_ref(art) if ref else None
        pres = art.get("presupuesto")
        precio_pres = None
        if pres and total_jpy is not None:
            base = total_jpy if pres.get("incluye_envio", True) else precio_eval_jpy
            precio_pres = monedas.convertir(base, "JPY", pres["moneda"], self.d["tasas"])
        ev = self.cla.evaluar(art, total_jpy, precio_pres, ref_total)
        subasta_abierta = l.subasta and not l.compra_inmediata

        reg = self.d["listados"].get(l.clave)
        es_nuevo = reg is None
        if es_nuevo:
            reg = {**l.dict(), "articulo": art["id"], "primera_vez": ahora_, "historial": [],
                   "alertas": [], "junk": self.cla.es_junk(l.titulo),
                   "sin_caja": self.cla.sin_caja(l.titulo)}
            self.d["listados"][l.clave] = reg
        precio_anterior = reg.get("precio_jpy")
        for k in ("titulo", "precio", "moneda", "foto", "vendido", "subasta", "compra_inmediata",
                  "termina", "pujas", "url"):
            v = getattr(l, k)
            if v not in (None, "") or k in ("vendido", "subasta"):
                reg[k] = v
        reg.update({"articulo": art["id"], "ultima_vez": ahora_, "precio_jpy": precio_jpy,
                    "referencia_jpy": ref, "descuento": ev["descuento"], "nivel": ev["nivel"],
                    "total_chile_jpy": round(total_jpy) if total_jpy is not None else None,
                    "personajes": self.cla.personajes_texto(busqueda, l.titulo)})
        if precio_jpy is not None and (not reg["historial"] or abs(reg["historial"][-1][1] - precio_jpy) > 1):
            reg["historial"].append([ahora_, round(precio_jpy)])

        avisar_nuevos = art.get("avisar_nuevos", self.aj.get("avisar_nuevos", True))
        alertas = reg["alertas"]
        nuevos = 1 if es_nuevo else 0
        es_oferta = 0

        if subasta_abierta:
            # subasta: avisar al aparecer (con sonido si el artículo es prioridad alta)
            if es_nuevo and not primera and (avisar_nuevos or ev["nivel"] != "normal"):
                self.alertar("nuevo", art, reg, ref, ev, silencioso=art.get("prioridad") != "alta")
                alertas.append("nuevo")
            if self.termina_pronto(l.termina) and ev["nivel"] != "normal" and "subasta_final" not in alertas:
                self.alertar("subasta_final", art, reg, ref, ev)
                alertas.append("subasta_final")
                es_oferta = 1
            return nuevos, es_oferta

        if ev["nivel"] != "normal":
            es_oferta = 1
            umbral = float(art.get("umbral_oferta", self.aj.get("umbral_oferta", 0.30)))
            if ev["nivel"] == "bomba":
                tipo = "bomba"
            elif ev["bajo_presupuesto"] and (ev["descuento"] or 0) < umbral:
                tipo = "presupuesto"   # no es tan barato vs. el mercado, pero entra en tu tope
            else:
                tipo = "oferta"
            ya = [a for a in alertas if a in ("oferta", "bomba", "presupuesto", "bajo_precio")]
            bajo = (precio_anterior and precio_jpy and precio_jpy < precio_anterior * 0.97)
            if not ya:
                self.alertar(tipo, art, reg, ref, ev)
                alertas.append(tipo)
            elif bajo:
                self.alertar("bajo_precio", art, reg, ref, ev)
                alertas.append("bajo_precio")
        elif es_nuevo and not primera and avisar_nuevos:
            self.alertar("nuevo", art, reg, ref, ev, silencioso=not art.get("sonido_nuevos", False))
            alertas.append("nuevo")
        return nuevos, es_oferta

    @staticmethod
    def termina_pronto(termina: str, horas: float = 3) -> bool:
        if not termina:
            return False
        try:
            t = datetime.fromisoformat(termina.replace("Z", "+00:00"))
        except ValueError:
            return False
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return timedelta(0) <= t - datetime.now(timezone.utc) <= timedelta(hours=horas)

    def guardar_sin_clasificar(self, busqueda, l: Listado):
        t = normalizar(l.titulo)
        if busqueda.get("debe_incluir") and not contiene(t, busqueda["debe_incluir"]):
            return
        lista = self.d["sin_clasificar"]
        if any(x["clave"] == l.clave for x in lista):
            return
        lista.append({"clave": l.clave, "titulo": l.titulo, "precio": l.precio, "moneda": l.moneda,
                      "url": l.url, "foto": l.foto, "fuente": l.fuente, "visto": ahora()})
        del lista[:-150]

    # ---------- precios de venta reales ----------
    def historico(self):
        for busqueda in self.cfg.get("busquedas", []):
            print(f"\n=== Ventas reales: {busqueda['nombre']} ===")
            for fuente, l in self.recolectar(busqueda, vendidos=True):
                art = self.cla.clasificar(busqueda, l)
                if art is None or not self.fuente_permitida(art, busqueda, fuente):
                    continue
                lista = self.d["vendidos"].setdefault(art["id"], [])
                if any(v["clave"] == l.clave for v in lista):
                    continue
                lista.append({"clave": l.clave, "fuente": l.fuente, "titulo": l.titulo, "url": l.url,
                              "foto": l.foto, "precio": l.precio, "moneda": l.moneda,
                              "precio_jpy": round(self.a_jpy(l) or 0), "fecha_venta": l.fecha_venta,
                              "registrado": ahora(), "junk": self.cla.es_junk(l.titulo),
                              "sin_caja": self.cla.sin_caja(l.titulo)})
                del lista[:-MAX_VENDIDOS]
        self.aprender_referencias()
        self.diagnostico()
        self.d["actualizado"] = ahora()
        self.d["articulos"] = self.resumen_articulos()
        self.resumen_diario()

    def diagnostico(self):
        """Busca algo genérico ("フィギュア") en cada sitio: si no sale nada, el lector se rompió."""
        print("\n=== Diagnóstico de lectores ===")
        rotos = []
        activas = {f for b in self.cfg.get("busquedas", []) for f in b.get("fuentes", [])}
        for fuente, (fn, _) in FUENTES.items():
            if fuente not in activas:
                continue   # sitios de revisión manual: no tiene sentido avisar que bloquean
            if self.solo and fuente not in self.solo:
                continue
            if not self.solo and fuente in self.solo_notebook():
                continue
            q = CONSULTA_DIAGNOSTICO.get(IDIOMA_FUENTE.get(fuente, "jp"), "figure")
            s = self.d["salud"].setdefault(fuente, {"fallas_seguidas": 0, "avisado": False})
            try:
                n = len(fn(q))
                s["diagnostico"] = {"fecha": ahora(), "resultados": n, "error": ""}
            except Exception as e:
                n = 0
                s["diagnostico"] = {"fecha": ahora(), "resultados": 0, "error": str(e)[:300]}
            print(f"  {NOMBRE_FUENTE.get(fuente, fuente):28s} {n:4d}")
            if n == 0:
                self.guardar_debug(fuente)
                rotos.append(f"• {NOMBRE_FUENTE.get(fuente, fuente)}: {s['diagnostico']['error'] or '0 resultados'}")
            time.sleep(PAUSA)
        if rotos:
            self.texto("🛠 <b>Sitios que hoy no respondieron</b>\n" + "\n".join(rotos) +
                       "\nSi se repite varios días, mándale este mensaje a Claude.", silencioso=True)

    def guardar_debug(self, fuente: str):
        """Guarda en docs/debug/ la página que devolvió el sitio, para poder arreglar su lector."""
        from .fuentes import base
        dominio = {"yahoo": "auctions.yahoo.co.jp", "rakuma": "fril.jp", "surugaya": "www.suruga-ya.jp",
                   "mandarake": "order.mandarake.co.jp", "rakuten": "search.rakuten.co.jp",
                   "yahoo_shopping": "shopping.yahoo.co.jp", "offmall": "netmall.hardoff.co.jp",
                   "lashinbang": "shop.lashinbang.com", "ebay": "www.ebay.com",
                   "mercadolibre_cl": "listado.mercadolibre.cl"}.get(fuente)
        r = base.ULTIMA.get(dominio or "")
        if not r:
            return
        carpeta = DATOS.parent / "debug"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / f"{fuente}.html").write_text(
            f"<!-- {r['status']} {r['url']} -->\n" + r["texto"], encoding="utf-8")

    def aprender_referencias(self):
        for art_id, lista in self.d["vendidos"].items():
            precios = [v["precio_jpy"] for v in lista if v["precio_jpy"] and not v.get("junk") and not v.get("sin_caja")]
            if len(precios) >= 3:
                self.d["ref_aprendida"][art_id] = {
                    "mediana": round(statistics.median(precios)), "minimo": min(precios),
                    "maximo": max(precios), "n": len(precios), "fecha": ahora()}

    def resumen_diario(self):
        activos = [r for r in self.d["listados"].values() if self.reciente(r)]
        ofertas = [r for r in activos if r.get("nivel") in ("oferta", "bomba")]
        malas = [NOMBRE_FUENTE.get(f, f) for f, s in self.d["salud"].items() if s.get("fallas_seguidas", 0) >= 4]
        msg = (f"📋 <b>Resumen diario</b>\n{len(activos)} listados activos de tus artículos, "
               f"{len(ofertas)} en oferta.")
        if malas:
            msg += "\n🛠 Fuentes con problemas: " + ", ".join(malas)
        self.texto(msg, silencioso=True)

    # ---------- mantenimiento ----------
    @staticmethod
    def reciente(r, horas=24) -> bool:
        try:
            return datetime.now(timezone.utc) - datetime.fromisoformat(r["ultima_vez"]) < timedelta(hours=horas)
        except (KeyError, ValueError):
            return False

    def podar(self):
        por_art: dict[str, list] = {}
        for k, r in self.d["listados"].items():
            por_art.setdefault(r.get("articulo"), []).append((r.get("ultima_vez", ""), k))
        for lst in por_art.values():
            lst.sort(reverse=True)
            for _, k in lst[MAX_POR_ARTICULO:]:
                del self.d["listados"][k]

    def resumen_articulos(self) -> list[dict]:
        out = []
        for b in self.cfg.get("busquedas", []):
            for a in b.get("articulos", []):
                out.append({"id": a["id"], "nombre": a["nombre"], "busqueda": b["nombre"],
                            "referencia_jpy": a.get("precio_referencia_jpy"),
                            "presupuesto": a.get("presupuesto"), "prioridad": a.get("prioridad", "media"),
                            "tipo": a.get("tipo", ""), "paises": a.get("paises") or b.get("paises")})
        return out


def cargar_env():
    """En el notebook las claves van en un archivo .env (en GitHub van como secretos)."""
    f = RAIZ / ".env"
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def links_manuales(config: dict) -> list[dict]:
    """Búsquedas listas para abrir a mano en los sitios que no permiten bots."""
    from urllib.parse import quote
    plantillas = {
        "goofish": "https://www.goofish.com/search?q={q}",
        "surugaya": "https://www.suruga-ya.jp/search?search_word={q}",
        "lashinbang": "https://shop.lashinbang.com/products/list?keyword={q}",
        "offmall": "https://netmall.hardoff.co.jp/search/?q={q}",
        "amiami": "https://www.amiami.com/eng/search/list/?s_keywords={q}&s_st_condition_flg=1",
        "rakuten": "https://search.rakuten.co.jp/search/mall/{q}/?s=4",
        "yahoo_shopping": "https://shopping.yahoo.co.jp/search?p={q}",
    }
    out = []
    for b in config.get("busquedas", []):
        for f in config.get("ajustes", {}).get("revision_manual", []):
            if f not in plantillas:
                continue
            qs = b.get("consultas", {}).get(IDIOMA_FUENTE.get(f, "jp")) or b.get("consultas", {}).get("jp") or []
            for q in qs[:2]:
                out.append({"busqueda": b["nombre"], "fuente": f, "consulta": q,
                            "url": plantillas[f].format(q=quote(q))})
    return out


def main():
    global DATOS
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", default="normal", choices=["normal", "historico", "diagnostico", "prueba"])
    ap.add_argument("--sin-enviar", action="store_true", help="no manda mensajes, solo imprime")
    ap.add_argument("--solo", help="fuentes separadas por coma (ej: goofish)")
    ap.add_argument("--datos", help="archivo de historial alternativo (modo notebook)")
    ap.add_argument("--forzar", action="store_true", help="revisar todas las fuentes ahora")
    ap.add_argument("--repetir", type=int, default=0,
                    help="seguir trabajando N minutos, revisando cada --intervalo (GitHub atrasa los horarios)")
    ap.add_argument("--intervalo", type=int, default=15)
    args = ap.parse_args()
    cargar_env()
    if args.datos:
        DATOS = Path(args.datos).resolve()

    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if args.modo == "prueba":
        ok = avisos.telegram_texto("✅ ¡Funciona! El cazador de figuras te puede mandar alertas.")
        print("Mensaje enviado" if ok else "No se pudo enviar (revisa TELEGRAM_TOKEN y TELEGRAM_CHAT_ID)")
        return
    datos = cargar_datos()
    solo = [x.strip() for x in args.solo.split(",")] if args.solo else None
    c = Cazador(config, datos, enviar=not args.sin_enviar, solo=solo, forzar=args.forzar)
    if args.modo == "historico":
        c.historico()
    elif args.modo == "diagnostico":
        c.diagnostico()
    else:
        inicio = time.time()
        while True:
            vuelta = time.time()
            c.rastrear()
            guardar_datos(c.d)
            if not args.repetir:
                break
            siguiente = vuelta + args.intervalo * 60
            if siguiente - inicio > args.repetir * 60:
                break
            print(f"Esperando {max(0, int(siguiente - time.time()))} s para la próxima revisión…", flush=True)
            time.sleep(max(0, siguiente - time.time()))
            c = Cazador(config, c.d, enviar=not args.sin_enviar, solo=solo, forzar=args.forzar)
    guardar_datos(c.d)


if __name__ == "__main__":
    main()

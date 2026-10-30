"""Decide a qué artículo corresponde cada listado y si es una oferta."""
from __future__ import annotations

from typing import Optional

from .modelos import Listado, normalizar, contiene

SIN_CAJA = ["箱なし", "箱無し", "箱無", "本体のみ", "ルース", "loose", "no box", "without box", "sin caja", "箱欠品"]
JUNK = ["ジャンク", "junk", "破損", "欠品", "難あり", "訳あり", "dañad", "roto", "broken", "damaged"]


class Clasificador:
    def __init__(self, config: dict):
        self.ajustes = config.get("ajustes", {})
        self.excluir_global = config.get("excluir_global", [])
        self.ref_aprendida = {}   # lo llena el Cazador con las ventas reales

    # ---------- coincidencias ----------
    def personajes_texto(self, busqueda: dict, titulo: str) -> list[str]:
        return self.personajes_en(busqueda, normalizar(titulo))

    def personajes_en(self, busqueda: dict, titulo_norm: str) -> list[str]:
        t = titulo_norm
        for frase in busqueda.get("quitar_antes_de_detectar", []):
            t = t.replace(normalizar(frase), " ")
        ambiguos = busqueda.get("alias_ambiguos") or {}
        seguros, dudosos = [], []
        for pid, alias in (busqueda.get("personajes") or {}).items():
            amb = [normalizar(x) for x in ambiguos.get(pid, [])]
            firmes = [x for x in alias if normalizar(x) not in amb]
            if contiene(t, firmes):
                seguros.append(pid)
            elif contiene(t, amb):
                dudosos.append(pid)
        es_lote = contiene(t, busqueda.get("palabras_lote", []))
        if dudosos and (not seguros or es_lote):
            seguros += dudosos
        orden = list((busqueda.get("personajes") or {}).keys())
        return sorted(set(seguros), key=orden.index)

    @staticmethod
    def _cumple_reglas(art: dict, titulo_norm: str) -> bool:
        for grupo in art.get("incluir", []) or []:
            if not contiene(titulo_norm, grupo):
                return False
        if contiene(titulo_norm, art.get("excluir", [])):
            return False
        return True

    def clasificar(self, busqueda: dict, listado: Listado) -> Optional[dict]:
        """Devuelve el artículo (dict) al que corresponde el listado, o None."""
        t = normalizar(listado.titulo)
        if contiene(t, self.excluir_global) or contiene(t, busqueda.get("excluir", [])):
            return None
        if busqueda.get("debe_incluir") and not contiene(t, busqueda["debe_incluir"]):
            return None

        arts = busqueda.get("articulos", [])
        if contiene(t, busqueda.get("palabras_piezas", [])):
            # caja vacía o pieza suelta: va solo al artículo de piezas (si existe)
            piezas = next((a for a in arts if a.get("tipo") == "piezas"), None)
            return piezas if piezas and self._cumple_reglas(piezas, t) else None
        hay_personajes = bool(busqueda.get("personajes"))
        pers = self.personajes_en(busqueda, t) if hay_personajes else []

        if hay_personajes and len(pers) >= 2:
            lote = next((a for a in arts if a.get("tipo") == "lote"), None)
            if lote and self._cumple_reglas(lote, t):
                return lote
            return None

        for art in arts:
            if art.get("tipo") in ("lote", "piezas"):
                continue
            if art.get("personaje"):
                if pers != [art["personaje"]]:
                    continue
            if self._cumple_reglas(art, t):
                return art
        return None

    def referencia_lote(self, busqueda: dict, listado: Listado) -> Optional[float]:
        """Suma la referencia de cada figura detectada en un lote."""
        t = normalizar(listado.titulo)
        total = 0.0
        for pid in self.personajes_en(busqueda, t):
            candidatos = [
                a for a in busqueda.get("articulos", [])
                if a.get("personaje") == pid and a.get("precio_referencia_jpy")
            ]
            if not candidatos:
                continue
            elegido = next((a for a in candidatos if self._cumple_reglas(a, t)), candidatos[0])
            aprendida = (self.ref_aprendida or {}).get(elegido["id"], {})
            total += float(aprendida["mediana"] if aprendida.get("n", 0) >= 5 else elegido["precio_referencia_jpy"])
        return total or None

    # ---------- evaluación de precio ----------
    def evaluar(self, art: dict, precio_jpy: Optional[float], precio_presupuesto: Optional[float],
                referencia: Optional[float]) -> dict:
        """precio_presupuesto = precio convertido a la moneda del presupuesto."""
        res = {"nivel": "normal", "descuento": None, "bajo_presupuesto": False}
        if precio_jpy is None:
            return res
        umbral = float(art.get("umbral_oferta", self.ajustes.get("umbral_oferta", 0.30)))
        bomba = float(art.get("umbral_bomba", self.ajustes.get("umbral_bomba", 0.50)))
        if referencia:
            desc = 1 - precio_jpy / referencia
            res["descuento"] = round(desc, 3)
            if desc >= bomba:
                res["nivel"] = "bomba"
            elif desc >= umbral:
                res["nivel"] = "oferta"
        pres = art.get("presupuesto")
        if pres and precio_presupuesto is not None and precio_presupuesto <= float(pres["monto"]):
            res["bajo_presupuesto"] = True
            if res["nivel"] == "normal":
                res["nivel"] = "oferta"
        return res

    @staticmethod
    def sin_caja(titulo: str) -> bool:
        return contiene(normalizar(titulo), SIN_CAJA)

    @staticmethod
    def es_junk(titulo: str) -> bool:
        return contiene(normalizar(titulo), JUNK)

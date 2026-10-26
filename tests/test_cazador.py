"""Pruebas sin internet: clasificación con títulos reales, lectura de HTML y flujo de alertas."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cazador.clasificador import Clasificador
from cazador.modelos import Listado, parse_precio, normalizar
from cazador.fuentes import yahoo, tiendas
from cazador import main as M

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text(encoding="utf-8"))
B = CFG["busquedas"][0]
C = Clasificador(CFG)


def art(titulo):
    a = C.clasificar(B, Listado("yahoo", "x", titulo, 1000, "JPY", "u"))
    return a["id"] if a else None


# Títulos reales vistos en Yahoo Auctions (jul–oct 2026)
CASOS = {
    "リアルアクションヒーローズ No.695 RAH MGM 魔法少女まどか☆マギカ 暁美ほむら 制服Ver. (ワンダーフェスティバル2015 [冬] 開催記念品)": "homura_escolar",
    "ジャンク　リアルアクションヒーローズ No.695 RAH MGM 魔法少女まどか☆マギカ 暁美ほむら 制服Ver.(ワンダーフェスティバル2015[冬]": "homura_escolar",
    "魔法少女まどか☆マギカ RAH MGM 鹿目まどか 制服 Ver.": "madoka_escolar",
    "開封品　RAH MGM 鹿目まどか 制服Ver. 劇場版 魔法少女まどか☆マギカ　フィギュア　NO2449": "madoka_escolar",
    "1円～ 未開封 メディコム・トイ RAH MGM 劇場版 魔法少女まどか☆マギカ 前編 始まりの物語/後編 永遠の物語 美樹さやか 制服Ver.": "sayaka_escolar",
    "劇場版 魔法少女まどか☆マギカ 美樹さやか 制服Ver. RAH MGM 新品未開封　WF2015 800体限定": "sayaka_escolar",
    "iohso メディコム・トイ RAH リアルアクションヒーローズ MGM 魔法少女まどか☆マギカ 佐倉 杏子": "kyoko_magica",
    "RAH MGM 佐倉杏子 私服Ver. 劇場版 魔法少女まどか☆マギカ": "kyoko_civil",
    "RAH MGM No.610 巴マミ 魔法少女まどか☆マギカ": "mami_magica",
    "1円～ メディコム・トイ RAH リアルアクションヒーローズ MGM 魔法少女まどか☆マギカ 新編 叛逆の物語 巴マミ 制服Ver.": None,  # Mami escolar: no la pediste
    "RAH MGM 暁美ほむら　魔法少女まどかマギカ　メディコムトイ": "homura_magica",
    "1円～ 未開封 メディコム・トイ RAH リアルアクションヒーローズ MGM 魔法少女まどか☆マギカ 暁美ほむら": "homura_magica",
    "メディコムトイ RAH 741 劇場版まどかマギカ 新編 叛逆の物語 【百江なぎさ】": "nagisa",
    "魔法少女まどかマギカ　制服版　RAH MGM WF開催記念限定品　5体セット　全て未開封新品　1/6 まどか　ほむら　マミ　さやか　杏子　絶版": "lotes",
    "RAH MGM　アルティメットまどか　リアルアクションヒーローズ No.673 魔法少女まどか☆マギカ メディコム・トイ": None,
    "RAH MGM 鹿目まどか 魔法少女まどか☆マギカ リアルアクションヒーローズ": None,  # Madoka transformada: no la pediste
    "ねんどろいど 暁美ほむら 制服Ver.": None,
    "RAH MGM 暁美ほむら 制服Ver. 箱のみ": "piezas",
    "RAH MGM 美樹さやか 制服 ヘッドのみ": "piezas",
    "メディコム RAH まどか 空箱 本体なし": "piezas",
    "RAH 魔法少女小圆 晓美焰 校服 二手": "homura_escolar",
    "RAH 魔法少女小圆 佐仓杏子 便服": "kyoko_civil",
    "RAH 小圆 空盒": "piezas",
    "RAH 渚カヲル エヴァンゲリオン": None,
    "RAH Kaworu Nagisa Evangelion": None,
    "Figura RAH Medicom Madoka Magica Homura Nueva": "homura_magica",
    "RAH Medicom Madoka Homura school uniform": "homura_escolar",
    "RAH 小圆 晓美焰 校服": "homura_escolar",
    "RAH Madoka Kaname school uniform": "madoka_escolar",
    "RAH まどか ほむら 制服 2体セット": "lotes",
    "RAH 鹿目まどか 暁美ほむら 制服": "lotes",
    "30MP 鹿目まどか(制服Ver.)": None,
    "非売品 チラシ RAH MGM 暁美ほむら 制服": None,
    "RAH MGM 暁美ほむら 制服Ver. 箱なし 本体のみ": "homura_escolar",
    "ジャンク 欠品あり RAH 美樹さやか 制服 箱無し": "sayaka_escolar",
    "RAH Homura Akemi school uniform loose no box": "homura_escolar",
    "Medicom RAH Real Action Heroes Puella Magi Madoka Magica Homura Akemi school uniform": "homura_escolar",
    "RAH Real Action Heroes Puella Magi Madoka Magica Tomoe Mami Medicom Toy figure": "mami_magica",
    "Figura RAH Medicom Madoka Magica Kyoko Sakura": "kyoko_magica",
}


def test_clasificacion():
    errores = [(t, esperado, art(t)) for t, esperado in CASOS.items() if art(t) != esperado]
    assert not errores, "\n".join(f"{e} != {o} :: {t}" for t, e, o in errores)


def test_precios():
    assert parse_precio("¥12,345") == 12345
    assert parse_precio("落札45,501円") == 45501
    assert parse_precio("$ 45.990") == 45990
    assert parse_precio("US $123.45") == 123.45
    assert parse_precio("１２，０００円") == 12000


def test_referencia_lote():
    l = Listado("yahoo", "x", "RAH MGM 制服版 まどか ほむら さやか 杏子 セット", 1, "JPY", "u")
    assert C.referencia_lote(B, l) == 45000 + 45000 + 50000 + 40000


def test_etiquetas():
    assert C.sin_caja("RAH ほむら 制服 箱なし") and not C.sin_caja("RAH ほむら 制服 未開封")
    assert C.es_junk("ジャンク RAH さやか")


def test_normalizar_katakana():
    assert normalizar("ホムラ") == normalizar("ほむら")


YAHOO_HTML = """
<html><body><ul>
<li class="Product">
  <div class="Product__image"><a class="Product__imageLink" href="https://auctions.yahoo.co.jp/jp/auction/e1246118405"
    data-auction-id="e1246118405" data-auction-title="RAH MGM 暁美ほむら 制服Ver."
    data-auction-img="https://auctions.c.yimg.jp/img/a.jpg" data-auction-price="12000"><img src="https://auctions.c.yimg.jp/img/a.jpg"></a></div>
  <div class="Product__detail"><a href="https://auctions.yahoo.co.jp/jp/auction/e1246118405">RAH MGM 暁美ほむら 制服Ver.</a>
  <span>現在 12,000円</span><span>即決 30,000円</span><span>入札 3</span></div>
</li>
<li class="Product">
  <a href="https://paypayfleamarket.yahoo.co.jp/item/z618461928">美樹さやか 制服Ver. RAH MGM</a>
  <img src="https://img/b.jpg"><span>39,800円</span>
</li>
</ul></body></html>"""


def test_yahoo_parser():
    ls = yahoo._listados(YAHOO_HTML, cerrados=False)
    assert len(ls) == 2
    h = next(l for l in ls if l.id == "e1246118405")
    assert h.precio == 12000 and h.compra_inmediata == 30000 and h.subasta and h.pujas == 3
    assert h.foto.endswith("a.jpg")
    s = next(l for l in ls if l.id == "z618461928")
    assert s.precio == 39800 and not s.subasta


YAHOO_CERRADO = """<ul><li><a href="https://auctions.yahoo.co.jp/jp/auction/w1246104932">魔法少女まどか☆マギカ RAH MGM 鹿目まどか 制服 Ver.</a>
<img src="https://x/c.jpg"> 落札65,001円 開始37,000円 未使用 30 9/30 20:40終了</li></ul>"""


def test_yahoo_cerrado():
    ls = yahoo._listados(YAHOO_CERRADO, cerrados=True)
    assert ls[0].precio == 65001 and ls[0].vendido and "9/30" in ls[0].fecha_venta


MELI_HTML = """<ol><li class="ui-search-layout__item"><div class="poly-card">
<img data-src="https://http2.mlstatic.com/x.webp">
<h3><a href="https://articulo.mercadolibre.cl/MLC-1234567890-figura-rah-madoka-_JM">Figura RAH Medicom Madoka Magica Homura</a></h3>
<span class="andes-money-amount__fraction">89.990</span></div></li></ol>"""


def test_mercadolibre_parser(monkeypatch):
    monkeypatch.setattr(tiendas, "descargar", lambda *a, **k: MELI_HTML)
    ls = tiendas.mercadolibre_cl("rah madoka")
    assert ls[0].precio == 89990 and ls[0].moneda == "CLP" and ls[0].id == "MLC1234567890"


def test_flujo_alertas(monkeypatch, tmp_path):
    """Primera corrida: avisa ofertas existentes. Segunda: avisa lo nuevo y bajadas de precio."""
    lotes = {"n": 1}

    def falso_mercari(q):
        base = [Listado("mercari", "m1", "RAH MGM 暁美ほむら 制服Ver.", 50000, "JPY", "u1", "f1")]
        if lotes["n"] >= 2:
            base.append(Listado("mercari", "m2", "RAH MGM 美樹さやか 制服Ver. ジャンク", 20000, "JPY", "u2", "f2"))
        if lotes["n"] >= 3:
            base[0].precio = 21000
        return base

    monkeypatch.setattr(M, "FUENTES", {"mercari": (falso_mercari, None)})
    monkeypatch.setattr(M, "PAUSA", 0)
    monkeypatch.setattr(M.monedas, "actualizar", lambda g: {"base": "JPY", "tasas": {"JPY": 1, "CLP": 6.3}, "fecha": 1})
    cfg = {**CFG, "busquedas": [{**B, "fuentes": ["mercari"]}]}
    enviados = []
    monkeypatch.setattr(M.Cazador, "alertar", lambda self, tipo, art, reg, ref, ev, silencioso=False: enviados.append((tipo, art["id"])))
    monkeypatch.setattr(M.Cazador, "texto", lambda self, msg, silencioso=False: None)

    d = {}
    M.Cazador(cfg, d).rastrear()
    assert enviados == []                      # ¥50.000 no es oferta y la 1ra vez no se avisa "nuevo"
    lotes["n"] = 2
    M.Cazador(cfg, d).rastrear()
    assert enviados == [("bomba", "sayaka_escolar")]   # (20.000+9.000) vs (50.000+9.000) = 51% menos
    lotes["n"] = 3
    M.Cazador(cfg, d).rastrear()
    assert ("oferta", "homura_escolar") in enviados     # ¥21.000 + ¥9.000 envío vs ¥54.000 = 44% menos
    M.Cazador(cfg, d).rastrear()
    assert len(enviados) == 2                  # no repite alertas
    assert d["listados"]["mercari:m2"]["junk"] is True


def test_costo_total_chile(monkeypatch):
    """Una figura en Chile sin envío puede ganarle a una 'más barata' en Japón."""
    monkeypatch.setattr(M.monedas, "actualizar", lambda g: {"base": "JPY", "tasas": {"JPY": 1, "CLP": 6.3, "USD": 0.0066, "CNY": 0.047}, "fecha": 1})
    c = M.Cazador(CFG, {}, enviar=False)
    homura = next(a for a in B["articulos"] if a["id"] == "homura_escolar")
    jp = Listado("mercari", "m9", "x", 25000, "JPY", "u")
    cl = Listado("mercadolibre_cl", "c9", "x", 189000, "CLP", "u")          # = ¥30.000
    eb = Listado("ebay", "e9", "x", 150, "USD", "u", envio=60)              # ¥22.727 + ¥9.091
    assert c.costo_chile(homura, jp) == 9000
    assert c.costo_chile(homura, cl) == 0
    assert round(c.costo_chile(homura, eb)) == round(60 / 0.0066)
    piezas = next(a for a in B["articulos"] if a["id"] == "piezas")
    assert c.costo_chile(piezas, jp) == 4500


def test_goofish_interpretar():
    from cazador.fuentes import goofish
    resp = {"ret": ["SUCCESS::调用成功"], "data": {"resultList": [
        {"data": {"item": {"main": {"exContent": {"itemId": "8123", "title": "RAH 魔法少女小圆 晓美焰 校服",
            "price": [{"text": "¥"}, {"text": "1200"}], "picUrl": "//img.alicdn.com/a.jpg"}}}}},
        {"data": {"item": {"main": {"exContent": {"itemId": "8124", "title": "RAH 小圆 套装",
            "price": [{"text": "1.2万"}], "picUrl": "https://x/b.jpg"}}}}}]}}
    ls = goofish.interpretar(resp)
    assert ls[0].precio == 1200 and ls[0].moneda == "CNY" and ls[0].foto.startswith("https://")
    assert ls[1].precio == 12000
    assert goofish.firmar("tok", "1", "{}") == __import__("hashlib").md5(b"tok&1&34839810&{}").hexdigest()


def test_ebay_envio(monkeypatch):
    html = """<ul><li class="s-item"><a href="https://www.ebay.com/itm/123456789012">RAH Medicom Madoka Homura school uniform</a>
    <img src="https://i.ebayimg.com/a.jpg"><span>$150.00</span><span>+$45.50 shipping</span></li>
    <li class="s-item"><a href="https://www.ebay.com/itm/223456789012">RAH Medicom Mami</a><span>$99.99</span><span>Free International Shipping</span></li></ul>"""
    monkeypatch.setattr(tiendas, "descargar", lambda *a, **k: html)
    ls = {l.id: l for l in tiendas.ebay("rah madoka")}
    assert ls["123456789012"].precio == 150 and ls["123456789012"].envio == 45.5
    assert ls["223456789012"].envio == 0


def test_yahoo_diseno_2026():
    """Página real de Yahoo (26-10-2026): los productos vienen en __NEXT_DATA__."""
    html = (Path(__file__).parent / "datos" / "yahoo_2026.html").read_text(encoding="utf-8")
    ls = {l.id: l for l in yahoo._listados(html, cerrados=False)}
    assert len(ls) == 12
    flea = ls["z707344464"]
    assert flea.url.startswith("https://paypayfleamarket") and not flea.subasta and flea.precio == 50000
    sub = ls["r1244775112"]
    assert sub.subasta and sub.compra_inmediata == 60000 and sub.termina.startswith("2026-10-30")
    clasif = {i: art(l.titulo) for i, l in ls.items()}
    assert clasif["z707344464"] == "homura_escolar"
    assert clasif["r1244775112"] == "homura_escolar"
    assert clasif["z516649870"] == "kyoko_magica"
    assert clasif["o1246133720"] == "mami_magica"
    assert clasif["r1248073141"] == "homura_magica"
    assert clasif["q1195912203"] is None          # folleto, no figura
    assert clasif["e1246114875"] is None          # Mami escolar: no está en tu lista

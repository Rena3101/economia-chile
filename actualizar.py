#!/usr/bin/env python3
"""Regenera data.json (junto a index.html). Solo usa la librería estándar de Python.

- Indicadores (UF, dólar, euro): API mindicador.cl, que replica los valores oficiales.
- BioBioChile: lee directamente la página de Economía (no se encontró un RSS).
- Cooperativa: lee su RSS general y se queda con titulares económicos.
"""
import html, json, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

BIO_URL = "https://www.biobiochile.cl/lista/categorias/economia"
COOP_RSS = "https://www.cooperativa.cl/noticias/site/tax/port/all/rss____1.xml"
CLAVES = ["dólar", "banco central", "ipc", "pib", "imacec", "tasa", "cobre", "bencina",
          "combustible", "bolsa", "economía", "inversión", "empresa", "mercado", "petróleo",
          "inflación", "desempleo", "empleo", "ocde", "litio", "exportaci", "arancel",
          "chips", "acciones", "ventas", "fmi", "fed "]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=25).read()


def clp(x):  # 41350.42 -> "41.350,42"
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def puntaje(titulo):
    return sum(k in titulo.lower() for k in CLAVES)


def noticias_bio(h):
    """Extrae [titulo, enlace, fecha] de la página de Economía de BioBioChile."""
    out, vistos = [], set()

    def agregar(url, bruto):
        tit = html.unescape(re.sub(r"<[^>]+>", "", bruto)).strip()
        if url.startswith("/"):
            url = "https://www.biobiochile.cl" + url
        if "/noticias/" not in url or len(tit) < 20 or url in vistos:
            return
        vistos.add(url)
        d = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        out.append([tit, url, f"{d.group(3)}-{d.group(2)}" if d else ""])

    for m in re.finditer(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h, re.S):
        agregar(m.group(1), m.group(2))
    if len(out) < 3:  # plan B: cualquier enlace a notas de economía
        for m in re.finditer(r'<a[^>]*href="([^"]*/noticias/economia/[^"]+\.shtml)"[^>]*>(.*?)</a>', h, re.S):
            agregar(m.group(1), m.group(2))
    return out[:10]


def noticias_rss(xml_bytes):
    out = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        out.append([it.findtext("title", "").strip(), it.findtext("link", "").strip(),
                    (it.findtext("pubDate") or "")[5:11]])
    return out


def seguro(nombre, f):
    try:
        return f()
    except Exception as e:  # una fuente caída no debe tumbar todo
        print(f"AVISO: falló {nombre}: {e}")
        return []


def main():
    ahora = datetime.now(ZoneInfo("America/Santiago"))
    ind = json.loads(get("https://mindicador.cl/api"))
    bio = seguro("BioBioChile", lambda: noticias_bio(get(BIO_URL).decode("utf-8", "replace")))
    coop = seguro("Cooperativa", lambda: noticias_rss(get(COOP_RSS)))
    coop = [n for n in coop if puntaje(n[0]) > 0][:6]
    print(f"BioBioChile: {len(bio)} notas | Cooperativa: {len(coop)} notas")
    if not bio and not coop:
        raise SystemExit("Sin noticias: no se actualiza data.json")

    top = sorted(bio + coop, key=lambda n: -puntaje(n[0]))[:5]
    data = {
        "updated": ahora.strftime("%d-%m-%Y %H:%M"),
        "ind": {"fecha": ahora.strftime("%d-%m-%Y"), "uf": clp(ind["uf"]["valor"]),
                "usd": clp(ind["dolar"]["valor"]), "eur": clp(ind["euro"]["valor"])},
        "resumen": [{"t": n[0], "d": ""} for n in top],
        "bio": bio, "coop": coop,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("data.json actualizado", data["updated"])


if __name__ == "__main__":
    main()

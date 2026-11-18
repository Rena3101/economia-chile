#!/usr/bin/env python3
#!/usr/bin/env python3
"""Regenera data.json (junto a index.html). Solo usa la librería estándar de Python.

- Indicadores (UF, dólar, euro): API mindicador.cl, que replica los valores oficiales.
- BioBioChile: lee directamente la página de Economía (no se encontró un RSS).
- Cooperativa: lee su RSS general y se queda con titulares económicos.
Si una fuente no responde, se reintenta y, si sigue fallando, se conservan los
últimos datos buenos de data.json en vez de romper la página.
"""
import html, json, re, time, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

BIO_URL = "https://www.biobiochile.cl/lista/categorias/economia"
COOP_RSS = "https://www.cooperativa.cl/noticias/site/tax/port/all/rss____1.xml"
CLAVES = ["dólar", "banco central", "ipc", "pib", "imacec", "tasa", "cobre", "bencina",
          "combustible", "bolsa", "economía", "inversión", "empresa", "mercado", "petróleo",
          "inflación", "desempleo", "empleo", "ocde", "litio", "exportaci", "arancel",
          "chips", "acciones", "ventas", "fmi", "fed "]


def get(url, intentos=3, espera=5, timeout=45):
    """Descarga con reintentos: los servidores chilenos a veces responden lento."""
    error = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0", "Accept": "application/json, text/html, */*"})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            error = e
            print(f"Intento {i + 1}/{intentos} falló ({url}): {e}")
            if i < intentos - 1:
                time.sleep(espera * (i + 1))
    raise error


def clp(x):  # 41350.42 -> "41.350,42"
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def puntaje(titulo):
    return sum(k in titulo.lower() for k in CLAVES)


def noticias_bio(h):
    """Extrae [titulo, enlace, fecha] de la página de Economía de BioBioChile.
    Prueba varias formas de leer el HTML, de la más precisa a la más general."""
    h = h.replace("\\/", "/")  # enlaces escapados dentro de JSON
    patron_url = r"/noticias/.+/\d{4}/\d{2}/\d{2}/[^/?#]+\.shtml"

    def limpia(url):
        url = re.split(r"[?#]", url.strip())[0]
        return "https://www.biobiochile.cl" + url if url.startswith("/") else url

    def fila(url, tit):
        d = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
        return [tit, url, f"{d.group(3)}-{d.group(2)}" if d else ""]

    # 1) Enlaces con texto (sirve si el título va dentro de <h2>, <h3> o <span>)
    cand, vistos = [], set()
    for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h, re.S):
        url = limpia(m.group(1))
        tit = html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        tit = re.sub(r"\s+", " ", tit).strip()
        if re.search(patron_url, url) and len(tit) >= 20 and url not in vistos:
            vistos.add(url)
            cand.append(fila(url, tit))
    out = [c for c in cand if "/noticias/economia/" in c[1]]
    if len(out) < 3:
        out = cand
    # 2) Último recurso: armar el título con el texto del propio enlace
    if len(out) < 3:
        urls = []
        for u in re.findall(r"""(?:https?://www\.biobiochile\.cl)?/noticias/[^\s"'<>\\]+?\.shtml""", h):
            u = limpia(u)
            if re.search(patron_url, u) and u not in urls:
                urls.append(u)
        pref = [u for u in urls if "/noticias/economia/" in u] or urls
        out = [fila(u, u.rsplit("/", 1)[-1][:-6].replace("-", " ").capitalize()) for u in pref]
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
        return None


def main():
    print("actualizar.py versión 3")
    ahora = datetime.now(ZoneInfo("America/Santiago"))
    try:
        with open("data.json", encoding="utf-8") as f:
            previo = json.load(f)
    except Exception:
        previo = {}

    # Indicadores: si mindicador.cl no responde, se conservan los últimos valores buenos
    def leer_indicadores():
        d = json.loads(get("https://mindicador.cl/api"))
        return {"fecha": ahora.strftime("%d-%m-%Y"), "uf": clp(d["uf"]["valor"]),
                "usd": clp(d["dolar"]["valor"]), "eur": clp(d["euro"]["valor"])}

    ind = seguro("mindicador.cl", leer_indicadores)
    if not ind:
        ind = previo.get("ind")
        if not ind:
            raise SystemExit("Sin indicadores (mindicador.cl no respondió) y sin datos previos")
        print("AVISO: se conservan los indicadores anteriores:", ind.get("fecha"))

    def leer_bio():
        h = get(BIO_URL).decode("utf-8", "replace")
        notas = noticias_bio(h)
        print(f"BioBioChile: página de {len(h)} caracteres, {len(notas)} notas encontradas")
        if not notas:
            print("Inicio de la página:", re.sub(r"\s+", " ", h[:300]))
        return notas

    bio_n = seguro("BioBioChile", leer_bio)
    coop_n = seguro("Cooperativa", lambda: noticias_rss(get(COOP_RSS)))
    bio = bio_n or previo.get("bio", [])
    rel = [n for n in (coop_n or []) if puntaje(n[0]) > 0]
    print(f"Cooperativa: {len(coop_n or [])} notas en el feed, {len(rel)} con palabras clave")
    coop = (rel[:6] or (coop_n or [])[:4]) or previo.get("coop", [])
    print(f"BioBioChile: {len(bio)} notas | Cooperativa: {len(coop)} notas")
    if not bio and not coop:
        raise SystemExit("Sin noticias: no se actualiza data.json")

    top = sorted(bio + coop, key=lambda n: -puntaje(n[0]))[:5]
    data = {"updated": ahora.strftime("%d-%m-%Y %H:%M"), "ind": ind,
            "resumen": [{"t": n[0], "d": ""} for n in top], "bio": bio, "coop": coop}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("data.json actualizado", data["updated"])


if __name__ == "__main__":
    main()

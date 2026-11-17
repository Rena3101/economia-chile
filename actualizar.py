#!/usr/bin/env python3
"""Regenera data.json (junto a economia-chile.html). Solo librería estándar.
Ejecútalo cada 30-60 min con cron o una tarea programada."""
import json, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

# Reemplaza BIO por el RSS de Economía (lista en https://www.biobiochile.cl/static/feed-rss)
FEEDS = {
    "bio":  "https://www.biobiochile.cl/static/feed-rss",
    "coop": "https://www.cooperativa.cl/noticias/site/tax/port/all/rss____1.xml",
}
CLAVES = ["dólar", "uf", "banco central", "ipc", "pib", "imacec", "tasa", "cobre",
          "bencina", "combustible", "bolsa", "economía", "inversión", "empresa", "mercado"]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read()

def clp(x):  # 41350.42 -> "41.350,42"
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def noticias(url, n=10):
    out = []
    for it in ET.fromstring(get(url)).iter("item"):
        out.append([it.findtext("title", "").strip(), it.findtext("link", "").strip(),
                    (it.findtext("pubDate") or "")[5:11]])
    return out[:n]

def puntaje(titulo):
    return sum(k in titulo.lower() for k in CLAVES)

# Indicadores: mindicador.cl replica los valores oficiales (UF, dólar observado, euro).
# Alternativa oficial: API BDE del Banco Central (requiere registro).
ind = json.loads(get("https://mindicador.cl/api"))
data = {
    "updated": datetime.now(ZoneInfo("America/Santiago")).strftime("%d-%m-%Y %H:%M"),
    "ind": {"fecha": datetime.now(ZoneInfo("America/Santiago")).strftime("%d-%m-%Y"),
            "uf": clp(ind["uf"]["valor"]), "usd": clp(ind["dolar"]["valor"]),
            "eur": clp(ind["euro"]["valor"])},
    "bio": noticias(FEEDS["bio"]),
    "coop": noticias(FEEDS["coop"], 30),
}
data["coop"] = sorted(data["coop"], key=lambda n: -puntaje(n[0]))[:6]
# Resumen simple: los 5 titulares con más palabras clave. Para un resumen redactado,
# envía estos titulares a la API de Claude desde aquí y guarda el texto en "resumen".
top = sorted(data["bio"] + data["coop"], key=lambda n: -puntaje(n[0]))[:5]
data["resumen"] = [{"t": t[0], "d": ""} for t in top]

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
print("data.json actualizado", data["updated"])

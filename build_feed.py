#!/usr/bin/env python3
"""
Arma UN feed RSS con todos los issues del newsletter:
  - los viejos, desde el archivo de listmonk (listmonk_archive.xml)
  - los nuevos de Mailmodo, desde la carpeta issues/ (.eml o .html)

Limpia cada issue para que sirva en una página web:
  - saca el pixel de tracking, los links de baja y el preheader oculto
  - reemplaza los links de tracking por la URL real
  - borra merge tags sin reemplazar ({{...}})

Todo se configura en config.json. Instrucciones en README.md.
"""
import csv
import html as htmllib
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
ISSUES_DIR = ROOT / "issues"
OUT = ROOT / "site"
CACHE_FILE = ROOT / "link_cache.json"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
REDIRECT_CODES = {301, 302, 303, 307, 308}

CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SITE_URL = CFG["site_url"].rstrip("/")
WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print("  AVISO:", msg)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70] or "issue"


def parse_date(value):
    """Acepta 2026-07-16, 2026-07-16T15:00:00+00:00 o 16/07/2026."""
    value = value.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if m:
        d, mo, y = map(int, m.groups())
        return datetime(y, mo, d, 12, 0, tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value)
    if len(value) == 10:  # solo fecha: mediodía UTC para que no cambie de día
        dt = dt.replace(hour=12)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- links

class LinkResolver:
    """Sigue los redirects de tracking hasta la URL real. Guarda un cache
    para no volver a pedir el mismo link en cada build."""

    def __init__(self):
        self.hosts = [h.lower() for h in CFG.get("tracking_hosts", [])]
        self.cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}

    def is_tracking(self, url):
        host = urlparse(url).netloc.lower().split(":")[0]
        return any(host == h or host.endswith("." + h) for h in self.hosts)

    def resolve(self, url):
        if url in self.cache:
            return self.cache[url]
        current = url
        try:
            for _ in range(8):
                if not self.is_tracking(current):
                    break
                r = requests.get(current, allow_redirects=False, timeout=20, stream=True,
                                 headers={"User-Agent": "Mozilla/5.0 (newsletter-feed-builder)"})
                r.close()
                loc = r.headers.get("Location")
                if r.status_code not in REDIRECT_CODES or not loc:
                    break
                current = urljoin(current, loc)
        except requests.RequestException as e:
            warn(f"no pude resolver {url} ({e.__class__.__name__}), queda como está")
            return url
        if current == url:
            # No redirigió a ningún lado: no se guarda en cache para reintentar en el próximo build
            warn(f"no pude resolver {url} (no redirige), queda como está")
            return url
        self.cache[url] = current
        return current

    def save(self):
        CACHE_FILE.write_text(json.dumps(self.cache, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- limpieza

def norm(text):
    return text.lower().replace("\u2019", "'")


def clean(html, resolver, title):
    tags = re.findall(r"\{\{[^{}]*\}\}", html)
    if tags:
        sample = ", ".join(sorted(set(tags))[:3])
        warn(f"'{title}': saqué {len(tags)} merge tags sin reemplazar ({sample})")
        html = re.sub(r"\{\{[^{}]*\}\}", "", html)

    soup = BeautifulSoup(html, "html.parser")

    # 1. Pixel de tracking
    pixel_pats = [p.lower() for p in CFG.get("pixel_patterns", [])]
    for img in soup.find_all("img"):
        src = (img.get("src") or "").lower()
        tiny = str(img.get("width", "")).strip() in ("0", "1") and \
               str(img.get("height", "")).strip() in ("0", "1")
        if tiny or any(p in src for p in pixel_pats):
            img.decompose()

    # 2. Preheader y todo lo oculto
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()

    # 3. Links de baja / preferencias / "ver en el navegador".
    #    Se borran ANTES de resolver links, así nunca se "clickea" una baja.
    link_pats = [norm(p) for p in CFG.get("remove_links_containing", [])]
    for a in soup.find_all("a"):
        href = norm(a.get("href") or "")
        text = norm(a.get_text(" ", strip=True))
        if any(p in href or p in text for p in link_pats):
            a.decompose()

    # 4. Párrafos tipo "You're receiving this because..."
    para_pats = [norm(p) for p in CFG.get("remove_paragraphs_containing", [])]
    to_remove = []
    for node in soup.find_all(string=True):
        if any(p in norm(str(node)) for p in para_pats):
            to_remove.append(node.find_parent("p") or node)
    for el in to_remove:
        if el.parent is not None:
            el.extract()

    # 5. Links de tracking -> URL real
    for a in soup.find_all("a", href=True):
        if resolver.is_tracking(a["href"]):
            a["href"] = resolver.resolve(a["href"])

    return soup


def to_fragment(soup):
    """Solo el contenido del <body>, envuelto en un div con el estilo del body.
    Sirve para insertar el issue dentro de una página sin romperle el layout."""
    body = soup.body
    if body is None:
        return str(soup)
    style = body.get("style", "")
    return (f'<div class="newsletter-issue" style="{htmllib.escape(style, quote=True)}">'
            f"{body.decode_contents()}</div>")


# ---------------------------------------------------------------- fuentes

def load_listmonk():
    snap = ROOT / CFG.get("listmonk_snapshot_file", "listmonk_archive.xml")
    if snap.exists():
        raw = snap.read_bytes()
    elif CFG.get("listmonk_feed_url"):
        warn("usando el feed de listmonk en vivo: conviene subir listmonk_archive.xml al repo")
        raw = requests.get(CFG["listmonk_feed_url"], timeout=60).content
    else:
        return []
    items = []
    for it in ET.fromstring(raw).iter("item"):
        link = (it.findtext("link") or "").strip()
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "date": parsedate_to_datetime(it.findtext("pubDate")),
            "html": it.findtext(f"{{{CONTENT_NS}}}encoded") or "",
            "guid": (it.findtext("guid") or link).strip(),  # se mantiene el original
            "source": "listmonk",
        })
    print(f"listmonk: {len(items)} issues")
    return items


def load_overrides():
    f = ROOT / "issues.csv"
    if not f.exists():
        return {}
    text = f.read_text(encoding="utf-8-sig")
    header = text.splitlines()[0] if text.strip() else ""
    delim = ";" if header.count(";") > header.count(",") else ","  # Excel en español usa ;
    rows = csv.DictReader(text.splitlines(), delimiter=delim)
    return {r["archivo"].strip(): r for r in rows if (r.get("archivo") or "").strip()}


def load_mailmodo():
    overrides = load_overrides()
    items = []
    for path in sorted(ISSUES_DIR.glob("*")):
        ext = path.suffix.lower()
        if ext not in (".eml", ".html", ".htm"):
            continue
        title = date = None
        if ext == ".eml":
            with path.open("rb") as fh:
                msg = BytesParser(policy=policy.default).parse(fh)
            part = msg.get_body(preferencelist=("html",))
            if part is None:
                warn(f"{path.name}: el .eml no tiene versión HTML, se saltea")
                continue
            html = part.get_content()
            title = str(msg.get("subject", "")).strip() or None
            if msg.get("date"):
                date = parsedate_to_datetime(str(msg["date"]))
        else:
            html = path.read_text(encoding="utf-8", errors="replace")
            t = BeautifulSoup(html, "html.parser").title
            title = t.get_text(strip=True) if t else None
            m = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
            if m:
                date = parse_date(m.group(1))

        ov = overrides.get(path.name, {})
        if (ov.get("titulo") or "").strip():
            title = ov["titulo"].strip()
        if (ov.get("fecha") or "").strip():
            date = parse_date(ov["fecha"])
        if not title or not date:
            warn(f"{path.name}: falta título o fecha. Agregalo en issues.csv. Se saltea.")
            continue
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        items.append({"title": title, "date": date, "html": html, "guid": None, "source": "mailmodo"})
    print(f"mailmodo: {len(items)} issues")
    return items


# ---------------------------------------------------------------- salida

def write_feed(items):
    e = htmllib.escape
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<rss version="2.0" xmlns:content="{CONTENT_NS}" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"<title>{e(CFG['title'])}</title>",
        f"<link>{e(SITE_URL)}/</link>",
        f"<description>{e(CFG.get('description', ''))}</description>",
        f'<atom:link href="{e(SITE_URL)}/feed.xml" rel="self" type="application/rss+xml"/>',
        f"<lastBuildDate>{format_datetime(datetime.now(timezone.utc))}</lastBuildDate>",
    ]
    for it in items:
        content = it["content"].replace("]]>", "]]]]><![CDATA[>")
        out += [
            "<item>",
            f"<title>{e(it['title'])}</title>",
            f"<link>{e(it['link'])}</link>",
            f'<guid isPermaLink="false">{e(it["guid"])}</guid>',
            f"<pubDate>{format_datetime(it['date'])}</pubDate>",
            f"<description>{e(it['excerpt'])}</description>",
            f"<content:encoded><![CDATA[{content}]]></content:encoded>",
            "</item>",
        ]
    out += ["</channel>", "</rss>"]
    (OUT / "feed.xml").write_text("\n".join(out), encoding="utf-8")


def write_index(items):
    e = htmllib.escape
    rows = "\n".join(
        f'<li><a href="{e(i["link"])}">{e(i["title"])}</a> <small>{i["date"]:%d/%m/%Y}</small></li>'
        for i in items)
    (OUT / "index.html").write_text(
        "<!doctype html><html lang='es'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{e(CFG['title'])}</title>"
        "<link rel='alternate' type='application/rss+xml' href='feed.xml'>"
        "<body style='font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px'>"
        f"<h1>{e(CFG['title'])}</h1><p><a href='feed.xml'>Feed RSS</a></p><ul>{rows}</ul></body></html>",
        encoding="utf-8")


def main():
    resolver = LinkResolver()
    items = load_listmonk() + load_mailmodo()
    if not items:
        sys.exit("No encontré ningún issue. Revisá listmonk_archive.xml y la carpeta issues/.")
    items.sort(key=lambda i: i["date"], reverse=True)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "archive").mkdir(parents=True)

    used = set()
    for it in items:
        base = f"{it['date']:%Y-%m-%d}-{slugify(it['title'])}"
        slug, n = base, 2
        while slug in used:
            slug, n = f"{base}-{n}", n + 1
        used.add(slug)

        soup = clean(it["html"], resolver, it["title"])
        (OUT / "archive" / f"{slug}.html").write_text(str(soup), encoding="utf-8")
        it["link"] = f"{SITE_URL}/archive/{slug}.html"
        it["guid"] = it["guid"] or it["link"]
        it["content"] = to_fragment(soup) if CFG.get("feed_content", "body") == "body" else str(soup)
        it["excerpt"] = BeautifulSoup(it["content"], "html.parser").get_text(" ", strip=True)[:300]

    write_feed(items)
    write_index(items)
    resolver.save()

    print(f"\nListo: {len(items)} issues en site/feed.xml")
    for i in items:
        print(f"  {i['date']:%Y-%m-%d}  [{i['source']:8}]  {i['title']}")
    if WARNINGS:
        print(f"\n{len(WARNINGS)} avisos (revisalos arriba).")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render a portable visual dashboard from a Visual Brand DNA manifest."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
CSS_COLOR = re.compile(r"^(?:#[0-9a-fA-F]{3,8}|rgba?\([0-9.,%\s]+\)|hsla?\([0-9.,%\s]+\))$")
SAFE_SCALAR = re.compile(r"^[a-zA-Z0-9#().,%/\s+\-]+$")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}.")
    return value


def text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def esc(value: Any, fallback: str = "") -> str:
    return html.escape(text(value, fallback), quote=True)


def items(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def strings(value: Any) -> list[str]:
    return [item.strip() for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def safe_color(value: Any, fallback: str) -> str:
    candidate = text(value)
    return candidate if CSS_COLOR.fullmatch(candidate) else fallback


def hex_rgb(value: str) -> tuple[int, int, int] | None:
    if not HEX_COLOR.fullmatch(value):
        return None
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def luminance(value: str) -> float:
    rgb = hex_rgb(value)
    if not rgb:
        return 0.5
    converted = []
    for channel in rgb:
        number = channel / 255
        converted.append(number / 12.92 if number <= 0.03928 else ((number + 0.055) / 1.055) ** 2.4)
    return 0.2126 * converted[0] + 0.7152 * converted[1] + 0.0722 * converted[2]


def readable_on(color: str) -> str:
    return "#111111" if luminance(color) > 0.45 else "#ffffff"


def role_color(colors: list[dict[str, Any]], pattern: str, fallback: str) -> str:
    matcher = re.compile(pattern, re.I)
    for item in colors:
        haystack = " ".join([text(item.get("name")), text(item.get("role"))])
        if matcher.search(haystack):
            return safe_color(item.get("value"), fallback)
    return fallback


def safe_font_family(value: Any) -> str:
    candidate = text(value, "system-ui")
    candidate = re.sub(r"[^a-zA-Z0-9 _,'\"\-]", "", candidate)[:120]
    return candidate or "system-ui"


def safe_scalar(value: Any, fallback: str = "") -> str:
    candidate = text(value)
    return candidate[:120] if candidate and SAFE_SCALAR.fullmatch(candidate) else fallback


def safe_href(value: Any, *, local: bool = False) -> str:
    candidate = text(value)
    if not candidate:
        return ""
    if local:
        path = Path(candidate)
        if path.is_absolute() or ".." in path.parts:
            return ""
        return html.escape(path.as_posix(), quote=True)
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return html.escape(candidate, quote=True)


def slug(value: str, fallback: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result or fallback


def source_pages(manifest: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_pages = items(manifest.get("sourcePages")) or items(manifest.get("pages"))
    summary_pages = items(summary.get("pages"))
    by_url = {text(page.get("url")): page for page in summary_pages}
    result: list[dict[str, Any]] = []
    for index, page in enumerate(manifest_pages or summary_pages):
        url = text(page.get("url"))
        evidence = by_url.get(url, page)
        files = evidence.get("files") if isinstance(evidence.get("files"), dict) else {}
        result.append({
            "label": text(page.get("label"), f"Source {index + 1}"),
            "url": url,
            "description": text(page.get("description"), text((page.get("metadata") or {}).get("description")) if isinstance(page.get("metadata"), dict) else "Captured website evidence."),
            "desktop": text(files.get("desktopScreenshot")),
            "mobile": text(files.get("mobileScreenshot")),
        })
    return result


def render_color_cards(colors: list[dict[str, Any]]) -> str:
    cards = []
    for index, color in enumerate(colors):
        value = safe_color(color.get("value"), "#d8d8de")
        cards.append(f"""
        <article class="color-card reveal" style="--delay:{index * 35}ms">
          <button class="swatch" data-copy="{esc(value)}" style="background:{esc(value)}" aria-label="Copy {esc(value)}"><span>Copy</span></button>
          <div class="color-meta">
            <div class="card-top"><h3>{esc(color.get('name'), f'Color {index + 1}')}</h3><span class="confidence {esc(color.get('confidence'), 'observed')}">{esc(color.get('confidence'), 'observed')}</span></div>
            <code>{esc(value)}</code>
            <p>{esc(color.get('role'), 'Observed brand color')}</p>
            <div class="evidence">{esc(color.get('evidence'), 'Website evidence')}</div>
          </div>
        </article>""")
    return "".join(cards) or '<p class="empty">No source-backed colors were established.</p>'


def render_type_cards(typography: list[dict[str, Any]]) -> str:
    cards = []
    for index, item in enumerate(typography):
        family = safe_font_family(item.get("family"))
        size = safe_scalar(item.get("size"), "42px")
        weight = safe_scalar(item.get("weight"), "700")
        line_height = safe_scalar(item.get("lineHeight"), "1.05")
        specimen_size = size if re.fullmatch(r"(?:clamp\(.+\)|\d+(?:\.\d+)?(?:px|rem|em))", size) else "42px"
        cards.append(f"""
        <article class="type-card reveal" style="--delay:{index * 45}ms">
          <div class="card-top"><div><span class="micro">{esc(item.get('name'), f'Type role {index + 1}')}</span><h3>{esc(family)}</h3></div><span class="confidence {esc(item.get('confidence'), 'observed')}">{esc(item.get('confidence'), 'observed')}</span></div>
          <div class="specimen" style="font-family:{esc(family)},system-ui,sans-serif;font-size:{esc(specimen_size)};font-weight:{esc(weight)};line-height:{esc(line_height)}">Brand DNA<br><span>Aa 0123</span></div>
          <dl class="type-stats"><div><dt>Size</dt><dd>{esc(size or 'Varies')}</dd></div><div><dt>Weight</dt><dd>{esc(weight)}</dd></div><div><dt>Line</dt><dd>{esc(line_height)}</dd></div></dl>
          <p>{esc(item.get('usage'), 'Observed typography role')}</p>
          <div class="evidence">{esc(item.get('evidence'), 'Website evidence')}</div>
        </article>""")
    return "".join(cards) or '<p class="empty">No source-backed typography roles were established.</p>'


def component_preview(component: dict[str, Any]) -> str:
    category = text(component.get("category"))
    name = text(component.get("name"), "Component")
    haystack = f"{category} {name}".lower()
    if "button" in haystack or "cta" in haystack:
        return '<div class="component-demo"><button class="demo-button">Primary action</button><button class="demo-button secondary">Secondary</button></div>'
    if "nav" in haystack or "header" in haystack:
        return '<div class="component-demo demo-nav"><strong>Brand</strong><span>Shop</span><span>About</span><i></i></div>'
    if "input" in haystack or "form" in haystack:
        return '<div class="component-demo"><div class="demo-input">Email address <span>Join</span></div></div>'
    return '<div class="component-demo"><div class="demo-card"><b>Featured content</b><span>Observed component pattern</span></div></div>'


def render_components(components: list[dict[str, Any]]) -> str:
    cards = []
    for index, component in enumerate(components):
        variants = strings(component.get("variants"))
        chips = "".join(f'<span class="variant">{esc(variant)}</span>' for variant in variants[:6])
        cards.append(f"""
        <article class="component-card reveal" style="--delay:{index * 40}ms">
          {component_preview(component)}
          <div class="component-copy"><div class="card-top"><div><span class="micro">{esc(component.get('category'), 'Component')}</span><h3>{esc(component.get('name'), f'Pattern {index + 1}')}</h3></div><span class="confidence {esc(component.get('confidence'), 'observed')}">{esc(component.get('confidence'), 'observed')}</span></div>
          <p>{esc(component.get('description'), 'Repeated source-backed pattern.')}</p><div class="variants">{chips}</div><div class="evidence">{esc(component.get('evidence'), 'Captured page evidence')}</div></div>
        </article>""")
    return "".join(cards) or '<p class="empty">No repeatable components were established.</p>'


def render_sources(pages: list[dict[str, Any]]) -> str:
    cards = []
    for index, page in enumerate(pages):
        desktop = safe_href(page.get("desktop"), local=True)
        mobile = safe_href(page.get("mobile"), local=True)
        source_url = safe_href(page.get("url"))
        visual = f'<img src="{desktop}" alt="{esc(page.get("label"))} desktop capture" loading="lazy">' if desktop else '<div class="source-empty">Screenshot unavailable</div>'
        mobile_link = f'<a href="{mobile}" target="_blank" rel="noreferrer">Mobile capture</a>' if mobile else '<span>Desktop only</span>'
        source_link = f'<a href="{source_url}" target="_blank" rel="noreferrer">Open source</a>' if source_url else ''
        cards.append(f"""
        <article class="source-card reveal" style="--delay:{index * 55}ms">
          <div class="source-visual">{visual}</div>
          <div class="source-copy"><div class="card-top"><h3>{esc(page.get('label'), f'Source {index + 1}')}</h3>{source_link}</div><p>{esc(page.get('description'), 'Captured website evidence.')}</p><div class="source-actions">{mobile_link}</div></div>
        </article>""")
    return "".join(cards) or '<p class="empty">No successful source-page captures were recorded.</p>'


def list_html(values: list[str], empty: str) -> str:
    if not values:
        return f'<p class="empty">{esc(empty)}</p>'
    return "".join(f'<li><span></span>{esc(value)}</li>' for value in values)


def render_dashboard(manifest: dict[str, Any], summary: dict[str, Any]) -> str:
    brand = text(manifest.get("brandName"), text(summary.get("brandNameSuggestion"), "Visual Brand"))
    website = text(manifest.get("websiteUrl"), text(summary.get("websiteUrl")))
    colors = items(manifest.get("colors"))[:24]
    typography = items(manifest.get("typography"))[:20]
    components = items(manifest.get("components"))[:30]
    pages = source_pages(manifest, summary)[:8]
    layout_rules = strings(manifest.get("layoutRules"))[:16]
    imagery = strings(manifest.get("imageryDirection"))[:16]
    caveats = strings(manifest.get("caveats"))[:20]
    personality = strings(manifest.get("personality"))[:8]
    artifacts = summary.get("artifactCount") if isinstance(summary.get("artifactCount"), int) else 4 + sum(1 for page in pages for key in ("desktop", "mobile") if page.get(key))

    first = safe_color(colors[0].get("value") if colors else "", "#33276f")
    ink = role_color(colors, r"ink|text|foreground|primary", first)
    accent = role_color(colors, r"sun|accent|cta|action|secondary", safe_color(colors[1].get("value") if len(colors) > 1 else "", "#f3cf48"))
    paper = role_color(colors, r"paper|background|canvas|surface", "#f7f7fb")
    ink_text = readable_on(ink)
    accent_text = readable_on(accent)
    palette_strip = "".join(f'<span style="background:{esc(safe_color(item.get("value"), "#ddd"))}"></span>' for item in colors[:8])
    personality_html = "".join(f'<span>{esc(value)}</span>' for value in personality)
    source_host = urlsplit(website).hostname or website
    confidence = text(manifest.get("confidence"), "medium").lower()
    generated = text(manifest.get("generatedAt"), text(summary.get("capturedAt"), ""))[:10]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(brand)} Visual Brand DNA</title>
<style>
:root{{--brand-ink:{ink};--brand-accent:{accent};--brand-paper:{paper};--on-ink:{ink_text};--on-accent:{accent_text};--canvas:#f5f5f8;--surface:#fff;--text:#17171a;--muted:#6f7078;--line:#e4e4e9;--radius:18px;--shadow:0 14px 35px rgba(26,24,38,.08)}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--canvas);color:var(--text);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.5}}button,a{{font:inherit}}a{{color:inherit}}.shell{{max-width:1500px;margin:auto;padding:0 28px 80px}}.topbar{{height:68px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10;background:rgba(245,245,248,.88);backdrop-filter:blur(18px);border-bottom:1px solid rgba(220,220,226,.8)}}.brandmark{{display:flex;align-items:center;gap:12px;font-weight:800}}.brandmark i{{width:16px;height:16px;background:var(--brand-accent);border:4px solid var(--brand-ink);border-radius:50%;box-shadow:4px 4px 0 var(--brand-ink)}}nav{{display:flex;gap:24px}}nav a{{font-size:12px;font-weight:700;text-decoration:none;color:var(--muted)}}.status{{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700}}.status:before{{content:"";width:8px;height:8px;background:#53b57a;border-radius:50%;box-shadow:0 0 0 4px rgba(83,181,122,.14)}}
.hero{{margin:28px 0 22px;display:grid;grid-template-columns:minmax(0,1.5fr) minmax(320px,.7fr);min-height:330px;border-radius:28px;overflow:hidden;background:var(--brand-ink);color:var(--on-ink);box-shadow:var(--shadow)}}.hero-copy{{padding:48px 52px;display:flex;flex-direction:column;justify-content:center}}.hero .label{{font-size:12px;text-transform:uppercase;letter-spacing:.16em;font-weight:800;opacity:.65}}h1{{font-size:clamp(42px,5vw,78px);letter-spacing:-.06em;line-height:.92;margin:18px 0 22px;max-width:900px}}.hero p{{font-size:16px;max-width:780px;margin:0;opacity:.78}}.personality{{display:flex;flex-wrap:wrap;gap:8px;margin-top:28px}}.personality span{{padding:7px 12px;border:1px solid currentColor;border-radius:999px;font-size:11px;font-weight:750;opacity:.82}}.hero-art{{background:var(--brand-accent);color:var(--on-accent);padding:30px;display:flex;flex-direction:column;justify-content:space-between;position:relative;isolation:isolate}}.hero-art:before,.hero-art:after{{content:"";position:absolute;border:3px solid var(--brand-ink);border-radius:50%;z-index:-1}}.hero-art:before{{width:210px;height:210px;right:-45px;top:-30px}}.hero-art:after{{width:120px;height:120px;left:30px;bottom:20px}}.hero-art strong{{font-size:60px;line-height:1;letter-spacing:-.08em}}.hero-art p{{color:inherit;opacity:.7}}.palette-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:auto}}.palette-strip span{{display:block;height:44px;border:2px solid var(--brand-ink);border-radius:9px;box-shadow:3px 3px 0 var(--brand-ink)}}
.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:0 0 42px}}.metric{{background:var(--surface);padding:20px 22px;border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 22px rgba(20,20,30,.04)}}.metric strong{{display:block;font-size:30px;letter-spacing:-.04em}}.metric span{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.09em;font-weight:750}}
section{{margin:54px 0;scroll-margin-top:90px}}.section-head{{display:flex;align-items:end;justify-content:space-between;gap:24px;margin-bottom:18px}}.section-head h2{{font-size:26px;letter-spacing:-.035em;margin:0}}.section-head p{{margin:5px 0 0;color:var(--muted);font-size:13px;max-width:720px}}.section-index{{font:700 12px/1 ui-monospace,SFMono-Regular,monospace;color:var(--muted)}}
.color-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}.color-card,.type-card,.component-card,.source-card,.rule-panel{{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;box-shadow:0 9px 24px rgba(20,20,30,.045)}}.swatch{{border:0;width:100%;height:150px;cursor:pointer;display:flex;align-items:end;justify-content:end;padding:12px}}.swatch span{{opacity:0;transform:translateY(5px);transition:.2s;background:rgba(255,255,255,.9);color:#111;padding:6px 9px;border-radius:7px;font-size:10px;font-weight:800}}.swatch:hover span{{opacity:1;transform:none}}.color-meta{{padding:18px}}.card-top{{display:flex;justify-content:space-between;align-items:start;gap:12px}}.card-top h3{{font-size:14px;margin:0}}.color-meta code{{display:block;font-size:12px;color:var(--muted);margin-top:9px}}.color-meta p,.type-card p,.component-copy p,.source-copy p{{font-size:12px;color:var(--muted);margin:10px 0 14px}}.confidence{{font-size:9px;text-transform:uppercase;letter-spacing:.06em;padding:5px 7px;border-radius:6px;background:#f0f0f3;color:#666;white-space:nowrap}}.confidence.exact{{background:#e9f8ef;color:#237444}}.confidence.inferred{{background:#fff4d5;color:#855f00}}.evidence{{border-top:1px solid var(--line);padding-top:12px;font-size:10px;color:#92939b;line-height:1.5}}
.type-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}}.type-card{{padding:22px}}.micro{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;font-weight:750}}.type-card h3{{font-size:15px;margin:4px 0 0}}.specimen{{min-height:150px;display:flex;flex-direction:column;justify-content:center;letter-spacing:-.045em;overflow:hidden;padding:18px 0;border-bottom:1px solid var(--line)}}.specimen span{{opacity:.25}}.type-stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0}}.type-stats div{{background:#f7f7f9;border-radius:10px;padding:9px}}dt{{font-size:9px;text-transform:uppercase;color:var(--muted)}}dd{{font:700 11px/1.4 ui-monospace,SFMono-Regular,monospace;margin:3px 0 0}}
.component-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.component-demo{{height:150px;background:color-mix(in srgb,var(--brand-accent) 28%,white);display:flex;align-items:center;justify-content:center;gap:10px;padding:20px}}.demo-button{{background:var(--brand-ink);color:var(--on-ink);border:2px solid var(--brand-ink);border-radius:9px;padding:12px 16px;font-size:11px;font-weight:800;box-shadow:4px 4px 0 color-mix(in srgb,var(--brand-ink) 35%,transparent)}}.demo-button.secondary{{background:transparent;color:var(--brand-ink);box-shadow:none}}.demo-nav{{justify-content:flex-start;color:var(--brand-ink);font-size:11px}}.demo-nav strong{{margin-right:auto;font-size:15px}}.demo-nav i{{width:28px;height:28px;background:var(--brand-ink);border-radius:50%}}.demo-input{{width:100%;background:white;border:2px solid var(--brand-ink);border-radius:10px;padding:11px;color:#8a8a91;font-size:11px;display:flex;justify-content:space-between;align-items:center}}.demo-input span{{background:var(--brand-ink);color:var(--on-ink);padding:8px 11px;border-radius:7px;font-weight:800}}.demo-card{{width:100%;height:95px;background:white;border:2px solid var(--brand-ink);border-radius:12px;box-shadow:5px 5px 0 var(--brand-ink);padding:16px;display:flex;flex-direction:column;justify-content:end;color:var(--brand-ink)}}.demo-card span{{font-size:10px;opacity:.6}}.component-copy{{padding:18px}}.variants{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:13px}}.variant{{font-size:9px;padding:4px 7px;background:#f3f3f6;border-radius:5px;color:#686972}}
.rules-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.rule-panel{{padding:24px}}.rule-panel h3{{margin:0 0 18px;font-size:15px}}.rule-panel ul{{list-style:none;padding:0;margin:0;display:grid;gap:14px}}.rule-panel li{{display:grid;grid-template-columns:10px 1fr;gap:10px;color:#55565e;font-size:12px}}.rule-panel li span{{width:7px;height:7px;border:2px solid var(--brand-ink);background:var(--brand-accent);border-radius:50%;margin-top:5px}}
.source-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:16px}}.source-visual{{aspect-ratio:16/9;background:#ededf1;overflow:hidden;border-bottom:1px solid var(--line)}}.source-visual img{{width:100%;height:100%;object-fit:cover;object-position:top;transition:transform .5s ease}}.source-card:hover img{{transform:scale(1.025)}}.source-empty{{height:100%;display:grid;place-items:center;color:var(--muted);font-size:12px}}.source-copy{{padding:18px}}.source-copy a{{font-size:10px;color:var(--brand-ink);font-weight:800;text-decoration:none}}.source-actions{{font-size:10px;color:var(--muted)}}
.caveats{{background:var(--brand-ink);color:var(--on-ink);border-radius:24px;padding:30px 34px;display:grid;grid-template-columns:.45fr 1fr;gap:30px}}.caveats h2{{font-size:28px;margin:0}}.caveats ul{{margin:0;padding-left:18px;display:grid;gap:12px;font-size:12px;opacity:.82}}.empty{{font-size:12px;color:var(--muted)}}footer{{border-top:1px solid var(--line);padding-top:24px;display:flex;justify-content:space-between;color:var(--muted);font-size:11px}}.toast{{position:fixed;bottom:22px;left:50%;transform:translate(-50%,20px);opacity:0;background:#17171a;color:white;padding:10px 14px;border-radius:9px;font-size:11px;transition:.2s;pointer-events:none;z-index:20}}.toast.show{{opacity:1;transform:translate(-50%,0)}}
.reveal{{animation:rise .55s cubic-bezier(.2,.8,.2,1) both;animation-delay:var(--delay,0ms)}}@keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}@media(prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}}html{{scroll-behavior:auto}}}}@media(max-width:1050px){{.hero{{grid-template-columns:1fr}}.hero-art{{min-height:200px}}.metrics{{grid-template-columns:repeat(3,1fr)}}.color-grid{{grid-template-columns:repeat(2,1fr)}}.component-grid{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:700px){{.shell{{padding:0 16px 50px}}nav{{display:none}}.topbar{{height:58px}}.hero{{margin-top:18px;border-radius:20px}}.hero-copy{{padding:34px 26px}}.hero-art{{padding:25px}}.metrics{{grid-template-columns:repeat(2,1fr)}}.metrics .metric:last-child{{grid-column:1/-1}}.color-grid,.type-grid,.component-grid,.rules-grid,.source-grid{{grid-template-columns:1fr}}.section-head{{align-items:start}}.section-index{{display:none}}.caveats{{grid-template-columns:1fr;padding:26px}}footer{{display:block}}}}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar"><div class="brandmark"><i></i>Visual Brand DNA</div><nav><a href="#colors">Colors</a><a href="#type">Typography</a><a href="#components">Components</a><a href="#sources">Sources</a></nav><div class="status">{esc(confidence)} confidence</div></header>
  <main>
    <section class="hero reveal"><div class="hero-copy"><div class="label">Source-backed visual system</div><h1>{esc(brand)}</h1><p>{esc(manifest.get('summary'), 'A reusable visual identity reconstructed from the live website and preserved evidence.')}</p><div class="personality">{personality_html}</div></div><div class="hero-art"><div><strong>{len(colors):02d}</strong><p>reusable color roles</p></div><div class="palette-strip">{palette_strip}</div></div></section>
    <div class="metrics reveal"><div class="metric"><strong>{len(colors)}</strong><span>Colors</span></div><div class="metric"><strong>{len(typography)}</strong><span>Type roles</span></div><div class="metric"><strong>{len(components)}</strong><span>Components</span></div><div class="metric"><strong>{len(pages)}</strong><span>Source pages</span></div><div class="metric"><strong>{artifacts}</strong><span>Artifacts</span></div></div>
    <section id="colors"><div class="section-head"><div><h2>Color system</h2><p>Core brand colors reconciled against captured styles, markup, and repeated page evidence.</p></div><div class="section-index">01 / PALETTE</div></div><div class="color-grid">{render_color_cards(colors)}</div></section>
    <section id="type"><div class="section-head"><div><h2>Typography</h2><p>Observed text roles, usage, scale, and confidence. Font names are evidence, not a redistribution licence.</p></div><div class="section-index">02 / TYPE</div></div><div class="type-grid">{render_type_cards(typography)}</div></section>
    <section id="components"><div class="section-head"><div><h2>Component language</h2><p>Only patterns supported by captured markup and repeated visual evidence are included.</p></div><div class="section-index">03 / COMPONENTS</div></div><div class="component-grid">{render_components(components)}</div></section>
    <section><div class="section-head"><div><h2>Layout and imagery</h2><p>The recurring rules that give the visual system its rhythm and recognizable point of view.</p></div><div class="section-index">04 / DIRECTION</div></div><div class="rules-grid"><article class="rule-panel"><h3>Layout rules</h3><ul>{list_html(layout_rules, 'No repeatable layout rules were established.')}</ul></article><article class="rule-panel"><h3>Imagery direction</h3><ul>{list_html(imagery, 'No repeatable imagery direction was established.')}</ul></article></div></section>
    <section id="sources"><div class="section-head"><div><h2>Source pages</h2><p>Desktop and mobile captures preserved as the visual QA reference for future creative work.</p></div><div class="section-index">05 / EVIDENCE</div></div><div class="source-grid">{render_sources(pages)}</div></section>
    <section class="caveats"><div><span class="micro">Evidence limits</span><h2>Caveats</h2></div><ul>{list_html(caveats, 'No material caveats were recorded.')}</ul></section>
  </main>
  <footer><span>Generated from public evidence for {esc(source_host)}</span><span>{esc(generated)} · Visual Brand DNA</span></footer>
</div><div class="toast" role="status">Copied to clipboard</div>
<script>document.querySelectorAll('[data-copy]').forEach(function(button){{button.addEventListener('click',function(){{navigator.clipboard&&navigator.clipboard.writeText(button.dataset.copy);var toast=document.querySelector('.toast');toast.textContent=button.dataset.copy+' copied';toast.classList.add('show');setTimeout(function(){{toast.classList.remove('show')}},1300)}})}});</script>
</body></html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Visual Brand DNA HTML dashboard.")
    parser.add_argument("manifest", help="Path to brand-manifest.json")
    parser.add_argument("summary", help="Path to SCRAPE-SUMMARY.json")
    parser.add_argument("--output", required=True, help="Destination HTML file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(Path(args.manifest))
    summary = load_json(Path(args.summary))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_dashboard(manifest, summary), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(destination.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

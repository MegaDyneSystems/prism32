"""Web Scraper Plugin for Prism32.
Registers /scrape command for fetching web content.
Uses PluginAPI.http_get() - no pip dependencies.
"""
import re
import json
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self._skip = True
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self._skip = False
    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self._text.append(t)
    def get_text(self):
        return ' '.join(self._text)


def _extract_text(html):
    p = _TextExtractor()
    try:
        p.feed(html.decode('utf-8', errors='replace') if isinstance(html, bytes) else html)
    except Exception:
        return str(html)[:8000]
    return p.get_text()


def cmd_scrape(args_str, history, cmd_log):
    url = args_str.strip()
    if not url:
        print("  Usage: /scrape <url>")
        print("  Example: /scrape https://example.com")
        return
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    print(f"  Fetching {url}...")
    raw = api.http_get(url)

    if raw.startswith("Error:"):
        print(f"  Failed: {raw}")
        return

    # Detect JSON
    if url.endswith('.json') or raw.strip().startswith('{'):
        try:
            parsed = json.loads(raw)
            raw = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            pass

    # Extract text if it looks like HTML
    if '<html' in raw[:500].lower() or '<!' in raw[:200]:
        raw = _extract_text(raw)

    if len(raw) > 8000:
        raw = raw[:8000] + "\n[... truncated ...]"

    lines = raw.split('\n')
    preview = '\n'.join(lines[:25])

    print(f"\n  \x1b[1mSCRAPE: {url[:60]}\x1b[0m")
    print(f"  \x1b[2m{len(raw)} chars, {len(lines)} lines\x1b[0m")
    print()
    for line in preview.split('\n'):
        print(f"  {line[:120]}")
    if len(lines) > 25:
        print(f"  \x1b[2m... ({len(lines) - 25} more lines)\x1b[0m")
    print()

    api.inject_context(
        f"[Web scrape of {url}]\n{raw[:4000]}\n"
    )


def on_message(api_ref, text):
    urls = re.findall(r'https?://[^\s<>"\'()]+', text)
    if urls and '/scrape' not in text:
        for u in urls[:2]:
            content = api_ref.http_get(u, timeout=8)
            if content and not content.startswith("Error:"):
                if '<html' in content[:500].lower():
                    content = _extract_text(content)
                api_ref.inject_context(
                    f"[Auto-scraped: {u}]\n{content[:2000]}\n"
                )


def register(api_ref):
    global api
    api = api_ref
    api.registry.register("scrape", cmd_scrape,
                          description="Fetch and display web content")
    print("  [plugin] web_scraper: /scrape <url> registered")
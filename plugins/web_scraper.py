"""Web Scraper Plugin for Prism32.

Registers /scrape for fetching, cleaning, saving, and crawling web/API
content. Pure stdlib; no pip dependencies.
"""
import json
import os
import re
import shlex
import urllib.parse
import urllib.request
from html.parser import HTMLParser


DEFAULT_HEADERS = {
    "User-Agent": "Prism32-WebScraper/1.2",
    "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.5",
}

_URL_RE = re.compile(r'https?://[^\s<>"\']+|www\.[^\s<>"\']+', re.IGNORECASE)
_AUTO_SEEN = []
_AUTO_SEEN_MAX = 60

USAGE_CONTEXT = """Web scraper plugin available:
- /scrape <url>: fetch URL, clean HTML/JSON/text, preview it, and inject useful content into AI context.
- /scrape --links <url>: fetch and show extracted links.
- /scrape --save PATH <url>: save raw fetched bytes, including binary files.
- /scrape --raw <url>: decode raw bytes instead of HTML/JSON cleanup.
- /scrape --no-context <url>: fetch/preview without injecting into AI context.
- /scrape --crawl [N] <url>: crawl same-host links to depth N, default 1.
- /scrape --crawl --depth N --max-pages N <url>: bounded crawl, max depth 3, max pages 50.
- /scrape --crawl --external <url>: allow crawler to leave the starting host.
- /scrape --crawl --save-dir DIR <url>: save raw responses for crawled pages.
- /web, /fetch-url, and /crawl are aliases.
Use this plugin when a task needs webpage text, API JSON, link discovery, lightweight crawling, or downloading raw web assets.
"""


class _TextExtractor(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._parts = []
        self._skip_depth = 0
        self.title = ""
        self.description = ""
        self.links = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs or [])
        if tag in ("script", "style", "noscript", "svg", "canvas"):
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag in ("a", "area") and attrs.get("href"):
            self.links.append(attrs.get("href"))
        if tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            if name in ("description", "og:description", "twitter:description") and attrs.get("content"):
                self.description = _compact_ws(attrs.get("content", ""))
        if tag in ("br", "p", "div", "section", "article", "header", "footer", "li",
                   "tr", "table", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("script", "style", "noscript", "svg", "canvas") and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag in ("p", "div", "section", "article", "li", "tr", "h1", "h2", "h3",
                   "h4", "h5", "h6", "blockquote"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = _compact_ws(data)
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        self._parts.append(text + " ")

    def get_text(self):
        text = "".join(self._parts)
        lines = []
        for line in text.splitlines():
            line = _compact_ws(line)
            if line:
                lines.append(line)
        return "\n".join(lines)


def _compact_ws(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean_url(url, base=None):
    url = (url or "").strip().strip('<>"\'')
    url = url.rstrip(".,;:!?)]}")
    if base:
        url = urllib.parse.urljoin(base, url)
    if url.startswith("www."):
        url = "https://" + url
    if url and not urllib.parse.urlparse(url).scheme:
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return ""
    return urllib.parse.urlunparse(parsed._replace(fragment=""))


def _extract_urls(text):
    urls = []
    for match in _URL_RE.findall(text or ""):
        url = _clean_url(match)
        if url and url not in urls:
            urls.append(url)
    return urls


def _looks_like_html(raw):
    head = raw[:1000].lower()
    return "<html" in head or "<!doctype html" in head or "<body" in head or "<article" in head


def _looks_like_json(raw):
    stripped = raw.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _headers_to_dict(headers):
    try:
        return {str(k).lower(): str(v) for k, v in headers.items()}
    except Exception:
        return {}


def _charset_from_content_type(content_type):
    m = re.search(r"charset=([^;]+)", content_type or "", re.I)
    return (m.group(1).strip().strip('"') if m else "") or "utf-8"


def _decode_body(body, content_type):
    charset = _charset_from_content_type(content_type)
    try:
        return body.decode(charset, errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


def _fetch(url, timeout):
    try:
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            headers = _headers_to_dict(resp.headers)
            return {
                "ok": True,
                "url": resp.geturl() or url,
                "status": getattr(resp, "status", None) or getattr(resp, "code", ""),
                "headers": headers,
                "content_type": headers.get("content-type", ""),
                "body": body,
            }
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e), "body": b"", "headers": {}}


def _extract_html(raw, base_url):
    parser = _TextExtractor()
    try:
        parser.feed(raw[:1000000])
    except Exception:
        return {"kind": "html", "title": "", "description": "", "text": _compact_ws(raw[:8000]), "links": []}
    links = []
    for href in parser.links:
        url = _clean_url(href, base=base_url)
        if url and url not in links:
            links.append(url)
    return {
        "kind": "html",
        "title": parser.title,
        "description": parser.description,
        "text": parser.get_text(),
        "links": links,
    }


def _is_textish(content_type, text):
    ct = (content_type or "").lower()
    return ct.startswith("text/") or "xml" in ct or "csv" in ct or "javascript" in ct or bool(text.strip())


def _process_content(url, fetched, force_raw=False):
    body = fetched.get("body") or b""
    content_type = fetched.get("content_type", "")
    text = _decode_body(body, content_type)
    result = {
        "kind": "binary",
        "title": "",
        "description": "",
        "text": "",
        "links": [],
        "bytes": len(body),
        "content_type": content_type or "unknown",
        "status": fetched.get("status", ""),
        "final_url": fetched.get("url") or url,
    }
    if force_raw:
        result.update({"kind": "raw", "text": text})
        return result
    if _looks_like_json(text) or "json" in content_type.lower() or url.split("?", 1)[0].lower().endswith(".json"):
        try:
            parsed = json.loads(text)
            result.update({"kind": "json", "text": json.dumps(parsed, indent=2, sort_keys=True)})
            return result
        except Exception:
            pass
    if _looks_like_html(text) or "html" in content_type.lower():
        html = _extract_html(text, fetched.get("url") or url)
        result.update(html)
        return result
    if _is_textish(content_type, text):
        result.update({"kind": "text", "text": text})
        return result
    result["text"] = "Binary content fetched. Use --save <path> to keep it or --raw to preview decoded bytes."
    return result


def _safe_filename(url, index=0):
    parsed = urllib.parse.urlparse(url)
    name = (parsed.netloc + parsed.path).strip("/") or "index"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:90] or "page"
    return f"{index:03d}_{name}"


def _save_bytes(path, body):
    path = os.path.expanduser(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as f:
        f.write(body or b"")
    return path


def _wrap_preview(text, max_lines, width=120):
    lines = []
    for raw_line in (text or "").splitlines() or [text or ""]:
        line = raw_line.strip()
        while len(line) > width:
            lines.append(line[:width])
            line = line[width:]
        if line:
            lines.append(line)
        if len(lines) >= max_lines:
            break
    return lines[:max_lines]


def _parse_int(value, default):
    try:
        return int(value)
    except Exception:
        return default


def _parse_args(args_str):
    opts = {
        "url": "",
        "chars": 8000,
        "context": 4000,
        "lines": 30,
        "timeout": 15,
        "raw": False,
        "context_enabled": True,
        "help": False,
        "links": False,
        "crawl": False,
        "depth": 1,
        "max_pages": 10,
        "external": False,
        "save": "",
        "save_dir": "",
    }
    try:
        parts = shlex.split(args_str or "")
    except ValueError:
        parts = (args_str or "").split()
    i = 0
    leftovers = []
    while i < len(parts):
        part = parts[i]
        if part in ("-h", "--help"):
            opts["help"] = True
        elif part == "--raw":
            opts["raw"] = True
        elif part == "--no-context":
            opts["context_enabled"] = False
        elif part == "--links":
            opts["links"] = True
        elif part == "--crawl":
            opts["crawl"] = True
            if i + 1 < len(parts) and re.match(r"^\d+$", parts[i + 1]):
                opts["depth"] = _parse_int(parts[i + 1], opts["depth"])
                i += 1
        elif part == "--external":
            opts["external"] = True
        elif part in ("--chars", "--context", "--lines", "--timeout", "--depth", "--max-pages"):
            if i + 1 < len(parts):
                key = part.lstrip("-").replace("-", "_")
                opts[key] = _parse_int(parts[i + 1], opts[key])
                i += 1
        elif part in ("--save", "--save-dir"):
            if i + 1 < len(parts):
                opts[part.lstrip("-").replace("-", "_")] = parts[i + 1]
                i += 1
        else:
            leftovers.append(part)
        i += 1
    if leftovers:
        opts["url"] = _clean_url(leftovers[0])
    opts["chars"] = max(0, min(opts["chars"], 50000))
    opts["context"] = max(0, min(opts["context"], 50000))
    opts["lines"] = max(0, min(opts["lines"], 300))
    opts["timeout"] = max(3, min(opts["timeout"], 60))
    opts["depth"] = max(0, min(opts["depth"], 3))
    opts["max_pages"] = max(1, min(opts["max_pages"], 50))
    return opts


def _usage():
    print("  Usage: /scrape [options] <url>")
    print("  Example: /scrape https://example.com")
    print("  Example: /scrape --crawl --depth 1 --max-pages 10 https://example.com")
    print("  Example: /scrape --save file.bin https://example.com/file.bin")
    print("  Options:")
    print("    --crawl [N]     crawl links to depth N (default 1)")
    print("    --depth N       crawl depth, max 3")
    print("    --max-pages N   crawl page limit, max 50")
    print("    --external      allow crawler to leave the starting host")
    print("    --links         show extracted links")
    print("    --lines N       preview lines to print (default 30)")
    print("    --chars N       max text chars to preview (default 8000, 0=none)")
    print("    --context N     chars injected into AI context (default 4000)")
    print("    --timeout N     request timeout seconds (default 15)")
    print("    --raw           decode bytes directly instead of cleaning/pretty-printing")
    print("    --save PATH     save fetched bytes for single URL")
    print("    --save-dir DIR  save raw bytes for each crawled page")
    print("    --no-context    print only; do not inject into AI context")


def _inject_context(url, data, limit, prefix="Web scrape"):
    if limit <= 0:
        return
    parts = [f"[{prefix}: {url}]", f"Type: {data.get('kind', 'text')}"]
    if data.get("content_type"):
        parts.append(f"Content-Type: {data.get('content_type')}")
    if data.get("bytes") is not None:
        parts.append(f"Bytes: {data.get('bytes')}")
    if data.get("title"):
        parts.append(f"Title: {data['title']}")
    if data.get("description"):
        parts.append(f"Description: {data['description']}")
    parts.append("Content:")
    parts.append((data.get("text") or "")[:limit])
    api.inject_context("\n".join(parts) + "\n")


def _print_result(url, data, opts):
    text = data.get("text") or ""
    preview_text = text[:opts["chars"]] if opts["chars"] else ""
    lines = _wrap_preview(preview_text, opts["lines"]) if opts["lines"] else []
    print(f"\n  \x1b[1mSCRAPE: {url[:90]}\x1b[0m")
    print(f"  \x1b[2mstatus={data.get('status')} type={data.get('kind')} content_type={data.get('content_type')} bytes={data.get('bytes')} chars={len(text)}\x1b[0m")
    if data.get("final_url") and data.get("final_url") != url:
        print(f"  \x1b[2mFinal URL:\x1b[0m {data.get('final_url')}")
    if data.get("title"):
        print(f"  \x1b[1mTitle:\x1b[0m {data['title'][:160]}")
    if data.get("description"):
        print(f"  \x1b[2mDescription:\x1b[0m {data['description'][:220]}")
    if data.get("links"):
        print(f"  \x1b[2mLinks:\x1b[0m {len(data.get('links', []))}")
    print()
    for line in lines:
        print(f"  {line}")
    if opts["chars"] and len(text) > len(preview_text):
        print("  \x1b[2m... truncated; increase --chars or --lines for more ...\x1b[0m")
    if opts["links"] and data.get("links"):
        print("\n  LINKS")
        for link in data["links"][:200]:
            print(f"  {link}")
    print()


def _same_host(seed, url):
    return urllib.parse.urlparse(seed).netloc.lower() == urllib.parse.urlparse(url).netloc.lower()


def _crawl(seed_url, opts):
    queue = [(seed_url, 0)]
    seen = set()
    pages = []
    context_budget = opts["context"]
    save_dir = os.path.expanduser(opts["save_dir"]) if opts["save_dir"] else ""
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    while queue and len(pages) < opts["max_pages"]:
        url, depth = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        fetched = _fetch(url, opts["timeout"])
        if not fetched.get("ok"):
            pages.append({"url": url, "depth": depth, "error": fetched.get("error", "fetch failed")})
            continue
        data = _process_content(url, fetched, force_raw=opts["raw"])
        pages.append({"url": url, "depth": depth, "data": data})
        if save_dir:
            filename = _safe_filename(url, len(pages))
            _save_bytes(os.path.join(save_dir, filename), fetched.get("body"))
        if opts["context_enabled"] and context_budget > 0:
            chunk = min(context_budget, max(500, opts["context"] // max(1, opts["max_pages"])))
            _inject_context(url, data, chunk, prefix="Crawl scrape")
            context_budget -= chunk
        if depth < opts["depth"] and data.get("links"):
            for link in data["links"]:
                if link in seen:
                    continue
                if not opts["external"] and not _same_host(seed_url, link):
                    continue
                queue.append((link, depth + 1))

    print(f"\n  \x1b[1mCRAWL: {seed_url}\x1b[0m")
    print(f"  \x1b[2mvisited={len(pages)} depth={opts['depth']} max_pages={opts['max_pages']} external={opts['external']}\x1b[0m")
    if save_dir:
        print(f"  \x1b[2mSaved raw responses to: {save_dir}\x1b[0m")
    print()
    for idx, item in enumerate(pages, 1):
        indent = "  " + ("  " * item.get("depth", 0))
        if item.get("error"):
            print(f"{indent}{idx:02d}. ERROR {item['url']} - {item['error']}")
            continue
        data = item["data"]
        title = data.get("title") or data.get("text", "").split("\n", 1)[0][:80]
        print(f"{indent}{idx:02d}. {data.get('kind')} {data.get('bytes')}B {item['url']}")
        if title:
            print(f"{indent}    {title[:120]}")
    print()


def cmd_scrape(args_str, history, cmd_log):
    opts = _parse_args(args_str)
    if opts["help"] or not opts["url"]:
        _usage()
        return
    url = opts["url"]
    if opts["crawl"]:
        _crawl(url, opts)
        return

    print(f"  Fetching {url}...")
    fetched = _fetch(url, opts["timeout"])
    if not fetched.get("ok"):
        print(f"  Failed: {fetched.get('error', 'fetch failed')}")
        return
    data = _process_content(url, fetched, force_raw=opts["raw"])
    if opts["save"]:
        saved = _save_bytes(opts["save"], fetched.get("body"))
        print(f"  Saved {len(fetched.get('body') or b'')} bytes to {saved}")
    _print_result(url, data, opts)
    if opts["context_enabled"]:
        _inject_context(url, data, opts["context"])
        print(f"  \x1b[2mInjected up to {opts['context']} chars into AI context.\x1b[0m")


def on_message(api_ref, text):
    urls = _extract_urls(text)
    if not urls or "/scrape" in (text or "").lower():
        return
    for url in urls[:2]:
        if url in _AUTO_SEEN:
            continue
        _AUTO_SEEN.append(url)
        del _AUTO_SEEN[:-_AUTO_SEEN_MAX]
        fetched = _fetch(url, 8)
        if not fetched.get("ok"):
            continue
        data = _process_content(url, fetched)
        snippet = data.get("text", "")[:2000]
        if snippet:
            api_ref.inject_context(
                f"[Auto-scraped URL: {url}]\nType: {data.get('kind')}\nContent-Type: {data.get('content_type')}\n{snippet}\n"
            )


def register(api_ref):
    global api
    api = api_ref
    api.registry.register(
        "scrape",
        cmd_scrape,
        aliases=["web", "fetch-url", "crawl"],
        description="Fetch, clean, save, crawl, and inject web/API content",
    )
    print("  [plugin] web_scraper: /scrape <url> registered")


def on_boot(api_ref):
    api_ref.inject_context(USAGE_CONTEXT)

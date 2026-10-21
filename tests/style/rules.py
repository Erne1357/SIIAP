"""Static style/convention scanners.

Each rule is a function ``() -> {relative_posix_path: violation_count}``.
Rules are registered in ``RULES``. ``tests/style/baseline.py`` stores the
accepted current counts; ``test_style_rules.py`` enforces the ratchet.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
TEMPLATES = APP / "templates"
CSS = APP / "static" / "css"
JS = APP / "static" / "js"

PDF_TEMPLATE = "app/templates/coordinator/student_record/_pdf.html"
EMAIL_DIR = "app/templates/emails/"
TOKENS_CSS = "app/static/css/_tokens.css"


# --------------------------------------------------------------------------- helpers
def _rel(path):
    return path.relative_to(ROOT).as_posix()


def _files(base, suffix):
    return sorted(p for p in base.rglob(f"*{suffix}") if "__pycache__" not in p.parts)


def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def _blank(m):
    return "\n" * m.group(0).count("\n")


def _strip_css(text):
    return re.sub(r"/\*.*?\*/", _blank, text, flags=re.S)


def _strip_tpl(text):
    text = re.sub(r"\{#.*?#\}", _blank, text, flags=re.S)
    return re.sub(r"<!--.*?-->", _blank, text, flags=re.S)


def _strip_js(text):
    text = re.sub(r"/\*.*?\*/", _blank, text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _strip_py(text):
    return re.sub(r"(?m)^\s*#.*$", "", text)


def _tpls(include_emails=False, include_pdf=False):
    for p in _files(TEMPLATES, ".html"):
        r = _rel(p)
        if not include_emails and r.startswith(EMAIL_DIR):
            continue
        if not include_pdf and r == PDF_TEMPLATE:
            continue
        yield r, _strip_tpl(_read(p))


def _css_files():
    for p in _files(CSS, ".css"):
        yield _rel(p), _strip_css(_read(p))


def _js_files():
    for p in _files(JS, ".js"):
        if "vendor" in p.relative_to(JS).parts:
            continue  # third-party code (see app/static/js/vendor/README.md; app/static/vendor/ is outside js/ and css/ so it is never scanned)
        yield _rel(p), _strip_js(_read(p))


def _py_files(sub=None):
    for p in _files(APP / sub if sub else APP, ".py"):
        yield _rel(p), _strip_py(_read(p))


def _css_blocks(text):
    return re.findall(r"\{([^{}]*)\}", text)


def _count(pattern, text, flags=0):
    return len(re.findall(pattern, text, flags))


def _collect(items, counter):
    out = {}
    for path, text in items:
        n = counter(text)
        if n:
            out[path] = n
    return out


# --------------------------------------------------------------------------- 1-2 templates
def tpl_style_block():
    """`<style>` blocks in templates (emails and the PDF template are exempt)."""
    return _collect(_tpls(), lambda t: _count(r"<style\b", t, re.I))


_CUSTOM_PROP_ONLY = re.compile(r"^\s*(?:--[\w-]+\s*:\s*[^;]*;?\s*)+$")


def _bad_inline_styles(text):
    bad = 0
    for m in re.finditer(r"""\bstyle\s*=\s*(?:"((?:[^"]|\{\{.*?\}\})*)"|'([^']*)')""", text, re.I | re.S):
        value = m.group(1) if m.group(1) is not None else m.group(2)
        if not _CUSTOM_PROP_ONLY.match(value):
            bad += 1
    return bad


def tpl_inline_style():
    """Inline style= that is not a custom-property-only declaration."""
    return _collect(_tpls(), _bad_inline_styles)


# --------------------------------------------------------------------------- 3 colors
_HEX_DECL = re.compile(r"(?<![\w&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b(?![-\w])")
_FUNC_COLOR = re.compile(r"\b(?:rgba?|hsla?)\(", re.I)


def css_hardcoded_colors():
    """#hex / rgb() / hsl() in CSS declarations outside _tokens.css."""
    out = {}
    for path, text in _css_files():
        if path == TOKENS_CSS:
            continue
        n = 0
        for body in _css_blocks(text):
            n += len(_HEX_DECL.findall(body)) + len(_FUNC_COLOR.findall(body))
        if n:
            out[path] = n
    return out


_TPL_HEX = re.compile(
    r"""(?:color|fill|stroke|background)\w*\s*[:=]\s*["']?\s*#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b""",
    re.I,
)


def tpl_hardcoded_colors():
    """Literal colors in non-email templates."""
    return _collect(_tpls(), lambda t: len(_TPL_HEX.findall(t)) + len(_FUNC_COLOR.findall(t)))


# --------------------------------------------------------------------------- 4 icons
_FA = re.compile(r"(?<![\w-])fa-[a-z]")


def fa_classes():
    """Font Awesome classes (not loaded) in templates and JS."""
    items = list(_tpls(include_emails=True, include_pdf=True)) + list(_js_files())
    return _collect(items, lambda t: len(_FA.findall(t)))


def tpl_inline_svg():
    """Inline <svg> in non-email templates (icons must be Bootstrap Icons)."""
    return _collect(_tpls(), lambda t: _count(r"<svg\b", t, re.I))


# --------------------------------------------------------------------------- 5-7 css
def css_keyframes_prefix():
    """@keyframes not prefixed siiap-."""
    return _collect(_css_files(), lambda t: _count(r"@keyframes\s+(?!siiap-)[\w-]+", t))


def css_components_important():
    """!important in components/*.css."""
    items = ((p, t) for p, t in _css_files() if p.startswith("app/static/css/components/"))
    return _collect(items, lambda t: _count(r"!\s*important", t, re.I))


def prefers_color_scheme():
    """prefers-color-scheme anywhere outside email templates."""
    items = list(_css_files()) + list(_tpls()) + list(_js_files())
    return _collect(items, lambda t: _count(r"prefers-color-scheme", t))


# --------------------------------------------------------------------------- 8 tables
def _table_violations(text):
    tables = _count(r"<table\b", text, re.I)
    captions = _count(r"<caption\b", text, re.I)
    missing_caption = max(0, tables - captions)
    th_no_scope = len(re.findall(r"<th\b(?![^>]*\bscope\s*=)[^>]*>", text, re.I))
    return missing_caption + th_no_scope


def tpl_tables():
    """<table> without <caption>, and <th> without scope (macro-based tables are fine)."""
    return _collect(_tpls(), _table_violations)


# --------------------------------------------------------------------------- 9 dates
_STRFTIME = re.compile(r"""strftime\(\s*['"][^'"]*%[Bb]""")


def strftime_month_names():
    """strftime with %B / %b prints English months."""
    items = list(_py_files()) + list(_tpls(include_emails=True, include_pdf=True))
    return _collect(items, lambda t: len(_STRFTIME.findall(t)))


# --------------------------------------------------------------------------- 10 python
def py_naive_now():
    """datetime.now()/utcnow() instead of now_local()."""
    return _collect(_py_files(), lambda t: _count(r"\bdatetime\.(?:utc)?now\(", t))


def py_deprecated_auth_import():
    """Imports from the deleted app.utils.auth module."""
    return _collect(_py_files(), lambda t: _count(r"from\s+app\.utils\.auth\b|import\s+app\.utils\.auth\b", t))


def py_roles_required():
    """Deprecated @roles_required."""
    return _collect(_py_files(), lambda t: _count(r"\broles_required\b", t))


def py_db_in_routes():
    """db.session / .query inside app/routes (routes must call services)."""
    return _collect(_py_files("routes"), lambda t: _count(r"\bdb\.session\b|\.query\b", t))


def py_user_program_index_zero():
    """`user_program[0]` in app/: use User.current_user_program() instead."""
    return _collect(_py_files(), lambda t: _count(r"user_program\[0\]", t))


def py_print():
    """print( calls in app/."""
    return _collect(_py_files(), lambda t: _count(r"(?<![\w.])print\(", t))


# --------------------------------------------------------------------------- 11 banned css
def css_gradient_text():
    """Gradient text (background-clip: text together with a gradient)."""

    def counter(text):
        n = 0
        for body in _css_blocks(text):
            if re.search(r"background-clip\s*:\s*text", body) and "gradient(" in body:
                n += 1
        return n

    return _collect(_css_files(), counter)


def css_bounce_easing():
    """cubic-bezier with out-of-range control values, or spring/bounce/elastic names."""

    def counter(text):
        n = 0
        for m in re.finditer(r"cubic-bezier\(([^)]*)\)", text):
            try:
                x1, y1, x2, y2 = [float(v) for v in m.group(1).split(",")]
            except ValueError:
                continue
            if any(v < 0 or v > 1 for v in (x1, y1, x2, y2)):
                n += 1
        return n + _count(r"--ease-(?:spring|bounce|elastic)", text)

    return _collect(_css_files(), counter)


def css_thick_side_borders():
    """border-left/right wider than 1px (best-effort)."""
    shorthand = re.compile(r"border-(?:left|right)\s*:\s*(\d+(?:\.\d+)?)px\s+(?!none|hidden)", re.I)
    width = re.compile(r"border-(?:left|right)-width\s*:\s*(\d+(?:\.\d+)?)px", re.I)

    def counter(text):
        n = 0
        for body in _css_blocks(text):
            for rx in (shorthand, width):
                n += sum(1 for m in rx.finditer(body) if float(m.group(1)) > 1)
        return n

    return _collect(_css_files(), counter)


# --------------------------------------------------------------------------- 13 flash
_FLASH = re.compile(r"""\bflash\(\s*f?(["'])(.*?)\1""", re.S)
_ES_MARKERS = re.compile(
    r"[áéíóúñ¿¡]|\b(?:el|la|los|las|de|del|se|no|por|para|con|un|una|su|sus|ha|han|al|en|y|o|que|es|fue|"
    r"usuario|debe|puede)\b",
    re.I,
)


def py_flash_not_spanish():
    """flash("...") literals with no Spanish marker at all."""

    def counter(text):
        return sum(1 for m in _FLASH.finditer(text) if not _ES_MARKERS.search(m.group(2)))

    return _collect(_py_files(), counter)


# --------------------------------------------------------------------------- 15 js
def js_console_log():
    """console.log left in JS."""
    return _collect(_js_files(), lambda t: _count(r"\bconsole\.log\(", t))


def js_location_reload():
    """location.reload( left in JS: re-render the region with an htmx fragment instead."""
    return _collect(_js_files(), lambda t: _count(r"location\.reload\(", t))


def js_alert():
    """Blocking alert( calls."""
    return _collect(_js_files(), lambda t: _count(r"(?<![\w.$])alert\(", t))


def js_mutation_without_csrf():
    """JS files that fetch with a mutating method but never mention csrf."""

    def counter(text):
        mutates = re.search(r"""method\s*:\s*['"`](?:POST|PUT|PATCH|DELETE)['"`]""", text, re.I)
        if "fetch(" in text and mutates and not re.search(r"csrf", text, re.I):
            return 1
        return 0

    return _collect(_js_files(), counter)


def js_csrf_meta_reads():
    """Reads of the csrf meta tag outside SIIAP.api (utils/http.js owns it)."""
    items = ((p, t) for p, t in _js_files() if not p.endswith("utils/http.js"))
    return _collect(items, lambda t: _count(r"""meta\[name=["']csrf-token["']\]""", t))


# --------------------------------------------------------------------------- 16 htmx
_HX_INLINE_JS = re.compile(
    r"""\bhx-on(?:[:\-][\w:.\-]*)?\s*=|\bhx-[a-z-]+\s*=\s*(["'])\s*js:""", re.I
)


def htmx_inline_js():
    """hx-on* attributes and `js:` expressions in hx-vals/hx-headers (allowEval is off)."""
    return _collect(_tpls(), lambda t: len(_HX_INLINE_JS.findall(t)))


RULES = {
    "tpl_style_block": tpl_style_block,
    "tpl_inline_style": tpl_inline_style,
    "css_hardcoded_colors": css_hardcoded_colors,
    "tpl_hardcoded_colors": tpl_hardcoded_colors,
    "fa_classes": fa_classes,
    "tpl_inline_svg": tpl_inline_svg,
    "css_keyframes_prefix": css_keyframes_prefix,
    "css_components_important": css_components_important,
    "prefers_color_scheme": prefers_color_scheme,
    "tpl_tables": tpl_tables,
    "strftime_month_names": strftime_month_names,
    "py_naive_now": py_naive_now,
    "py_deprecated_auth_import": py_deprecated_auth_import,
    "py_roles_required": py_roles_required,
    "py_db_in_routes": py_db_in_routes,
    "py_print": py_print,
    "py_user_program_index_zero": py_user_program_index_zero,
    "htmx_inline_js": htmx_inline_js,
    "css_gradient_text": css_gradient_text,
    "css_bounce_easing": css_bounce_easing,
    "css_thick_side_borders": css_thick_side_borders,
    "py_flash_not_spanish": py_flash_not_spanish,
    "js_console_log": js_console_log,
    "js_location_reload": js_location_reload,
    "js_alert": js_alert,
    "js_mutation_without_csrf": js_mutation_without_csrf,
    "js_csrf_meta_reads": js_csrf_meta_reads,
}


# --------------------------------------------------------------------------- 14 secrets
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY"),
    "aws access key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "client secret": re.compile(
        r"""CLIENT_SECRET\w*\s*[=:]\s*["']?(?![\s$'"{])[A-Za-z0-9~._-]{34,40}(?![A-Za-z0-9~._-])""", re.I
    ),
    "password literal": re.compile(r"""(?<![\w-])password\s*=\s*["'](?![{$%])[^"'\s]{4,}["']""", re.I),
}
_SKIP_SECRET_DIRS = ("database/", "venv/", ".venv/", "node_modules/", "migrations/versions/")
_TEXT_EXT = {".py", ".js", ".html", ".css", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".env",
             ".sh", ".conf", ".txt", ".md", ".sql", ".example", ""}


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        files = [ROOT / line for line in out.splitlines() if line]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    skip = {"venv", ".venv", ".git", "database", "node_modules", "__pycache__"}
    ignored = _gitignore_patterns()
    out = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT).as_posix()
        if not p.is_file() or (set(p.relative_to(ROOT).parts) & skip) or _is_ignored(rel, ignored):
            continue
        out.append(p)
    return out


def _gitignore_patterns():
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return []
    lines = [line.strip() for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines()]
    return [line.strip("/") for line in lines if line and not line.startswith(("#", "!"))]


def _is_ignored(rel, patterns):
    import fnmatch

    parts = rel.split("/")
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(parts[-1], pat):
            return True
        if any(fnmatch.fnmatch(seg, pat) for seg in parts[:-1]):
            return True
    return False


def _is_test_code(rel):
    return rel.startswith("tests/") or "/tests/" in rel or Path(rel).name.startswith("test_")


def scan_secrets():
    """Return 'path:line: kind' findings across git-tracked text files."""
    findings = []
    for p in tracked_files():
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(_SKIP_SECRET_DIRS) or p.suffix.lower() not in _TEXT_EXT or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for kind, rx in SECRET_PATTERNS.items():
            if kind == "password literal" and (_is_test_code(rel) or p.suffix not in {".py", ".js"}):
                continue
            for m in rx.finditer(text):
                findings.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: {kind}")
    return findings

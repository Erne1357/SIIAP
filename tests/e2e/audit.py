"""
Page audits shared by the E2E modules. Pure functions over a Playwright `page`.
Each returns a list of human-readable problems; an empty list means clean.
"""

from urllib.parse import urlparse

_AUDIT_JS = r"""
() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const text = (el) => (el.textContent || '').replace(/\s+/g, ' ').trim();
  const label = (el) => {
    const aria = el.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    const by = el.getAttribute('aria-labelledby');
    if (by) {
      const t = by.split(/\s+/).map(id => document.getElementById(id)).filter(Boolean).map(text).join(' ');
      if (t) return t;
    }
    if (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA') {
      if (el.labels && el.labels.length) return Array.from(el.labels).map(text).join(' ');
      if (el.title) return el.title;
      return '';
    }
    const t = text(el);
    if (t) return t;
    const img = el.querySelector('img[alt]');
    if (img && img.alt.trim()) return img.alt.trim();
    return (el.getAttribute('title') || '').trim();
  };
  const describe = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '');

  const unnamed = Array.from(document.querySelectorAll(
    'a[href], button, [role=button], input:not([type=hidden]), select, textarea'
  )).filter(el => visible(el) && !label(el)).map(describe);

  return {
    lang: document.documentElement.getAttribute('lang'),
    title: document.title,
    h1: Array.from(document.querySelectorAll('h1')).map(text),
    mains: document.querySelectorAll('main, [role=main]').length,
    viewport: !!document.querySelector('meta[name=viewport]'),
    skipLink: !!document.querySelector('a.skip-link[href^="#"]'),
    imgsWithoutAlt: Array.from(document.images).filter(i => !i.hasAttribute('alt')).map(i => i.getAttribute('src')),
    unnamed: unnamed,
  };
}
"""


def settle(page, timeout=3000, quiet_ms=300):
    """
    Wait for the page's fetch/XHR traffic to drain (and stay drained for
    `quiet_ms`) so late errors surface in `diag`. Playwright's `networkidle`
    is useless here: Socket.IO long-polls forever, so it always burns the timeout.
    """
    diag = getattr(page, '_e2e_diag', None)
    if diag is None:
        try:
            page.wait_for_load_state('networkidle', timeout=timeout)
        except Exception:
            pass
        return
    elapsed = quiet = 0
    while elapsed < timeout:
        if diag.pending:
            quiet = 0
        else:
            quiet += 50
            if quiet >= quiet_ms:
                return
        page.wait_for_timeout(50)
        elapsed += 50


def audit_page(page, *, expect_h1=True):
    """Structural + accessibility checks that must hold on every page."""
    data = page.evaluate(_AUDIT_JS)
    problems = []
    if data['lang'] != 'es':
        problems.append(f'html lang={data["lang"]!r}, expected "es"')
    if not (data['title'] or '').strip():
        problems.append('empty <title>')
    if not data['viewport']:
        problems.append('missing <meta name="viewport">')
    if expect_h1 and len(data['h1']) != 1:
        problems.append(f'{len(data["h1"])} <h1> elements ({data["h1"]}), expected exactly 1')
    if data['mains'] != 1:
        problems.append(f'{data["mains"]} <main> landmarks, expected exactly 1')
    if not data['skipLink']:
        problems.append('no skip link (a.skip-link)')
    if data['imgsWithoutAlt']:
        problems.append(f'images without alt attribute: {data["imgsWithoutAlt"]}')
    return problems, data['unnamed']


def horizontal_overflow(page):
    """Empty when the page does not scroll horizontally."""
    m = page.evaluate(
        '() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth})'
    )
    if m['sw'] > m['iw']:
        return [f'scrollWidth {m["sw"]} > innerWidth {m["iw"]}']
    return []


def small_targets(page, selector, minimum=44):
    """Visible elements matching `selector` whose box is smaller than `minimum` px."""
    return page.evaluate(
        r"""([selector, minimum]) => Array.from(document.querySelectorAll(selector))
            .map(el => ({el, r: el.getBoundingClientRect(), s: getComputedStyle(el)}))
            .filter(({r, s}) => r.width > 0 && r.height > 0 && s.visibility !== 'hidden')
            .filter(({r}) => r.height < minimum || r.width < minimum)
            .map(({el, r}) => (el.textContent || el.getAttribute('aria-label') || el.tagName)
                .replace(/\s+/g, ' ').trim().slice(0, 40) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height))""",
        [selector, minimum],
    )


def nav_links(page, base_url):
    """Unique same-origin hrefs of the desktop sidebar navigation (path + query)."""
    hrefs = page.evaluate(
        """() => Array.from(document.querySelectorAll('#sidebar nav a[href]'))
                  .map(a => a.getAttribute('href'))"""
    )
    host = urlparse(base_url).netloc
    seen, out = set(), []
    for href in hrefs:
        if not href or href.startswith(('#', 'mailto:', 'javascript:')):
            continue
        parsed = urlparse(href)
        if parsed.netloc and parsed.netloc != host:
            continue
        if parsed.path.startswith('/api/'):
            continue
        key = parsed.path + (('?' + parsed.query) if parsed.query else '')
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out

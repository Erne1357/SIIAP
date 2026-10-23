# Vendored third-party assets (CSS, fonts, JS)

Self-hosted, exact versions, no runtime CDN: the app must render and work when
the user's internet is flaky (a failed CDN request used to leave the app without
styles, icons and `io`). Files are served as `/static/vendor/...?v={{ static_version }}`
from `base.html` / `auth_base.html`. Files are byte-identical to the originals
(minified files keep their `sourceMappingURL` comment; the maps are not shipped,
so the browser devtools may log a harmless 404 for them).

htmx and idiomorph live in `../js/vendor/` (see its README). The style ratchet
skips both vendor folders.

To upgrade: download the new file from the same URL pattern, update the version
folder, the table below and the tags in both base templates.

| File | Source | sha384 (base64) | Size |
|------|--------|-----------------|------|
| `bootstrap/5.3.3/bootstrap.min.css` | https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css | `QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH` | 232803 B |
| `bootstrap/5.3.3/bootstrap.bundle.min.js` | https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js | `YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz` | 80721 B |
| `bootstrap-icons/1.11.3/bootstrap-icons.css` | https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css | `tViUnnbYAV00FLIhhi3v/dWt3Jxw4gZQcNoSCxCIFNJVCx7/D55/wXsrNIRANwdD` | 98255 B |
| `bootstrap-icons/1.11.3/fonts/bootstrap-icons.woff2` | https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff2 | `QV+/zNG6sFIQ/qAWRxaR4sjpF37wr046d3pTS5QlogmJfbmyeiWip4YIIGmdK4pa` | 130396 B |
| `bootstrap-icons/1.11.3/fonts/bootstrap-icons.woff` | https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/bootstrap-icons.woff | `jiOBsoZ7OEMAq7BXRR05+D5H/5Lna7TAlXVGHhkfH68p5P1eKJTeI4KCIOfBzG/O` | 176032 B |
| `socket.io/4.7.5/socket.io.min.js` | https://cdn.socket.io/4.7.5/socket.io.min.js | `2huaZvOR9iDzHqslqwpR87isEmrfxqyWOF7hr7BY6KG0+hVKLoEXMPUJw3ynWuhO` | 49993 B |

The CSS, bundle and Socket.IO hashes equal the `integrity=` values the templates
carried when they pointed at the CDN. The icon CSS expects `./fonts/` next to it.

Still external on purpose: Google Fonts (Inter, Plus Jakarta Sans). It degrades to
the system font stack when offline.

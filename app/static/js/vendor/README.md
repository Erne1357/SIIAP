# Vendored third-party JavaScript

Self-hosted, exact versions, never a range and never a CDN (the rest of the JS is
versioned with `?v={{ static_version }}`, and a CDN would add a third origin to
negotiate if a CSP ever lands). To upgrade: download the new file, verify the
version string, update the table and the `<script>` tag in `base.html`.

| File | Package | Source | sha384 (base64) | Size |
|------|---------|--------|-----------------|------|
| `htmx-2.0.10.min.js` | htmx.org 2.0.10 (header: `version:"2.0.10"`) | https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js | `H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V` | 51238 B |
| `idiomorph-ext-0.7.4.min.js` | idiomorph 0.7.4 (bundles Idiomorph + the htmx `morph` extension) | https://cdn.jsdelivr.net/npm/idiomorph@0.7.4/dist/idiomorph-ext.min.js | `SsScJKzATF/w6suEEdLbgYGsYFLzeKfOA6PY+/C5ZPxOSuA+ARquqtz/BZz9JWU8` | 10153 B |

Both files were also checked against the sha256 that the jsDelivr package index
publishes for them (they match).

Notes:

- htmx 4 is deliberately not used (beta at the time of writing). Keep to `hx-*`
  attributes so a future migration stays cheap.
- Do not add `htmx-ext-ws` / `htmx-ext-sse`: Socket.IO is the realtime channel.
- `idiomorph` 0.8.0 exists but 0.7.4 is the line documented for htmx 2.
- The Idiomorph file registers the extension as `morph`; use
  `hx-ext="morph"` and `hx-swap="morph:innerHTML"` / `morph:outerHTML`.
- Runtime configuration lives in `../utils/htmx-bridge.js`, not here.

# SIIAP — Plan de Implementación de Mejoras Estéticas y UX

> Plan de ejecución concreto basado en [PROPUESTAS_ESTETICAS.md](PROPUESTAS_ESTETICAS.md). Está organizado por **sprints** (no por fases abstractas), con orden de dependencias respetado, archivos a tocar, tests/verificaciones por paso, y una rama git por sprint para integración limpia.
>
> **Convenciones:**
> - Cada sprint = una rama `feature/ui-sprint-N` que mergea a `main` (o a `feature/ui-system` si se prefiere agrupar).
> - Cada paso indica **archivos**, **comando de verificación** y **criterio de aceptación**.
> - **Riesgo de regresión:** 🟢 bajo · 🟡 medio · 🔴 alto.
> - **Esfuerzo:** S = ≤4h · M = 4–16h · L = >16h.
>
> **Convención de commits:** `Feat(ui)`, `Fix(ui)`, `Refactor(ui)`, `Style(ui)`, `A11y(ui)` — siguiendo el patrón ya usado en el repo.

---

## Tabla de sprints

| # | Sprint | Duración | Riesgo | Entregable visible |
|---|---|---|---|---|
| 1 | **Fundamentos invisibles** | 1 sem | 🟡 | Nada visual cambia. Tokens listos, íconos unificados, z-index ordenado |
| 2 | **Quick-wins de marca** | 3 días | 🟢 | Botón register azul, FAB azul TECNM, banner verde fuera, links rotos arreglados |
| 3 | **Tipografía + auth hero** | 4 días | 🟡 | Inter cargado; login/register con hero institucional |
| 4 | **Accesibilidad transversal** | 4 días | 🟢 | `prefers-reduced-motion`, ARIA, contrastes AA, focus visible |
| 5 | **Skeletons + spinners** | 3 días | 🟢 | Tablas y botones con feedback unificado |
| 6 | **StatusBadge + paleta coordinador** | 4 días | 🟡 | Badges de estado consistentes en todos los flujos |
| 7 | **Hero programs/list + events** | 3 días | 🟢 | Cara pública con identidad TECNM |
| 8 | **Componentes reutilizables** | 1 sem | 🟡 | EmptyState, ConfirmModal, DataTable, Stepper en macros |
| 9 | **RoleBanner + dashboards** | 4 días | 🟢 | Identidad de rol explícita, refinamientos de dashboards |
| 10 | **Pulido y deuda** | 1 sem | 🟢 | Footer, 404/500, AOS→IO, optimistic UI, timeline consolidada |

**Total:** ~6–8 semanas con un dev al 50%.

---

## Antes de empezar — preparación (1h)

### Pre-1. Verificar entorno

```powershell
docker ps                                # Confirmar nombre real del contenedor
docker exec siiap-web-1 flask --version  # Confirmar Flask 3.x
git status                               # Working tree limpio
git checkout main && git pull
git checkout -b feature/ui-system        # Rama paraguas (opcional)
```

### Pre-2. Crear directorio de assets nuevos (si aplica)

```powershell
ls app/static/css/                       # Verificar estructura
ls app/templates/                        # Verificar estructura
```

### Pre-3. Snapshot visual

Antes de tocar nada, capturar screenshots de las pantallas clave para comparar después:
- `auth/login`, `auth/register`
- Cada dashboard de rol
- `coordinator/{dashboard,acceptance,deliberation,permanence}`
- `programs/list`, `programs/view/<slug>`
- `events/list`, un evento individual

Guardar en `docs/before-after/before/` (no commitear si pesa).

---

## Sprint 1 — Fundamentos invisibles

> **Objetivo:** crear la base de tokens, unificar íconos, ordenar z-index. **Cero cambios visuales perceptibles.** Habilita todo lo siguiente.
>
> **Rama:** `feature/ui-foundation`

### S1.1 — Crear `_tokens.css` 🟢 · M

**Archivos:**
- ➕ Nuevo: `app/static/css/_tokens.css`
- ✏️ `app/templates/base.html` — agregar `<link>` ANTES de `base.css`
- ✏️ `app/templates/auth_base.html` — idem

**Pasos:**
1. Copiar el bloque completo de tokens de [PROPUESTAS_ESTETICAS.md §2](PROPUESTAS_ESTETICAS.md) a `_tokens.css`.
2. En `base.html` línea 22 (antes de `session.css`), agregar:
   ```html
   <link href="{{ url_for('static', filename='css/_tokens.css') }}?v={{ static_version }}" rel="stylesheet">
   ```
3. Idem en `auth_base.html`.

**Verificación:**
```powershell
docker compose restart web
# Abrir cualquier página → DevTools → Computed → confirmar que --color-brand-primary existe
```

**Criterio de aceptación:** ninguna pantalla cambia visualmente. Variables CSS disponibles en `:root`.

### S1.2 — Reorganizar z-index 🟢 · S

**Archivos:**
- ✏️ `app/static/css/base.css`
- ✏️ `app/static/css/flash.css`
- ✏️ `app/static/css/session.css`
- ✏️ `app/static/css/notifications.css`

**Pasos:**
1. En cada archivo, sustituir literales `9999`, `10000`, `100001`, `1055`, `1060` por `var(--z-toast)`, `var(--z-modal)`, etc.
2. Documentar excepciones (modal-backdrop con `!important` debe quedarse hasta sprint 8).

**Verificación:**
```powershell
# Probar las superposiciones críticas:
# 1. Abrir modal → debe estar sobre todo
# 2. Abrir flash mientras modal abierto → flash debe verse encima
# 3. Abrir offcanvas móvil → debe estar sobre footer
```

**Criterio:** sin glitches de z-index en los 3 escenarios anteriores.

### S1.3 — Migrar íconos Font Awesome → Bootstrap Icons 🟡 · M

**Archivos:**
- ✏️ `app/templates/base.html` (eliminar `<link>` FA)
- ✏️ `app/templates/auth_base.html` (idem)
- ✏️ `app/templates/_sidebar_nav.html`
- ✏️ Todos los `templates/**/*.html` con `class="fas fa-*"` o `class="far fa-*"`

**Tabla de mapeo (mínima):**

| Font Awesome | Bootstrap Icons |
|---|---|
| `fas fa-user` | `bi bi-person` |
| `fas fa-th-large` | `bi bi-grid-fill` |
| `fas fa-clipboard` | `bi bi-clipboard` |
| `fas fa-clipboard-list` | `bi bi-clipboard-data` |
| `fas fa-calendar-check` | `bi bi-calendar-check` |
| `fas fa-calendar` | `bi bi-calendar` |
| `fas fa-calendar-plus` | `bi bi-calendar-plus` |
| `fas fa-calendar-alt` | `bi bi-calendar3` |
| `fas fa-users` | `bi bi-people-fill` |
| `fas fa-user-plus` | `bi bi-person-plus-fill` |
| `fas fa-user-cog` | `bi bi-person-gear` |
| `fas fa-user-tie` | `bi bi-person-vcard-fill` |
| `fas fa-gavel` | `bi bi-hammer` |
| `fas fa-file-alt` | `bi bi-file-earmark-text` |
| `fas fa-cog` | `bi bi-gear-fill` |
| `fas fa-folder` | `bi bi-folder-fill` |
| `fas fa-envelope` | `bi bi-envelope-fill` |
| `fas fa-graduation-cap` | `bi bi-mortarboard-fill` |
| `fas fa-robot` | `bi bi-robot` |
| `fas fa-shield-alt` | `bi bi-shield-lock-fill` |
| `fas fa-chevron-right` | `bi bi-chevron-right` |
| `fas fa-sign-out-alt` | `bi bi-box-arrow-right` |
| `fas fa-spinner fa-spin` | `<div class="spinner-border spinner-border-sm">` |
| `fas fa-upload` | `bi bi-upload` |
| `fas fa-download` | `bi bi-download` |
| `fas fa-check-circle` | `bi bi-check-circle-fill` |
| `fas fa-times` / `fa-times-circle` | `bi bi-x-circle-fill` |
| `fas fa-exclamation-triangle` | `bi bi-exclamation-triangle-fill` |
| `fas fa-info-circle` | `bi bi-info-circle-fill` |

**Búsqueda exhaustiva:**
```powershell
# Listar todos los archivos con FA todavía
# Usar Grep tool en lugar de PowerShell para evitar permisos
```
Use Grep tool: pattern `fas fa-|far fa-|fab fa-` en `app/templates/`.

**Verificación:** clic en cada link de la sidebar; abrir cada modal con botón. Cero íconos rotos (cuadrados vacíos).

### S1.4 — Refactor sessionModal a Bootstrap modal 🟡 · S

**Archivos:**
- ✏️ `app/templates/base.html` (líneas 257-266)
- ❌ Eliminar contenido de `app/static/css/session.css` (o vaciarlo)
- ✏️ `app/static/js/session_timeout.js` — actualizar selectores

**Pasos:**
1. Sustituir el bloque actual por:
   ```html
   <div class="modal fade" id="sessionModal" tabindex="-1"
        aria-labelledby="sessionModalLabel" aria-hidden="true"
        data-bs-backdrop="static" data-bs-keyboard="false">
     <div class="modal-dialog modal-dialog-centered">
       <div class="modal-content">
         <div class="modal-header">
           <h5 class="modal-title" id="sessionModalLabel">
             <i class="bi bi-clock-history me-2"></i>Sesión por expirar
           </h5>
         </div>
         <div class="modal-body">
           <p class="mb-0">Tu sesión expirará en <strong>1 minuto</strong>. ¿Deseas continuar conectado?</p>
         </div>
         <div class="modal-footer">
           <button id="logoutBtn" class="btn btn-outline-secondary">Cerrar sesión</button>
           <button id="continueBtn" class="btn btn-primary">Continuar</button>
         </div>
       </div>
     </div>
   </div>
   ```
2. En `session_timeout.js`, sustituir manipulación directa de `display:none` por `bootstrap.Modal.getOrCreateInstance(modal).show()/.hide()`.

**Verificación:** simular expiración de sesión (esperar 14 min en dev o forzar en consola). Modal aparece centrado, no se cierra con ESC, ambos botones funcionan.

### S1.5 — Fix typo HTML inválido 🟢 · S

**Archivos:**
- ✏️ `app/templates/programs/view/_hero.html`

**Cambio:** `max-heigh="400px"` → eliminarlo y agregar `style="max-height:400px"` o (mejor) clase CSS `.program-hero-img { max-height: 400px; }`.

**Verificación:** el HTML valida en https://validator.w3.org/.

### Cierre Sprint 1

```powershell
git add -A
git commit -m "$(cat <<'EOF'
Refactor(ui): introducir sistema de tokens y unificar fundamentos

- Crear app/static/css/_tokens.css con paleta TECNM, tipografia, espaciado, sombras, z-index, motion
- Migrar todos los iconos de Font Awesome a Bootstrap Icons
- Refactorizar sessionModal como Bootstrap modal estandar
- Reorganizar z-index en escala discreta (eliminar 9999/10000/100001)
- Fix typo HTML max-heigh en programs/view/_hero.html

Sin cambios visuales perceptibles. Habilita las siguientes mejoras incrementales.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 2 — Quick-wins de marca y bugs funcionales

> **Objetivo:** errores funcionales (links rotos, form sin action) + alineación cromática inmediata. Cambios pequeños, alto valor visible.
>
> **Rama:** `feature/ui-quickwins`

### S2.1 — Fix link `<a>` sin href en admission_steps 🔴 · S (BUG)

**Archivo:** `app/templates/programs/view/_admission_steps.html`

**Investigación previa:** leer el contexto exacto del `<a class="document-link">`. Identificar si el dato `file.url` (o equivalente) existe en el contexto Jinja del macro.

**Cambio:**
```html
<!-- Antes -->
<a class="document-link">{{ file.name }}</a>

<!-- Después (caso A: hay URL) -->
<a class="document-link" href="{{ file.url }}" target="_blank" rel="noopener">
  <i class="bi bi-file-earmark-text"></i> {{ file.name }}
</a>

<!-- Después (caso B: solo descriptivo, no es link) -->
<span class="document-tag">
  <i class="bi bi-file-earmark-text"></i> {{ file.name }}
</span>
```

**Verificación manual:** ir a `/programs/<slug>` en navegador, click en cada documento listado. Debe abrir el archivo o (si solo informativo) verse como tag no clickeable.

### S2.2 — Fix `<form>` sin action en _contact 🔴 · S (BUG)

**Archivo:** `app/templates/programs/view/_contact.html`

**Investigación:**
```
Grep: pattern "_contact" en app/routes/
```
Si **no existe handler**, hay dos opciones:
- (a) Implementar endpoint `POST /programs/<slug>/contact` que envíe correo a coordinador y devuelva flash success.
- (b) Sustituir formulario por `mailto:` link y eliminar inputs.

**Recomendado: opción (a)** porque el form ya está construido. Crear:
- `app/routes/api/programs_contact_api.py` (blueprint, `/api/v1/programs/<slug>/contact` POST)
- `app/services/contact_service.py` (envía correo con `email_service`)
- Frontend: agregar `<script>` que intercepte submit, llame a `api()` y muestre flash.

Si urgencia es alta y no se puede implementar correctamente, **agregar disclaimer**:
```html
<div class="alert alert-info">
  <i class="bi bi-info-circle"></i> Para consultas, escribe directamente a
  <a href="mailto:posgrado@itcj.edu.mx">posgrado@itcj.edu.mx</a>.
</div>
<!-- Comentar el form mientras se implementa -->
```

### S2.3 — FAB notificaciones azul TECNM 🟢 · S

**Archivo:** `app/static/css/notifications.css`

**Cambio:**
```css
/* Línea ~400, dentro de .notification-fab */
background: var(--color-brand-primary);   /* antes: #007bff */
```

Buscar también `#007bff` en otros lados del CSS y sustituir por `var(--color-brand-primary)`.

**Verificación:** redimensionar a móvil (<768px), aparece FAB azul TECNM (no Bootstrap blue).

### S2.4 — Botón "Registrarme" verde → azul TECNM 🟢 · S

**Archivo:** `app/templates/auth/register.html` línea 63

**Cambio:** `class="btn btn-success ..."` → `class="btn btn-primary ..."`

**Verificación:** /register muestra botón azul, coherente con login.

### S2.5 — Banner verde de auth → gradiente TECNM 🟡 · S

**Archivo:** `app/static/css/auth/common.css` (línea ~170 y ~93)

**Cambios:**
```css
/* Antes */
.auth-banner {
  background: linear-gradient(135deg, #2c5530 0%, #4a7c59 100%);
}
.auth-card {
  border-top: 5px solid #4a7c59;
}

/* Después */
.auth-banner {
  background: linear-gradient(135deg,
    var(--color-brand-primary) 0%,
    var(--color-brand-accent) 100%);
}
.auth-card {
  border-top: 4px solid var(--color-brand-primary);
}
```

**Verificación:** /login y /register sin verde. Borde superior de card en azul TECNM.

### S2.6 — Bootstrap 5.1.3 → 5.3.3 en auth_base 🟡 · S

**Archivo:** `app/templates/auth_base.html` línea 14

**Cambio:**
```html
<!-- Antes -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/.../bootstrap.min.css" ...>

<!-- Después (igual que base.html) -->
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
```

Verificar que el JS bundle correspondiente también esté en 5.3.3.

**Verificación:** /login → DevTools Network → confirmar Bootstrap 5.3.3 cargado. Probar login completo, registro completo, validación de formularios. Debe funcionar idéntico.

### S2.7 — Eliminar animación bounce infinita en 404 🟢 · S

**Archivo:** `app/static/css/404.css`

**Cambio:** eliminar `@keyframes bounce` y la regla que la usa. Sustituir por estado estático.

**Verificación:** /alguna-ruta-inexistente → 404 sin animación distractora.

### Cierre Sprint 2

```powershell
git commit -m "$(cat <<'EOF'
Fix(ui): bugs funcionales y alineacion cromatica con paleta TECNM

- Fix link sin href en _admission_steps.html
- Fix form sin action en _contact.html (handler o disclaimer)
- FAB notificaciones #007bff -> var(--color-brand-primary)
- Boton register btn-success -> btn-primary
- Banner verde #4a7c59 -> gradiente azul/rojo TECNM
- Bootstrap 5.1.3 -> 5.3.3 en auth_base.html
- Eliminar animacion bounce infinita en 404

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 3 — Tipografía y hero institucional de auth

> **Objetivo:** primera transformación visible. Inter como fuente. Login y register con hero institucional.
>
> **Rama:** `feature/ui-typography-hero`

### S3.1 — Cargar Inter como fuente global 🟡 · S

**Archivos:**
- ✏️ `app/templates/base.html`
- ✏️ `app/templates/auth_base.html`
- ✏️ `app/static/css/base.css`

**Pasos:**

En `<head>` de ambos base templates, ANTES del `<link>` de Bootstrap:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700&display=swap" rel="stylesheet">
```

En `base.css` línea 68 (la regla `body`):
```css
body {
  /* ... */
  font-family: var(--font-sans);
}
h1, h2, .h1, .h2, .brand-text {
  font-family: var(--font-display);
}
```

**Verificación:** abrir cualquier página → DevTools → Computed → font-family de body resuelve a Inter. Inspeccionar h1 → Plus Jakarta Sans.

**Performance check:** `display=swap` evita FOIT. Si LCP empeora >300ms, considerar self-host de Inter en `static/assets/fonts/`.

### S3.2 — Hero institucional para login (split-pane) 🟡 · M

**Archivos:**
- ✏️ `app/templates/auth/login.html`
- ✏️ `app/static/css/auth/login.css`
- ✏️ `app/templates/auth_base.html` (ajustar block container_class)

**Mockup objetivo:** cf. [PROPUESTAS_ESTETICAS.md §4.1.1](PROPUESTAS_ESTETICAS.md).

**Estructura HTML propuesta** (dentro del block content de login.html):
```html
<div class="auth-split">
  <aside class="auth-split__hero">
    <div class="auth-split__hero-content">
      <span class="auth-split__eyebrow">ITCJ · TECNM</span>
      <h1 class="auth-split__title">
        Sistema Integral de Información Académica de Posgrado
      </h1>
      <p class="auth-split__tagline">
        Ingresa para gestionar tu trayectoria académica.
      </p>
    </div>
    <svg class="auth-split__pattern" aria-hidden="true">
      <!-- patrón geométrico sutil opcional -->
    </svg>
  </aside>
  <main class="auth-split__form">
    <div class="card auth-card">
      <div class="card-body">
        <h2 class="h3 mb-4 text-center">
          <i class="bi bi-mortarboard-fill text-brand-primary"></i>
          Iniciar sesión
        </h2>
        <!-- form actual -->
      </div>
    </div>
  </main>
</div>
```

**CSS propuesto** (en login.css o common.css):
```css
.auth-split {
  display: grid;
  grid-template-columns: 1fr;
  min-height: calc(100vh - var(--header-h) - var(--footer-h));
}
@media (min-width: 992px) {
  .auth-split { grid-template-columns: 6fr 4fr; }
}
.auth-split__hero {
  position: relative;
  display: flex;
  align-items: center;
  padding: var(--space-12) var(--space-8);
  background: linear-gradient(135deg,
    var(--color-brand-primary) 0%,
    var(--color-brand-accent) 120%);
  color: var(--text-inverse);
  overflow: hidden;
}
.auth-split__eyebrow {
  display: inline-block;
  padding: var(--space-1) var(--space-3);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: var(--radius-pill);
  font-size: var(--fs-xs);
  letter-spacing: var(--tracking-wide);
  text-transform: uppercase;
  margin-bottom: var(--space-6);
}
.auth-split__title {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: var(--lh-tight);
  margin-bottom: var(--space-4);
}
.auth-split__form {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-8) var(--space-4);
  background: var(--bg-page);
}
@media (max-width: 991.98px) {
  .auth-split__hero { min-height: 200px; padding: var(--space-6); }
  .auth-split__title { font-size: var(--fs-xl); }
}
```

**Verificación:**
- Desktop (1440×900): hero a la izquierda, form a la derecha.
- Tablet (768×1024): hero arriba (200-280px), form abajo.
- Móvil (375×667): hero compacto arriba, form abajo, ambos legibles.
- Form sigue funcionando (login real).
- Contraste del título blanco sobre gradiente: ratio ≥ 4.5:1 (probar con devtools).

### S3.3 — Aplicar mismo split a register 🟢 · S

**Archivo:** `app/templates/auth/register.html`

**Cambio:** envolver el contenido en `<div class="auth-split">` con hero similar (puede ser el mismo o uno diferenciado, ej. tagline "Crea tu cuenta para iniciar tu proceso de admisión").

### S3.4 — Refinar brand-text "SIIAP" 🟢 · S

**Archivo:** `app/static/css/base.css` líneas 147-154

**Cambio:**
```css
.brand-text {
  font-family: var(--font-display);
  font-weight: var(--fw-bold);
  font-size: var(--fs-display);
  color: var(--color-brand-accent);
  letter-spacing: var(--tracking-display);
  line-height: 1;
  text-shadow: none;       /* eliminar la sombra que mata la elegancia */
}
```

### Cierre Sprint 3

```powershell
git commit -m "$(cat <<'EOF'
Feat(ui): tipografia Inter y hero institucional para auth

- Cargar Inter (body) y Plus Jakarta Sans (display) desde Google Fonts
- Aplicar var(--font-sans) y var(--font-display) en base.css
- Login con layout split-pane: hero institucional gradiente TECNM (60%) + form (40%)
- Register con mismo patron split, tagline diferenciado
- Refinar brand-text SIIAP eliminando text-shadow

Cambia la primera impresion del sistema. Coherencia tipografica global.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 4 — Accesibilidad transversal

> **Objetivo:** WCAG 2.1 AA en componentes globales. ARIA, contrastes, focus, motion.
>
> **Rama:** `feature/ui-a11y`

### S4.1 — `prefers-reduced-motion` global 🟢 · S

**Archivo:** `app/static/css/_tokens.css` (al final)

**Agregar:**
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

**Verificación:** en macOS: System Settings → Accessibility → Display → Reduce motion. Recargar — animaciones detenidas. En Chrome DevTools: Rendering → "Emulate CSS prefers-reduced-motion: reduce".

### S4.2 — `aria-live` en flash y notificaciones 🟢 · S

**Archivos:**
- ✏️ `app/templates/_flash.html`
- ✏️ `app/templates/base.html` (notification dropdown)
- ✏️ `app/static/js/notifications.js` (si construye items dinámicamente)

**Cambios:**

`_flash.html`:
```html
<div class="flash-container" role="region" aria-live="polite" aria-label="Notificaciones del sistema">
  <!-- ... -->
</div>
```

`base.html` líneas 153-155:
```html
<div class="notification-list" id="notificationsList" aria-live="polite" aria-busy="false">
```

En `notifications.js`, antes de actualizar el contenido:
```js
list.setAttribute('aria-busy', 'true');
// ... fetch + render
list.setAttribute('aria-busy', 'false');
```

### S4.3 — `aria-label` dinámico en notification badge 🟢 · S

**Archivo:** `app/static/js/notifications.js`

Cuando se actualiza `#notificationBadge`:
```js
function updateBadge(count) {
  const badge = document.getElementById('notificationBadge');
  badge.textContent = count;
  badge.classList.toggle('d-none', count === 0);
  badge.setAttribute('aria-label',
    count === 0 ? '' :
    count === 1 ? '1 notificación no leída' :
    `${count} notificaciones no leídas`);
}
```

### S4.4 — Focus visible global 🟢 · S

**Archivo:** `app/static/css/_tokens.css` o `base.css`

**Agregar:**
```css
*:focus-visible {
  outline: 2px solid var(--color-brand-primary);
  outline-offset: 2px;
  box-shadow: var(--shadow-focus);
}
.notification-bell-btn:focus-visible,
.notification-fab:focus-visible {
  outline: 2px solid var(--color-brand-primary);
  outline-offset: 3px;
}
.btn-close:focus-visible {
  outline: 2px solid var(--color-brand-primary);
  outline-offset: 2px;
}
```

**Verificación:** Tab por toda la página → cada elemento focusable muestra outline azul TECNM visible.

### S4.5 — `bg-warning` con contraste AA 🟡 · S

**Estrategia:** crear utility class `.bg-warning-soft` con fondo claro + texto oscuro (mejor que pelear con Bootstrap nativo).

**Archivo:** `app/static/css/base.css` (al final)

```css
.bg-warning-soft {
  background-color: var(--color-warning-100);
  color: #6b4f00;
  border: 1px solid rgba(184, 134, 0, 0.25);
}
.text-warning-strong { color: var(--color-warning); }
```

**Aplicar en:** badges de pestañas en `coordinator/acceptance.html`, `coordinator/permanence.html` (sustituir `bg-warning text-dark` por `bg-warning-soft`).

**Verificación:** abrir https://webaim.org/resources/contrastchecker/, validar `#b88600` sobre `#ffffff` ≥ 4.5:1.

### S4.6 — `aria-disabled` en links/cards deshabilitados 🟢 · S

**Archivos:**
- ✏️ `app/templates/programs/admission/admission_dashboard.html` (tabs disabled)
- ✏️ `app/templates/user/dashboard/program_admin_dashboard.html` (.quick-action-card-disabled)

**Cambio:**
```html
<!-- Antes -->
<a class="nav-link disabled" href="...">...</a>

<!-- Después -->
<a class="nav-link disabled" href="..." aria-disabled="true" tabindex="-1">...</a>
```

Para cards:
```html
<a class="quick-action-card quick-action-card-disabled"
   aria-disabled="true" tabindex="-1"
   role="link"
   href="#">...</a>
```

### S4.7 — Macro `required_mark` semántico 🟢 · S

**Archivos:**
- ➕ Nuevo: `app/templates/_macros.html`
- ✏️ `app/templates/auth/register.html`
- ✏️ `app/static/css/_tokens.css`

**Macro:**
```html
{# app/templates/_macros.html #}
{% macro required_mark() %}
<abbr class="required-mark" title="Campo requerido" aria-label="requerido">*</abbr>
{% endmacro %}
```

**CSS:**
```css
.required-mark {
  color: var(--color-danger);
  text-decoration: none;
  margin-left: 2px;
  font-weight: var(--fw-semibold);
  cursor: help;
}
```

**Uso en register.html:**
```html
{% from '_macros.html' import required_mark %}
<!-- Antes -->
Email <span style="color:red">*</span>
<!-- Después -->
Email {{ required_mark() }}
```

Sustituir las 7 ocurrencias.

### Cierre Sprint 4

```powershell
git commit -m "$(cat <<'EOF'
A11y(ui): WCAG 2.1 AA transversal — motion, ARIA, contrastes, focus

- prefers-reduced-motion global en _tokens.css
- aria-live=polite en flash messages y notification list
- aria-label dinamico en notification badge segun cantidad
- focus-visible global con outline TECNM (2px solid + offset)
- Utility .bg-warning-soft con contraste AA (#b88600 sobre fondo claro)
- aria-disabled + tabindex=-1 en links/cards deshabilitados
- Macro required_mark semantico (abbr title) sustituye <span style=color:red>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 5 — Skeletons y spinners (performance percibida)

> **Objetivo:** eliminar la sensación de lentitud. Skeletons en tablas, spinners consistentes en botones.
>
> **Rama:** `feature/ui-skeleton-spinners`

### S5.1 — Componente Skeleton 🟢 · M

**Archivos:**
- ➕ Nuevo: `app/static/css/components/_skeleton.css`
- ➕ Nuevo macros en `app/templates/_macros.html`
- ✏️ `app/templates/base.html` (cargar skeleton.css)

**CSS:**
```css
.skeleton {
  background: linear-gradient(90deg,
    var(--color-neutral-100) 25%,
    var(--color-neutral-200) 37%,
    var(--color-neutral-100) 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
  border-radius: var(--radius-sm);
  display: block;
}
@keyframes skeleton-shimmer {
  0%   { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
.skeleton-text { height: 1em; margin-bottom: var(--space-2); }
.skeleton-text--sm { width: 40%; }
.skeleton-text--md { width: 60%; }
.skeleton-text--lg { width: 100%; }
.skeleton-avatar { width: 40px; height: 40px; border-radius: var(--radius-pill); }
.skeleton-card { height: 200px; border-radius: var(--radius-md); }
.skeleton-row {
  display: grid;
  grid-template-columns: repeat(var(--cols, 4), 1fr);
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-default);
}
.skeleton-cell { height: 1.25em; }
@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; opacity: 0.6; }
}
```

**Macro:**
```html
{% macro skeleton_table(rows=5, cols=4) %}
<div class="skeleton-table" aria-hidden="true">
  <div class="skeleton-row" style="--cols: {{ cols }}">
    {% for _ in range(cols) %}<span class="skeleton skeleton-cell"></span>{% endfor %}
  </div>
  {% for _ in range(rows) %}
    <div class="skeleton-row" style="--cols: {{ cols }}">
      {% for _ in range(cols) %}<span class="skeleton skeleton-cell"></span>{% endfor %}
    </div>
  {% endfor %}
</div>
{% endmacro %}

{% macro skeleton_cards(count=3) %}
<div class="row g-3" aria-hidden="true">
  {% for _ in range(count) %}
    <div class="col-md-4"><div class="skeleton skeleton-card"></div></div>
  {% endfor %}
</div>
{% endmacro %}
```

### S5.2 — Aplicar skeletons en flujos de coordinador 🟡 · M

**Archivos:**
- ✏️ `app/templates/coordinator/dashboard.html`
- ✏️ `app/templates/coordinator/acceptance.html`
- ✏️ `app/templates/coordinator/deliberation.html`
- ✏️ `app/templates/coordinator/permanence.html`
- ✏️ `app/static/js/coordinator/*.js` (agregar/remover clases)

**Patrón:**
1. En cada `<tbody id="...">`, agregar contenedor skeleton hermano:
   ```html
   {% from '_macros.html' import skeleton_table %}
   <div id="acceptanceTableSkeleton" class="js-skeleton">
     {{ skeleton_table(rows=6, cols=5) }}
   </div>
   <table id="acceptanceTable" class="d-none">...</table>
   ```
2. En el JS, al inicio del fetch:
   ```js
   document.getElementById('acceptanceTableSkeleton').classList.remove('d-none');
   document.getElementById('acceptanceTable').classList.add('d-none');
   ```
3. Al recibir data:
   ```js
   document.getElementById('acceptanceTableSkeleton').classList.add('d-none');
   document.getElementById('acceptanceTable').classList.remove('d-none');
   ```

**Verificación:** simular red lenta (DevTools → Network → Slow 3G) y observar skeleton durante carga.

### S5.3 — Aplicar skeletons en student dashboard 🟡 · S

**Archivo:** `app/templates/user/dashboard/student_dashboard.html`

**Cambio:** sustituir los múltiples spinners individuales por **un esqueleto del dashboard completo** que se desvanece cuando todos los módulos cargaron. Si es complejo coordinar múltiples fetch, mantener spinners por módulo PERO con `<div class="skeleton skeleton-card">` en lugar del spinner aislado.

### S5.4 — Patrón de spinner en botones 🟢 · S

**Archivos:**
- ➕ Nuevo: `app/static/js/utils/button-loading.js`
- ✏️ `app/templates/base.html` (cargar el script)
- ✏️ Componentes coordinator/* y otros que tengan submit async

**Helper JS:**
```js
// app/static/js/utils/button-loading.js
window.SIIAP = window.SIIAP || {};
window.SIIAP.setButtonLoading = function(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  const label = btn.querySelector('.btn-label');
  let spinner = btn.querySelector('.btn-spinner');
  if (!spinner) {
    spinner = document.createElement('span');
    spinner.className = 'btn-spinner spinner-border spinner-border-sm ms-2 d-none';
    spinner.setAttribute('aria-hidden', 'true');
    btn.appendChild(spinner);
  }
  if (label) label.classList.toggle('d-none', loading);
  spinner.classList.toggle('d-none', !loading);
};
```

**Patrón en HTML:**
```html
<button class="btn btn-primary" id="confirmDecisionBtn">
  <span class="btn-label">Confirmar decisión</span>
</button>
```

**Patrón en JS (sustituir lógica ad-hoc actual):**
```js
btn.addEventListener('click', async () => {
  SIIAP.setButtonLoading(btn, true);
  try {
    await api(...);
  } finally {
    SIIAP.setButtonLoading(btn, false);
  }
});
```

**Aplicar al menos en:**
- `coordinator/dashboard.js` (#refreshBtn, modales)
- `coordinator/deliberation.js` (#confirmDecisionBtn)
- `coordinator/acceptance.js` (todos los confirmar)
- `coordinator/permanence.js` (idem)

### Cierre Sprint 5

```powershell
git commit -m "$(cat <<'EOF'
Feat(ui): skeleton loaders y spinners consistentes en botones

- Componente skeleton (text, avatar, card, table, row) con shimmer animado
- Macros skeleton_table y skeleton_cards en _macros.html
- Aplicar skeleton en tablas dinamicas de coordinator/*
- Helper SIIAP.setButtonLoading para feedback uniforme
- Aplicar patron en botones de acciones asincronas (confirmar/aprobar/rechazar)

Elimina la sensacion de lentitud al cargar tablas y al confirmar acciones.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 6 — StatusBadge y paleta coordinador

> **Objetivo:** consistencia cromática en badges + ícono + texto (no solo color).
>
> **Rama:** `feature/ui-status-badge`

### S6.1 — Componente StatusBadge 🟢 · M

**Archivos:**
- ➕ Nuevo: `app/static/css/components/_status-badge.css`
- ➕ Nuevo macro en `_macros.html`
- ✏️ `base.html` (cargar CSS)

**CSS:**
```css
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--fs-xs);
  font-weight: var(--fw-semibold);
  line-height: 1.4;
  border-radius: var(--radius-pill);
  background: var(--bg-surface-sunken);
  color: var(--text-secondary);
  white-space: nowrap;
}
.status-badge i { font-size: 1em; }

.status-badge--accepted    { background: var(--color-success-100); color: #0e6e3a; }
.status-badge--rejected    { background: var(--color-danger-100);  color: var(--color-brand-accent-600); }
.status-badge--in-progress { background: var(--color-info-100);    color: var(--color-brand-secondary); }
.status-badge--deliberation{ background: var(--color-warning-100); color: #6b4f00; }
.status-badge--deferred    { background: var(--color-neutral-200); color: var(--color-neutral-700); }
.status-badge--enrolled    { background: var(--color-brand-primary-100); color: var(--color-brand-primary); }
.status-badge--interview-completed { background: rgba(110, 63, 191, 0.1); color: #6e3fbf; }
```

**Macro:**
```html
{% set _STATUS = {
  'in_progress':         {'icon': 'arrow-repeat',         'label': 'En proceso'},
  'interview_completed': {'icon': 'mic-fill',             'label': 'Entrevista completada'},
  'deliberation':        {'icon': 'hourglass-split',      'label': 'En deliberación'},
  'accepted':            {'icon': 'check-circle-fill',    'label': 'Aceptado'},
  'rejected':            {'icon': 'x-circle-fill',        'label': 'Rechazado'},
  'deferred':            {'icon': 'arrow-right-circle',   'label': 'Diferido'},
  'enrolled':            {'icon': 'mortarboard-fill',     'label': 'Inscrito'},
} %}

{% macro status_badge(status, label=none) %}
{% set s = _STATUS.get(status, {'icon': 'circle', 'label': status}) %}
<span class="status-badge status-badge--{{ status|replace('_', '-') }}">
  <i class="bi bi-{{ s.icon }}" aria-hidden="true"></i>
  <span>{{ label or s.label }}</span>
</span>
{% endmacro %}
```

### S6.2 — Migrar badges en coordinator/* 🟡 · M

**Archivos:**
- ✏️ `app/templates/coordinator/dashboard.html`
- ✏️ `app/templates/coordinator/acceptance.html`
- ✏️ `app/templates/coordinator/deliberation.html`
- ✏️ `app/templates/coordinator/permanence.html`
- ✏️ JS que renderiza badges dinámicamente

**Patrón:**
```html
<!-- Antes -->
<span class="badge bg-success">Aprobado</span>
<span class="badge bg-danger">Rechazado</span>

<!-- Después (Jinja) -->
{% from '_macros.html' import status_badge %}
{{ status_badge('accepted') }}
{{ status_badge('rejected') }}

<!-- Después (JS dinámico) -->
function statusBadge(status, label) {
  const meta = STATUS_META[status] || { icon: 'circle', label: status };
  return `<span class="status-badge status-badge--${status.replace('_','-')}">
    <i class="bi bi-${meta.icon}" aria-hidden="true"></i>
    <span>${label || meta.label}</span>
  </span>`;
}
```

Crear constante compartida en `app/static/js/utils/status.js` para que todos los JS accedan al mismo mapa.

### S6.3 — Migrar badges en applicant_dashboard, student_dashboard 🟢 · S

Idem patrón. Especial atención a la barra multicolor en applicant_dashboard ([líneas 143-156](app/templates/user/dashboard/applicant_dashboard.html#L143-L156)):

**Cambio:** agregar números encima de cada segmento + patrón rayado en "rechazado":
```css
.progress-bar--rejected {
  background-image: repeating-linear-gradient(
    45deg,
    var(--color-danger),
    var(--color-danger) 6px,
    var(--color-brand-accent-600) 6px,
    var(--color-brand-accent-600) 12px
  );
}
```

### S6.4 — Banner periodo activo en permanence con verde institucional 🟢 · S

**Archivo:** `app/templates/coordinator/permanence.html` líneas 60-66

**Cambio:**
```html
<!-- Antes -->
<div class="alert alert-success">...</div>
<!-- Después -->
<div class="alert" style="background: var(--color-success-100); color: #0e6e3a; border-color: rgba(31,157,85,0.25);">
  <i class="bi bi-check-circle-fill"></i> ...
</div>
```

O crear utility `.alert-success-soft` y usarla.

### Cierre Sprint 6

```powershell
git commit -m "$(cat <<'EOF'
Feat(ui): componente status-badge consistente con icono + texto

- Componente .status-badge con 7 variantes (in_progress, deliberation, accepted, etc.)
- Macro status_badge en Jinja + helper JS compartido en utils/status.js
- Migrar badges Bootstrap (bg-success/warning/danger) en coordinator/* a status_badge
- Migrar en applicant_dashboard y student_dashboard
- Barra de progreso multicolor con patron rayado en segmento rechazado
- Banner periodo activo en permanence con paleta institucional

Cumple WCAG 1.4.1 (color no es unico diferenciador).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 7 — Hero programs/list y events

> **Objetivo:** la cara pública refleja la institución. Eliminar el púrpura genérico de events.
>
> **Rama:** `feature/ui-public-hero`

### S7.1 — Hero institucional para programs/list 🟢 · M

**Archivos:**
- ✏️ `app/templates/programs/list.html`
- ✏️ `app/static/css/program/list.css`

**Estructura HTML antes del grid de programas:**
```html
<header class="programs-hero">
  <div class="programs-hero__content">
    <span class="programs-hero__eyebrow">ITCJ · Posgrado</span>
    <h1 class="programs-hero__title">
      Forma parte del posgrado de excelencia<br>
      del Tecnológico Nacional de México
    </h1>
    <p class="programs-hero__lead">
      {{ programs|length }} programas reconocidos por el SNP — Sistema Nacional de Posgrados.
    </p>
    <form class="programs-hero__search" action="{{ url_for('program.list_programs') }}" method="get" role="search">
      <i class="bi bi-search programs-hero__search-icon" aria-hidden="true"></i>
      <input type="search" name="q" placeholder="Buscar programa o área de interés..."
             class="form-control programs-hero__search-input"
             aria-label="Buscar programa">
    </form>
  </div>
</header>

<section class="programs-filters">
  <!-- filtros nivel/modalidad existentes -->
</section>
```

**CSS:**
```css
.programs-hero {
  position: relative;
  padding: var(--space-12) var(--space-6);
  background: linear-gradient(135deg,
    var(--color-brand-primary) 0%,
    var(--color-brand-primary-700) 80%,
    var(--color-brand-accent) 130%);
  color: var(--text-inverse);
  border-radius: var(--radius-xl);
  margin-bottom: var(--space-8);
  overflow: hidden;
}
.programs-hero::before {
  /* patrón geométrico sutil opcional, SVG inline o pseudo-elemento */
  content: "";
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle at 20% 80%, rgba(255,255,255,0.08), transparent 40%);
  pointer-events: none;
}
.programs-hero__content { position: relative; max-width: 720px; }
.programs-hero__title {
  font-family: var(--font-display);
  font-size: clamp(1.75rem, 4vw, 2.75rem);
  margin-bottom: var(--space-4);
  line-height: var(--lh-tight);
}
.programs-hero__lead {
  font-size: var(--fs-md);
  color: rgba(255,255,255,0.85);
  margin-bottom: var(--space-6);
}
.programs-hero__search {
  position: relative;
  max-width: 480px;
}
.programs-hero__search-icon {
  position: absolute;
  left: var(--space-4);
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
}
.programs-hero__search-input {
  padding-left: calc(var(--space-4) * 2 + 1rem);
  height: 3rem;
  border-radius: var(--radius-pill);
  border: none;
  font-size: var(--fs-base);
}
@media (max-width: 767.98px) {
  .programs-hero { padding: var(--space-8) var(--space-4); border-radius: var(--radius-md); }
}
```

**Verificación:** /programs muestra hero arriba con gradiente TECNM, búsqueda funcional. Eliminar el h1 antiguo.

### S7.2 — Hero events/list con paleta TECNM 🟢 · S

**Archivo:** `app/static/css/events/list.css`

**Buscar:**
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```

**Sustituir:**
```css
background: linear-gradient(135deg,
  var(--color-brand-primary) 0%,
  var(--color-brand-secondary) 50%,
  var(--color-brand-accent) 100%);
```

### S7.3 — Cards de programas con paleta institucional 🟢 · S

**Archivos:**
- ✏️ `app/static/css/program/list.css`

**Cambios:**
```css
/* Antes */
.badge-maestria   { background: rgba(13, 110, 253, 0.9); }
.badge-doctorado  { background: rgba(108, 117, 125, 0.9); }

/* Después */
.badge-maestria   { background: var(--color-brand-primary); color: white; }
.badge-doctorado  { background: var(--color-brand-accent);  color: white; }
.badge-especialidad { background: var(--color-brand-secondary); color: white; }
```

### S7.4 — Lazy loading e imágenes responsive 🟢 · S

**Archivo:** `app/templates/programs/list.html`

**Cambio en cada `<img>` de tarjeta:**
```html
<!-- Antes -->
<img src="..." alt="{{ p.name }}" class="card-img-top">
<!-- Después -->
<img src="..." alt="{{ p.name }}" class="card-img-top"
     loading="lazy" decoding="async">
```

**NO** lazy en imágenes del hero (LCP).

### S7.5 — Galería events/view responsive 🟢 · S

**Archivo:** `app/static/css/events/view.css`

**Cambio:**
```css
/* Antes */
.event-gallery {
  grid-template-columns: repeat(3, 1fr);
}
/* Después */
.event-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
}
```

### S7.6 — Animaciones events sin reduced-motion 🟢 · S

**Archivo:** `app/static/css/events/list.css`

**Cambio:** envolver `@keyframes invitation-pulse` y su uso:
```css
@media (prefers-reduced-motion: no-preference) {
  .invitation-card { animation: invitation-pulse 2.5s infinite; }
}
```

(O confiar en el wrapper global del Sprint 4 — verificar que aplique).

### Cierre Sprint 7

```powershell
git commit -m "$(cat <<'EOF'
Feat(ui): hero institucional en paginas publicas con identidad TECNM

- Hero programs/list con gradiente azul TECNM, busqueda integrada
- Hero events/list cambia gradiente purpura #667eea por paleta TECNM
- Badges de programas (maestria/doctorado/especialidad) con paleta institucional
- loading=lazy en imagenes de tarjetas (no en hero)
- Galeria events/view con auto-fit minmax(200px) responsive
- Animaciones de invitation-pulse respetan prefers-reduced-motion

La cara publica del SIIAP ahora refleja la marca ITCJ/TECNM.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 8 — Componentes reutilizables avanzados

> **Objetivo:** macros que el equipo reutilizará en cada feature futura.
>
> **Rama:** `feature/ui-components`

### S8.1 — Componente EmptyState 🟢 · M

**Archivos:**
- ➕ `app/static/css/components/_empty-state.css`
- ➕ Macro en `_macros.html`

**CSS:**
```css
.empty-state {
  text-align: center;
  padding: var(--space-12) var(--space-6);
  color: var(--text-secondary);
}
.empty-state__icon {
  font-size: 3rem;
  color: var(--color-neutral-400);
  margin-bottom: var(--space-4);
}
.empty-state__title {
  font-size: var(--fs-lg);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.empty-state__description {
  font-size: var(--fs-sm);
  max-width: 360px;
  margin: 0 auto var(--space-6);
}
```

**Macro:**
```html
{% macro empty_state(icon='inbox', title='Sin resultados',
                     description='', action_label=none, action_url=none) %}
<div class="empty-state">
  <div class="empty-state__icon"><i class="bi bi-{{ icon }}"></i></div>
  <h3 class="empty-state__title">{{ title }}</h3>
  {% if description %}<p class="empty-state__description">{{ description }}</p>{% endif %}
  {% if action_label %}
    <a href="{{ action_url or '#' }}" class="btn btn-primary">{{ action_label }}</a>
  {% endif %}
</div>
{% endmacro %}
```

**Aplicar en:**
- Tablas de coordinator cuando no hay datos
- `events/list.html` cuando no hay eventos
- `_profile_history.html` cuando no hay historial
- `programs/list.html` cuando no hay programas filtrados

### S8.2 — Componente ConfirmModal 🟡 · M

**Archivos:**
- ➕ Macro en `_macros.html`
- ✏️ Aplicar en `coordinator/deliberation.html`, `coordinator/acceptance.html`, etc.

**Macro:** ver [PROPUESTAS_ESTETICAS.md §8.5](PROPUESTAS_ESTETICAS.md).

**Aplicación gradual** (no migrar todos de golpe):
- Primero el modal de "Eliminar usuario" en admin/settings/users (si existe).
- Después modales de decisión en deliberation.

### S8.3 — Tabla con scroll hint y sticky col 🟡 · M

**Archivos:**
- ➕ `app/static/css/components/_data-table.css`
- ➕ `app/static/js/utils/data-table.js`

**CSS:**
```css
.siiap-table-wrapper {
  position: relative;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border-radius: var(--radius-md);
}
.siiap-table-wrapper::after {
  content: "";
  position: absolute;
  top: 0; right: 0; bottom: 0;
  width: 32px;
  background: linear-gradient(to right, transparent, var(--bg-surface));
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--duration-fast);
}
.siiap-table-wrapper.has-overflow::after { opacity: 1; }
.siiap-table-wrapper.scrolled-end::after { opacity: 0; }
@media (max-width: 767.98px) {
  .siiap-table th:first-child,
  .siiap-table td:first-child {
    position: sticky;
    left: 0;
    background: var(--bg-surface);
    z-index: 1;
  }
}
```

**JS:**
```js
// app/static/js/utils/data-table.js
function initDataTable(wrapper) {
  const update = () => {
    const overflow = wrapper.scrollWidth > wrapper.clientWidth;
    const atEnd = wrapper.scrollLeft + wrapper.clientWidth >= wrapper.scrollWidth - 1;
    wrapper.classList.toggle('has-overflow', overflow);
    wrapper.classList.toggle('scrolled-end', atEnd);
  };
  update();
  wrapper.addEventListener('scroll', update, { passive: true });
  new ResizeObserver(update).observe(wrapper);
}
document.querySelectorAll('.siiap-table-wrapper').forEach(initDataTable);
```

**Migrar gradualmente:** sustituir `.table-responsive` por `.siiap-table-wrapper` en tablas críticas.

### S8.4 — Stepper component 🟢 · M

**Archivos:**
- ➕ `app/static/css/components/_stepper.css`
- ➕ Macro

**CSS:**
```css
.stepper {
  display: flex;
  list-style: none;
  padding: 0;
  gap: var(--space-2);
  counter-reset: step;
}
.stepper__step {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  position: relative;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--bg-surface-sunken);
  font-size: var(--fs-sm);
  color: var(--text-muted);
}
.stepper__step--active {
  background: var(--color-brand-primary-100);
  color: var(--color-brand-primary);
  font-weight: var(--fw-semibold);
}
.stepper__step--completed {
  background: var(--color-success-100);
  color: #0e6e3a;
}
.stepper__number {
  width: 1.75rem;
  height: 1.75rem;
  border-radius: var(--radius-pill);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-neutral-0);
  font-weight: var(--fw-semibold);
}
.stepper__step--active .stepper__number {
  background: var(--color-brand-primary);
  color: var(--text-inverse);
}
@media (max-width: 575.98px) {
  .stepper { flex-direction: column; }
}
```

**Aplicar después en:** wizard de register (Sprint 10), modales de decisión de deliberation.

### Cierre Sprint 8

```powershell
git commit -m "$(cat <<'EOF'
Feat(ui): componentes reutilizables EmptyState, ConfirmModal, DataTable, Stepper

- EmptyState con icono + titulo + descripcion + CTA opcional
- ConfirmModal estandar con seccion 'consecuencia' opcional + spinner integrado
- DataTable wrapper con scroll hint (gradient overlay) y columna sticky en movil
- Stepper component para wizards y procesos de decision multi-paso

Componentes documentados como macros Jinja en _macros.html.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 9 — RoleBanner y refinamientos de dashboards

> **Objetivo:** identidad de rol explícita; pulir dashboards existentes.
>
> **Rama:** `feature/ui-dashboards`

### S9.1 — Componente RoleBanner 🟡 · M

**Archivos:**
- ➕ `app/static/css/components/_role-banner.css`
- ➕ Macro
- ✏️ `app/templates/user/dashboard/dashboard.html` (al inicio)

**Macro:**
```html
{% macro role_banner(user, role_label, role_icon, context_line=none, next_action=none, progress=none) %}
<header class="role-banner">
  <div class="role-banner__avatar">
    <i class="bi bi-{{ role_icon }}"></i>
  </div>
  <div class="role-banner__content">
    <p class="role-banner__greeting">Hola, {{ user.first_name }} {{ user.last_name }}</p>
    <p class="role-banner__role">
      <span class="status-badge status-badge--enrolled">{{ role_label }}</span>
      {% if context_line %}<span class="text-muted">· {{ context_line }}</span>{% endif %}
    </p>
    {% if next_action %}
      <p class="role-banner__next-action">
        <i class="bi bi-arrow-right-circle"></i>
        <strong>Próximo paso:</strong> {{ next_action }}
      </p>
    {% endif %}
  </div>
  {% if progress is not none %}
    <div class="role-banner__progress">
      <div class="role-banner__progress-bar">
        <span style="width: {{ progress }}%"></span>
      </div>
      <span class="role-banner__progress-label">{{ progress }}%</span>
    </div>
  {% endif %}
</header>
{% endmacro %}
```

**Uso en applicant_dashboard:**
```html
{{ role_banner(
  user=current_user,
  role_label='Aspirante',
  role_icon='mortarboard-fill',
  context_line=user_program.program.name,
  next_action='Sube tu carta de exposición de motivos',
  progress=docs_progress
) }}
```

**Iconos por rol:**
- aspirante: `mortarboard-fill`
- estudiante: `book-half`
- program_admin: `building-fill-gear`
- postgraduate_admin: `building-fill-check`
- social_service: `heart-fill`

### S9.2 — Selector "Ver todos" en program_admin claro 🟢 · S

**Archivo:** `app/templates/user/dashboard/program_admin_dashboard.html`

**Cambio:** cuando `selected_program == 'all'`, mostrar arriba de las acciones rápidas:
```html
<div class="alert" style="background: var(--color-info-100); color: var(--color-brand-secondary);">
  <i class="bi bi-info-circle-fill"></i>
  Estás viendo todos los programas. <strong>Selecciona uno específico</strong>
  arriba para activar las acciones rápidas y ver actividad detallada.
</div>
```

Y aplicar `aria-disabled="true" tabindex="-1"` en los `.quick-action-card-disabled`.

### S9.3 — Páginas error 404/500 institucionales 🟢 · S

**Archivos:**
- ✏️ `app/templates/404.html`
- ✏️ `app/templates/500.html`
- ✏️ `app/static/css/404.css`

**Cambios:**
- Mantener `{% block navbar %}{% endblock %}` vacío SOLO si el usuario no está autenticado; si lo está, mostrar sidebar.
- Agregar landmarks: `<main role="main">`.
- Eliminar animación bounce (ya hecho en Sprint 2).
- Agregar enlaces contextuales:
  ```html
  <h1>404</h1>
  <p>No encontramos la página que buscas.</p>
  <ul class="error-suggestions">
    <li><a href="{{ url_for('pages_user.dashboard') }}">Ir al dashboard</a></li>
    <li><a href="{{ url_for('program.list_programs') }}">Ver programas</a></li>
    <li><a href="mailto:posgrado@itcj.edu.mx">Reportar problema</a></li>
  </ul>
  ```

500 idéntico pero con tono empático: "Estamos trabajando en ello. Si persiste, repórtalo a soporte mencionando este código: `{{ error_id }}`" (timestamp generado por backend).

### S9.4 — Refinamientos sidebar (agrupación) 🟡 · M

**Archivo:** `app/templates/_sidebar_nav.html`

**Cambio:** agregar `<h6 class="sidebar-section-label">` antes de cada grupo lógico (cf. [PROPUESTAS_ESTETICAS.md §T-06](PROPUESTAS_ESTETICAS.md)).

**CSS:**
```css
.sidebar-section-label {
  font-size: var(--fs-xs);
  font-weight: var(--fw-semibold);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  color: var(--text-muted);
  padding: var(--space-4) var(--space-6) var(--space-1);
  margin: 0;
}
```

### Cierre Sprint 9

```powershell
git commit -m "$(cat <<'EOF'
Feat(ui): RoleBanner para identidad de rol explicita en dashboards

- Componente RoleBanner con avatar/icono de rol, contexto, proximo paso, progreso
- Aplicado en applicant_dashboard, student_dashboard, program_admin_dashboard, postgraduate_admin
- Sidebar con agrupacion logica (PERSONAL, ACADEMICO, GESTION, EVENTOS, CONFIG)
- Selector "Ver todos" en program_admin con alerta clara cuando hay degradacion
- Paginas 404/500 institucionales con sugerencias contextuales y landmarks

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Sprint 10 — Pulido y deuda técnica

> **Objetivo:** los detalles que pasan desapercibidos individualmente pero suman calidad global.
>
> **Rama:** `feature/ui-polish`

### S10.1 — Footer de valor 🟢 · S

**Archivo:** `app/templates/base.html` líneas 140-142

**Cambio:**
```html
<footer class="d-none d-md-flex">
  <div class="container-fluid d-flex justify-content-between align-items-center px-4">
    <small>ITCJ · TECNM &copy; 2026</small>
    <small>
      <a href="mailto:posgrado@itcj.edu.mx">Soporte</a>
      ·
      <a href="{{ url_for('static', filename='docs/manual.pdf') }}" target="_blank">Manual</a>
      ·
      <span aria-label="Estado del sistema operativo">
        <span class="status-dot status-dot--ok"></span> Operativo
      </span>
    </small>
  </div>
</footer>
```

CSS para `.status-dot`:
```css
.status-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  margin-right: var(--space-1);
}
```

En móvil el footer queda oculto (`d-md-flex`) → más espacio para contenido.

### S10.2 — Wizard 2 pasos en register 🟡 · M

Aplicar `Stepper` (sprint 8) en register. Dividir campos en:
- Paso 1: email, username, password, confirm_password
- Paso 2: first_name, last_name_p, last_name_m

Si la complejidad es alta (validación cruzada, navegación), considerar diferir al Sprint 11.

### S10.3 — Refactor offcanvas a flex layout 🟢 · S

**Archivo:** `app/static/css/base.css`

**Cambio (líneas 316-413):**
```css
.offcanvas {
  width: 280px !important;
  height: 100vh !important;
  display: flex;
  flex-direction: column;
  z-index: var(--z-offcanvas);
}
.offcanvas-header,
.mobile-user-section,
.offcanvas-footer { flex-shrink: 0; }
.offcanvas-body {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
}
/* Eliminar el max-height: calc(100vh - 220px) */
```

### S10.4 — Eliminar AOS, sustituir por IntersectionObserver 🟡 · M

**Archivos:**
- ❌ Eliminar `<script>` de AOS en `base.html` (si existe)
- ➕ `app/static/js/utils/reveal.js`
- ✏️ Templates con `data-aos` → cambiar a `data-reveal`
- ➕ CSS en `_tokens.css` o nuevo `_reveal.css`

Implementación: cf. [PROPUESTAS_ESTETICAS.md §7.4](PROPUESTAS_ESTETICAS.md).

### S10.5 — Optimistic UI en aprobar/rechazar 🟡 · M

**Archivos:**
- ✏️ `app/static/js/coordinator/deliberation.js`
- ✏️ `app/static/js/coordinator/acceptance.js`

**Patrón:**
```js
async function approveCandidate(row, candidateId) {
  row.classList.add('row-updating');
  try {
    await api(`/api/v1/deliberation/${candidateId}/approve`, { method: 'POST' });
    // Mover fila a tab "Aceptados" con animación
  } catch (err) {
    row.classList.remove('row-updating');
    flash('Error al aprobar', 'danger');
  }
}
```

CSS:
```css
.row-updating {
  opacity: 0.5;
  pointer-events: none;
  position: relative;
}
.row-updating::after {
  content: "";
  position: absolute;
  top: 50%; right: var(--space-3);
  transform: translateY(-50%);
  width: 1rem; height: 1rem;
  border: 2px solid var(--color-brand-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
```

### S10.6 — Consolidar 3 timelines en componente único 🟡 · M

**Archivos:**
- ➕ `app/static/css/components/_timeline.css`
- ➕ Macro `timeline_item`
- ✏️ `_profile_info.html`, `_profile_academic.html`, `_profile_history.html`
- ✏️ `app/static/js/user/profile_history.js` (mover JS inline)

Tomar el mejor diseño existente (`.timeline-modern` en `profile.css:472+`) como base canónica y migrar los otros 2 patterns a esta clase.

### S10.7 — Imágenes WebP con fallback 🟡 · M

**Archivos:**
- Convertir `app/static/assets/images/*.jpg` y `.png` a WebP (script local con `cwebp` o Pillow).
- ➕ Macro `responsive_img` (cf. [PROPUESTAS_ESTETICAS.md §7.3](PROPUESTAS_ESTETICAS.md))
- ✏️ Aplicar en `programs/list.html`, `programs/view/_hero.html`, `events/*`

### S10.8 — Mover JS inline a archivos 🟢 · M

**Archivos a auditar:**
- `app/templates/auth/login.html` líneas 36-100
- `app/templates/user/profile/_profile_history.html` líneas 27-106
- Otros templates con `<script>` largo

**Patrón:** crear archivo en `app/static/js/<feature>/`, importar como módulo:
```html
<script type="module" src="{{ url_for('static', filename='js/auth/login.js') }}?v={{ static_version }}"></script>
```

### Cierre Sprint 10

```powershell
git commit -m "$(cat <<'EOF'
Refactor(ui): pulido final, deuda tecnica y optimizaciones

- Footer con enlaces utiles (soporte, manual, estado) visible solo en desktop
- Wizard 2 pasos en register usando Stepper component
- Offcanvas refactor a flex layout (sin calc heights fragiles)
- Sustituir AOS por IntersectionObserver + data-reveal (sin dependencia)
- Optimistic UI en aprobar/rechazar de coordinator (sensacion instantanea)
- Consolidar 3 patrones de timeline en componente .siiap-timeline
- Imagenes WebP con fallback via macro responsive_img
- Mover JS inline a archivos modularizados

Sprint final del rediseno. Sistema con tokens, componentes y experiencia
consistente.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Verificación final (post-sprint 10)

### V1. Pruebas manuales por flujo

| Flujo | Pasos | Resultado esperado |
|---|---|---|
| Login → dashboard aspirante | login con credenciales válidas | Hero institucional, dashboard con RoleBanner, cards rápidas, progreso visible |
| Aspirante → ver programa | Click en "Programas" → un programa | Hero TECNM, secciones bien jerarquizadas, links de documento funcionan |
| Coordinador → deliberación | Login program_admin → deliberación | Pestañas con badges, tabla con skeleton al cambiar tab, modal con cards de decisión |
| Coordinador → aprobar | Click "Aprobar" en una solicitud | Botón con spinner, fila con `.row-updating`, fila se mueve al tab correcto |
| Móvil → todo | Resize a 375px | Todos los flujos siguen siendo usables, sin scroll horizontal involuntario |

### V2. Pruebas de accesibilidad

```powershell
# axe-core via Lighthouse o axe DevTools extension
# 1. Abrir cada pantalla principal en Chrome
# 2. DevTools > Lighthouse > Accessibility audit
# 3. Esperar score >= 95
```

Checklist mínimo:
- [ ] Tab navigation funciona en cada pantalla, focus visible siempre
- [ ] Screen reader (VoiceOver/NVDA) anuncia flash messages
- [ ] Contrastes >= 4.5:1 en todo texto (probar con WAVE extension)
- [ ] `prefers-reduced-motion: reduce` detiene todas las animaciones
- [ ] Formularios con error muestran feedback semántico

### V3. Pruebas de performance

```powershell
# Lighthouse Performance audit
# - First Contentful Paint < 1.8s
# - Largest Contentful Paint < 2.5s
# - Cumulative Layout Shift < 0.1
```

### V4. Verificación cross-browser

- [ ] Chrome 120+ (principal)
- [ ] Firefox latest
- [ ] Safari latest (incluye iOS Safari para `100dvh`, `aspect-ratio`)
- [ ] Edge latest

### V5. Tests automatizados (si los hay)

```powershell
docker exec siiap-web-1 pytest tests/ -v
```

Verificar que las rutas API que se tocaron en Sprint 2 (form contacto si se implementó) tengan cobertura.

---

## Plan B — Si tienes menos tiempo

Si no puedes ejecutar los 10 sprints completos, aquí están las **prioridades brutales**:

### Si tienes 1 semana
- Sprint 1 completo
- Sprint 2 completo
- Sprint 5 (skeletons + spinners)

**Resultado:** marca alineada, bugs arreglados, sensación de velocidad. ~70% del valor con 30% del esfuerzo.

### Si tienes 2 semanas
- Sprints 1, 2, 3, 5

**Resultado:** lo anterior + login con personalidad + Inter + mucho más identidad visible.

### Si tienes 3 semanas
- Sprints 1, 2, 3, 4, 5, 6

**Resultado:** WCAG AA + StatusBadge consistente. Listo para auditoría externa.

### Si tienes 4 semanas
- 1–7

**Resultado:** la cara pública del SIIAP es completamente nueva. Productivo de inmediato.

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Bootstrap 5.3.3 rompe estilos en auth | Media | Medio | Diff visual con snapshots antes/después; rollback rápido si surge problema |
| Migración FA→BI deja íconos rotos | Alta | Bajo | Tabla de mapeo exhaustiva + grep final por `fas fa-`/`far fa-` antes de eliminar el `<link>` |
| Inter no carga en redes lentas | Baja | Bajo | `display=swap` evita FOIT; system stack sigue siendo el fallback |
| Skeleton loaders no coinciden con tabla real | Media | Bajo | Documentar que cada tabla debe ajustar `cols` del macro |
| Refactor sessionModal rompe flujo de keep-alive | Media | Alto | Test manual exhaustivo: simular expiración real |
| Form contacto sin handler en Sprint 2.2 | Alta | Medio | Si no se puede implementar a tiempo, sustituir por `mailto:` (no dejar form roto) |
| Optimistic UI muestra estado incorrecto si POST falla | Media | Medio | Manejar el `catch` con rollback explícito y mensaje de error |
| Cambios visuales bloqueados por usuarios acostumbrados | Baja | Medio | Comunicar el cambio antes de deploy; ofrecer screenshot del antes/después |

---

## Comandos de referencia rápida

```powershell
# Reiniciar el contenedor después de cambios CSS (suele bastar Ctrl+F5)
docker compose restart web

# Si tocas modelos o templates Jinja con sintaxis nueva
docker compose down && docker compose up -d

# Verificar logs de errores
docker compose logs -f web --tail=100

# Ejecutar comandos Flask
docker exec siiap-web-1 flask <comando>

# Ver el static_version actual (cache busting)
docker exec siiap-web-1 flask shell
>>> from app import app
>>> app.jinja_env.globals.get('static_version')
```

---

## Cierre

Este plan **respeta la arquitectura actual** (Flask + Bootstrap + Vanilla JS), **no introduce dependencias pesadas** (la única adición es Inter desde Google Fonts), y **es ejecutable de forma incremental** — cada sprint deja la app desplegable.

**Recomendación:** ejecutar Sprint 1 completo en una sentada (mañana entera), porque sin tokens nada de lo siguiente tiene sentido. Después, los sprints 2–7 se pueden interrumpir/retomar sin perder consistencia.

— *Plan derivado de [PROPUESTAS_ESTETICAS.md](PROPUESTAS_ESTETICAS.md). Total: 10 sprints, 39+ tareas concretas, ~94 horas estimadas.*

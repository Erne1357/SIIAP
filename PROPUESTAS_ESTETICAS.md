# SIIAP — Propuestas Estéticas y de UX

> **Documento de diagnóstico y propuestas priorizadas** para modernizar la presentación visual del sistema SIIAP (TECNM/ITCJ Posgrado) **manteniendo la identidad institucional** (`#0b1e8a` azul TECNM, `#b21f2d` rojo TECNM).
>
> No modifica archivos del proyecto. Es una hoja de ruta para ejecutar incremental, ordenada por impacto (P0 → P2) y esfuerzo (S/M/L).
>
> **Fecha:** 2026-05-04 · **Branch base:** `feature/permission-system` · **Stack:** Flask 3 + Bootstrap 5.3.3 + Vanilla JS

---

## Tabla de contenidos

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Sistema de tokens propuesto](#2-sistema-de-tokens-propuesto)
3. [Hallazgos transversales (chrome / shell)](#3-hallazgos-transversales-chrome--shell)
4. [Hallazgos por dominio](#4-hallazgos-por-dominio)
   - 4.1 [Entrada (login, register, errores)](#41-entrada-login-register-errores)
   - 4.2 [Dashboards por rol](#42-dashboards-por-rol)
   - 4.3 [Flujos de coordinador](#43-flujos-de-coordinador)
   - 4.4 [Páginas públicas y eventos](#44-páginas-públicas-y-eventos)
5. [Auditoría de accesibilidad (WCAG 2.1 AA)](#5-auditoría-de-accesibilidad-wcag-21-aa)
6. [Responsive y mobile-first](#6-responsive-y-mobile-first)
7. [Performance percibida](#7-performance-percibida)
8. [Componentes propuestos](#8-componentes-propuestos)
9. [Roadmap priorizado P0 / P1 / P2](#9-roadmap-priorizado-p0--p1--p2)
10. [Apéndice: anti-patrones detectados](#10-apéndice-anti-patrones-detectados)

---

## 1. Resumen ejecutivo

SIIAP tiene una **base sólida de UX** (flujos claros, lógica condicional por rol, responsive funcional) pero **una capa visual fragmentada** que no comunica la identidad institucional con la dignidad que merece. Hay tres clases de problemas:

| Clase | Naturaleza | Ejemplo concreto |
|---|---|---|
| **Sistémicos** | Decisiones de fundamento que se manifiestan en todas las pantallas | Sin design tokens (solo color); dos librerías de íconos (FA + BI = 67 KB redundantes); `!important` proliferado en `menu_colors.css`; z-index caóticos (1020 → 9999 → 10001) |
| **De marca** | La paleta institucional no se respeta en componentes Bootstrap | Login con border verde `#4a7c59` arbitrario; botón "Registrarme" verde Bootstrap; FAB notificaciones azul `#007bff` (no `--bg--tecnm`); hero de eventos en gradiente púrpura `#667eea → #764ba2` |
| **De experiencia** | Detalles que el usuario percibe como "se siente lento", "no entiendo qué pasó" | Skeleton loaders ausentes en TODAS las tablas dinámicas; spinners en botones inconsistentes; modales con `backdrop="static"` sin feedback de por qué; columnas críticas ocultas en móvil sin acceso alternativo |

### Veredicto

> SIIAP **funciona** como una herramienta institucional competente, pero **no seduce** como un portal académico moderno. Un aspirante que llega a `programs/list` ve un catálogo correcto comparable a una grilla de productos de Amazon; no a la cara visible de una institución educativa de prestigio. Un coordinador que pasa 6 horas al día en `coordinator/deliberation` percibe parpadeos, modales atrapantes y badges sin coherencia cromática.

### Estrategia propuesta — 3 fases

1. **Fase 0 (Fundamentos, 1–2 semanas).** Introducir el sistema de tokens (§2), unificar la librería de íconos, eliminar el modal custom de session timeout, y fijar la pila de z-index. **No cambia visualmente nada todavía**, pero habilita todo lo siguiente.
2. **Fase 1 (Marca + Performance percibida, 2–4 semanas).** Sustituir el banner verde de auth por gradiente institucional, alinear la paleta de eventos, agregar `<SkeletonTable>` y `<SkeletonCard>`, agregar `aria-live` a flash y notificaciones.
3. **Fase 2 (Experiencia, 4–8 semanas).** Rediseñar hero de `programs/list`, consolidar las 3 variantes de timeline, mejorar microcopy de modales, introducir el componente `RoleBanner` y reordenar la navegación lateral.

Costo total estimado: **~30–50 horas** de un dev medio, **sin** romper compatibilidad ni requerir migraciones.

---

## 2. Sistema de tokens propuesto

> **Cómo aplicar:** crear `app/static/css/_tokens.css` y cargarlo ANTES de `base.css` en `templates/base.html` y `templates/auth_base.html`. Después, refactorizar gradualmente los CSS por feature para usar `var(--token)` en lugar de valores literales.
>
> Este bloque **no es código a copiar tal cual**, sino la propuesta que el dev valida, ajusta y mete al proyecto. Los nombres siguen la convención **`--<categoría>-<variante>-<modificador>`**.

### 2.1 Color

```css
:root {
  /* === Marca institucional (anclas inmutables) === */
  --color-brand-primary:        #0b1e8a;  /* Azul TECNM (--bg--tecnm actual) */
  --color-brand-primary-600:    #0a1a7a;  /* hover/active */
  --color-brand-primary-700:    #081570;
  --color-brand-primary-100:    #e6e9f4;  /* fondo sutil */
  --color-brand-primary-50:     #f3f5fa;

  --color-brand-accent:         #b21f2d;  /* Rojo TECNM (--rojoTec actual) */
  --color-brand-accent-600:     #951a26;
  --color-brand-accent-100:     #fce8ea;

  --color-brand-secondary:      #1a71cf;  /* Azul fuerte (--azulFuerte actual) */

  /* === Escala de grises neutrales === */
  --color-neutral-0:            #ffffff;
  --color-neutral-50:           #fafbfc;
  --color-neutral-100:          #f4f6f8;
  --color-neutral-200:          #e5e9ed;
  --color-neutral-300:          #cbd2d9;
  --color-neutral-400:          #9aa5b1;
  --color-neutral-500:          #7b8794;
  --color-neutral-600:          #616e7c;
  --color-neutral-700:          #3e4c59;
  --color-neutral-800:          #1f2933;
  --color-neutral-900:          #0a0e13;

  /* === Semánticos (alineados con la marca, no con Bootstrap) === */
  --color-success:              #1f9d55;  /* sustituye #28a745 */
  --color-success-100:          #def7ec;
  --color-warning:              #b88600;  /* sustituye #ffc107 — contraste AA contra blanco */
  --color-warning-100:          #fef3c7;
  --color-danger:               var(--color-brand-accent);  /* el rojo institucional ES el danger */
  --color-danger-100:           var(--color-brand-accent-100);
  --color-info:                 var(--color-brand-secondary);
  --color-info-100:             #dceeff;

  /* === Mapas semánticos a roles de UI === */
  --bg-page:                    var(--color-neutral-50);
  --bg-surface:                 var(--color-neutral-0);
  --bg-surface-raised:          var(--color-neutral-0);
  --bg-surface-sunken:          var(--color-neutral-100);
  --border-default:             var(--color-neutral-200);
  --border-strong:              var(--color-neutral-300);
  --text-primary:               var(--color-neutral-800);
  --text-secondary:             var(--color-neutral-600);
  --text-muted:                 var(--color-neutral-500);
  --text-inverse:               var(--color-neutral-0);

  /* === Estados de admisión (mapeo directo desde valores del modelo) === */
  --status-in-progress:         var(--color-info);
  --status-interview-completed: #6e3fbf;        /* púrpura discreto */
  --status-deliberation:        var(--color-warning);
  --status-accepted:            var(--color-success);
  --status-rejected:            var(--color-danger);
  --status-deferred:            var(--color-neutral-500);
  --status-enrolled:            var(--color-brand-primary);
}
```

> **Regla de oro:** los nombres `--color-brand-*` son las anclas; los `--color-success/warning/danger` son los semánticos. NUNCA un componente debería usar `#0b1e8a` literal — siempre `var(--color-brand-primary)`. Esto permite redefinir paletas (dark mode, futuro rebrand) sin tocar templates.

### 2.2 Tipografía

```css
:root {
  /* Familias */
  --font-sans:    'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-display: 'Plus Jakarta Sans', var(--font-sans);  /* opcional, para hero/h1 */
  --font-mono:    ui-monospace, 'SF Mono', Menlo, Consolas, monospace;

  /* Escala (modular ratio 1.200) */
  --fs-xs:        0.75rem;    /* 12px — labels, footnotes */
  --fs-sm:        0.875rem;   /* 14px — body small */
  --fs-base:      1rem;       /* 16px — body */
  --fs-md:        1.125rem;   /* 18px — lead */
  --fs-lg:        1.25rem;    /* 20px — h4 */
  --fs-xl:        1.5rem;     /* 24px — h3 */
  --fs-2xl:       2rem;       /* 32px — h2 */
  --fs-3xl:       2.5rem;     /* 40px — h1 */
  --fs-display:   clamp(2.5rem, 5vw, 4rem);  /* SIIAP brand-text */

  /* Pesos */
  --fw-regular:   400;
  --fw-medium:    500;
  --fw-semibold:  600;
  --fw-bold:      700;

  /* Alturas de línea */
  --lh-tight:     1.2;   /* títulos */
  --lh-normal:    1.5;   /* body */
  --lh-relaxed:   1.7;   /* texto largo */

  /* Tracking */
  --tracking-tight:  -0.01em;
  --tracking-wide:    0.04em;
  --tracking-display: 0.06em;  /* SIIAP en mayúscula */
}
```

**Cargar Inter** (variable, una sola petición):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### 2.3 Espaciado (escala de 8)

```css
:root {
  --space-0:    0;
  --space-1:    0.25rem;   /*  4px */
  --space-2:    0.5rem;    /*  8px */
  --space-3:    0.75rem;   /* 12px */
  --space-4:    1rem;      /* 16px */
  --space-5:    1.25rem;   /* 20px */
  --space-6:    1.5rem;    /* 24px */
  --space-8:    2rem;      /* 32px */
  --space-10:   2.5rem;    /* 40px */
  --space-12:   3rem;      /* 48px */
  --space-16:   4rem;      /* 64px */
  --space-20:   5rem;      /* 80px */
}
```

**Por qué importa:** hoy en CSS hay valores como `0.65rem`, `0.875rem`, `1.875rem` (cf. [base.css:198](app/static/css/base.css#L198), [acceptance.css:26-39](app/static/css/coordinator/acceptance.css)) que rompen la grilla rítmica. Con tokens, todos los paddings/márgenes/gaps se alinean a la escala de 8px.

### 2.4 Radios de borde

```css
:root {
  --radius-xs:    0.25rem;   /*  4px — inputs pequeños */
  --radius-sm:    0.375rem;  /*  6px — botones, badges */
  --radius-md:    0.5rem;    /*  8px — cards */
  --radius-lg:    0.75rem;   /* 12px — modales, sections */
  --radius-xl:    1rem;      /* 16px — hero, cards prominentes */
  --radius-pill:  9999px;    /* pills, avatars */
}
```

### 2.5 Sombras y elevación

```css
:root {
  /* Niveles de elevación — sigan a Material/Apple HIG */
  --shadow-0:  none;
  --shadow-1:  0 1px 2px 0 rgba(15, 23, 42, 0.05);                 /* hairline */
  --shadow-2:  0 1px 3px 0 rgba(15, 23, 42, 0.08),
               0 1px 2px -1px rgba(15, 23, 42, 0.06);              /* card en reposo */
  --shadow-3:  0 4px 6px -2px rgba(15, 23, 42, 0.06),
               0 2px 4px -2px rgba(15, 23, 42, 0.06);              /* card hover, dropdown */
  --shadow-4:  0 10px 15px -3px rgba(15, 23, 42, 0.10),
               0 4px 6px -4px rgba(15, 23, 42, 0.08);              /* modal */
  --shadow-5:  0 20px 25px -5px rgba(15, 23, 42, 0.12),
               0 8px 10px -6px rgba(15, 23, 42, 0.08);              /* hero CTAs, FABs */
  --shadow-focus: 0 0 0 3px rgba(11, 30, 138, 0.25);                /* outline focus */
}
```

**Hoy** las sombras están literalmente repartidas: `0 1px 3px rgba(0,0,0,0.06)` ([base.css:193](app/static/css/base.css#L193)), `0 8px 20px rgba(0,0,0,0.3)` ([flash.css:24](app/static/css/flash.css#L24)), `0 2px 4px rgba(0,0,0,0.2)` ([notifications.css:17](app/static/css/notifications.css#L17)). Sin sistema, cada componente eligió arbitrariamente.

### 2.6 Z-index (escala discreta)

```css
:root {
  --z-base:        0;
  --z-dropdown:    1000;
  --z-sticky:      1020;     /* footer */
  --z-fixed:       1030;     /* header */
  --z-fab:         1040;     /* notifications FAB */
  --z-backdrop:    1050;
  --z-offcanvas:   1055;
  --z-modal:       1060;
  --z-popover:     1070;
  --z-tooltip:     1080;
  --z-toast:       1090;     /* flash messages — antes 9999 */
  --z-max:         2147483647;
}
```

**Hoy** hay un caos: flash usa `9999`, alert dentro de flash usa `10000`, btn-close `100001`, sessionModal `9999`, modal-backdrop `1055 !important` ([flash.css:13](app/static/css/flash.css#L13), [base.css:507](app/static/css/base.css#L507), [session.css:11](app/static/css/session.css)). El bug típico — "el modal se ocultó tras el flash" — es consecuencia directa.

### 2.7 Movimiento

```css
:root {
  --duration-instant:  100ms;
  --duration-fast:     150ms;
  --duration-normal:   250ms;
  --duration-slow:     400ms;
  --duration-pulse:    2000ms;

  --ease-out:          cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out:       cubic-bezier(0.65, 0, 0.35, 1);
  --ease-spring:       cubic-bezier(0.34, 1.56, 0.64, 1);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

> **Crítico:** SIIAP **no** respeta `prefers-reduced-motion` en ningún archivo. Las animaciones `pulse-glow` ([program/view.css](app/static/css/program/view.css)), `invitation-pulse` ([events/list.css](app/static/css/events/list.css)) e `invitation-blink` deben envolverse en este media query. WCAG 2.3.3 (AAA) y muchos usuarios con vértigo lo agradecerán.

### 2.8 Layout (consolidando lo que ya existe)

```css
:root {
  --header-h:         80px;   /* ya existe */
  --header-h-md:      72px;
  --header-h-sm:      64px;
  --sidebar-w:        240px;  /* ya existe */
  --footer-h:         56px;   /* ya existe */
  --content-max-w:    1280px;
  --content-padding:  var(--space-6);
}
```

---

## 3. Hallazgos transversales (chrome / shell)

> Estos son problemas **sistémicos** que se ven en cada pantalla. Resolverlos da el mayor rendimiento por hora invertida.

### T-01 · Dos librerías de íconos coexisten — **P0 / S**

[base.html:17-19](app/templates/base.html#L17-L19) carga **Font Awesome 5.15.4** y **Bootstrap Icons 1.11.3**. La sidebar mezcla ambas en un mismo bloque ([_sidebar_nav.html:34](app/templates/_sidebar_nav.html#L34) usa `fas fa-user`, [línea 100](app/templates/_sidebar_nav.html#L100) usa `bi bi-file-earmark-check-fill`).

**Coste:** ~67 KB extra en cada pageload, dos sistemas mentales para devs, riesgo de inconsistencia visual (los pesos visuales de FA y BI no coinciden).

**Propuesta:**
- Migrar TODO a **Bootstrap Icons** (más moderno, mejor cobertura institucional/educativa, gratis, sin licencia FA Pro).
- Eliminar `<link>` de Font Awesome.
- Tabla de mapeo: `fas fa-user` → `bi bi-person`, `fas fa-th-large` → `bi bi-grid-fill`, `fas fa-cog` → `bi bi-gear`, `fas fa-envelope` → `bi bi-envelope`, `fas fa-spinner fa-spin` → `<div class="spinner-border spinner-border-sm">`.

### T-02 · `!important` proliferado — **P1 / M**

[menu_colors.css](app/static/css/menu_colors.css) tiene **22 declaraciones con `!important`** y [base.css](app/static/css/base.css) tiene **15 más**. Probablemente compensan especificidad de Bootstrap.

**Propuesta:** una vez que existan tokens, refactorizar mediante **selectores más específicos** (e.g. `.siiap-nav .nav-link.active` en lugar de `.nav-link.active !important`). Documentar excepciones (modal-backdrop sí lo necesita por z-index).

### T-03 · Header con 4 logos sin jerarquía — **P1 / M**

[base.html:60-87](app/templates/base.html#L60-L87) muestra SEP + TECNM + ITCJ + Posgrado en dos flancos. En `<768px` desaparecen `logo-sep` y `logo-posgrado` ([base.css:278-280](app/static/css/base.css#L278-L280)); en `<576px` desaparecen TODOS, dejando solo "SIIAP" centrado.

El problema: en desktop el logo SEP (federal) y Posgrado pesan visualmente lo mismo que ITCJ, diluyendo la marca propia.

**Propuesta visual:**

```
DESKTOP HOY                        DESKTOP PROPUESTO
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ [SEP][TECNM]  SIIAP  [ITCJ][P]│   │ [ITCJ]  SIIAP   [SEP·TECNM·P]│
│                          🔔   │   │                          🔔 │
└──────────────────────────────┘   └──────────────────────────────┘
                                    ↑ ITCJ a la izquierda, único
                                       protagonista; los demás como
                                       "asociados" más pequeños a la
                                       derecha, agrupados.
```

Implementación: ITCJ con `max-height: clamp(48px, 6vh, 72px)` en flanco izquierdo; SEP/TECNM/Posgrado con `clamp(28px, 3.5vh, 42px)` agrupados en un `<div class="logos-asociados">` derecho. La campana **migra** a la izquierda del avatar (donde el usuario espera notificaciones — Slack, Gmail, GitHub).

### T-04 · Brand-text "SIIAP" sin personalidad — **P1 / S**

[base.css:147-154](app/static/css/base.css#L147-L154) define `brand-text` con `font-weight: 700` y `text-shadow: 2px 2px 4px rgba(0,0,0,0.1)`. La sombra mata la elegancia institucional y compite con la limpieza de los logos.

**Propuesta:**
```css
.brand-text {
  font-family: var(--font-display);
  font-weight: var(--fw-bold);
  font-size: var(--fs-display);
  color: var(--color-brand-accent);
  letter-spacing: var(--tracking-display);
  text-shadow: none;             /* eliminar */
  /* Opcional: sutil gradiente vertical */
  background: linear-gradient(180deg, var(--color-brand-accent) 0%, var(--color-brand-accent-600) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
```

### T-05 · Footer aporta cero valor — **P2 / S**

[base.html:140-142](app/templates/base.html#L140-L142): 56px de pantalla solo dicen `© 2026 SIIAP. Todos los derechos reservados.` En móvil vertical (667px), eso es **8% del viewport**.

**Propuesta:** o bien (a) **eliminarlo en móvil** y dejarlo solo en desktop; (b) **ampliarlo** a 3 columnas con enlaces útiles (contacto, manual de usuario, repositorio TECNM) y firma institucional. Recomiendo (a) para quick-win.

```
FOOTER PROPUESTO (DESKTOP, 56-72px)
┌────────────────────────────────────────────────────────────────┐
│  ITCJ · TECNM      Soporte: posgrado@itcj.edu.mx · Manual PDF │
│  © 2026 SIIAP      Estado del sistema: ● Operativo            │
└────────────────────────────────────────────────────────────────┘
```

### T-06 · Sidebar — agrupación lógica débil — **P2 / M**

[_sidebar_nav.html:30-187](app/templates/_sidebar_nav.html#L30-L187) presenta 9 secciones planas (Perfil, Dashboard, Programas, Admisión, Eventos, Coordinación, Permanencia, Documentos, Configuración) sin jerarquía. Configuración tiene su `<hr>`, pero Coordinación y Permanencia podrían agruparse bajo "Gestión académica".

**Propuesta — estructura propuesta:**

```
PERSONAL
  · Perfil
  · Dashboard

ACADÉMICO (visible solo si tiene programa o coordina)
  · Programas
  · Admisión             [solo aspirante]
  · Permanencia          [coordinador]
  · Documentos           [revisor]

GESTIÓN (visible solo a coordinator)
  · Coordinación
  · Deliberación
  · Aceptación

EVENTOS
  · Eventos públicos
  · Gestión de eventos   [admin]

────────────────
CONFIGURACIÓN          [solo admin]
  · ...
```

Implementación: agregar pequeños `<h6 class="sidebar-section-label">PERSONAL</h6>` con `font-size: var(--fs-xs)`, `text-transform: uppercase`, `letter-spacing: var(--tracking-wide)`, color `var(--text-muted)`. Es un patrón usado por GitHub, Linear, Notion.

### T-07 · Notification FAB en color azul Bootstrap — **P0 / S**

[notifications.css:400](app/static/css/notifications.css) usa `background: #007bff` (azul Bootstrap), no `var(--bg--tecnm)` (`#0b1e8a`). Es el primer choque visual cuando el usuario abre el sistema en móvil.

**Fix de 1 línea:** sustituir `#007bff` por `var(--color-brand-primary)`.

### T-08 · Tres patrones de timeline no consolidados — **P1 / M**

Existen tres implementaciones de timeline:
1. `.timeline` antiguo en [_profile_info.html:60-67](app/templates/user/profile/_profile_info.html#L60-L67) (border-left manual).
2. `.timeline-modern` en [profile.css:472+](app/static/css/user/profile.css#L472) (gradient markers — el mejor diseño).
3. Generado por JS sin clase dedicada en [_profile_history.html:27-106](app/templates/user/profile/_profile_history.html#L27-L106).

**Propuesta:** consolidar en un componente único `.siiap-timeline` con variantes (`-vertical`, `-horizontal`, `-with-icons`). Documentar en un futuro `STYLEGUIDE.md`.

### T-09 · Modal "session timeout" vive fuera del sistema de modales — **P0 / S**

[base.html:257-266](app/templates/base.html#L257) define un `<div id="sessionModal" class="session-modal" style="display:none;">` con CSS propio en [session.css](app/static/css/session.css) y `z-index: 9999`. Bootstrap modal usa `1060`. Cuando se solapan, hay glitch.

**Propuesta:** refactorizar como Bootstrap modal estándar (`<div class="modal fade" id="sessionTimeoutModal">`) con header de color `--color-warning`. Reutiliza animaciones, accesibilidad y stack de z-index.

### T-10 · Asteriscos rojos inline `<span style="color:red">` — **P1 / S**

[register.html:22, 28, 32, 43, 47, 54, 58](app/templates/auth/register.html) inserta `<span style="color:red">*</span>` sin semántica. Screen readers leen "asterisco".

**Propuesta:** crear macro Jinja `{% from '_macros.html' import required_mark %}` que genere `<abbr title="Campo requerido" class="required-mark" aria-label="requerido">*</abbr>` con CSS asociado.

---

## 4. Hallazgos por dominio

### 4.1 Entrada (login, register, errores)

#### 4.1.1 Login — [auth/login.html](app/templates/auth/login.html)

**Hallazgo principal: identidad institucional invisible.**

| Síntoma | Ubicación | Impacto |
|---|---|---|
| Banner verde `#4a7c59` arbitrario, sin justificación en branding | [auth/common.css:170](app/static/css/auth/common.css) | Color "intruso" que no aparece en otra parte del sistema |
| Botón CTA usa `--bg--tecnm` (azul) pero sin firma visual | [login.html:26](app/templates/auth/login.html#L26) | Login se ve como cualquier SaaS genérico |
| Bootstrap **5.1.3** cargado en CDN | [auth_base.html:14](app/templates/auth_base.html) | Mismatch con base.html que usa 5.3.3 — riesgo de regresiones |
| Sin animación de entrada (no usa AOS aquí) | toda la pantalla | "Aparece" sin presencia |

**Mockup propuesto (desktop, ratio 1440×900):**

```
┌─────────────────────────────────────────────────────────────────┐
│  [Logos SEP·TECNM]            SIIAP            [ITCJ·Posgrado] │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌───────────────────────────┐   ┌──────────────────────────┐ │
│   │                           │   │                          │ │
│   │   Sistema Integral de     │   │  [🎓]                    │ │
│   │   Información Académica   │   │  Iniciar sesión          │ │
│   │   de Posgrado             │   │  ────────────────         │ │
│   │                           │   │                          │ │
│   │   ITCJ · TECNM            │   │  Usuario                 │ │
│   │                           │   │  ┌──────────────────────┐│ │
│   │   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  │   │  └──────────────────────┘│ │
│   │   (gradiente azul TECNM    │   │                          │ │
│   │    → rojo TECNM, sutil,   │   │  Contraseña              │ │
│   │    con SVG geométrico)    │   │  ┌──────────────────────┐│ │
│   │                           │   │  └──────────────────────┘│ │
│   │   "Ingresa para gestionar │   │                          │ │
│   │    tu trayectoria         │   │  ┌──────────────────────┐│ │
│   │    académica."            │   │  │  Entrar           →  ││ │
│   │                           │   │  └──────────────────────┘│ │
│   └───────────────────────────┘   │                          │ │
│                                   │  ¿No tienes cuenta?      │ │
│                                   │  Regístrate aquí →       │ │
│                                   └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

- **Hero izquierdo (60%)**: gradiente diagonal `linear-gradient(135deg, var(--color-brand-primary) 0%, var(--color-brand-accent) 120%)` con un SVG de patrón geométrico sutil (líneas sobrepuestas o un mapa de México estilizado). Texto blanco con tagline institucional.
- **Card derecha (40%)**: blanca, `--shadow-4`, `--radius-lg`, sin borde verde. Header con ícono `bi bi-mortarboard-fill` en `--color-brand-primary`.
- **Móvil**: el hero pasa arriba (160px de alto, solo gradiente + tagline corto), card debajo.

**Eliminar:** banner "Bienvenido al Sistema..." duplicado en [auth_base.html](app/templates/auth_base.html) que repite info ya implícita.

#### 4.1.2 Register — [auth/register.html](app/templates/auth/register.html)

**Problemas:**
- **Botón "Registrarme" verde** (`btn-success`) ([register.html:63](app/templates/auth/register.html#L63)) — incoherente con el botón azul de login. Sin patrón documentado.
- **6 filas de campos en 3 columnas** ([register.css:43](app/static/css/auth/register.css)) — denso pero el usuario no ve estructura. Sin agrupación tipo "Datos personales" / "Datos de cuenta".
- **Validación de contraseña** se hace inline con `setCustomValidity()` ([register.html:191](app/templates/auth/register.html#L191)) sin `aria-invalid`.

**Propuesta:**
1. **Mismo botón azul TECNM** para todos los CTAs principales (login, register, recuperar). El verde queda solo para confirmaciones secundarias.
2. **Wizard en 2 pasos**:
   - Paso 1: "Datos de cuenta" (email, usuario, contraseña, confirmar).
   - Paso 2: "Datos personales" (nombre, apellidos, control opcional).
3. Indicador visual de pasos en el header del card.
4. Reemplazar `<span style="color:red">*</span>` por macro semántico (cf. T-10).

```
WIZARD PASO 1                        WIZARD PASO 2
┌──────────────────────────────┐     ┌──────────────────────────────┐
│  ●━━━━━○      Cuenta · 1/2   │     │  ✓━━━━━●      Personal · 2/2 │
│                              │     │                              │
│  Email *                     │     │  Nombre *                    │
│  [____________________]      │     │  [____________________]      │
│                              │     │                              │
│  Nombre de usuario *         │     │  Apellido paterno *          │
│  [____________________]      │     │  [____________________]      │
│                              │     │                              │
│  Contraseña *                │     │  Apellido materno            │
│  [____________________] ⓘ    │     │  [____________________]      │
│  ──────────  fuerza: media   │     │                              │
│                              │     │                              │
│  Confirmar contraseña *      │     │                              │
│  [____________________]      │     │                              │
│  ✓ Las contraseñas coinciden │     │                              │
│                              │     │                              │
│         [ Continuar →  ]     │     │  [ ← Atrás ]   [ Registrar ] │
└──────────────────────────────┘     └──────────────────────────────┘
```

#### 4.1.3 Errores 404 / 500 — [404.html](app/templates/404.html), [500.html](app/templates/500.html)

**Problemas:**
- Idénticas: mismo CSS, solo cambia el número.
- 404 con animación `bounce` infinita — lúdica pero **inapropiada en error**. WCAG 2.3.3.
- Sin landmarks (`{% block navbar %}` se vacía), sin sugerencias.

**Propuesta:**
- Mantener layout simple, sin animación infinita.
- Agregar enlaces contextuales: "Ir al dashboard", "Buscar programa", "Reportar problema".
- 500: tono empático ("Estamos trabajando en ello") + ID de error (timestamp Unix) para soporte.
- En `<main role="main">` propio, sin esconder el header (el usuario debe poder navegar).

### 4.2 Dashboards por rol

#### 4.2.1 Patrón general — identidad de rol invisible

**Hallazgo:** [dashboard.html](app/templates/user/dashboard/dashboard.html) hace routing condicional por permiso pero **el usuario nunca ve "Eres aspirante / estudiante / coordinador"**. El bienvenido genérico ("Bienvenido, Juan — Panel de Control") no contextualiza.

**Propuesta — componente `RoleBanner`:**

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌───┐                                                           │
│  │ 🎓 │  Hola, Juan Pérez                                         │
│  └───┘  Aspirante · Maestría en Sistemas Computacionales         │
│                                                                  │
│         Próximo paso: Sube tu carta de exposición de motivos    │
│                       antes del 15 de mayo · Faltan 11 días     │
│                                                                  │
│  ────────────────────────────────────────────────────────────   │
│  PROGRESO     ▓▓▓▓▓▓▓▓░░░░░░  60%   8 de 13 documentos          │
└──────────────────────────────────────────────────────────────────┘
```

- Avatar grande con ícono semántico por rol (mortarboard aspirante, building admin, gear coordinator).
- Badge de rol explícito.
- "Próximo paso" calculado dinámicamente del estado.
- Barra de progreso sutil (no la barra multicolor que ya existe — eso va más abajo en la página).

#### 4.2.2 Applicant Dashboard — [applicant_dashboard.html](app/templates/user/dashboard/applicant_dashboard.html)

> **Lo que ya está bien** ✓ — rico, modular, con timeline, barra de progreso multicolor, secciones por estado. **No tocar lo que funciona**, solo refinar.

**Refinamientos sugeridos:**
- La barra multicolor ([líneas 143-156](app/templates/user/dashboard/applicant_dashboard.html#L143-L156)) depende solo de color. Agregar **patrón** (rayas diagonales en "rechazado") y **número** sobre cada segmento.
- Cards de "Acciones Rápidas" ([líneas 41-100](app/templates/user/dashboard/applicant_dashboard.html#L41-L100)): los iconos `icon-2xl` (2.5rem) son grandes pero todos del mismo peso visual. Usar **ilustraciones lineales** sutiles en lugar de íconos sólidos para no saturar.
- "Próximamente disponible" en cursiva ([línea 70-95](app/templates/user/dashboard/applicant_dashboard.html#L70-L95)) muy sutil — agregar un badge `<span class="badge bg-neutral-200 text-muted">Próximamente</span>` para que se entienda.

#### 4.2.3 Student Dashboard — [student_dashboard.html](app/templates/user/dashboard/student_dashboard.html)

**Problema crítico: cascada de spinners.**
[Líneas 277-294](app/templates/user/dashboard/student_dashboard.html), [259-261](app/templates/user/dashboard/student_dashboard.html), etc. — cada módulo carga independientemente con su propio spinner. Usuario ve 4-5 puntos "esperando" simultáneos.

**Propuesta:** un solo `<SkeletonDashboard>` global que muestre la silueta de todas las cards en gris claro mientras se completan. Cuando los datos llegan, fade-in.

```css
.skeleton {
  background: linear-gradient(90deg,
    var(--color-neutral-100) 25%,
    var(--color-neutral-200) 37%,
    var(--color-neutral-100) 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
  border-radius: var(--radius-md);
}
@keyframes skeleton-shimmer {
  0%   { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
@media (prefers-reduced-motion: reduce) {
  .skeleton { animation: none; opacity: 0.6; }
}
```

#### 4.2.4 Program Admin Dashboard — [program_admin_dashboard.html](app/templates/user/dashboard/program_admin_dashboard.html)

**Buen diseño base** (KPIs, selector de programa, actividad reciente). **Pero:**
- Selector de programa "Ver todos" causa que **todas las acciones se grisen** ([líneas 58-94](app/templates/user/dashboard/program_admin_dashboard.html#L58-L94)). El admin queda atrapado en estado degradado sin entender el contrato.
- Cards `quick-action-card-disabled` con `opacity: 0.6` pero `<a href>` aún clickeable (sin `aria-disabled`, sin `tabindex="-1"`).

**Propuesta:**
1. Cuando "Ver todos" está activo, mostrar un mensaje claro arriba de las acciones: `<div class="alert alert-info-soft">Selecciona un programa específico para activar las acciones rápidas.</div>`.
2. Las cards realmente deshabilitadas: `aria-disabled="true"`, `tabindex="-1"`, cursor `not-allowed`, ícono candado.

#### 4.2.5 Postgraduate Admin Dashboard — [postgraduate_admin_dashboard.html](app/templates/user/dashboard/postgraduate_admin_dashboard.html)

**Bien estructurado** (tabs Vista General / Programas / Recordatorios). **Pero:**
- Sin bienvenida contextual (solo aparece KPIs en frío).
- Tabla de programas ([línea 209](app/templates/user/dashboard/postgraduate_admin_dashboard.html#L209)) sin `<caption>`.
- Tab "Recordatorios" carga vía JS con spinner único — bien, pero sin estado vacío amistoso.

### 4.3 Flujos de coordinador

> **El núcleo operativo del sistema.** Los `program_admin` pasan acá horas. Cada microsegundo de fricción se multiplica.

#### 4.3.1 Patrones repetidos críticos en TODO el dominio

| ID | Hallazgo | Severidad |
|---|---|---|
| C-01 | **Skeleton loaders ausentes en todas las tablas dinámicas** ([dashboard.html:129](app/templates/coordinator/dashboard.html#L129), [acceptance.html:90](app/templates/coordinator/acceptance.html#L90), [deliberation.html:107](app/templates/coordinator/deliberation.html#L107), [permanence.html:103](app/templates/coordinator/permanence.html#L103)) — el coordinador ve tablas vacías 1-3s sin saber si está cargando o no hay datos | P0 |
| C-02 | **Spinners en botones inconsistentes**. Confirmar/Aprobar/Rechazar no muestran spinner durante POST. Usuarios cliquean múltiples veces. | P0 |
| C-03 | **Modales con `data-bs-backdrop="static"` sin feedback** ([acceptance.html:277](app/templates/coordinator/acceptance.html#L277), [dashboard.html:260](app/templates/coordinator/dashboard.html#L260)) — usuario "atrapado" sin entender por qué ESC no funciona | P1 |
| C-04 | **Filtros no persisten al cambiar pestaña** ([dashboard.html:30-77](app/templates/coordinator/dashboard.html#L30-L77)) — reconfigurar cada vez es fricción acumulativa | P1 |
| C-05 | **Stats cards con border-left arbitrario 4-8px** ([acceptance.css:15-21](app/static/css/coordinator/acceptance.css#L15-L21), [deliberation.css:13-27](app/static/css/coordinator/deliberation.css#L13-L27)), sin tokens, colores Bootstrap (no TECNM) | P1 |
| C-06 | **Badges en pestañas tamaño 0.7rem (10px)** — ilegibles en zoom 150% o pantallas pequeñas | P1 |
| C-07 | **Tablas de 6-7 columnas sin scroll hint en móvil** — usuarios no descubren columnas ocultas | P1 |
| C-08 | **Animación `.perm-blink`** ([dashboard.css:19-27](app/static/css/coordinator/dashboard.css#L19-L27)) con opacity 30%-100% sin easing — parpadeo brusco | P2 |
| C-09 | **Decisiones aprobar/rechazar SOLO con color** — color-blind unfriendly | P0 (a11y) |
| C-10 | **Diferimiento sin countdown** — aspirante diferido sin "vuelve en X días" visible | P2 |

#### 4.3.2 Acceptance — [coordinator/acceptance.html](app/templates/coordinator/acceptance.html)

**Hallazgos específicos:**
- 4 pestañas (Pendientes/Recibida/Completados/Diferidos) con badges `bg-warning text-dark` sobre blanco = contraste 3.7:1 — **falla WCAG AA**.
- Sección Deferred dividida en 2 tablas (`pendingRequestsSection` + `deferredTable`) cuyo orden depende de JS. Si JS falla, usuario ve la 2ª sin contexto.
- Botón "Confirmar" en `reviewReceiptModal` ([línea 320](app/templates/coordinator/acceptance.html#L320)) **no cambia color** según decisión (Aprobar/Rechazar). Posible decisión equivocada.

**Mockup propuesto — `reviewReceiptModal` con feedback claro:**

```
┌──────────────────────────────────────────────┐
│  Revisar comprobante de pago        × Cerrar │
├──────────────────────────────────────────────┤
│                                              │
│  Aspirante: Juan Pérez López                 │
│  Documento: comprobante-pago.pdf  [Abrir ↗] │
│                                              │
│  Decisión:                                   │
│  ┌──────────────────┐  ┌─────────────────┐  │
│  │ ●  ✓ Aprobar     │  │ ○  ✗ Rechazar   │  │
│  │    El pago es    │  │    Hay un       │  │
│  │    correcto      │  │    problema     │  │
│  └──────────────────┘  └─────────────────┘  │
│      (verde, sólido)      (gris, hover rojo)│
│                                              │
│  Notas (opcional):                           │
│  ┌────────────────────────────────────────┐ │
│  │                                        │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ⚠  Esta acción notificará al aspirante     │
│     por correo. No se puede deshacer.       │
│                                              │
├──────────────────────────────────────────────┤
│              [ Cancelar ]  [ ✓ Aprobar ]    │
│                            ↑ verde si Aprobar│
│                              rojo si Rechazar│
└──────────────────────────────────────────────┘
```

- Las dos decisiones son **cards seleccionables grandes**, no radio buttons pequeños. Cada uno con ícono + descripción corta.
- El botón final **cambia de color** según selección (`btn-success` o `btn-danger-soft`).
- Microcopy de consecuencia ("notificará al aspirante por correo. No se puede deshacer.") visible antes de confirmar.

#### 4.3.3 Deliberation — [coordinator/deliberation.html](app/templates/coordinator/deliberation.html)

**Hallazgos específicos:**
- 5 pestañas con badges (`bg-secondary`, `bg-warning`, `bg-info`, `bg-success`, `bg-danger`). El `bg-danger` (`#dc3545`) **NO** es el rojo TECNM (`#b21f2d`). Inconsistencia.
- Modal `decisionModal` ([líneas 251-271](app/templates/coordinator/deliberation.html#L251-L271)) revela campos según radio button. Sin radio seleccionado, los campos son invisibles — usuario no entiende.
- `.notes-cell` ([deliberation.css:124-134](app/static/css/coordinator/deliberation.css#L124-L134)) usa `overflow: visible` en hover sin transition + sin posicionamiento absolute. Layout salta.

**Propuesta:** convertir el modal de decisión en **stepper** (Decidir → Detallar → Confirmar) en lugar de campos condicionales sin pista.

#### 4.3.4 Permanence — [coordinator/permanence.html](app/templates/coordinator/permanence.html)

**Hallazgos específicos:**
- Tab "Inscripción" tiene **4 cards apiladas** (Pendientes, Reincorporación, Rezagados, Confirmados) ([líneas 119-228](app/templates/coordinator/permanence.html#L119-L228)) — sobrecarga visual.
- Tabla `studentsTable` con 7 columnas sin scroll hint en móvil. Columnas "Periodo Actual", "CONACyT" se pierden.
- Banner período activo en `alert-success` (verde Bootstrap `#198754`) — no es verde institucional.

**Propuesta:** las 4 cards de Inscripción se condensan en **1 card con tabs internos** o **acordeón con badges de contador** en cada cabecera. Reduce scroll en 75%.

```
PROPUESTA — Tab Inscripción condensada
┌──────────────────────────────────────────────────────────────┐
│  Inscripción del periodo  2026-1                             │
├──────────────────────────────────────────────────────────────┤
│  ┌─Pendientes (12)─┬─Reincorp.(3)─┬─Rezagados (5)─┬─Conf.(89)┐│
│  │                                                            │
│  │  [tabla del filtro activo]                                │
│  │                                                            │
│  └────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

#### 4.3.5 Coordinator Dashboard — [coordinator/dashboard.html](app/templates/coordinator/dashboard.html)

**Buen patrón** (3 tabs principales con badges de contador). **Pero:**
- Modal `studentDetailsModal` ([línea 204](app/templates/coordinator/dashboard.html#L204)) en `modal-xl` (1200px) sin `max-height: 90vh` — atrapa al usuario en móvil.
- Modal `permanenceDetailsModal` ([línea 260](app/templates/coordinator/dashboard.html#L260)) con `data-bs-backdrop="static"` sin razón clara.

**Propuesta:** introducir clase utilitaria `.modal-body-scroll` (que **ya existe** en [base.css:52-55](app/static/css/base.css#L52-L55) pero se usa muy poco) en TODOS los modales largos.

### 4.4 Páginas públicas y eventos

> **La cara externa al aspirante.** Aquí la estética importa más que en cualquier otro lado: es la primera impresión.

#### 4.4.1 Programs / List — [programs/list.html](app/templates/programs/list.html)

**Diagnóstico:**
- **Sin hero**. La página empieza con un h1 plano, lista de cards, fin. No cuenta historia.
- Badges por nivel usan Bootstrap colors (`rgba(13, 110, 253, 0.9)`), no TECNM.
- Imágenes sin `loading="lazy"`, sin `srcset`, sin WebP.

**Propuesta — hero institucional:**

```
┌──────────────────────────────────────────────────────────────────┐
│ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│ ▒  Forma parte del posgrado de excelencia               ▒│
│ ▒  del Tecnológico Nacional de México.                  ▒│
│ ▒                                                                │
│ ▒  8 programas · Reconocidos por el SNP                ▒│
│ ▒                                                                │
│ ▒  [Buscar programa o área de interés...    🔍]                 ▒│
│ ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│
│                                                                  │
│  Filtros:  [Maestría] [Doctorado] [Especialidad]  ·  Modalidad: ▼│
│                                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                          │
│  │ [foto]  │  │ [foto]  │  │ [foto]  │   (cards alineadas       │
│  │  Maestr.│  │  Doctor.│  │  Maestr.│    al sistema de tokens) │
│  │  ────   │  │  ────   │  │  ────   │                          │
│  │  ...    │  │  ...    │  │  ...    │                          │
│  └─────────┘  └─────────┘  └─────────┘                          │
└──────────────────────────────────────────────────────────────────┘
```

- Hero con gradiente diagonal `--color-brand-primary → --color-brand-accent`, overlay sutil `rgba(11, 30, 138, 0.92)` sobre imagen institucional (campus ITCJ).
- Tagline con jerarquía clara: el programa de **excelencia**, no "el sistema de gestión".
- Búsqueda y filtros visibles arriba (sin ocultar bajo "Filtros avanzados").
- Cards con badge de nivel en `--color-brand-primary` (no Bootstrap).

#### 4.4.2 Programs / View — [programs/view/_hero.html](app/templates/programs/view/_hero.html)

**Hallazgos:**
- Atributo HTML inválido: `max-heigh="400px"` (typo, debería ser `max-height` y como style/class).
- Imagen sin overlay — si la foto es oscura, el texto adyacente compite visualmente.

**Propuesta:** layout idéntico pero con **gradient overlay** sobre la imagen y bg-color institucional sutil en la columna de texto.

#### 4.4.3 Programs / View — Subsections

| Subsección | Hallazgo | Propuesta |
|---|---|---|
| `_program_info.html` | 4 cards idénticas (mismo color, mismo estilo) | Cada card con ícono + color de acento sutil distinto, manteniendo paleta TECNM |
| `_curriculum.html` | Acordeón limpio pero sin progreso visual | Agregar barra "X de Y semestres" arriba del acordeón |
| `_graduate_profile.html` | Lista plana | Convertir en grid 2-col con íconos de competencias |
| `_admission_steps.html` | **`<a class="document-link">` sin href** — link roto | **P0**: agregar `href` o convertir en `<button>` con handler |
| `_contact.html` | `<form>` sin `action` | **P0**: definir endpoint y handler |
| `_floating_buttons.html` | `top: 130px; left: 260px;` hardcoded | Usar `position: sticky` con `top: calc(var(--header-h) + var(--space-4))` |

#### 4.4.4 Events / List — [events/list.html](app/templates/events/list.html)

**Hallazgo crítico — paleta no institucional:**
[events/list.css](app/static/css/events/list.css) define el hero con:
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
```
Es el gradiente "purple haze" de plantillas Bootstrap genéricas. **No tiene nada que ver con TECNM**.

**Fix:**
```css
background: linear-gradient(135deg,
  var(--color-brand-primary) 0%,
  var(--color-brand-accent) 100%);
```

Adicional: la animación `invitation-pulse` debe envolverse en `@media (prefers-reduced-motion: no-preference)`.

#### 4.4.5 Events / View — [events/view.html](app/templates/events/view.html)

**Buen diseño** (hero full-image con overlay 78%, sidebar derecha, galería con lightbox). **Pero:**
- Galería `grid-template-columns: repeat(3, 1fr)` **fijo** — en móvil < 480px, items minúsculos.
- Imagen hero sin alt (es CSS background) — sin fallback si no carga.

**Fix galería:**
```css
.event-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
}
```

---

## 5. Auditoría de accesibilidad (WCAG 2.1 AA)

### 5.1 Contrastes — **fallas detectadas**

| Combinación | Ratio | Nivel | Ubicación | Fix |
|---|---|---|---|---|
| `bg-warning #ffc107` + `text-dark` sobre blanco | **3.7 : 1** | ✗ AA | Badges en pestañas de [acceptance.html:52](app/templates/coordinator/acceptance.html), [permanence.html:124](app/templates/coordinator/permanence.html) | Usar `--color-warning #b88600` (4.7:1) |
| Badges `font-size: 0.7rem` | (tamaño) | ✗ AA | [base.css:459](app/static/css/base.css#L459) | Subir a `--fs-xs (0.75rem)` mínimo |
| `text-muted #6c757d` sobre blanco | **4.6 : 1** | ✓ AA marginal | uso generalizado | OK pero subir a `var(--color-neutral-600)` para AAA |
| Bootstrap `bg-info #0dcaf0` sobre blanco | **2.0 : 1** | ✗✗ AA | Múltiples badges info | Usar `var(--color-brand-secondary #1a71cf)` (4.7:1) |
| `nav-link` color `#495057` sobre `#f8f9fa` | **9.2 : 1** | ✓ AAA | sidebar | OK |

### 5.2 Focus visible — **mixto**

Hay focus styles bien definidos en [base.css:451-455](app/static/css/base.css#L451-L455) y [menu_colors.css:150-154](app/static/css/menu_colors.css#L150-L154), pero NO se aplican en:
- `.notification-bell-btn` ([notifications.css](app/static/css/notifications.css)) — ✗
- `.notification-fab` — ✗
- Botones `.btn-close` en flash messages — débil
- Cards clickeables (toda la grilla de programs/list)

**Propuesta global:**
```css
*:focus-visible {
  outline: 2px solid var(--color-brand-primary);
  outline-offset: 2px;
  border-radius: var(--radius-xs);
  box-shadow: var(--shadow-focus);
}
```

### 5.3 ARIA — **lagunas críticas**

| Elemento | Falta | Impacto | Prioridad |
|---|---|---|---|
| `.flash-container` | `role="status"`, `aria-live="polite"` | Usuario con SR no escucha mensajes flash | P0 |
| `.notification-dropdown` | `aria-live="polite"` en `.notification-list` | No se anuncia llegada de notificaciones | P0 |
| `.notification-badge` | `aria-label="N notificaciones no leídas"` dinámico | El número solo es visual | P1 |
| `data-dropdown` toggle en sidebar | `aria-expanded`, `aria-controls`, `aria-haspopup="true"` | Navegación por teclado opaca | P1 |
| `.nav-link.disabled` (admission_dashboard tabs) | `aria-disabled="true"`, `tabindex="-1"` | Keyboard users pueden focusar pero presionar no hace nada | P1 |
| `<table>` (todas las tablas largas) | `<caption>` con descripción | Screen reader sin contexto | P2 |
| Decisiones aprobar/rechazar | Solo color → falla WCAG 1.4.1 | Color-blind users perdidos | P0 |
| Todos los `<button>` con solo ícono | `aria-label` | SR no anuncia acción | P1 |

### 5.4 Semántica HTML

- **404/500** sin `<main>` ni landmarks — los SR leen toda la página como una sola región.
- **Errores de form** en `register.html` no se asocian con `aria-describedby` al input correspondiente.
- **Asteriscos rojos inline** sin semántica (cf. T-10).

### 5.5 Movimiento — falta `prefers-reduced-motion`

- Animación `bounce` infinita en 404 — **inapropiado siempre** + WCAG 2.3.3.
- `.invitation-pulse` 2.5s infinite ([events/list.css](app/static/css/events/list.css)).
- `.pulse-glow` 2s infinite ([programs/view.css](app/static/css/program/view.css)).
- `.perm-blink` ([dashboard.css:19-27](app/static/css/coordinator/dashboard.css#L19-L27)).

**Wrapper global propuesto** (cf. §2.7).

---

## 6. Responsive y mobile-first

### 6.1 Breakpoints fragmentados

Hoy:
- `base.css`: `991.98px`, `767.98px`, `575.98px` ✓ (Bootstrap-aligned)
- `notifications.css`: `767px` ✗ (sin .98)
- `events/list.css`, `programs/view.css`: mixto

**Propuesta — variables de breakpoints** (Sass-like, ya hay soporte CSS):
```css
/* En _tokens.css */
:root {
  --bp-sm: 576px;
  --bp-md: 768px;
  --bp-lg: 992px;
  --bp-xl: 1200px;
}
/* Uso */
@media (min-width: 768px) { /* md+ */ }
@media (max-width: 767.98px) { /* <md */ }
```
Convención: **mobile-first** (`min-width`) cuando sea posible. `max-width` solo para overrides.

### 6.2 Tablas en móvil — **problema sistémico**

Todas las tablas largas (`coordinator/*`, `admin_review`, `program_admin`) usan `table-responsive` (scroll horizontal) **sin scroll hint**. Usuarios no saben que hay más columnas.

**Patrón propuesto: indicador de scroll + columna sticky.**

```css
.table-responsive {
  position: relative;
}
.table-responsive::after {
  content: "";
  position: absolute;
  top: 0; right: 0; bottom: 0;
  width: 24px;
  background: linear-gradient(to right, transparent, var(--bg-surface));
  pointer-events: none;
  opacity: 0;
  transition: opacity var(--duration-fast);
}
.table-responsive.has-scroll::after { opacity: 1; }
.table-responsive table thead th:first-child,
.table-responsive table tbody td:first-child {
  position: sticky;
  left: 0;
  background: var(--bg-surface);
  z-index: 1;
}
```
JS añade `.has-scroll` cuando `scrollWidth > clientWidth`.

### 6.3 Touch targets < 44×44px

WCAG 2.5.5 (AAA) recomienda mínimo 44×44 CSS px. Hoy fallan:
- `.btn-action` ([acceptance.css:78-80](app/static/css/coordinator/acceptance.css#L78-L80)) ~30×24
- Botones en `_archive_rows.html` con padding `.25rem .5rem`
- `btn-close` en flash y modales

**Fix sistémico:** clase `.btn` mínima `min-height: 2.5rem; min-width: 2.5rem;` en móvil.

### 6.4 Modales sin `max-height: 90vh`

Casi todos los modales del proyecto carecen de límite vertical. En móvil 667px, modales con formularios largos saturan el viewport.

**Aplicar globalmente:**
```css
@media (max-width: 767.98px) {
  .modal-dialog {
    margin: var(--space-2);
    max-height: calc(100vh - var(--space-4));
  }
  .modal-content { max-height: 100%; }
  .modal-body { overflow-y: auto; }
}
```

### 6.5 Offcanvas frágil

[base.css:379](app/static/css/base.css#L379) usa `max-height: calc(100vh - 220px)` calculado a mano. Si header cambia, todo se rompe.

**Refactor:**
```css
.offcanvas { display: flex; flex-direction: column; }
.offcanvas-header,
.mobile-user-section,
.offcanvas-footer { flex-shrink: 0; }
.offcanvas-body { flex: 1 1 0; min-height: 0; overflow-y: auto; }
```
Sin cálculos de altura — flex hace el trabajo.

---

## 7. Performance percibida

### 7.1 Skeleton loaders — el mayor quick-win

**El problema más universal del proyecto.** Las tablas, listas, dashboards cargan vía JS desde APIs. Mientras tanto: pantalla en blanco o un texto "Cargando...".

**Componente propuesto — `_skeleton.html`:**
```html
{% macro skeleton_table(rows=5, cols=4) %}
<div class="skeleton-table" aria-hidden="true">
  <div class="skeleton skeleton-thead"></div>
  {% for _ in range(rows) %}
    <div class="skeleton-row">
      {% for _ in range(cols) %}
        <span class="skeleton skeleton-cell"></span>
      {% endfor %}
    </div>
  {% endfor %}
</div>
{% endmacro %}
```

Aplicar en TODA tabla cargada por JS (admission_dashboard, coordinator/*, program_admin, etc.).

### 7.2 Spinners en botones — patrón consistente

**Propuesta — micro-componente:**
```html
<button class="btn btn-primary" data-loading-text="Procesando...">
  <span class="btn-label">Confirmar decisión</span>
  <span class="btn-spinner spinner-border spinner-border-sm d-none"></span>
</button>
```
JS helper:
```js
function setButtonLoading(btn, loading) {
  btn.disabled = loading;
  btn.querySelector('.btn-label').classList.toggle('d-none', loading);
  btn.querySelector('.btn-spinner').classList.toggle('d-none', !loading);
}
```
Aplicar en TODOS los botones que disparen `fetch()`. Hoy es ad-hoc.

### 7.3 Imágenes — optimización

**Hallazgos:**
- `programs/list.html` carga todas las imágenes inmediatamente (no `loading="lazy"`).
- Sin `srcset` ni `<picture>`.
- Sin WebP.

**Propuesta — Jinja macro `responsive_img`:**
```html
{% macro responsive_img(filename, alt, sizes='100vw', loading='lazy') %}
<picture>
  <source srcset="{{ url_for('static', filename='assets/images/' ~ filename ~ '.webp') }}" type="image/webp">
  <img src="{{ url_for('static', filename='assets/images/' ~ filename) }}"
       alt="{{ alt }}" loading="{{ loading }}" sizes="{{ sizes }}">
</picture>
{% endmacro %}
```

Hero images NO deben tener `loading="lazy"` (LCP).

### 7.4 AOS — uso disperso

[base.html:301](app/templates/base.html) — AOS está cargado pero **no se inicializa globalmente**. Cada página lo hace o no. Resultado: elementos con `data-aos="fade-up"` que **nunca se animan**.

**Propuesta:** o (a) inicializar globalmente en `base.js` con config razonable, o (b) **eliminar AOS** y usar `IntersectionObserver` + clases CSS (más liviano, ~100 líneas, sin dependencia).

```js
// app/static/js/utils/reveal.js
const io = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('revealed');
      io.unobserve(e.target);
    }
  });
}, { threshold: 0.1 });
document.querySelectorAll('[data-reveal]').forEach(el => io.observe(el));
```

```css
[data-reveal] {
  opacity: 0;
  transform: translateY(16px);
  transition: opacity var(--duration-slow) var(--ease-out),
              transform var(--duration-slow) var(--ease-out);
}
[data-reveal].revealed { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) {
  [data-reveal] { opacity: 1; transform: none; transition: none; }
}
```

### 7.5 Optimistic UI

En decisiones de coordinador (aprobar/rechazar), hoy: click → loader → ~800ms → tabla recargada. **Propuesta:** marcar la fila como "actualizando" inmediatamente (opacity 0.6 + spinner inline), y revertir solo si el POST falla. Sensación de instantáneo.

---

## 8. Componentes propuestos

> Estos son los **building blocks** que SIIAP debería tener documentados. Hoy se reinventan en cada feature. Crear `app/templates/_components.html` con macros reutilizables.

### 8.1 `<RoleBanner>` — header de bienvenida contextual

Cf. §4.2.1. Para todos los dashboards. Macro Jinja `{{ role_banner(user, role, next_action, progress) }}`.

### 8.2 `<StatusBadge>` — badge semántico

Reemplaza Bootstrap badges arbitrarios.

```html
{% macro status_badge(status, label=none) %}
<span class="status-badge status-badge--{{ status }}"
      role="status">
  <i class="bi bi-{{ STATUS_ICONS[status] }}" aria-hidden="true"></i>
  <span>{{ label or STATUS_LABELS[status] }}</span>
</span>
{% endmacro %}
```

CSS:
```css
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--fs-xs);
  font-weight: var(--fw-semibold);
  border-radius: var(--radius-pill);
  background: var(--bg-surface-sunken);
  color: var(--text-secondary);
  white-space: nowrap;
}
.status-badge--accepted    { background: var(--color-success-100); color: #0e6e3a; }
.status-badge--rejected    { background: var(--color-danger-100);  color: var(--color-brand-accent-600); }
.status-badge--in-progress { background: var(--color-info-100);    color: var(--color-brand-secondary); }
.status-badge--deferred    { background: var(--color-neutral-200); color: var(--color-neutral-700); }
.status-badge--enrolled    { background: var(--color-brand-primary-100); color: var(--color-brand-primary); }
```

**Importante:** cada badge tiene **ícono + texto** — nunca depende solo del color (cumple WCAG 1.4.1).

### 8.3 `<EmptyState>` — estados vacíos amistosos

```html
{% macro empty_state(icon, title, description, action_label=none, action_url=none) %}
<div class="empty-state">
  <div class="empty-state__icon"><i class="bi bi-{{ icon }}"></i></div>
  <h3 class="empty-state__title">{{ title }}</h3>
  <p class="empty-state__description">{{ description }}</p>
  {% if action_label %}
    <a href="{{ action_url }}" class="btn btn-primary">{{ action_label }}</a>
  {% endif %}
</div>
{% endmacro %}
```

Hoy: las tablas vacías muestran nada o un texto plano. Aplicar este patrón en `coordinator/*`, `events/list`, listas vacías de notificaciones, etc.

### 8.4 `<DataTable>` — tabla con scroll hint y empty state

Wrapper que combina:
- `table-responsive` con `.has-scroll` indicator (cf. §6.2)
- skeleton loader integrado
- empty state cuando data llega vacía
- columna sticky en móvil

### 8.5 `<ConfirmModal>` — modal de confirmación con consecuencia clara

Hoy cada feature define su propio modal. Estandarizar:

```html
{% macro confirm_modal(id, title, body, confirm_label='Confirmar',
                       confirm_variant='primary', consequence=none) %}
<div class="modal fade" id="{{ id }}" tabindex="-1" role="dialog">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">{{ title }}</h5>
        <button class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
      </div>
      <div class="modal-body">
        <p>{{ body }}</p>
        {% if consequence %}
          <div class="alert alert-warning-soft mt-3" role="note">
            <i class="bi bi-exclamation-triangle"></i>
            <strong>Consecuencia:</strong> {{ consequence }}
          </div>
        {% endif %}
      </div>
      <div class="modal-footer">
        <button class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
        <button class="btn btn-{{ confirm_variant }}" data-confirm-trigger>
          <span class="btn-label">{{ confirm_label }}</span>
          <span class="btn-spinner spinner-border spinner-border-sm d-none"></span>
        </button>
      </div>
    </div>
  </div>
</div>
{% endmacro %}
```

### 8.6 `<Skeleton>` — placeholders animados

Cf. §4.2.3. Variantes: `.skeleton-text`, `.skeleton-card`, `.skeleton-table`, `.skeleton-avatar`.

### 8.7 `<Stepper>` — wizard de pasos

Para register, modal de decisión de deliberación, flujo de admisión. Hoy se reimplementa en cada lugar.

```html
{% macro stepper(steps, current) %}
<ol class="stepper" aria-label="Progreso del proceso">
  {% for step in steps %}
    {% set state = 'completed' if loop.index < current else 'active' if loop.index == current else 'pending' %}
    <li class="stepper__step stepper__step--{{ state }}"
        aria-current="{{ 'step' if loop.index == current else '' }}">
      <span class="stepper__number">
        {% if state == 'completed' %}<i class="bi bi-check"></i>{% else %}{{ loop.index }}{% endif %}
      </span>
      <span class="stepper__label">{{ step.label }}</span>
    </li>
  {% endfor %}
</ol>
{% endmacro %}
```

---

## 9. Roadmap priorizado P0 / P1 / P2

> **Convenciones:**
> - **P0** = bloqueante o impacto inmediato en accesibilidad / marca / errores funcionales
> - **P1** = alto valor, ejecución 1–3 días por item
> - **P2** = mejoras de pulido, ejecución posterior
> - **Esfuerzo:** S = ≤4h · M = 4–16h · L = >16h

### Fase 0 — Fundamentos (sin cambio visual)

| ID | Tarea | Impacto | Esfuerzo | Notas |
|---|---|---|---|---|
| F0-1 | Crear `app/static/css/_tokens.css` con todos los tokens (§2) | P0 | M | Cargar en `base.html` y `auth_base.html` antes de `base.css` |
| F0-2 | Migrar TODA la sidebar de Font Awesome a Bootstrap Icons; eliminar `<link>` de FA | P0 | M | Tabla de mapeo en T-01 |
| F0-3 | Refactor `sessionModal` como Bootstrap modal estándar | P0 | S | Cf. T-09 |
| F0-4 | Reorganizar z-index en escala discreta (§2.6); eliminar `9999`, `100001` | P0 | S | Solo cambia variables CSS y declaraciones |
| F0-5 | Fix botón "Registrarme" verde → azul TECNM | P0 | S | 1 cambio en `register.html` |
| F0-6 | Fix FAB notificaciones `#007bff` → `var(--color-brand-primary)` | P0 | S | 1 línea en `notifications.css` |
| F0-7 | Bootstrap 5.1.3 → 5.3.3 en `auth_base.html` | P0 | S | Verificar que no rompe nada |
| F0-8 | Fix `<a class="document-link">` sin href en `_admission_steps.html` | P0 | S | Link roto crítico |
| F0-9 | Fix `<form>` sin action en `_contact.html` | P0 | S | Form roto |

### Fase 1 — Marca y accesibilidad

| ID | Tarea | Impacto | Esfuerzo | Notas |
|---|---|---|---|---|
| F1-1 | Cargar Inter (Google Fonts) y aplicar `--font-sans` global | P1 | S | Cambia toda la sensación tipográfica |
| F1-2 | Hero institucional para `auth/login.html` con gradiente azul→rojo TECNM (cf. §4.1.1 mockup) | P1 | M | Quick win brutal — primera impresión |
| F1-3 | Hero institucional para `programs/list.html` (cf. §4.4.1) | P1 | M | Cara externa: el aspirante |
| F1-4 | Cambiar `events/list.css` hero `#667eea→#764ba2` por gradiente TECNM | P1 | S | Coherencia cromática |
| F1-5 | Wrapper global `prefers-reduced-motion` | P1 | S | A11y crítico |
| F1-6 | `aria-live="polite"` en `.flash-container` y `.notification-list` | P1 | S | A11y crítico |
| F1-7 | Componente `<StatusBadge>` (§8.2) y migrar badges en `coordinator/*` | P1 | M | Consistencia + a11y |
| F1-8 | Componente `<Skeleton>` (§8.6) e integrar en TODAS las tablas dinámicas | P1 | M | Performance percibida |
| F1-9 | Patrón estándar de spinners en botones (§7.2) | P1 | M | Aplicar en coordinator/* y admin/* |
| F1-10 | Eliminar `!important` redundantes en `menu_colors.css` | P1 | M | Deuda técnica |
| F1-11 | Macro `required_mark` semántico (cf. T-10) | P1 | S | A11y register |
| F1-12 | Eliminar animación `bounce` infinita en 404 | P1 | S | A11y |
| F1-13 | Reemplazar Bootstrap `bg-warning #ffc107` por `--color-warning #b88600` (contraste AA) | P1 | S | A11y |

### Fase 2 — Experiencia

| ID | Tarea | Impacto | Esfuerzo | Notas |
|---|---|---|---|---|
| F2-1 | Componente `<RoleBanner>` (§4.2.1) en TODOS los dashboards | P2 | M | Identidad de rol |
| F2-2 | Reorganizar sidebar con secciones agrupadas (§T-06) | P2 | M | Densidad / UX |
| F2-3 | Refactor offcanvas frágil → flex layout (§6.5) | P2 | S | Robustez |
| F2-4 | Componente `<EmptyState>` (§8.3) en listas vacías | P2 | M | UX |
| F2-5 | Componente `<DataTable>` con scroll hint + sticky col (§6.2, §8.4) | P2 | L | Tablas reusables |
| F2-6 | Componente `<ConfirmModal>` (§8.5) y migrar modales `coordinator/*` | P2 | L | Consistencia |
| F2-7 | Wizard 2 pasos en register (§4.1.2) | P2 | M | UX register |
| F2-8 | Tab "Inscripción" condensada en `permanence.html` (§4.3.4) | P2 | M | Reduce scroll 75% |
| F2-9 | Galería de eventos responsive `auto-fit minmax(200px)` (§4.4.5) | P2 | S | Móvil |
| F2-10 | `responsive_img` macro con WebP + lazy (§7.3) | P2 | M | Performance |
| F2-11 | Eliminar AOS, sustituir por `IntersectionObserver` + CSS (§7.4) | P2 | M | Bundle size |
| F2-12 | Consolidar 3 patrones de timeline en `<Timeline>` (§T-08) | P2 | M | DRY |
| F2-13 | Footer de valor con enlaces útiles (§T-05) | P2 | S | Marca |
| F2-14 | Página 404/500 institucional con sugerencias contextuales | P2 | M | Marca |
| F2-15 | Decisión modal con cards seleccionables grandes (§4.3.2 mockup) | P2 | M | UX coordinador |
| F2-16 | Optimistic UI en aprobar/rechazar (§7.5) | P2 | M | Sensación |
| F2-17 | Stepper component (§8.7) | P2 | M | Reuso |

### Resumen de esfuerzo

| Fase | Items | Total estimado |
|---|---|---|
| Fase 0 (fundamentos) | 9 | ~16h |
| Fase 1 (marca + a11y) | 13 | ~28h |
| Fase 2 (experiencia) | 17 | ~50h |
| **Total** | **39** | **~94h** |

Con un dev medio dedicado al 50%, esto es ~3 semanas de trabajo.

---

## 10. Apéndice: anti-patrones detectados

> Documentación rápida para no repetir estos errores en código futuro.

### A1. Inline styles en HTML

```html
<!-- ❌ -->
<span style="color:red">*</span>
<div id="sessionModal" class="session-modal" style="display:none;">

<!-- ✓ -->
<span class="required-mark">*</span>
<div id="sessionModal" class="session-modal" hidden>
```

### A2. Atributos HTML inválidos

[programs/view/_hero.html](app/templates/programs/view/_hero.html) tiene `max-heigh="400px"` (typo). HTML válido: `style="max-height:400px"` o clase CSS.

### A3. Duplicación de librerías

Font Awesome **+** Bootstrap Icons cargados simultáneamente. Una sola librería.

### A4. `!important` por defecto

Si necesitas `!important` para que un estilo "agarre", probablemente la especificidad del selector está mal. Usa `.parent .child` antes que `!important`.

### A5. Hardcoded magic numbers

```css
/* ❌ */
max-height: calc(100vh - 220px);   /* ¿de dónde sale 220? */
top: 130px; left: 260px;           /* ¿layout asumido? */

/* ✓ */
max-height: calc(100vh - var(--header-h) - var(--footer-h) - var(--space-8));
top: calc(var(--header-h) + var(--space-4));
```

### A6. Color como único diferenciador

```html
<!-- ❌ -->
<span class="badge bg-success">Aprobado</span>
<span class="badge bg-danger">Rechazado</span>

<!-- ✓ -->
<span class="status-badge status-badge--accepted">
  <i class="bi bi-check-circle"></i> Aprobado
</span>
<span class="status-badge status-badge--rejected">
  <i class="bi bi-x-circle"></i> Rechazado
</span>
```

### A7. Modales con `data-bs-backdrop="static"` sin razón explícita

Solo justificado cuando hay operación irreversible en curso. No por defecto.

### A8. Animaciones infinitas sin `prefers-reduced-motion`

Cualquier `animation: ... infinite` debe envolverse en el media query.

### A9. CSS sin documentar de qué token sale

```css
/* ❌ — un mes después nadie sabe por qué 0.65rem */
padding: 0.65rem 1.25rem;

/* ✓ */
padding: var(--space-3) var(--space-5);
```

### A10. JS inline en templates

[_profile_history.html:27-106](app/templates/user/profile/_profile_history.html#L27-L106) y otros tienen `<script>` con lógica embebida. Migrar a archivos en `app/static/js/`.

---

## Apéndice B — referencias por archivo (resumen)

| Archivo | Hallazgos críticos |
|---|---|
| [app/static/css/base.css](app/static/css/base.css) | 15+ `!important`, sombras planas, sin tokens más allá de header/sidebar/footer |
| [app/static/css/menu_colors.css](app/static/css/menu_colors.css) | 22 `!important` |
| [app/static/css/notifications.css](app/static/css/notifications.css) | FAB `#007bff`, animación pulse sin reduced-motion |
| [app/static/css/flash.css](app/static/css/flash.css) | z-index `9999`, `10000`, `100001` |
| [app/static/css/session.css](app/static/css/session.css) | Modal custom fuera del sistema |
| [app/static/css/auth/common.css](app/static/css/auth/common.css) | Border verde `#4a7c59` arbitrario |
| [app/static/css/events/list.css](app/static/css/events/list.css) | Hero `#667eea→#764ba2` no institucional |
| [app/static/css/program/view.css](app/static/css/program/view.css) | Floating buttons hardcoded, 23 keyframes |
| [app/static/css/coordinator/acceptance.css](app/static/css/coordinator/acceptance.css) | Stats cards sin tokens, `.btn-action` <44px |
| [app/static/css/coordinator/deliberation.css](app/static/css/coordinator/deliberation.css) | `.notes-cell` overflow visible salta layout |
| [app/static/css/coordinator/dashboard.css](app/static/css/coordinator/dashboard.css) | `.perm-blink` parpadeo brusco |
| [app/templates/base.html](app/templates/base.html) | 4 logos sin jerarquía, FA + BI duplicados, sessionModal custom |
| [app/templates/auth/login.html](app/templates/auth/login.html) | Sin branding institucional, banner verde duplicado |
| [app/templates/auth/register.html](app/templates/auth/register.html) | Botón verde, asteriscos inline, sin agrupación |
| [app/templates/_sidebar_nav.html](app/templates/_sidebar_nav.html) | Mezcla FA + BI en un mismo bloque |
| [app/templates/coordinator/dashboard.html](app/templates/coordinator/dashboard.html) | Skeleton ausente, modal-xl sin max-height |
| [app/templates/coordinator/acceptance.html](app/templates/coordinator/acceptance.html) | Badges contraste 3.7:1, decisión solo por color |
| [app/templates/coordinator/deliberation.html](app/templates/coordinator/deliberation.html) | Modal con campos condicionales sin pista |
| [app/templates/coordinator/permanence.html](app/templates/coordinator/permanence.html) | 4 cards apiladas saturan, banner verde no institucional |
| [app/templates/programs/list.html](app/templates/programs/list.html) | Sin hero, badges Bootstrap, imágenes sin lazy |
| [app/templates/programs/view/_hero.html](app/templates/programs/view/_hero.html) | `max-heigh` typo, sin overlay |
| [app/templates/programs/view/_admission_steps.html](app/templates/programs/view/_admission_steps.html) | Links sin `href` (rotos) |
| [app/templates/programs/view/_contact.html](app/templates/programs/view/_contact.html) | `<form>` sin action |
| [app/templates/events/list.html](app/templates/events/list.html) | Hero púrpura no institucional, animación sin reduced-motion |
| [app/templates/404.html](app/templates/404.html) | Animación bounce infinita, sin landmarks |

---

## Cierre

Este documento es **un mapa, no un plan rígido**. Cada item está identificado, ubicado y priorizado, pero la ejecución exacta queda a criterio del equipo.

**Si tuviera que elegir tres cosas para hoy:**

1. **F0-1**: introducir `_tokens.css`. Es la condición de posibilidad de todo lo demás.
2. **F1-2**: hero institucional en login. Cambia la primera impresión del sistema completo en una tarde.
3. **F1-8**: skeleton loaders en tablas. Elimina la sensación más persistente de "esto se siente lento".

Con eso, el proyecto cambia de tono visual sin romper ningún flujo, sin migración compleja y sin discusión con stakeholders.

— *Documento generado tras auditoría exhaustiva de 70+ templates, 30+ CSS y 4 reportes especializados (entrada, coordinador, públicas, transversal).*

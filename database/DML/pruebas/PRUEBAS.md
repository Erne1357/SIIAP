# Guia de Pruebas — Datos de Prueba SIIAP

## Ejecucion

```bash
flask seed-test-data --confirm   # Inserta datos y copia PDFs
flask clean-test-data --confirm  # Limpia todo
```

**Password de todos los usuarios**: misma que el usuario `admin`.

---

## BLOQUE A: ASPIRANTES

### A1 — `test_a01_nuevo` (Laura Soto)
**Estado**: in_progress, sin documentos
**Probar**:
- Login → dashboard muestra alerta roja con TODOS los docs de admision pendientes
- Subir un documento → debe cambiar a "review" y aparecer en panel de coordinador
- No debe poder acceder a nada de permanencia ni aceptacion

### A2 — `test_a02_parcial` (Ana Garcia)
**Estado**: in_progress, 1 aprobado + 1 en revision + 1 rechazado + 5 pendientes
**Probar**:
- Dashboard muestra alerta con los 5 docs pendientes, 1 en revision y 1 rechazado
- Coordinador aprueba/rechaza el doc en revision
- Aspirante puede resubir el documento rechazado
- Subir los docs faltantes

### A3 — `test_a03_listo` (Carlos Martinez)
**Estado**: in_progress, TODOS los docs aprobados
**Probar**:
- Dashboard NO muestra alerta de docs pendientes (todo aprobado)
- Coordinador puede iniciar deliberacion → entrevista
- Flujo completo: entrevista → deliberacion → aceptar/rechazar

### A4 — `test_a04_rech_parcial` (Diana Hernandez)
**Estado**: rejected (parcial), 1 doc marcado como rechazado
**Probar**:
- Dashboard muestra que fue rechazada parcialmente
- El doc rechazado (3er archivo, Titulo) tiene `status=rejected` y comentario del coordinador
- La aspirante puede resubir el documento rechazado
- Al resubir, el doc vuelve a "review" y el coordinador puede re-evaluar

### A5 — `test_a05_rech_total` (Eduardo Flores)
**Estado**: rejected (total), programa MANI
**Probar**:
- Dashboard muestra rechazo total con motivo
- NO puede subir documentos ni hacer nada mas
- Verificar que la decision tiene `decision_notes` y `decision_by`

### A6 — `test_a06_prorroga` (Fernanda Lopez)
**Estado**: in_progress, prorroga ACTIVA (vence en 30 dias)
**Probar**:
- 6 aprobados + 1 en revision con prorroga activa (7mo archivo, `is_in_extension=true`) + 1 sin subir
- Dashboard muestra que tiene prorroga activa con fecha limite
- Puede subir el documento antes de que venza la prorroga
- Si sube el doc, la prorroga se completa

### A7 — `test_a07_prorr_venc` (Gabriel Perez)
**Estado**: in_progress, prorroga VENCIDA
**Probar**:
- 7 docs aprobados + 1 con prorroga vencida (6to archivo)
- El doc tiene `status=extended` y la prorroga `granted_until` ya paso
- Verificar que la tarea Celery `cleanup_expired_admission_files` detecta esto
- Dashboard debe mostrar deuda documental

### A8 — `test_a08_viejo` (Hugo Ramirez)
**Estado**: in_progress, periodo 20241 (hace mas de 2 anos), programa DCI
**Probar**:
- Aspirante lleva desde enero 2024 sin completar admision
- 3 docs en revision (subidos en enero 2024, nunca revisados), 5 sin subir
- Verificar que deberia expirar automaticamente por inactividad
- Tarea Celery de limpieza deberia detectar este caso

### A9 — `test_a09_acept_nopaga` (Irene Castillo)
**Estado**: accepted, tiene carta + tira pero NO sube boleta
**Probar**:
- Coordinador ya genero carta de aceptacion y tira de materias
- La boleta de inscripcion esta en `pending` (nunca la subio)
- NO se le puede asignar numero de control hasta que suba y aprueben la boleta
- Verificar alerta: "Pendiente: subir boleta de inscripcion"

### A10 — `test_a10_acept_listo` (Jorge Morales)
**Estado**: accepted, carta + tira + boleta aprobada
**Probar**:
- Los 3 documentos de aceptacion estan completos
- La boleta fue subida por el aspirante y aprobada por coordinador
- LISTO para asignar numero de control e inscribir
- Flujo: asignar control → cambiar status a `enrolled` → crear primer semestre

### A11 — `test_a11_diferido1` (Karen Navarro)
**Estado**: deferred, 1 diferimiento activo (de 20253 a 20261)
**Probar**:
- Fue aceptada pero solicito diferimiento
- La carta de aceptacion se conserva, tira y boleta vuelven a `pending`
- Cuando llegue el periodo 20261, debe poder retomar el proceso
- Puede solicitar 1 diferimiento mas (maximo 2)

### A12 — `test_a12_diferido2` (Luis Dominguez)
**Estado**: deferred, 2 diferimientos agotados, programa MANI
**Probar**:
- 1er diferimiento: 20251→20253 (usado, se reactivo)
- 2do diferimiento: 20253→20263 (activo)
- NO puede pedir mas diferimientos (maximo 2 agotados)
- Si no se inscribe en 20263, deberia expirar

### A13 — `test_a13_doc_vencido` (Monica Rios)
**Estado**: in_progress, periodo 20251, doc con vigencia vencida
**Probar**:
- Aplico en enero 2025, ya paso mas de 1 ano
- El Comprobante de Ingles tiene `validity_months=12` y fue aprobado hace +14 meses
- El doc deberia aparecer como vencido y requerir resubida
- Verificar logica de `archive.validity_months` + `submission.upload_date`

---

## BLOQUE B: ESTUDIANTES

### B1 — `M24110001` (Nicolas Torres)
**Estado**: enrolled, semestre 4, desde 20243, programa MII, **becario CONACyT**
**Probar**:
- 4 inscripciones semestrales (3 completed + 1 active)
- TODOS los docs de admision aprobados (8/8)
- TODOS los docs de permanencia aprobados en CADA semestre (14 x 4 = 56 submissions)
- Tiene `has_conacyt_scholarship = true` → requiere reportes CONACyT mensuales
- Dashboard NO muestra alertas (todo al dia)
- Puede ver historial de semestres con docs por periodo
- Caso ideal para probar "pasar de periodo" exitosamente

### B2 — `M24110002` (Olivia Salazar)
**Estado**: enrolled, semestre 3, DEBE docs de admision Y permanencia, **becaria CONACyT**
**Probar**:
- 3 inscripciones (2 completed + 1 active)
- Solo 3/8 docs admision aprobados, 5 pendientes
- Permanencia sem 1 y 2 completos (14/14 cada uno), sem 3 parcial (4/14)
- Tiene `has_conacyt_scholarship = true` → debe reportes CONACyT mensuales pendientes
- Dashboard muestra AMBAS alertas rojas (admision + permanencia sem 3)
- Lista los docs faltantes con sus nombres
- Deuda documental puede bloquear reinscripcion al "pasar de periodo"

### B3 — `M25110001` (Pablo Cruz)
**Estado**: enrolled, semestre 2, docs de PERMANENCIA pendientes
**Probar**:
- 2 inscripciones (1 completed + 1 active)
- Admision completa, permanencia sem 1 completo (14/14)
- Sem 2 (activo): SIN docs de permanencia → alerta roja total
- Dashboard muestra alerta: "Tienes 14 documentos de permanencia pendientes"
- Verificar que la tarea `notify_pending_permanence_docs` lo detecta
- Al "pasar de periodo" deberia BLOQUEARSE por falta total de docs sem actual

### B4 — `M25110002` (Raquel Vega)
**Estado**: enrolled, semestre 2, PENDIENTE DE PAGO
**Probar**:
- Semestre 1 completado (permanencia 14/14), semestre 2 `pending` con `enrollment_confirmed=false`
- No ha pagado la inscripcion del semestre actual
- Sem 2: 3/14 docs permanencia aprobados, 11 pendientes
- Dashboard debe indicar que falta confirmar inscripcion + alerta permanencia
- Coordinador confirma pago → `enrollment_confirmed=true`, status→`active`
- Al "pasar de periodo" deberia BLOQUEARSE por pago pendiente + docs faltantes

### B5 — `M25110003` (Samuel Luna)
**Estado**: enrolled, semestre 2 en BAJA TEMPORAL, programa MANI
**Probar**:
- Semestre 1 completado (permanencia 14/14), semestre 2 `on_leave`
- Baja autorizada por motivos de salud, puede reincorporarse en 20271
- Sem 2: 2/14 docs permanencia aprobados (subidos antes de la baja)
- Dashboard debe mostrar estado de baja temporal + alerta permanencia
- Tiene nota: "Baja temporal autorizada por motivos de salud"
- Al "pasar de periodo" deberia tratarse como caso especial (on_leave no avanza semestre)
- Al llegar 20271 puede solicitar reincorporacion

---

## Eventos de Entrevista

### Eventos historicos (status=completed)

| Evento | Programa | Periodo | Aspirantes |
|---|---|---|---|
| Entrevistas MII — Ago-Dic 2024 | MII | 20243 | B1 (done), B2 (done) |
| Entrevistas MII — Ago-Dic 2025 | MII | 20253 | B3 (done), B4 (done) |
| Entrevistas MANI — Ago-Dic 2025 | MANI | 20253 | B5 (done) |

### Eventos actuales (status=published)

| Evento | Programa | Periodo | Slots | Aspirantes |
|---|---|---|---|---|
| Entrevistas MII — Ago-Dic 2026 | MII | 20263 | 14 free + 4 booked | A4 (done), A9 (done), A10 (done), A11 (done) |
| Entrevistas MANI — Ago-Dic 2026 | MANI | 20263 | 6 free + 2 booked | A5 (done), A12 (done) |

### Aspirantes SIN entrevista (para probar elegibilidad)

| Usuario | Razon |
|---|---|
| A1 (test_a01_nuevo) | Sin documentos, no elegible |
| A2 (test_a02_parcial) | Docs incompletos, no elegible |
| **A3 (test_a03_listo)** | **ELEGIBLE — probar flujo completo de asignacion** |
| A6 (test_a06_prorroga) | Doc en revision + 1 sin subir, no elegible |
| A7 (test_a07_prorr_venc) | Prorroga vencida, no elegible |
| A8 (test_a08_viejo) | Periodo viejo, docs en revision |
| A13 (test_a13_doc_vencido) | Doc con vigencia vencida |

---

## Ventanas de Entrega (DocumentDeadline)

### Periodo 20261 (Ene-Jun 2026, cerrado) — Historial MII
- Programacion de Materias (cerrada)
- Boleta de Inscripcion (cerrada)
- 1er Reporte Semestral (cerrada)
- Boleta de Calificaciones (cerrada)

### Periodo 20263 (Ago-Dic 2026, ACTIVO) — MII
| Ventana | Apertura | Cierre | Estado |
|---|---|---|---|
| Programacion de Materias | 10/08/2026 | 10/09/2026 | Abierta |
| Boleta de Inscripcion | 10/08/2026 | 10/10/2026 | Abierta |
| 1er Reporte Semestral | 01/10/2026 | 15/11/2026 | Abierta |
| Boleta de Calificaciones | 15/11/2026 | 11/12/2026 | Abierta |
| Carta de Director de Tesis | 10/08/2026 | sin limite | Abierta |
| **CONACyT - Agosto** | 01/08 | 31/08 | Cerrada |
| **CONACyT - Septiembre** | 01/09 | 30/09 | Cerrada |
| **CONACyT - Octubre** | 01/10 | 31/10 | Abierta |
| **CONACyT - Noviembre** | 01/11 | 30/11 | Abierta |
| **CONACyT - Diciembre** | 01/12 | 11/12 | Abierta |

### Periodo 20263 (ACTIVO) — MANI
- Programacion de Materias, Boleta de Inscripcion, 1er Reporte Semestral

---

## Matriz de cobertura

| Funcionalidad | Usuarios que la cubren |
|---|---|
| Subida de documentos | A1, A2, A6, A9 |
| Revision/aprobacion | A2, A3 |
| Rechazo parcial (deliberacion) | A4 |
| Rechazo total | A5 |
| Prorrogas activas | A6 |
| Prorrogas vencidas | A7 |
| Expiracion por inactividad | A8 |
| Aceptacion + carta/tira | A9, A10 |
| Boleta de inscripcion | A9, A10 |
| Diferimientos (1x) | A11 |
| Diferimientos (2x agotados) | A12 |
| Vigencia de documentos | A13 |
| Estudiante al dia (admision+permanencia) | B1 |
| Deuda documental (admision) | B2 |
| Deuda documental (permanencia parcial) | B2, B4, B5 |
| Docs permanencia pendientes (todos) | B3 |
| Pago pendiente semestral | B4 |
| Baja temporal | B5 |
| Alertas dashboard (admision) | B2 |
| Alertas dashboard (permanencia) | B2, B3, B4, B5 |
| Tareas Celery (limpieza) | A7, A8, A13 |
| Tareas Celery (permanencia) | B3 |
| Tareas Celery (diferimientos) | A12 |
| Beca CONACyT (reportes mensuales) | B1, B2 |
| Ventanas de entrega (abiertas/cerradas) | B1, B2, B3, B4 |
| Ventanas CONACyT mensuales | B1, B2 |
| Submissions por semestre (historial) | B1, B2, B3, B4, B5 |
| Pasar de periodo (caso exitoso) | B1 |
| Pasar de periodo (bloqueado por docs) | B2, B3 |
| Pasar de periodo (bloqueado por pago) | B4 |
| Pasar de periodo (on_leave, no avanza) | B5 |
| Entrevista completada (done) | A4, A5, A9, A10, A11, A12, B1-B5 |
| Elegible sin entrevista asignada | A3 |
| No elegible para entrevista | A1, A2, A6, A7, A8, A13 |
| Evento con slots libres | MII 20263, MANI 20263 |
| Eventos historicos (completed) | MII 20243, MII 20253, MANI 20253 |

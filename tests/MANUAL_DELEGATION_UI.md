# Prueba manual — Flujo completo de delegación desde UI

> Parte de Fase 12 de `PLAN_PERMISOS_GRANULARES.md`. Los tests automatizados
> en `tests/test_phase12_integration.py` cubren el backend end-to-end; este
> checklist verifica la UI (HTML + JS) que no se puede validar con unittest.
>
> Ejecutar en entorno de desarrollo con `flask db upgrade && flask seed-permissions`
> ya aplicados.

---

## Requisitos previos

1. Contenedor `siiap-dev-real-web-1` corriendo.
2. Seed ejecutado: `docker exec siiap-dev-real-web-1 flask seed-permissions --confirm`.
3. Al menos un `postgraduate_admin` activo (ej: `admin@itcj.edu.mx`).
4. Al menos un `program_admin` que sea `Program.coordinator_id` de 1+ programa.
5. Navegador con herramientas de desarrollador para inspeccionar respuestas JSON.

---

## Flujo 1 — Coordinador crea usuario de servicio social y delega permisos

**Actor:** `program_admin` (coordinador de al menos un programa).

1. Iniciar sesión como coordinador.
2. Ir a `/admin/settings/users`.
3. Hacer clic en **"Nuevo Servicio Social"** (botón verde).
   - [ ] El modal abre con formulario: nombre, apellido, apellido materno, email, `expires_at` opcional.
   - [ ] Aparece banner informativo del scope auto-asignado (`"Los permisos se otorgarán para los programas que coordinas: <lista>"`).
   - [ ] La checklist de permisos se renderiza agrupada por recurso.
   - [ ] Los permisos del recurso `permissions` NO aparecen (bloqueo anti-escalación).
   - [ ] Los permisos de tipo `page` NO aparecen (no son delegables).
4. Llenar formulario con datos válidos.
5. Seleccionar 2-3 permisos (ej: `acceptance.api.list_applicants`,
   `acceptance.api.upload_doc`).
6. Hacer clic en **"Crear usuario"**.
   - [ ] Respuesta exitosa: flash `"Usuario de servicio social creado con N permisos delegados"`.
   - [ ] Modal cierra.
   - [ ] Lista de usuarios se refresca y el nuevo `social_service` aparece.

---

## Flujo 2 — Social service accede a endpoints gracias a delegación

**Actor:** `social_service` recién creado.

1. Iniciar sesión con el usuario de servicio social (debe cambiar contraseña
   en primer login).
2. Verificar en `/user/dashboard`:
   - [ ] Dashboard carga sin 500 y muestra solo elementos compatibles con
     su rol base.
3. Navegar a un endpoint que requiera un permiso delegado. Ej, si delegamos
   `acceptance.api.list_applicants` con scope al programa 3, visitar:
   `/coordinator/acceptance/3`.
   - [ ] La página renderiza (no redirect a login ni 403).
   - [ ] Solo se ven datos del programa delegado; programas NO delegados
     no aparecen en el selector.
4. Intentar acceder a un programa NO delegado: `/coordinator/acceptance/<otro_id>`.
   - [ ] Flask devuelve 403 con flash: `"No tienes permiso..."`.

---

## Flujo 3 — Revocar delegación

**Actor:** coordinador.

1. Volver a `/admin/settings/users`.
2. Abrir el detalle del `social_service` creado.
   - [ ] Aparece sección **"Permisos Delegados"** con la lista de UserPermission activos.
   - [ ] Cada fila muestra codename, scope de programa, expira (si hay),
     y botón **Revocar**.
3. Hacer clic en **Revocar** sobre uno de los permisos.
   - [ ] Aparece `siiapConfirm` con mensaje de confirmación.
   - [ ] Al aceptar, el permiso desaparece de la lista.
4. Cerrar sesión y reloguear como el `social_service`.
5. Intentar el endpoint revocado.
   - [ ] Ahora responde 403 / redirect por falta de permiso.

---

## Flujo 4 — Jefe de posgrado agrega override a rol

**Actor:** `postgraduate_admin`.

1. Iniciar sesión como jefe de posgrado.
2. Ir a `/admin/settings/permissions` (entrada en submenú **Configuración > Permisos de roles**).
   - [ ] La página carga y lista los 5 roles en la columna izquierda.
   - [ ] Al seleccionar un rol aparecen tabs **Permisos Base** y **Overrides**.
3. Seleccionar `program_admin`.
4. Hacer clic en **"Agregar permiso"**.
   - [ ] Abre modal con filtro por recurso y lista completa del catálogo.
   - [ ] Campo `reason` visible y opcional.
5. Seleccionar un permiso (ej: `archives.api.delete`, que solo tiene `postgraduate_admin` por defecto).
6. Escribir justificación y confirmar.
   - [ ] El override aparece en el tab **Overrides** del rol.
   - [ ] El panel lateral de **Auditoría** muestra la entrada con
     acción=`grant`, quién, cuándo y razón.
7. Reloguear como un `program_admin` y verificar que el permiso se refleja.
   - [ ] Endpoint/UI que requiere `archives.api.delete` ahora es accesible.

---

## Flujo 5 — Revertir override

**Actor:** `postgraduate_admin`.

1. Volver a `/admin/settings/permissions` → seleccionar `program_admin`.
2. En el tab **Overrides**, clicar **Revertir** en la fila del override creado.
   - [ ] `siiapConfirm` aparece.
   - [ ] Al aceptar, la fila sale del tab Overrides.
   - [ ] Auditoría registra entrada con acción=`revert` y `previous_state`
     poblado.
3. Reloguear como `program_admin`.
   - [ ] Endpoint/UI ya no es accesible (vuelve a 403).

---

## Flujo 6 — Scope de programa efectivo

**Actor:** `social_service` con delegación scoped a programa A.

1. El coordinador delega `permanence.api.list_students` con scope `program_id=A`.
2. Social hace `GET /api/v1/permanence/program/<A>/students` (vía DevTools o UI).
   - [ ] Respuesta 200 OK con lista de estudiantes del programa A.
3. Social hace `GET /api/v1/permanence/program/<B>/students` (otro programa).
   - [ ] Respuesta 403 FORBIDDEN.

---

## Flujo 7 — Expiración automática de delegación

**Actor:** coordinador crea delegación con `expires_at` en +5 minutos.

1. Delegar con `expires_at` = `now + 5 min` vía modal "Nuevo Servicio Social".
2. Social accede al endpoint inmediatamente → 200.
3. Esperar 6 minutos.
4. Social reintenta → 403.
   - [ ] La expiración se respeta sin intervención manual.

---

## Checklist final

- [ ] Todos los flujos pasan sin errores 500 en el servidor.
- [ ] Todas las acciones críticas aparecen en `user_history` del actor
  (delegación, revocación, override, revert).
- [ ] Notificaciones socket en tiempo real: jefe de posgrado recibe
  `role_permission:changed` al agregar/revertir overrides.
- [ ] Las traducciones / textos en español se muestran correctamente
  (no "FORBIDDEN" ni strings en inglés hacia el usuario final).

---

## Cómo correr los tests automatizados complementarios

```bash
docker exec siiap-dev-real-web-1 python -m unittest \
    tests.test_permissions \
    tests.test_permission_integration \
    tests.test_phase12_integration
```

Se esperan 74 OK, 0 failures, 0 errors.

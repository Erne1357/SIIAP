# Estructura del Proyecto para la Plataforma de Posgrado

Este documento describe una **estructura de proyecto** extensa que integra todas las modificaciones recientes a la base de datos y la lógica de flujo (admisión, permanencia y conclusión). Incluye la idea general, el modelo de datos, los componentes técnicos y la organización de carpetas recomendada.

---

## 1. Idea General del Proyecto

La plataforma está diseñada para la **División de Posgrados** (o similar), con el fin de automatizar:

1. **Admisión de Aspirantes**  
   - Control de roles y permisos (administrador de posgrado, administrador de programa, revisor de documentos, etc.).
   - Manejo de documentos y pasos para la inscripción.
   - Validación y notificación sobre el estado de cada documento.

2. **Permanencia de Alumnos**  
   - Seguimiento de su semestre o cuatrimestre actual.
   - Carga de documentos periódicos (reportes, constancias, avances de tesis, etc.).
   - Validación y retroalimentación por parte de administradores o revisores.

3. **Conclusión**  
   - Etapa final de graduación: subida de documentos finales (tesis, carta de terminación, etc.).
   - Cambio de estatus a “graduated” o “concluded” en la base de datos.
   - Registro en bitácora de las acciones relevantes.

Esta plataforma permitirá que la administración de posgrado y los estudiantes interactúen de manera ordenada, manteniendo un registro completo de cada paso y documento.

---

## 2. Modelo de Datos y Flujo de la Aplicación

### 2.1. Tablas Principales

1. **`role`**  
   - Define los distintos roles del sistema (por ejemplo, "postgraduate_admin", "program_admin", "document_reviewer", "applicant").
   - Tabla simple con `id`, `name`, `description`.

2. **`user`**  
   - Almacena datos personales de cada usuario (nombre, apellidos, correo, contraseña, etc.).
   - Tiene una FK a `role` (`role_id`) para asignar permisos y alcance.

3. **`program`**  
   - Representa cada programa de posgrado.
   - Posee un `coordinator_id` apuntando a la tabla `user` para determinar quién es el coordinador del programa.

4. **`phase`**  
   - Agrupa las etapas generales del proceso (por ejemplo, "admission", "permanence", "mobility", "conclusion").
   - Sirve para categorizar los `step`.

5. **`step`**  
   - Cada paso o requisito en el sistema (p. ej. "Subir CV", "Subir Anteproyecto").
   - Tiene una FK a `phase` (`phase_id`), indicando en qué fase se ubica ese paso.

6. **`program_step`** (puente para muchos a muchos)  
   - Relaciona `program` con `step`.
   - Permite que un mismo `step` (por ejemplo, "Subir CV") pueda aplicarse a varios programas, o cada programa tenga su lista distinta de pasos.

7. **`archive`**  
   - Plantillas de documentos (por ejemplo, "Solicitud de ingreso.pdf").
   - Campos típicos: `name`, `description`, `is_downloadable` y `file_path` (ruta al archivo base en el servidor).
   - Al relacionarlo con `submission`, cada usuario sube su versión de dicho documento.

8. **`submission`**  
   - Cada envío real que hace un usuario para un determinado step (o program_step).
   - Campos como `file_path` (ruta del documento subido por el usuario), `status`, `upload_date`, `review_date`, etc.
   - Contiene FKs para identificar el `user`, el `program` (u opcionalmente `program_step`), y el `archive` (la plantilla base).

9. **`user_program`**  
   - Manejo de permanencia: relaciona a un usuario con un programa en un estado "active", "graduated", "dropped", etc.
   - Incluye campos como `current_semester`, `enrollment_date`, etc.

10. **`log`**  
    - Bitácora de acciones realizadas (cambios de estatus, validaciones, etc.).
    - Típicamente: `user_id`, `action`, `description`, `created_at`.

### 2.2. Flujo de Trabajo

1. **Admisión**  
   - El usuario (rol = "applicant") se registra o inicia sesión.
   - Selecciona el programa y ve los pasos de la fase "admission". Cada paso se asocia a uno o varios `archive` (plantillas).
   - Sube los documentos correspondientes (creando entradas en `submission`).
   - Una vez validados los pasos, se crea o actualiza el registro en `user_program` (`status = 'active'`).

2. **Permanencia**  
   - El alumno activo ve la fase "permanence" (con sus `step`s).  
   - Sube documentos semestrales o de movilidad.  
   - El `user_program` se actualiza (`current_semester` = n), y el staff valida los documentos.

3. **Conclusión**  
   - Fase "conclusion" con sus propios pasos (por ejemplo, "Subir Tesis"), registrados en `submission`.  
   - Al cumplir los requisitos, `user_program.status` pasa a "graduated" y se registra en la bitácora (`log`).

4. **Roles y Visibilidad**  
   - `postgraduate_admin`: control total (ver todos los programas, usuarios y validaciones).  
   - `program_admin`: maneja un programa específico (validar documentos de su programa, editar requisitos, etc.).  
   - `social_service`: revisa archivos con un alcance más limitado.  
   - `applicant`: sube documentos y sigue su estado de admisión o permanencia.

---

## 3. Arquitectura y Tecnologías

1. **Backend**:  
   - **Python con Flask** (u otro framework similar) para manejar la lógica de negocio, rutas, control de sesiones y conexiones con la base de datos.
   - **ORM** (SQLAlchemy) o consultas directas a PostgreSQL.  
   - Separación de lógica en módulos (auth, admin, user, reviewer, etc.).

2. **Frontend**:  
   - HTML, CSS y JavaScript, empleando **Jinja2 Templates** en Flask.  
   - **TailwindCSS** puede usarse para la pantalla de login, y **Bootstrap** para el resto de la interfaz.  
   - Vistas específicas para roles: formularios de subida, dashboards de validación, etc.

3. **Base de Datos (PostgreSQL)**:  
   - Manejo de las tablas antes descritas, con integridad referencial (FOREIGN KEY, ON DELETE CASCADE, etc.).  
   - Scripts de creación en `create_tables.sql` o configuración automática vía el ORM.

4. **Despliegue**:  
   - **Docker**: contenedores para la aplicación Flask y el servicio PostgreSQL.  
   - **docker-compose**: orquesta contenedores, define puertos y volúmenes.  
   - Variables de entorno para la configuración (credenciales DB, SECRET_KEY de Flask, etc.).

---

## 4. Estructura de Carpetas Recomendadas

**Descripción**:
- **`app/models/`**: Clases o scripts Python definiendo tus tablas (ya sea con un ORM o la capa de acceso a datos).
- **`app/routes/`**: Lógica de controladores y endpoints Flask (auth, admin, user).
- **`app/templates/`**: Archivos HTML (con Jinja2) que componen la interfaz.  
- **`app/static/`**: Archivos estáticos (CSS, JS, imágenes).
- **`database/`**: Scripts de creación (DDL) y datos de prueba (DML).
- **`docker/`**: Todo lo referente al despliegue con contenedores.
- **`tests/`**: Pruebas unitarias o de integración.

---

## 5. Conclusiones y Beneficios

1. **Ciclo de Vida Completo**: El sistema engloba desde la admisión hasta la graduación del alumno.
2. **Roles y Permisos**: Diferentes vistas y permisos según el rol (admin general, admin de programa, revisor, alumno).
3. **Flexibilidad para Fases**: Con la tabla `phase` y la relación con `step`, se pueden definir y extender fases como “admission”, “permanence”, “mobility” o “conclusion”.
4. **Gestión de Plantillas**: `archive` guarda cada tipo de documento base; `submission` registra los documentos subidos por los usuarios.
5. **Permanencia y Avance**: `user_program` maneja el estado de un alumno en un programa (activo, graduado, etc.).
6. **Auditoría**: `log` permite registrar acciones clave para un historial transparente.

En conjunto, esta arquitectura y estructura satisfacen la necesidad de una plataforma robusta, escalable y centrada en la experiencia de uso tanto para los alumnos como para el personal administrativo. Además, la modularidad del diseño facilita la evolución del sistema a medida que se añadan nuevas fases o requerimientos.

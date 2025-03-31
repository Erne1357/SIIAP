# Proyecto de Seguimiento de Registros para Posgrados

## 1. Resumen
Este proyecto busca desarrollar una plataforma web para la División de Posgrado del Instituto Tecnológico de Cd. Juárez (ITCJ), con el objetivo de dar seguimiento al proceso de admisión y a las fases de registro de los aspirantes a distintos programas de posgrado. Se maneja una arquitectura basada en Flask (Python), con PostgreSQL como base de datos, y el uso de contenedores Docker para facilitar la implementación y despliegue.

## 2. Objetivos
- Permitir a usuarios internos y externos (alumnos del Tec y externos) registrarse para postularse a un programa de posgrado.
- Gestionar la carga y validación de documentos en distintas fases (por ejemplo, Información General, Documentación Específica, etc.).
- Diferenciar roles: Admin. de posgrado, Admin. de programa, Revisor de documentos y Usuario normal, cada uno con permisos específicos.
- Proveer un panel de administración para supervisar y validar los documentos de los solicitantes.

## 3. Alcance
- Manejo de múltiples programas de posgrado.
- Control de flujos por fases, posibilitando que cada fase requiera ciertos documentos.
- Interfaz simple para subir y validar documentos, con notificaciones de estatus.

## 4. Estructura Técnica
- **Backend**: Python con Flask. Configuración de rutas separadas por roles e integración con la base de datos (ORM o consultas directas).
- **Frontend**: 
  - Uso de TailwindCSS (para login) y Bootstrap (para el resto de la aplicación).
  - Estructura de templates organizada y modular.
- **Base de Datos**: PostgreSQL.
  - Tablas principales: `user`, `program`, `step`, `archive`, `submission`, `rol`, `program_step` (para relaciones de muchos a muchos).
- **Despliegue**: Docker y docker-compose para mantener la coherencia entre entornos de desarrollo y producción.

## 5. Roles Principales
1. **Postgraduate Admin**: Control total sobre el sistema (programas, usuarios, validaciones).
2. **Program Admin**: Gestión de su programa (aceptar/rechazar documentos, enviar notificaciones).
3. **Document Reviewer**: Revisa documentos y actualiza estatus de aprobación.
4. **Applicant (Usuario)**: Descarga/llena formularios, sube comprobantes y da seguimiento a su proceso.

## 6. Avances y Documentos
- **Diagramas**: Se cuenta con un diagrama E-R y un diagrama Relacional (`DB_ER_DIAGRAM.png`, `DB_RELATIONAL_DIAGRAM.png`) dentro de la carpeta `docs/`.
- **Casos de Uso**: Recopilados en `docs/USE_CASES.md` (o similar, si existiera).
- **Pruebas**: Se planea tener pruebas unitarias e integraciones en `tests/`.

## 7. Próximos Pasos
- Completar la configuración de Docker y orquestar la base de datos en conjunto con la aplicación Flask.
- Implementar las pantallas de subida y validación de documentos, con control de accesos según el rol.
- Realizar pruebas locales y desplegar en un servidor de pruebas del ITCJ.


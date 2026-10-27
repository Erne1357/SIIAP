# app/routes/api/admin/users_admin_api.py
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.models.user import User
from app.services import user_admin_service as admin_svc
from app.services.user_history_service import UserHistoryService
from app.services import program_scope_service as scope_service
from app.utils.permissions import guard_user_scope, permission_required
from app.utils.api_response import api_server_error
from app.routes._public_id import resolved_id
from app.utils.validators import (
    EMAIL_MAX_LENGTH,
    InputValidationError,
    validate_person_name,
    validate_short_text,
)
from app.utils.datetime_utils import now_local
import json
import re

api_admin_users = Blueprint("api_admin_users", __name__, url_prefix="/api/v1/admin/users")

def _sanitize(s: str | None) -> str | None:
    """Sanitiza strings eliminando espacios y retornando None si está vacío"""
    if s is None:
        return None
    s = s.strip()
    return s or None


def _validate_if_changed(raw, current, validator, **kwargs):
    """
    Run `validator` only when the submitted value differs from the stored one.

    Resubmitting the value already in the column is a no-op, so it is returned
    untouched. This keeps rows that predate app/utils/validators.py editable
    while still refusing to accept a new value that breaks the rules.
    """
    if isinstance(raw, str) and raw.strip() == (current or '').strip():
        return current
    return validator(raw, **kwargs)


def _validation_error_response(message: str):
    """Envelope estándar para un valor rechazado por app/utils/validators.py."""
    return jsonify({
        "data": None,
        "flash": [{"level": "danger", "message": message}],
        "error": {"code": "VALIDATION", "message": message},
        "meta": {}
    }), 400


@api_admin_users.get("")
@login_required
@permission_required('admin_users.api.list')
def list_users():
    """
    Lista usuarios con filtros opcionales.

    Alcance: el registro completo (`include_sensitive`: número de control,
    programa, historial, estado) sólo sale para usuarios dentro de los
    programas del llamador. El resto se proyecta al nivel reducido
    (nombre y correo) y, si el llamador ni siquiera tiene ese nivel, se omite.

    Los FILTROS respetan el mismo reparto que la proyección, porque un filtro
    sobre un campo prohibido lo convierte en oráculo (ver la nota sobre
    `_FULL_SEARCH_COLUMNS`):

      - `search` sobre número de control / username / apellido materno …:
        el conjunto completo sólo se evalúa contra las filas que el llamador
        puede ver completas; contra las demás se evalúa el conjunto reducido
        (nombre y correo, `CROSS_PROGRAM_SEARCHABLE_FIELDS`).
      - `role` y `active`: `role` y `is_active` no están en la lista blanca del
        nivel reducido, así que tampoco se evalúan sobre filas ajenas. Las filas
        de otros programas no se filtran por ellos —ni entran ni salen por su
        valor— y `meta.cross_program_filters_ignored` lo declara.
      - `program`: `program_id` SÍ está en la lista blanca, así que aplica a
        todas las filas.
      - Orden (`last_name`, `first_name`): ambos están en la lista blanca; no
        se ordena nunca por número de control, que publicaría su valor relativo.
    """
    # Parámetros de paginación
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    # Filtros
    role_filter = request.args.get('role', type=str)
    program_filter = request.args.get('program', type=int)
    active_filter = request.args.get('active', 'all', type=str)
    search = request.args.get('search', type=str)

    # Alcance del llamador: None = global (todo visible completo).
    scope = scope_service.accessible_program_ids(current_user)
    may_summarize = scope_service.may_view_cross_program_summary(current_user)

    pagination, ignored_cross_program = admin_svc.search_users(
        page=page,
        per_page=per_page,
        role_filter=role_filter,
        program_filter=program_filter,
        active_filter=active_filter,
        search=search,
        scope=scope,
        may_summarize=may_summarize,
        caller_id=current_user.id,
    )

    # Una sola consulta de alcance para toda la página.
    in_scope = scope_service.users_in_scope(
        current_user, [u.id for u in pagination.items]
    )
    may_summarize = scope_service.may_view_cross_program_summary(current_user)

    users_data = []
    restricted = 0
    for user in pagination.items:
        if user.id in in_scope:
            users_data.append(user.to_dict(include_sensitive=True))
        elif may_summarize:
            # Proyección sobre la lista blanca: caen foto, historial, número de
            # control, rol, estado y cualquier campo que se añada más adelante.
            #
            # `restricted` va DENTRO de la fila, no sólo en meta: la consola
            # pinta fila por fila y necesita saber, en cada una, si la ausencia
            # de `is_active` significa "cuenta desactivada" o "no tienes derecho
            # a saberlo". Sin la marca, el JS leía la ausencia como `false` y
            # etiquetaba de «Inactivo» a cuentas activas de otros programas.
            row = scope_service.to_cross_program_summary(user.to_dict())
            row['restricted'] = True
            users_data.append(row)
            restricted += 1
        else:
            restricted += 1

    return jsonify({
        "data": {
            "users": users_data,
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev
            }
        },
        "error": None,
        "meta": {
            "restricted_count": restricted,
            # Filtros que NO se aplicaron a las filas de otros programas porque
            # recaen sobre campos prohibidos entre programas. La consola puede
            # decirlo en voz alta en lugar de dejar creer que la lista está
            # filtrada por igual.
            "cross_program_filters_ignored": ignored_cross_program,
        }
    }), 200


@api_admin_users.get("/<uuid:user_uuid>")
@login_required
@permission_required('admin_users.api.list')
def get_user(user_uuid):
    """
    Obtiene información detallada de un usuario específico.

    Fuera del alcance del llamador se devuelve el nivel reducido: nombre y
    correo, sin historial (prohibido entre programas), sin número de control y
    sin foto.
    """
    # Identificador desconocido o malformado: mismo 404 que un usuario
    # inexistente — el UUID nunca se distingue de la ausencia de la fila.
    user = User.by_uuid(user_uuid)
    if not user:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": "Usuario no existe"},
            "meta": {}
        }), 404
    user_id = user.id

    # Obtener programa
    user_program = admin_svc.get_user_program(user_id)

    if not scope_service.user_in_scope(current_user, user):
        if not scope_service.may_view_cross_program_summary(current_user):
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": "No tienes acceso a este usuario."}],
                "error": {"code": "FORBIDDEN", "message": "Usuario fuera de tu alcance"},
                "meta": {}
            }), 403

        # La marca viaja también dentro de `user` para que el modal de detalle
        # aplique la misma prueba que la tabla y no invente valores por omisión.
        restricted_user = scope_service.to_cross_program_summary(user.to_dict())
        restricted_user['restricted'] = True

        return jsonify({
            "data": {
                "user": restricted_user,
                "program": None,
                "history": []
            },
            "error": None,
            "meta": {"restricted": True}
        }), 200

    # Obtener historial
    history_entries = UserHistoryService.get_user_history(user_id=user_id, limit=50)

    return jsonify({
        "data": {
            "user": user.to_dict(include_sensitive=True),
            "program": {
                "id": user_program.program.id,
                "name": user_program.program.name,
                "slug": user_program.program.slug
            } if user_program else None,
            "history": [entry.to_dict() for entry in history_entries]
        },
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.patch("/<uuid:user_uuid>")
@login_required
@permission_required('admin_users.api.update')
# allow_self=True (por omisión) a propósito, pero sólo para el NOMBRE: editarse
# el propio nombre ya es autoservicio en `PATCH /api/v1/users/me`, así que
# negarlo aquí sólo sería incoherente. El correo es otra cosa y lo rechaza el
# cuerpo de la vista con un mensaje específico — ver ahí el porqué.
def update_user(user_uuid):
    """Actualiza información básica del usuario"""
    # El decorador `@program_scope_required(user_id_kwarg=...)` leía el id del
    # URL; con UUID el destino se resuelve aquí y la MISMA regla se aplica con
    # la guarda imperativa. `guard_user_scope(None)` falla cerrado, así que un
    # identificador desconocido y uno fuera de alcance devuelven exactamente el
    # mismo 403: no hay oráculo de existencia en la puerta nueva.
    user = User.by_uuid(user_uuid)
    denied = guard_user_scope(resolved_id(user))
    if denied:
        return denied
    user_id = user.id
    
    payload = request.get_json(silent=True) or {}

    # Same rules as self-registration and PATCH /users/me (app/utils/validators.py):
    # an admin edit is another write path into columns the staff consoles render,
    # so the value is either clean or the request is rejected.
    #
    # Validation gates NEW values only. The edit modal always PATCHes all four
    # fields, prefilled from the stored record, so validating unconditionally
    # would make any legacy row whose name predates these rules ("Ramirez, Juan",
    # "Jose Luis (Pepe)") permanently unsavable: even an edit that only touches
    # the e-mail would be rejected on a field the admin never typed in. Rows
    # already in the database are cleaned by a data migration, not by locking
    # their owner out of the console.
    try:
        if 'first_name' in payload:
            first_name = _validate_if_changed(
                payload['first_name'], user.first_name,
                validate_person_name, label="Nombre",
            )
        if 'last_name' in payload:
            last_name = _validate_if_changed(
                payload['last_name'], user.last_name,
                validate_person_name, label="Apellido paterno",
            )
        if 'mother_last_name' in payload:
            mother_last_name = _validate_if_changed(
                payload['mother_last_name'], user.mother_last_name,
                validate_person_name, label="Apellido materno", required=False,
            )
        if 'email' in payload:
            email = _validate_if_changed(
                payload['email'], user.email,
                validate_short_text,
                label="Correo electrónico",
                required=True,
                max_length=EMAIL_MAX_LENGTH,
            )
    except InputValidationError as e:
        return _validation_error_response(e.message)

    values = {}
    if 'first_name' in payload:
        values['first_name'] = first_name
    if 'last_name' in payload:
        values['last_name'] = last_name
    if 'mother_last_name' in payload:
        values['mother_last_name'] = mother_last_name
    if 'email' in payload:
        values['email'] = email

    try:
        changed_fields = admin_svc.update_basic_info(
            user, values, caller_id=current_user.id)
    except admin_svc.OwnEmailChangeForbidden as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": e.message}],
            "error": {"code": "FORBIDDEN", "message": "Cambio de correo propio no permitido"},
            "meta": {}
        }), 403
    except admin_svc.EmailAlreadyInUse as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": e.message}],
            "error": {"code": "VALIDATION", "message": "Email duplicado"},
            "meta": {}
        }), 400

    if changed_fields:
        try:
            from app.sockets.emitters import emit_admin_user_change
            role_name = user.role.name if user.role else None
            payload_ws = {
                'action': 'updated',
                # Public handle: the browser matches this against the `id` the
                # listing payloads publish, which is also the UUID.
                'user_id': str(user.uuid) if user.uuid else None,
                'role': role_name,
                'email': user.email,
                'full_name': f'{user.first_name} {user.last_name}',
                'changed_fields': list(changed_fields.keys()),
            }
            # Una cuenta de personal no es alumno de nadie: sus programas no
            # forman audiencia, sólo el alcance global la ve.
            audience_pids = (
                scope_service.program_ids_of_user(user.id)
                if role_name in ('applicant', 'student')
                else None
            )
            emit_admin_user_change(payload_ws, audience_pids)
        except Exception:
            pass

    return jsonify({
        "data": {"user": user.to_dict(include_sensitive=True)},
        "flash": [{"level": "success", "message": "Usuario actualizado exitosamente."}],
        "error": None,
        "meta": {"changed_fields": list(changed_fields.keys())}
    }), 200

# ESTA ES LA CONTINUACIÓN - PEGAR DESPUÉS DE LA PARTE 1

@api_admin_users.post("/<uuid:user_uuid>/reset-password")
@login_required
@permission_required('admin_users.api.reset_password')
# allow_self=True a propósito: la acción sobre uno mismo la rechaza el cuerpo de
# la vista con un mensaje específico, no con el 403 genérico de alcance.
def reset_password(user_uuid):
    """
    Invalida la contraseña del usuario y le envía por correo un enlace de un
    solo uso para que defina una nueva.

    El administrador nunca ve ni dicta una contraseña: no existe contraseña
    por defecto en el sistema.
    """
    from app.services import password_reset_service as prs

    # Misma regla de alcance que antes, ahora imperativa (ver `update_user`).
    user = User.by_uuid(user_uuid)
    denied = guard_user_scope(resolved_id(user))
    if denied:
        return denied
    user_id = user.id

    # No permitir resetear la propia contraseña
    if user_id == current_user.id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No puedes resetear tu propia contraseña."}],
            "error": {"code": "FORBIDDEN", "message": "Acción no permitida"},
            "meta": {}
        }), 403

    try:
        result = admin_svc.issue_admin_password_reset(
            user_id=user_id, admin_id=current_user.id)
    except prs.TokenNotFound as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Usuario no encontrado."}],
            "error": {"code": "NOT_FOUND", "message": str(e)},
            "meta": {}
        }), 404
    except prs.MissingEmail as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "BUSINESS_ERROR", "message": str(e)},
            "meta": {}
        }), 400

    user = result['user']
    return jsonify({
        "data": {"expires_at": result['expires_at'].isoformat() if result['expires_at'] else None},
        "flash": [{
            "level": "success",
            "message": (
                f"Se envió a {user.email} un enlace para que "
                f"{user.first_name} {user.last_name} defina una contraseña nueva. "
                f"El enlace vence en {result['ttl_minutes']} minutos y la contraseña "
                f"anterior quedó invalidada."
            )
        }],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.patch("/<uuid:user_uuid>/toggle-active")
@login_required
@permission_required('admin_users.api.update')
def toggle_active(user_uuid):
    """Activa o desactiva un usuario"""
    # No hay rama 404 aquí a propósito: `guard_user_scope(None)` ya falla
    # cerrado, así que un identificador desconocido sale con el MISMO 403 que
    # uno fuera de alcance y nunca llega hasta aquí. Añadir un 404 después de
    # la guarda volvería a distinguir "no existe" de "no es tuyo".
    user = User.by_uuid(user_uuid)
    denied = guard_user_scope(resolved_id(user))
    if denied:
        return denied
    user_id = user.id

    # No permitir desactivarse a sí mismo
    if user_id == current_user.id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No puedes desactivarte a ti mismo."}],
            "error": {"code": "FORBIDDEN", "message": "Acción no permitida"},
            "meta": {}
        }), 403
    
    # Toggle estado
    is_active = admin_svc.toggle_user_active(user)
    message = f"Usuario {user.first_name} {user.last_name} {'activado' if is_active else 'desactivado'}."

    # Deactivation has to reach the open sockets too. load_user() already turns
    # the next HTTP request anonymous, but a Socket.IO connection is authorised
    # once at the handshake and then keeps its rooms for the lifetime of the
    # sid, so without this the tab keeps receiving live payloads. Runs after the
    # commit so a failed write never evicts anybody.
    if not is_active:
        from app.sockets.emitters import disconnect_user_sockets
        disconnect_user_sockets(user_id)

    return jsonify({
        "data": {"is_active": is_active},
        "flash": [{"level": "success", "message": message}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.post("/<uuid:user_uuid>/assign-control-number")
@login_required
@permission_required('admin_users.api.assign_control_number')
def assign_control_number(user_uuid):
    """Asigna un número de control al usuario"""
    # allow_self=False como antes: nadie se asigna su propio número de control.
    user = User.by_uuid(user_uuid)
    denied = guard_user_scope(resolved_id(user), allow_self=False)
    if denied:
        return denied
    user_id = user.id
    
    # Solo aspirantes pueden recibir un número de control desde este endpoint.
    # (Para correcciones de estudiantes ya transicionados, usar el flujo del coordinador.)
    current_role = getattr(getattr(user, 'role', None), 'name', None)
    if current_role != 'applicant':
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": f"Solo se puede asignar número de control a aspirantes. Rol actual: {current_role or 'desconocido'}."}],
            "error": {"code": "INVALID_ROLE", "message": "Rol no elegible para asignación de número de control"},
            "meta": {}
        }), 400

    payload = request.get_json(silent=True) or {}
    control_number = _sanitize(payload.get('control_number'))

    if not control_number:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Número de control es requerido."}],
            "error": {"code": "VALIDATION", "message": "Campo requerido"},
            "meta": {}
        }), 400
    
    # Validar formato: M o D seguido de 8 dígitos
    if not re.match(r'^[MD]\d{8}$', control_number):
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Formato inválido. Debe ser M o D seguido de 8 dígitos."}],
            "error": {"code": "VALIDATION", "message": "Formato inválido"},
            "meta": {}
        }), 400
    
    # Unicidad institucional. La consulta sigue siendo global —así debe ser: el
    # número de control es único en toda la institución— pero la RESPUESTA ya no
    # dice por qué se rechazó. Antes contestaba "ya está asignado", y como el
    # guard de alcance sólo mira al usuario destino (un aspirante propio), quien
    # llama podía preguntar por cualquier número del padrón y leer la respuesta:
    # un oráculo de existencia sobre el mismo dato que el buscador de alumnos ya
    # protege (CROSS_PROGRAM_SEARCHABLE_FIELDS). El texto vive en el servicio
    # para que los tres puntos de rechazo digan exactamente lo mismo.
    #
    # La colisión sí queda registrada en el log de la aplicación (ops-only, sin
    # PII persistida y sin filas que el llamador pueda provocar en la base):
    # el sondeo requiere una petición autenticada por intento, así que lo que
    # protege de verdad es la detección del volumen, no un mensaje más.
    if admin_svc.control_number_exists(control_number):
        from flask import current_app
        from app.services.acceptance_service import CONTROL_NUMBER_REJECTED_MESSAGE
        current_app.logger.warning(
            '[control_number] Colisión al asignar número de control '
            f'(admin_id={current_user.id}, target_user_id={user_id}, '
            f'control_number={control_number})'
        )
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": CONTROL_NUMBER_REJECTED_MESSAGE}],
            "error": {"code": "VALIDATION", "message": CONTROL_NUMBER_REJECTED_MESSAGE},
            "meta": {}
        }), 400

    # Verificar que tenga programa
    user_program = admin_svc.get_user_program(user_id)
    if not user_program:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El usuario debe tener un programa asignado primero."}],
            "error": {"code": "VALIDATION", "message": "Sin programa asignado"},
            "meta": {}
        }), 400

    # Validar tipo de programa
    program_type = control_number[0]
    program_name = user_program.program.name.lower()

    if program_type == 'M' and 'maestr' not in program_name:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El número debe comenzar con 'M' para maestrías."}],
            "error": {"code": "VALIDATION", "message": "Tipo no coincide"},
            "meta": {}
        }), 400
    elif program_type == 'D' and 'doctor' not in program_name:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "El número debe comenzar con 'D' para doctorados."}],
            "error": {"code": "VALIDATION", "message": "Tipo no coincide"},
            "meta": {}
        }), 400

    # Ejecutar transición completa a estudiante (sin chequeos rigurosos del flujo
    # de aceptación — variante administrativa para casos legacy).
    try:
        up = admin_svc.assign_control_number_as_admin(
            user_id=user_id,
            program_id=user_program.program_id,
            control_number=control_number,
            admin_id=current_user.id,
        )
    except ValueError as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "VALIDATION", "message": str(e)},
            "meta": {}
        }), 400
    except Exception as e:
        return api_server_error(e, context='assign_control_number')

    return jsonify({
        "data": {
            "control_number": user.control_number,
            "username": user.username,
            "role": getattr(user.role, 'name', None),
            "admission_status": up.admission_status,
            "current_semester": up.current_semester,
        },
        "flash": [{"level": "success", "message": f"Número de control {control_number} asignado y transición a estudiante completada."}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.delete("/<uuid:user_uuid>")
@login_required
@permission_required('admin_users.api.delete')
def delete_user(user_uuid):
    """Elimina un usuario (solo admin general)"""
    user = User.by_uuid(user_uuid)
    denied = guard_user_scope(resolved_id(user))
    if denied:
        return denied
    user_id = user.id
    # El identificador público se guarda antes del DELETE: la fila deja de
    # existir y el payload de Socket.IO todavía tiene que nombrarla.
    user_uuid_public = str(user.uuid) if user.uuid else None

    # No permitir eliminarse a sí mismo
    if user_id == current_user.id:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "No puedes eliminarte a ti mismo."}],
            "error": {"code": "FORBIDDEN", "message": "Acción no permitida"},
            "meta": {}
        }), 403
    
    payload = request.get_json(silent=True) or {}
    force = payload.get('force', False)
    
    # Verificar datos relacionados
    has_submissions = len(user.submissions) > 0
    
    if has_submissions and not force:
        return jsonify({
            "data": None,
            "flash": [{"level": "warning", "message": "El usuario tiene documentos. Usa 'force=true' para eliminar."}],
            "error": {"code": "VALIDATION", "message": "Usuario tiene datos relacionados"},
            "meta": {"has_submissions": True}
        }), 400
    
    # Registrar eliminación
    user_name = f"{user.first_name} {user.last_name}"
    user_email = user.email
    user_role = user.role.name if user.role else None
    # Audiencia del aviso en tiempo real: hay que resolverla ANTES del delete,
    # después las filas de user_program ya no existen. Una cuenta de personal no
    # es alumno de nadie, así que su aviso no tiene audiencia program-scoped.
    ws_audience_pids = (
        scope_service.program_ids_of_user(user_id)
        if user_role in ('applicant', 'student')
        else None
    )
    admin_svc.delete_user_account(user, user_name)

    # Misma razón que en toggle_active: las salas de Socket.IO se unen una sola
    # vez en el handshake y no se vuelven a resolver contra la base. Sin esto,
    # la pestaña de un usuario ya borrado sigue recibiendo el feed hasta que
    # reconecte por su cuenta.
    from app.sockets.emitters import disconnect_user_sockets
    disconnect_user_sockets(user_id)

    try:
        from app.sockets.emitters import emit_admin_user_change
        payload_ws = {
            'action': 'deleted',
            'user_id': user_uuid_public,
            'role': user_role,
            'email': user_email,
            'full_name': user_name,
        }
        emit_admin_user_change(payload_ws, ws_audience_pids)
    except Exception:
        pass

    return jsonify({
        "data": None,
        "flash": [{"level": "success", "message": f"Usuario {user_name} eliminado."}],
        "error": None,
        "meta": {}
    }), 200


@api_admin_users.post("/social-service")
@login_required
@permission_required('admin_users.api.create_social_service')
def create_social_service():
    """
    Crea un usuario con rol 'social_service' y delega los permisos indicados.

    Body JSON:
      first_name        : str
      last_name         : str
      mother_last_name  : str | null
      email             : str
      is_internal       : bool (default True)
      permissions       : list[str]  — codenames a delegar (obligatorio, >=1)
      program_ids       : list[int] | null
      expires_at        : str ISO 8601 | null
    """
    from datetime import datetime
    from app.services.permission_service import PermissionServiceError as PermErr

    payload = request.get_json(silent=True) or {}

    required = ['first_name', 'last_name', 'email', 'permissions']
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": f"Campos requeridos: {', '.join(missing)}."}],
            "error": {"code": "VALIDATION", "message": "Campos faltantes"},
            "meta": {"missing": missing}
        }), 400

    if not isinstance(payload['permissions'], list) or len(payload['permissions']) == 0:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": "Debes seleccionar al menos un permiso."}],
            "error": {"code": "VALIDATION", "message": "permissions vacío"},
            "meta": {}
        }), 400

    expires_at = None
    if payload.get('expires_at'):
        try:
            expires_at = datetime.fromisoformat(payload['expires_at'])
        except ValueError:
            return jsonify({
                "data": None,
                "flash": [{"level": "danger", "message": "Fecha de expiración inválida."}],
                "error": {"code": "VALIDATION", "message": "expires_at inválido"},
                "meta": {}
            }), 400

    try:
        new_user, delegations, email_sent = admin_svc.create_social_service_account(
            creator_id=current_user.id,
            user_data={
                'first_name':       payload['first_name'],
                'last_name':        payload['last_name'],
                'mother_last_name': payload.get('mother_last_name'),
                'email':            payload['email'],
                'is_internal':      payload.get('is_internal', True),
            },
            permissions=payload['permissions'],
            program_ids=payload.get('program_ids'),
            expires_at=expires_at,
            raw_expires_at=payload.get('expires_at'),
        )

        created_msg = (
            f"Usuario {new_user.first_name} {new_user.last_name} creado con "
            f"{len(delegations)} delegación(es)."
        )
        if email_sent:
            flash_entry = {
                "level": "success",
                "message": (
                    f"{created_msg} Se envió a {new_user.email} un enlace para "
                    f"que defina su contraseña; vence en 45 minutos."
                ),
            }
        else:
            # The account and its activation token exist; only the mail could
            # not be queued. Say so instead of implying the user was notified.
            flash_entry = {
                "level": "warning",
                "message": (
                    f"{created_msg} No se pudo enviar el correo con el enlace de "
                    f"activación a {new_user.email}. Usa «Restablecer contraseña» "
                    f"para generar y enviar uno nuevo."
                ),
            }

        return jsonify({
            "data": {
                "user": new_user.to_dict(include_sensitive=True),
                "delegations_count": len(delegations),
                "activation_email_sent": email_sent,
            },
            "flash": [flash_entry],
            "error": None,
            "meta": {}
        }), 201

    except InputValidationError as e:
        # The service validates the person-name fields; the route is what turns
        # that into the envelope.
        return _validation_error_response(e.message)
    except PermErr as e:
        return jsonify({
            "data": None,
            "flash": [{"level": "danger", "message": str(e)}],
            "error": {"code": "BUSINESS_ERROR", "message": str(e)},
            "meta": {}
        }), 400
    except Exception as e:
        return api_server_error(e, context='create_user')


@api_admin_users.get("/<uuid:user_uuid>/history")
@login_required
@permission_required('admin_users.api.list')
def user_history(user_uuid):
    """
    Obtiene el historial completo de un usuario.

    El historial es información prohibida entre programas: no existe nivel
    reducido, el alcance lo resuelve `guard_user_scope`.
    """
    user = User.by_uuid(user_uuid)
    denied = guard_user_scope(resolved_id(user))
    if denied:
        return denied
    user_id = user.id
    
    history_entries = UserHistoryService.get_user_history(user_id=user_id)
    
    return jsonify({
        "data": {
            # Public handle, never the integer primary key.
            "user": {"id": str(user.uuid) if user.uuid else None,
                     "name": f"{user.first_name} {user.last_name}"},
            "history": [entry.to_dict() for entry in history_entries]
        },
        "error": None,
        "meta": {"total": len(history_entries)}
    }), 200
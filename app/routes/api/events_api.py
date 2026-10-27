from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.utils.permissions import permission_required, guard_program_scope
from app.utils.api_response import api_ok, api_error, api_server_error
from app.utils.validation import parse_json
from app.schemas.events import (
    CreateEventIn, AddWindowIn, UpdateEventIn, UnarchiveEventIn, SetHostsIn,
)
from app.services import program_scope_service as scope_service
from app.services.events_service import EventsService

api_events = Blueprint('api_events', __name__, url_prefix='/api/v1/events')


# ============================================================================
# Alcance por programa — permiso ≠ alcance
# ============================================================================

def _deny(code: str, message: str, status: int):
    """Denegación con el envelope del proyecto y mensaje en español."""
    return api_error(code, message, status=status, level='danger')


def _requires_force(message: str):
    """409 que pide confirmación: `data.requires_force` le dice al front que reintente con ?force=true."""
    resp, status = api_error('CONFLICT', message, status=409)
    body = resp.get_json()
    body['data'] = {'requires_force': True, 'message': message}
    return jsonify(body), status


def _event_managed_by_current_user(event) -> bool:
    """
    True si `current_user` puede GESTIONAR este evento. Regla única para todo
    el módulo; vive en `EventsService.user_may_manage_event`.

    - Evento CON programa: exige alcance sobre ese programa. Aquí se cierra el
      paso de un coordinador al calendario de otro.
    - Evento SIN programa (institucional): sólo alcance global.

    La excepción institucional que había antes ("sin programa = de todos los
    gestores") era la puerta de atrás del módulo: convertía cada evento con
    `program_id = NULL` en un objeto que cualquier coordinador podía editar,
    concluir, archivar, rellenar de ventanas y — por `update_event` — reclamar
    como suyo poniéndole su propio program_id. Con `create_event` ya cerrado,
    ningún usuario con alcance limitado puede fabricar uno de esos eventos, así
    que la regla estricta no le quita nada que él pueda producir hoy.
    """
    return EventsService.user_may_manage_event(current_user, event)


def _event_participable_by_current_user(event) -> bool:
    """
    True si `current_user` puede PARTICIPAR en este evento: verlo, apuntarse,
    ver sus ponentes, sus imágenes y sus horarios.

    Regla única para todo el módulo; vive en
    `EventsService.user_may_participate_in_event`. Los sitios que sirven a las
    dos audiencias preguntan `gestión OR participación` — nunca inventan una
    tercera variante. Tres de ellos (hosts, imágenes y el servidor de bytes)
    usaban un predicado que ignoraba `visibility` y el programa, así que
    cualquier cuenta autenticada leía el cartel de ponentes y las imágenes de
    un evento PRIVADO de cualquier posgrado.
    """
    return EventsService.user_may_participate_in_event(current_user, event)


def _check_event_access(event_id: int):
    """
    Carga el evento y exige autoridad de GESTIÓN sobre él.

    404 EN LAS DOS RAMAS, a propósito. Estas rutas se dirigen por un id crudo
    que el llamante puede teclear, y el listado de gestión
    (`GET /api/v1/events`) ya está acotado a su alcance: un evento que no
    gestiona nunca le llegó en una lista, así que su existencia no es
    información que él tenga. Contestar 403 aquí y 404 veinte líneas más allá
    convertía el par en un oráculo: un `program_admin` recorría los ids y sabía
    cuáles existen —cuántos eventos hay en la institución y en qué rango de
    ids— sin ver ninguno. `invitations_api.cancel_invitation` ya había elegido
    404 por este motivo; ahora el módulo entero dice lo mismo.

    Las rutas de PARTICIPACIÓN (`/slots`, `/hosts`, `/images`, `/public/<id>`)
    llevaron un 403 durante una revisión, con el argumento de que allí el
    evento sí llegó en una lista que el llamante recibió legítimamente. El
    argumento no se sostiene precisamente en el caso que importa: si el
    predicado de participación DENIEGA, ese evento no estuvo en ninguna lista
    suya — un borrador o un evento privado de otro posgrado no aparece en
    ningún listado que él reciba. Así que el 403 sólo le confirmaba que el id
    existe, y cualquier cuenta autenticada sin un solo permiso podía recorrer
    1..N y levantar el censo. Ahora las cuatro contestan 404 igual que estas.

    La regla, en una línea: 403 cuando la existencia del objeto ya es
    información suya; 404 cuando el propio hecho de denegarle prueba que no lo
    es.

    Returns:
        (event, None) si procede; (None, respuesta_error) si no.
    """
    event = EventsService.get_event_or_none(event_id)
    if not event or not _event_managed_by_current_user(event):
        return None, _deny("NOT_FOUND", "Evento no encontrado.", 404)
    return event, None


@api_events.route('', methods=['POST'])
@login_required
@permission_required('events.api.create')
def create_event():
    payload = parse_json(CreateEventIn)

    # Un usuario con alcance limitado DEBE anclar el evento a uno de sus
    # programas: sin program_id el evento sería institucional y se saltaría
    # todos los controles de alcance posteriores.
    program_id = payload.program_id or None

    if not scope_service.is_global_scope(current_user):
        if not program_id:
            return _deny(
                "VALIDATION_ERROR",
                "Debes indicar el programa al que pertenece el evento.",
                400,
            )
        denied = guard_program_scope(program_id)
        if denied:
            return denied

    try:
        ev = EventsService.create_event(
            program_id=program_id,
            type_=payload.type,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            created_by=current_user.id,
            visible_to_students=payload.visible_to_students,
            capacity_type=payload.capacity_type,
            max_capacity=payload.max_capacity,
            requires_registration=payload.requires_registration,
            allows_attendance_tracking=payload.allows_attendance_tracking,
            status=payload.status,
            academic_period_id=payload.academic_period_id,
            visibility=payload.visibility,
            reminders_enabled=payload.reminders_enabled
        )
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='create_event')

    from app.sockets.emitters import emit_event_change
    emit_event_change({
        'action': 'created',
        'event_id': ev.id,
        'program_id': ev.program_id,
        'title': ev.title,
    }, event=ev)

    return api_ok({"id": ev.id}, status=201)

@api_events.route('/<int:event_id>/windows', methods=['POST'])
@login_required
@permission_required('events.api.create_window')
def add_window(event_id:int):
    event, err = _check_event_access(event_id)
    if err:
        return err

    payload = parse_json(AddWindowIn)
    try:
        win = EventsService.add_window(
            event_id=event_id,
            window_date=payload.date,
            start=payload.start_time,
            end=payload.end_time,
            slot_minutes=payload.slot_minutes,
            timezone_str=payload.timezone
        )
        return api_ok({"id": win.id}, status=201)
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='add_window')

@api_events.route('/windows/<int:window_id>/generate-slots', methods=['POST'])
@login_required
@permission_required('events.api.generate_slots')
def generate_slots(window_id:int):
    owner_event_id = EventsService.get_event_id_of_window(window_id)
    # Un solo 404 para "no existe" y para "no es de un evento que gestionas":
    # dos mensajes distintos reconstruyen el oráculo que `_check_event_access`
    # acaba de cerrar, sólo que sobre ids de ventana.
    if owner_event_id is None or _check_event_access(owner_event_id)[1]:
        return _deny("NOT_FOUND", "Ventana no encontrada.", 404)

    try:
        result = EventsService.generate_slots(window_id)
        # `generate_slots` devuelve {'created', 'skipped', 'total'}: antes se
        # publicaba len(dict) — siempre 3.
        return api_ok({
            "created": result.get('created', 0),
            "skipped": result.get('skipped', 0),
            "total": result.get('total', 0),
        }, status=201)
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='generate_slots')

@api_events.route('/<int:event_id>/slots', methods=['GET'])
@login_required
def list_slots(event_id:int):
    event = EventsService.get_event_or_none(event_id)
    if not event:
        return _deny("NOT_FOUND", "Evento no encontrado.", 404)

    # Gestores del programa, o quien pueda participar en el evento (mismo
    # criterio que el detalle público).
    if not (_event_managed_by_current_user(event) or _event_participable_by_current_user(event)):
        # 404, no 403: mismo cuerpo y mismo codigo que el evento inexistente de
        # arriba. Un 403 aqui confirma que ese id existe, y quien pregunta no
        # tiene por que saberlo — recorriendo 1..N obtiene el censo de eventos
        # privados y en borrador de toda la institucion.
        return _deny("NOT_FOUND", "Evento no encontrado.", 404)

    status = request.args.get('status')
    items = EventsService.list_slots(event_id=event_id, status=status)
    payload = [{"id": s.id, "starts_at": s.starts_at.isoformat(), "ends_at": s.ends_at.isoformat(), "status": s.status} for s in items]
    return api_ok({"items": payload})

@api_events.route('', methods=['GET'])
@login_required
@permission_required('events.api.list')
def list_events():
    """
    Lista eventos para el PANEL DE ADMINISTRACIÓN — no es la lista pública.

    La lista del aspirante y del estudiante es `GET /api/v1/events/public`, que
    pasa por `user_may_participate_in_event`. Esta trae borradores, eventos
    privados, los ocultos al alumnado y los contadores de registros e
    invitaciones pendientes: es material de gestión y `events.api.list` es un
    permiso de gestión. Los roles applicant y student lo tenían por semilla, así
    que un aspirante leía el calendario institucional completo —incluidos los
    borradores— desde aquí; ver el parche
    `database/DML/patches/2026_08_12_01_events_list_revoke_applicant_student.sql`.

    Sigue incluyendo los institucionales (sin programa) para que un coordinador
    vea el calendario general, pero sólo los ya publicados: el borrador
    institucional es de la Jefatura y nadie sin alcance global puede tocarlo
    (`EventsService._institutional_readable_clause`). Cada fila trae
    `can_manage`; el front debe ocultar/deshabilitar las acciones cuando venga
    en False.
    """
    filters = {
        'academic_period_id': request.args.get('academic_period_id', type=int),
        'program_id': request.args.get('program_id', type=int),
        'type': request.args.get('type'),
        'status': request.args.get('status'),
        'capacity_type': request.args.get('capacity_type'),
        'search': request.args.get('search'),
    }

    accessible_pids = current_user.get_accessible_program_ids()
    events = EventsService.list_admin_events(accessible_pids, filters)

    items = []
    for event in events:
        item = EventsService.build_admin_event_item(event)
        item["can_manage"] = _event_managed_by_current_user(event)
        items.append(item)

    return api_ok({"items": items})

@api_events.route('/<int:event_id>', methods=['DELETE'])
@login_required
@permission_required('events.api.manage')
def delete_event(event_id: int):
    """Elimina un evento y todos sus slots/appointments asociados"""
    # Misma regla —y misma respuesta— que el resto de la gestión: borrar
    # arrastra ventanas, horarios y citas, y un evento institucional sólo lo
    # borra el alcance global. El 403 propio que había aquí delataba qué ids
    # existen; ver `_check_event_access`.
    event, err = _check_event_access(event_id)
    if err:
        return err

    # Verificar si hay appointments activas
    appointments_count = EventsService.count_active_appointments(event_id)

    if appointments_count > 0:
        force = request.args.get('force') in ('true', '1', 'yes')
        if not force:
            return _requires_force(
                f"El evento tiene {appointments_count} citas activas. Usa ?force=true para eliminar."
            )

    try:
        # Cascade debería manejar la eliminación de windows, slots y appointments
        info = EventsService.delete_event(event_id)

        # Sin `event=`: la fila ya no existe y no se puede releer su status ni
        # su visibility, así que sólo se avisa a la gestión. Es el lado seguro.
        from app.sockets.emitters import emit_event_change
        emit_event_change({
            'action': 'deleted',
            'event_id': event_id,
            'program_id': info['program_id'],
            'title': info['title'],
        })

        return api_ok({"deleted": event_id})

    except Exception as e:
        return api_server_error(e, context='delete_event')

@api_events.route('/<int:event_id>', methods=['GET'])
@login_required
@permission_required('events.api.manage')
def get_event_details(event_id: int):
    """Obtiene detalles completos de un evento incluyendo sus ventanas"""
    event, err = _check_event_access(event_id)
    if err:
        return err

    return api_ok(EventsService.build_admin_event_detail(event))


@api_events.route('/windows/<int:window_id>', methods=['DELETE'])
@login_required
@permission_required('events.api.manage')
def delete_window(window_id: int):
    """Elimina una ventana y todos sus slots"""
    from app.services.events_service import EventsService
    
    owner_event_id = EventsService.get_event_id_of_window(window_id)
    # Un solo 404 para las dos razones — ver `generate_slots`.
    if owner_event_id is None or _check_event_access(owner_event_id)[1]:
        return _deny("NOT_FOUND", "Ventana no encontrada.", 404)

    force = request.args.get('force') in ('true', '1', 'yes')

    try:
        EventsService.delete_window(window_id, force=force)
        return api_ok({"deleted": window_id})
    except ValueError as e:
        if "force=True" in str(e):
            return _requires_force(str(e))
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='delete_window')


@api_events.route('/slots/<int:slot_id>', methods=['DELETE'])
@login_required
@permission_required('events.api.manage')
def delete_slot(slot_id: int):
    """Elimina un slot individual"""
    from app.services.events_service import EventsService
    
    owner_event_id = EventsService.get_event_id_of_slot(slot_id)
    # Un solo 404 para las tres razones — ver `generate_slots`.
    if owner_event_id is None or _check_event_access(owner_event_id)[1]:
        return _deny("NOT_FOUND", "Horario no encontrado.", 404)

    force = request.args.get('force') in ('true', '1', 'yes')

    try:
        EventsService.delete_slot(slot_id, force=force)
        return api_ok({"deleted": slot_id})
    except ValueError as e:
        if "force=True" in str(e):
            return _requires_force(str(e))
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='delete_slot')


@api_events.route('/<int:event_id>/windows-list', methods=['GET'])
@login_required
@permission_required('events.api.manage')
def list_event_windows(event_id: int):
    """Lista todas las ventanas de un evento con estadísticas"""
    event, err = _check_event_access(event_id)
    if err:
        return err

    return api_ok({"windows": EventsService.list_windows_with_stats(event_id)})

@api_events.route('/<int:event_id>', methods=['PUT'])
@login_required
@permission_required('events.api.manage')
def update_event(event_id: int):
    """
    Actualizar información de un evento.

    `program_id` es INMUTABLE para quien no tiene alcance global. El programa
    no es un campo más: decide quién manda sobre el evento, y dejarlo editable
    convertía la ruta en una herramienta de apropiación — el coordinador de A
    reclamaba un evento institucional poniéndole su program_id, o soltaba el
    suyo a NULL para volverlo institución-wide y sacarlo del alcance de
    cualquiera menos el global. Mover un evento además arrastra sus ventanas,
    horarios, citas, invitaciones y registros, que son de alumnos del programa
    de origen. Reasignar es un acto de la Jefatura de Posgrado; para el resto,
    el camino es borrar y volver a crear.

    Reenviar el mismo program_id que ya tiene el evento es un no-op aceptado:
    el formulario manda el objeto completo.
    """
    event, err = _check_event_access(event_id)
    if err:
        return err

    payload = parse_json(UpdateEventIn)
    data = payload.model_dump(exclude_unset=True)

    if 'program_id' in data:
        new_pid = data['program_id']

        if new_pid == event.program_id:
            data.pop('program_id')          # no-op: no lo toques
        elif not scope_service.is_global_scope(current_user):
            return _deny(
                "FORBIDDEN",
                "No puedes cambiar el programa de un evento. Pide a la "
                "Jefatura de Posgrado que lo reasigne.",
                403,
            )
        # Alcance global: puede reasignar, incluso a institucional.

    try:
        event = EventsService.update_event(event_id, data)
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='update_event')

    from app.sockets.emitters import emit_event_change
    emit_event_change({
        'action': 'updated',
        'event_id': event.id,
        'program_id': event.program_id,
        'title': event.title,
    }, event=event)

    return api_ok({"id": event.id})

@api_events.route('/public', methods=['GET'])
@login_required
def list_public_events():
    """Lista eventos visibles para estudiantes (filtrados por periodo activo + visibilidad)."""
    return api_ok({"items": EventsService.build_public_event_items(current_user.id)})


@api_events.route('/public/<int:event_id>', methods=['GET'])
@login_required
def get_public_event_detail(event_id: int):
    """
    Detalle público de un evento visible para estudiantes.

    Incluye:
      - datos del evento + programa
      - registro actual del usuario (si aplica)
      - cita actual del usuario (si aplica, para capacity_type='single')
      - ventanas con slots (para eventos 1:1)
      - conteo de registros actuales (para multiple/unlimited)
    """
    # Una sola respuesta para "no existe" y para "no es tuyo": cualquier otra
    # cosa convierte el id en un oráculo. Con dos códigos distintos, o con dos
    # mensajes distintos, cualquier cuenta autenticada recorre 1..N y obtiene
    # el censo de eventos de la institución — cuántos hay, qué ids ocupan y,
    # por el mensaje, cuáles están en borrador. No se filtra nada personal,
    # pero se filtra la existencia, y eso basta para preparar el resto.
    #
    # Aquí vivía además una comprobación de `visible_to_students` y `status`
    # ANTES del ACL real de abajo. Era una copia a mano del predicado
    # compartido, más estricta que él (negaba a quien gestiona su propio
    # borrador) y era justo la que partía el mensaje en dos. Se va: la regla
    # la contesta `EventsService`, en un solo sitio.
    event = EventsService.get_event_or_none(event_id)
    if event is None:
        return api_error('NOT_FOUND', "Evento no encontrado", status=404)

    # ACL — el creador, quien gestiona el evento, o quien puede participar en
    # él (`EventsService.user_may_participate_in_event`: público de su programa
    # o institucional, o invitado).
    #
    # Ya NO cuenta estar registrado. El registro es una escritura que el propio
    # usuario se concede (`POST /api/v1/attendance/event/<id>/register`), así
    # que aceptarlo aquí era regalar la llave: bastaba con apuntarse a un evento
    # privado de otro posgrado para que este endpoint devolviera su
    # descripción, su sede, su cupo y sus horarios. Una autorización que el
    # llamante puede firmarse a sí mismo no es una autorización.
    #
    # La rama de programa tampoco se resuelve ya a mano: `UserProgram...first()`
    # leía UNA sola fila, de modo que un usuario con dos programas quedaba
    # fuera del evento de su segundo programa.
    is_creator = event.created_by == current_user.id
    is_admin = _event_managed_by_current_user(event)

    if not (is_creator or is_admin or _event_participable_by_current_user(event)):
        # Mismo cuerpo y mismo código que el evento inexistente de arriba.
        return api_error('NOT_FOUND', "Evento no encontrado", status=404)

    return api_ok(EventsService.build_public_event_detail(event, current_user.id))


# ============================================================================
# STATUS TRANSITIONS (conclude / archive / unarchive)
# ============================================================================

@api_events.route('/<int:event_id>/conclude', methods=['POST'])
@login_required
@permission_required('events.api.conclude')
def conclude_event(event_id: int):
    """Concluye evento: status='completed', cancela pending invitations, purga media."""
    event, err = _check_event_access(event_id)
    if err:
        return err
    try:
        event = EventsService.conclude_event(event_id, current_user.id)

        from app.sockets.emitters import emit_event_change
        emit_event_change({
            'action': 'concluded',
            'event_id': event_id,
            'program_id': event.program_id,
            'title': event.title,
        }, event=event)
        return api_ok({"status": event.status})
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='conclude_event')


@api_events.route('/<int:event_id>/archive', methods=['POST'])
@login_required
@permission_required('events.api.archive')
def archive_event(event_id: int):
    """Archiva evento: oculto del público, cancela invitaciones, notifica registrados, purga media."""
    event, err = _check_event_access(event_id)
    if err:
        return err
    try:
        event = EventsService.archive_event(event_id, current_user.id)

        from app.sockets.emitters import emit_event_change
        emit_event_change({
            'action': 'archived',
            'event_id': event_id,
            'program_id': event.program_id,
            'title': event.title,
        }, event=event)
        return api_ok({"status": event.status})
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='archive_event')


@api_events.route('/<int:event_id>/unarchive', methods=['POST'])
@login_required
@permission_required('events.api.archive')
def unarchive_event(event_id: int):
    """Reactiva evento archivado. Body opcional: {new_status: 'published'|'draft'}."""
    event, err = _check_event_access(event_id)
    if err:
        return err
    new_status = parse_json(UnarchiveEventIn).new_status
    try:
        event = EventsService.unarchive_event(event_id, current_user.id, new_status)

        from app.sockets.emitters import emit_event_change
        emit_event_change({
            'action': 'unarchived',
            'event_id': event_id,
            'program_id': event.program_id,
            'title': event.title,
        }, event=event)
        return api_ok({"status": event.status})
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='unarchive_event')


# ============================================================================
# HOSTS / PRESENTADORES
# ============================================================================

@api_events.route('/<int:event_id>/hosts', methods=['GET'])
@login_required
def list_event_hosts(event_id: int):
    """
    Lista hosts de un evento. Visible para quien lo gestiona o participa en él.

    El cartel de ponentes lleva nombres internos y la URL de su fotografía, y
    la ACL anterior (`visible_to_students and published and capacity_type !=
    'single'`) no miraba ni la `visibility` ni el programa: cualquier cuenta
    autenticada leía los ponentes de un evento PRIVADO de cualquier posgrado.

    El lector va al servicio porque la foto de un ponente interno sólo se
    publica a quien puede pedir esos bytes (`may_view_avatar`): el índice y el
    servidor de archivos tienen que contestar lo mismo.
    """
    event = EventsService.get_event_or_none(event_id)
    if not event:
        return _deny("NOT_FOUND", "Evento no encontrado.", 404)

    if not (_event_managed_by_current_user(event) or _event_participable_by_current_user(event)):
        # 404, no 403: mismo cuerpo y mismo codigo que el evento inexistente de
        # arriba. Un 403 aqui confirma que ese id existe, y quien pregunta no
        # tiene por que saberlo — recorriendo 1..N obtiene el censo de eventos
        # privados y en borrador de toda la institucion.
        return _deny("NOT_FOUND", "Evento no encontrado.", 404)

    hosts = EventsService.get_event_hosts(event_id, viewer=current_user)
    return api_ok({"hosts": hosts})


@api_events.route('/<int:event_id>/hosts/photo', methods=['POST'])
@login_required
@permission_required('events.api.manage_hosts')
def upload_host_photo(event_id: int):
    """
    Sube foto para un host externo. Retorna el path relativo para usar en
    `external_photo_path` al llamar PUT /hosts.
    """
    event, err = _check_event_access(event_id)
    if err:
        return err

    file_storage = request.files.get('file')
    if not file_storage:
        return api_error('VALIDATION_ERROR', "Archivo 'file' es requerido", status=400)

    try:
        from app.utils.files import save_event_image
        path = save_event_image(file_storage, event_id, 'host')
        return api_ok({"path": path}, status=201)
    except Exception as e:
        return api_server_error(e, context='upload_host_photo')


@api_events.route('/<int:event_id>/hosts', methods=['PUT'])
@login_required
@permission_required('events.api.manage_hosts')
def set_event_hosts(event_id: int):
    """
    Reemplaza la lista completa de hosts de un evento.

    Gestionar el evento autoriza a EDITAR SU CARTEL, no a nombrar ponente a
    cualquier cuenta de la institución: cada `user_id` interno lo valida
    `EventsService.user_may_be_named_host` contra el actor. Sin eso, la fila
    que el propio gestor escribe era la prueba con la que
    `file_access_service` le servía el rostro de la víctima.
    """
    event, err = _check_event_access(event_id)
    if err:
        return err

    hosts_data = parse_json(SetHostsIn).hosts

    try:
        hosts = EventsService.set_event_hosts(
            event_id, hosts_data, acting_user=current_user
        )
        return api_ok({"count": len(hosts)})
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='set_event_hosts')


# ============================================================================
# IMÁGENES (COVER + GALLERY)
# ============================================================================

@api_events.route('/<int:event_id>/images', methods=['GET'])
@login_required
def list_event_images(event_id: int):
    """
    Lista imágenes de un evento (cover + gallery).

    Mismo criterio que los ponentes: gestión o participación. Estas rutas son
    el índice de los bytes que sirve `api_files.event_image`, y las dos deben
    contestar lo mismo o el índice delata lo que el servidor niega.
    """
    event = EventsService.get_event_or_none(event_id)
    if not event:
        return _deny("NOT_FOUND", "Evento no encontrado.", 404)

    if not (_event_managed_by_current_user(event) or _event_participable_by_current_user(event)):
        # 404, no 403: mismo cuerpo y mismo codigo que el evento inexistente de
        # arriba. Un 403 aqui confirma que ese id existe, y quien pregunta no
        # tiene por que saberlo — recorriendo 1..N obtiene el censo de eventos
        # privados y en borrador de toda la institucion.
        return _deny("NOT_FOUND", "Evento no encontrado.", 404)

    data = EventsService.get_event_images(event_id)
    return api_ok(data)


@api_events.route('/<int:event_id>/cover', methods=['POST'])
@login_required
@permission_required('events.api.manage_images')
def upload_event_cover(event_id: int):
    """Sube (o reemplaza) la imagen de portada del evento."""
    event, err = _check_event_access(event_id)
    if err:
        return err

    file_storage = request.files.get('file')
    if not file_storage:
        return api_error('VALIDATION_ERROR', "Archivo 'file' es requerido", status=400)

    try:
        image = EventsService.upload_event_cover(event_id, file_storage)
        return api_ok({"image": image.to_dict()}, status=201)
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='upload_event_image')


@api_events.route('/<int:event_id>/images', methods=['POST'])
@login_required
@permission_required('events.api.manage_images')
def upload_event_gallery_image(event_id: int):
    """Agrega imagen a la galería del evento."""
    event, err = _check_event_access(event_id)
    if err:
        return err

    file_storage = request.files.get('file')
    if not file_storage:
        return api_error('VALIDATION_ERROR', "Archivo 'file' es requerido", status=400)

    caption = request.form.get('caption')
    try:
        image = EventsService.upload_event_gallery_image(event_id, file_storage, caption)
        return api_ok({"image": image.to_dict()}, status=201)
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='upload_event_image')


@api_events.route('/images/<int:image_id>', methods=['DELETE'])
@login_required
@permission_required('events.api.manage_images')
def delete_event_image(image_id: int):
    """Elimina imagen (cover o galería) + archivo físico."""
    owner_event_id = EventsService.get_event_id_of_image(image_id)
    # Un solo 404 para las dos razones — ver `generate_slots`.
    if owner_event_id is None or _check_event_access(owner_event_id)[1]:
        return _deny("NOT_FOUND", "Imagen no encontrada.", 404)

    try:
        EventsService.delete_event_image(image_id)
        return api_ok({"deleted": image_id})
    except ValueError as e:
        return api_error('BUSINESS_ERROR', str(e), status=400)
    except Exception as e:
        return api_server_error(e, context='delete_event_image')


# ============================================================================
# FASE 6 — PROMOCIÓN & DESCUBRIMIENTO
# ============================================================================

@api_events.route('/admin-stats', methods=['GET'])
@login_required
@permission_required('events.api.list')
def get_admin_dashboard_stats():
    """
    KPIs para el dashboard de administración de eventos.

    Mismo permiso y mismo universo de filas que `list_events`: un contador
    también es una lectura. Cuenta sólo lo que ese llamador podría listar.
    """
    accessible_pids = current_user.get_accessible_program_ids()
    stats = EventsService.get_admin_dashboard_stats(accessible_pids)
    return api_ok(stats)


@api_events.route('/new-count', methods=['GET'])
@login_required
def get_new_events_count():
    """Cuenta eventos públicos creados desde la última visita del usuario."""
    try:
        count = EventsService.count_new_events(current_user.id)
        return api_ok({"count": count})
    except Exception as e:
        return api_server_error(e, context='get_new_events_count')


@api_events.route('/mark-seen', methods=['POST'])
@login_required
def mark_events_seen():
    """Marca los eventos como vistos por el usuario actual."""
    try:
        EventsService.mark_events_seen(current_user.id)
        return api_ok()
    except Exception as e:
        return api_server_error(e, context='mark_events_seen')
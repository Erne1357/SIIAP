from datetime import datetime, date, time, timedelta
from app import db
from app.models.event import Event, EventWindow, EventSlot,EventAttendance
from sqlalchemy import and_
from datetime import timezone
from app.utils.datetime_utils import now_local

class EventsService:
    
    @staticmethod
    def create_event(
        program_id: int | None,
        type_: str,
        title: str,
        description: str | None,
        location: str | None,
        created_by: int,
        visible_to_students: bool = True,
        capacity_type: str = 'single',
        max_capacity: int | None = None,
        requires_registration: bool = True,
        allows_attendance_tracking: bool = False,
        status: str = 'published'
    ) -> Event:
        """Crear evento con nuevos parámetros de capacidad"""
        
        if capacity_type not in ('single', 'multiple', 'unlimited'):
            raise ValueError("capacity_type debe ser 'single', 'multiple' o 'unlimited'")
        
        if capacity_type == 'multiple' and not max_capacity:
            raise ValueError("max_capacity es requerido para eventos de capacidad múltiple")
        
        ev = Event(
            program_id=program_id,
            type=type_ or 'interview',
            title=title,
            description=description,
            location=location,
            created_by=created_by,
            visible_to_students=visible_to_students,
            capacity_type=capacity_type,
            max_capacity=max_capacity,
            requires_registration=requires_registration,
            allows_attendance_tracking=allows_attendance_tracking,
            status=status
        )
        db.session.add(ev)
        db.session.commit()
        return ev

    @staticmethod
    def add_window(
        event_id: int,
        window_date: date,
        start: time,
        end: time,
        slot_minutes: int,
        timezone_str: str = 'America/Ciudad_Juarez'
    ) -> EventWindow:
        """Agregar ventana de horarios"""
        
        if start >= end:
            raise ValueError("start_time debe ser menor a end_time")
        if slot_minutes not in (15, 20, 30, 45, 60):
            raise ValueError("slot_minutes debe ser 15, 20, 30, 45 o 60")

        win = EventWindow(
            event_id=event_id,
            date=window_date,
            start_time=start,
            end_time=end,
            slot_minutes=slot_minutes,
            timezone=timezone_str,
            slots_generated=False
        )
        db.session.add(win)
        db.session.commit()
        return win

    @staticmethod
    def generate_slots(window_id: int, overwrite_free: bool = True) -> dict:
        """
        Genera slots para una ventana.
        
        Args:
            window_id: ID de la ventana
            overwrite_free: Si True, regenera slots libres. Si False, solo crea los faltantes.
        
        Returns:
            dict con 'created', 'skipped', 'total'
        """
        win = db.session.get(EventWindow, window_id)
        if not win:
            raise ValueError("EventWindow no encontrado")

        # Construir timestamps
        starts = datetime.combine(win.date, win.start_time)
        ends = datetime.combine(win.date, win.end_time)

        created = 0
        skipped = 0
        cursor = starts
        
        while cursor < ends:
            slot_end = cursor + timedelta(minutes=win.slot_minutes)
            if slot_end > ends:
                break

            # Verificar si ya existe un slot en este horario
            existing = EventSlot.query.filter(
                and_(
                    EventSlot.event_window_id == win.id,
                    EventSlot.starts_at == cursor
                )
            ).first()

            if existing:
                # Si existe y está libre, actualizar
                if overwrite_free and existing.status == 'free':
                    existing.ends_at = slot_end
                    skipped += 1
                else:
                    # Slot ocupado o no se permite sobrescribir
                    skipped += 1
            else:
                # Crear nuevo slot
                slot = EventSlot(
                    event_window_id=win.id,
                    starts_at=cursor,
                    ends_at=slot_end,
                    status='free'
                )
                db.session.add(slot)
                created += 1

            cursor = slot_end

        # Marcar ventana como generada
        win.slots_generated = True
        db.session.commit()
        
        return {
            'created': created,
            'skipped': skipped,
            'total': created + skipped
        }

    @staticmethod
    def delete_slot(slot_id: int, force: bool = False) -> bool:
        """
        Elimina un slot individual.
        
        Args:
            slot_id: ID del slot
            force: Si True, elimina aunque esté ocupado (cancela la cita)
        
        Returns:
            True si se eliminó correctamente
        """
        slot = db.session.get(EventSlot, slot_id)
        if not slot:
            raise ValueError("Slot no encontrado")
        
        if slot.status != 'free' and not force:
            raise ValueError("El slot está ocupado. Usa force=True para eliminar de todas formas.")
        
        # Si está ocupado y force=True, cancelar la cita asociada
        if slot.status == 'booked':
            from app.models.appointment import Appointment
            appointment = Appointment.query.filter_by(slot_id=slot_id).first()
            if appointment:
                appointment.status = 'cancelled'
                appointment.notes = f"{appointment.notes or ''}\n[Sistema]: Slot eliminado".strip()
        
        db.session.delete(slot)
        db.session.commit()
        return True

    @staticmethod
    def delete_window(window_id: int, force: bool = False) -> bool:
        """
        Elimina una ventana completa con todos sus slots.
        
        Args:
            window_id: ID de la ventana
            force: Si True, elimina aunque tenga slots ocupados
        
        Returns:
            True si se eliminó correctamente
        """
        window = db.session.get(EventWindow, window_id)
        if not window:
            raise ValueError("Ventana no encontrada")
        
        # Verificar si tiene slots ocupados
        occupied_slots = EventSlot.query.filter(
            and_(
                EventSlot.event_window_id == window_id,
                EventSlot.status == 'booked'
            )
        ).count()
        
        if occupied_slots > 0 and not force:
            raise ValueError(f"La ventana tiene {occupied_slots} slots ocupados. Usa force=True para eliminar.")
        
        # Si tiene slots ocupados y force=True, cancelar todas las citas
        if occupied_slots > 0 and force:
            from app.models.appointment import Appointment
            booked_slots = EventSlot.query.filter(
                and_(
                    EventSlot.event_window_id == window_id,
                    EventSlot.status == 'booked'
                )
            ).all()
            
            for slot in booked_slots:
                appointment = Appointment.query.filter_by(slot_id=slot.id).first()
                if appointment:
                    appointment.status = 'cancelled'
                    appointment.notes = f"{appointment.notes or ''}\n[Sistema]: Ventana eliminada".strip()
        
        # Cascade eliminará automáticamente los slots
        db.session.delete(window)
        db.session.commit()
        return True

    @staticmethod
    def list_slots(event_id: int = None, status: str = None):
        """Lista slots con filtros opcionales"""
        q = db.session.query(EventSlot).join(
            EventWindow, EventWindow.id == EventSlot.event_window_id
        )
        
        if event_id:
            q = q.join(Event, Event.id == EventWindow.event_id).filter(Event.id == event_id)
        if status:
            q = q.filter(EventSlot.status == status)
        
        return q.order_by(EventSlot.starts_at.asc()).all()
    
    @staticmethod
    def register_to_event(event_id: int, user_id: int, notes: str = None) -> 'EventAttendance':
        """
        Registra un usuario a un evento de capacidad múltiple/ilimitada
        """
        from app.models.event import EventAttendance
        
        event = db.session.get(Event, event_id)
        if not event:
            raise ValueError("Evento no encontrado")
        
        if event.capacity_type == 'single':
            raise ValueError("Este evento requiere asignación de slot individual")
        
        # Verificar si ya está registrado
        existing = EventAttendance.query.filter_by(
            event_id=event_id,
            user_id=user_id
        ).first()
        
        if existing:
            raise ValueError("El usuario ya está registrado en este evento")
        
        # Verificar capacidad para eventos múltiples
        if event.capacity_type == 'multiple' and event.max_capacity:
            current_count = EventAttendance.query.filter_by(
                event_id=event_id,
                status='registered'
            ).count()
            
            if current_count >= event.max_capacity:
                raise ValueError(f"El evento ha alcanzado su capacidad máxima ({event.max_capacity})")
        
        # Crear registro
        attendance = EventAttendance(
            event_id=event_id,
            user_id=user_id,
            status='registered',
            notes=notes
        )
        
        db.session.add(attendance)
        db.session.commit()
        
        return attendance
    
    @staticmethod
    def unregister_from_event(event_id: int, user_id: int) -> bool:
        """
        Cancela el registro de un usuario a un evento
        """
        from app.models.event import EventAttendance
        
        attendance = EventAttendance.query.filter_by(
            event_id=event_id,
            user_id=user_id
        ).first()
        
        if not attendance:
            raise ValueError("No se encontró el registro")
        
        db.session.delete(attendance)
        db.session.commit()
        
        return True
    
    @staticmethod
    def mark_attendance(event_id: int, user_id: int, attended: bool = True, notes: str = None, reset: bool = False):
        """
        Marca la asistencia de un usuario a un evento.

        Args:
            event_id: ID del evento
            user_id: ID del usuario
            attended: True=asistió, False=no asistió
            notes: Notas adicionales
            reset: Si True, resetea a 'registered'
        """
        from app.models.event import EventAttendance

        attendance = EventAttendance.query.filter_by(
            event_id=event_id,
            user_id=user_id
        ).first()

        if not attendance:
            raise ValueError("El usuario no está registrado en este evento")

        if reset:
            # Resetear a estado registrado
            attendance.status = 'registered'
            attendance.attended_at = None
        elif attended:
            attendance.status = 'attended'
            attendance.attended_at = now_local()
        else:
            attendance.status = 'no_show'
            attendance.attended_at = None

        if notes:
            attendance.notes = f"{attendance.notes or ''}\n{notes}".strip()

        db.session.commit()

        return attendance
    
    @staticmethod
    def get_event_registrations(event_id: int):
        """
        Obtiene todos los registros de un evento
        """
        from app.models.event import EventAttendance
        from app.models.user import User
        
        registrations = db.session.query(EventAttendance, User).join(
            User, EventAttendance.user_id == User.id
        ).filter(
            EventAttendance.event_id == event_id
        ).order_by(EventAttendance.registered_at.desc()).all()
        
        return [{
            'id': attendance.id,
            'user_id': user.id,
            'full_name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'status': attendance.status,
            'registered_at': attendance.registered_at.isoformat(),
            'attended_at': attendance.attended_at.isoformat() if attendance.attended_at else None,
            'notes': attendance.notes
        } for attendance, user in registrations]
    
    @staticmethod
    def invite_students(event_id: int, user_ids: list[int], invited_by: int, notes: str = None):
        """
        Invita múltiples estudiantes a un evento
        
        Returns:
            dict con 'invited', 'already_invited', 'already_registered', 'wrong_program'
        """
        from app.models.event import EventInvitation, EventAttendance
        from app.models.user_program import UserProgram
        
        event = db.session.get(Event, event_id)
        if not event:
            raise ValueError("Evento no encontrado")
        
        if event.capacity_type == 'single':
            raise ValueError("Este evento requiere asignación de slots individuales")
        
        results = {
            'invited': [],
            'already_invited': [],
            'already_registered': [],
            'wrong_program': []  # NUEVO
        }
        
        for user_id in user_ids:
            # NUEVO: Si el evento tiene programa específico, validar
            if event.program_id:
                user_program = UserProgram.query.filter_by(
                    user_id=user_id,
                    program_id=event.program_id
                ).first()
                
                if not user_program:
                    results['wrong_program'].append(user_id)
                    continue
            
            # Verificar si ya está registrado
            existing_reg = EventAttendance.query.filter_by(
                event_id=event_id,
                user_id=user_id
            ).first()
            
            if existing_reg:
                results['already_registered'].append(user_id)
                continue
            
            # Verificar si ya tiene invitación
            existing_inv = EventInvitation.query.filter_by(
                event_id=event_id,
                user_id=user_id
            ).first()
            
            if existing_inv:
                results['already_invited'].append(user_id)
                continue
            
            # Crear invitación
            invitation = EventInvitation(
                event_id=event_id,
                user_id=user_id,
                invited_by=invited_by,
                status='pending',
                notes=notes
            )
            db.session.add(invitation)
            results['invited'].append(user_id)
        
        db.session.commit()
        
        # NUEVO: Enviar notificaciones y registrar en historial después del commit
        try:
            from app.services.user_history_service import UserHistoryService
            from app.services.notification_service import NotificationService
            
            for user_id in results['invited']:
                # Obtener la invitación recién creada
                invitation = EventInvitation.query.filter_by(
                    event_id=event_id,
                    user_id=user_id,
                    invited_by=invited_by
                ).first()
                
                if invitation:
                    # Registrar en historial del admin
                    UserHistoryService.log_event_invitation(
                        user_id=user_id,
                        event_title=event.title,
                        event_id=event_id,
                        invitation_id=invitation.id,
                        event_date=event.event_date.strftime('%d/%m/%Y') if event.event_date else 'Por definir',
                        invited_by=invited_by
                    )
                    
                    # Enviar notificación al estudiante
                    NotificationService.notify_event_invitation(
                        user_id=user_id,
                        event_title=event.title,
                        event_id=event_id,
                        invitation_id=invitation.id,
                        event_date=event.event_date.strftime('%d/%m/%Y') if event.event_date else 'Por definir',
                        description=event.description
                    )
                    
            db.session.commit()
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error enviando notificaciones de invitación: {e}")
        
        return results
    
    @staticmethod
    def respond_to_invitation(invitation_id: int, user_id: int, accept: bool):
        """
        Responder a una invitación (aceptar/rechazar)
        """
        from app.models.event import EventInvitation
        
        invitation = db.session.get(EventInvitation, invitation_id)
        if not invitation:
            raise ValueError("Invitación no encontrada")
        
        if invitation.user_id != user_id:
            raise ValueError("Esta invitación no es para ti")
        
        if invitation.status != 'pending':
            raise ValueError("Esta invitación ya fue respondida")
        
        invitation.status = 'accepted' if accept else 'rejected'
        invitation.responded_at = now_local()
        
        # Si acepta, crear registro automáticamente
        if accept:
            try:
                EventsService.register_to_event(
                    event_id=invitation.event_id,
                    user_id=user_id,
                    notes=f"Registrado mediante invitación #{invitation.id}"
                )
            except ValueError as e:
                # Si ya no hay cupo, marcar invitación como rechazada
                invitation.status = 'rejected'
                invitation.notes = f"{invitation.notes or ''}\nNo se pudo registrar: {str(e)}".strip()
                raise
        
        db.session.commit()
        return invitation
    
    @staticmethod
    def get_event_invitations(event_id: int):
        """
        Obtiene todas las invitaciones de un evento con info de usuarios
        """
        from app.models.event import EventInvitation
        from app.models.user import User
        
        invitations = db.session.query(EventInvitation, User).join(
            User, EventInvitation.user_id == User.id
        ).filter(
            EventInvitation.event_id == event_id
        ).order_by(EventInvitation.invited_at.desc()).all()
        
        # Obtener info del invitador
        result = []
        for invitation, user in invitations:
            inviter = db.session.get(User, invitation.invited_by) if invitation.invited_by else None
            result.append({
                'id': invitation.id,
                'user_id': user.id,
                'full_name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'status': invitation.status,
                'invited_at': invitation.invited_at.isoformat(),
                'responded_at': invitation.responded_at.isoformat() if invitation.responded_at else None,
                'inviter_name': f"{inviter.first_name} {inviter.last_name}" if inviter else "Sistema",
                'notes': invitation.notes
            })
        
        return result
    
    @staticmethod
    def get_my_invitations(user_id: int):
        """
        Obtiene invitaciones pendientes de un usuario
        """
        from app.models.event import EventInvitation
        
        invitations = db.session.query(EventInvitation, Event).join(
            Event, EventInvitation.event_id == Event.id
        ).filter(
            EventInvitation.user_id == user_id,
            EventInvitation.status == 'pending'
        ).order_by(EventInvitation.invited_at.desc()).all()
        
        return [{
            'invitation_id': inv.id,
            'event_id': event.id,
            'event_title': event.title,
            'event_type': event.type,
            'event_location': event.location,
            'event_date': event.event_date.isoformat() if event.event_date else None,
            'invited_at': inv.invited_at.isoformat(),
            'notes': inv.notes
        } for inv, event in invitations]
    
    @staticmethod
    def cancel_invitation(invitation_id: int):
        """
        Cancela una invitación (solo si está pendiente)
        """
        from app.models.event import EventInvitation
        
        invitation = db.session.get(EventInvitation, invitation_id)
        if not invitation:
            raise ValueError("Invitación no encontrada")
        
        if invitation.status != 'pending':
            raise ValueError("Solo se pueden cancelar invitaciones pendientes")
        
        db.session.delete(invitation)
        db.session.commit()
        return True
    
    @staticmethod
    def update_event_dates(event_id: int, event_date: datetime = None, event_end_date: datetime = None):
        """
        Actualiza las fechas de un evento
        """
        event = db.session.get(Event, event_id)
        if not event:
            raise ValueError("Evento no encontrado")
        
        if event.capacity_type == 'single':
            raise ValueError("Los eventos de capacidad individual usan ventanas de horarios")
        
        event.event_date = event_date
        event.event_end_date = event_end_date
        
        db.session.commit()
        return event
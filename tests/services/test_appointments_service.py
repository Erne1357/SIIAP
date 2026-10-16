"""
AppointmentsService: slot booking, double booking, cancel, change requests,
stale-reservation release and context resolvers.

ACL/scope over HTTP is covered by tests/appointments_scope.
"""

from datetime import date, datetime, time, timedelta

import pytest

from app import db
from app.models.appointment import Appointment, AppointmentChangeRequest
from app.models.event import Event, EventSlot, EventWindow
from app.services.appointments_service import AppointmentAccessDenied, AppointmentsService as AS
from tests.support.factories import make_program, make_user


@pytest.fixture
def cal(app):
    coord = make_user('program_admin')
    prog = make_program(coord)
    ev = Event(program_id=prog.id, type='interview', title='Entrevistas', description='',
               location='Sala 1', created_by=coord.id, capacity_type='single',
               requires_registration=True, status='published')
    db.session.add(ev)
    db.session.flush()
    win = EventWindow(event_id=ev.id, date=date(2026, 5, 4), start_time=time(9), end_time=time(11),
                      slot_minutes=30)
    db.session.add(win)
    db.session.flush()
    slots = []
    base = datetime(2026, 5, 4, 9, 0)
    for i in range(4):
        s = EventSlot(event_window_id=win.id, starts_at=base + timedelta(minutes=30 * i),
                      ends_at=base + timedelta(minutes=30 * (i + 1)), status='free')
        db.session.add(s)
        slots.append(s)
    a1, a2 = make_user('applicant'), make_user('applicant')
    db.session.commit()
    return type('C', (), dict(coord=coord, prog=prog, ev=ev, win=win, slots=slots, a1=a1, a2=a2))


def _assign(c, slot_idx=0, who=None):
    return AS.assign_slot(c.ev.id, c.slots[slot_idx].id, (who or c.a1).id, c.coord.id)


class TestAssignSlot:
    def test_books_slot(self, cal):
        appt = _assign(cal)
        assert appt.status == 'scheduled' and appt.assigned_by == cal.coord.id
        slot = EventSlot.query.get(cal.slots[0].id)
        assert slot.status == 'booked' and slot.held_by == cal.a1.id

    def test_notes_stored(self, cal):
        appt = AS.assign_slot(cal.ev.id, cal.slots[0].id, cal.a1.id, cal.coord.id, notes='traer CV')
        assert appt.notes == 'traer CV'

    def test_double_booking_same_slot_refused(self, cal):
        _assign(cal, 0, cal.a1)
        with pytest.raises(ValueError, match='no está disponible'):
            _assign(cal, 0, cal.a2)
        assert Appointment.query.filter_by(slot_id=cal.slots[0].id).count() == 1

    def test_same_applicant_two_slots_allowed_by_service(self, cal):
        _assign(cal, 0)
        _assign(cal, 1)
        assert Appointment.query.filter_by(applicant_id=cal.a1.id).count() == 2

    def test_unknown_slot(self, cal):
        with pytest.raises(ValueError, match='Slot no encontrado'):
            AS.assign_slot(cal.ev.id, 99999, cal.a1.id, cal.coord.id)

    def test_slot_of_other_event_refused(self, cal):
        other = Event(program_id=cal.prog.id, type='interview', title='Otro', description='',
                      location='', created_by=cal.coord.id, capacity_type='single',
                      requires_registration=True, status='published')
        db.session.add(other)
        db.session.commit()
        with pytest.raises(ValueError, match='no pertenece'):
            AS.assign_slot(other.id, cal.slots[0].id, cal.a1.id, cal.coord.id)
        assert EventSlot.query.get(cal.slots[0].id).status == 'free'

    @pytest.mark.parametrize('status', ['booked', 'held', 'blocked'])
    def test_non_free_slot_refused(self, cal, status):
        cal.slots[0].status = status
        db.session.commit()
        with pytest.raises(ValueError):
            _assign(cal)

    def test_failed_booking_leaves_slot_untouched(self, cal):
        _assign(cal, 0, cal.a1)
        with pytest.raises(ValueError):
            _assign(cal, 0, cal.a2)
        slot = EventSlot.query.get(cal.slots[0].id)
        assert slot.held_by == cal.a1.id


class TestCancelAppointment:
    def test_owner_cancels_and_frees_slot(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, reason='enfermo', acting_user_id=cal.a1.id)
        assert Appointment.query.get(appt.id).status == 'cancelled'
        slot = EventSlot.query.get(cal.slots[0].id)
        assert slot.status == 'free' and slot.held_by is None

    def test_reason_appended_to_notes(self, cal):
        appt = AS.assign_slot(cal.ev.id, cal.slots[0].id, cal.a1.id, cal.coord.id, notes='base')
        AS.cancel_appointment(appt.id, reason='x', acting_user_id=cal.a1.id)
        assert Appointment.query.get(appt.id).notes == 'base\n[CANCEL]: x'

    def test_reason_without_prior_notes(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, reason='x', as_admin=True)
        assert Appointment.query.get(appt.id).notes == '[CANCEL]: x'

    def test_stranger_cannot_cancel(self, cal):
        appt = _assign(cal)
        with pytest.raises(AppointmentAccessDenied):
            AS.cancel_appointment(appt.id, acting_user_id=cal.a2.id)
        assert Appointment.query.get(appt.id).status == 'scheduled'
        assert EventSlot.query.get(cal.slots[0].id).status == 'booked'

    def test_no_actor_fails_closed(self, cal):
        appt = _assign(cal)
        with pytest.raises(AppointmentAccessDenied):
            AS.cancel_appointment(appt.id)

    def test_admin_flag_bypasses_ownership(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, as_admin=True)
        assert Appointment.query.get(appt.id).status == 'cancelled'

    def test_cancel_twice_refused(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, acting_user_id=cal.a1.id)
        with pytest.raises(ValueError, match='ya estaba cancelada'):
            AS.cancel_appointment(appt.id, acting_user_id=cal.a1.id)
        assert 'CANCEL' not in (Appointment.query.get(appt.id).notes or '')

    def test_unknown_appointment(self, cal):
        with pytest.raises(ValueError, match='no encontrada'):
            AS.cancel_appointment(99999, as_admin=True)

    def test_slot_can_be_rebooked_after_cancel(self, cal):
        first = _assign(cal, 0, cal.a1)
        AS.cancel_appointment(first.id, acting_user_id=cal.a1.id)
        second = _assign(cal, 0, cal.a2)
        assert second.applicant_id == cal.a2.id and second.status == 'scheduled'

    def test_rebooking_releases_dead_reservation_row(self, cal):
        first = _assign(cal, 0, cal.a1)
        AS.cancel_appointment(first.id, acting_user_id=cal.a1.id)
        _assign(cal, 0, cal.a2)
        assert Appointment.query.filter_by(applicant_id=cal.a1.id).count() == 0
        assert Appointment.query.filter_by(slot_id=cal.slots[0].id).count() == 1

    def test_cancelled_slot_has_no_active_appointment(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, acting_user_id=cal.a1.id)
        assert AS.get_active_appointment_for_slot(cal.slots[0].id) is None

    def test_booked_slot_has_active_appointment(self, cal):
        appt = _assign(cal)
        assert AS.get_active_appointment_for_slot(cal.slots[0].id).id == appt.id

    def test_release_stale_reservation_counts(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, acting_user_id=cal.a1.id)
        assert AS._release_stale_reservation(cal.slots[0].id) == 1
        assert AS._release_stale_reservation(cal.slots[0].id) == 0

    def test_release_keeps_requested_row(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, acting_user_id=cal.a1.id)
        assert AS._release_stale_reservation(cal.slots[0].id, keep_appointment_id=appt.id) == 0


class TestChangeRequests:
    def test_owner_requests_change(self, cal):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id, reason='clase', suggestions='tarde')
        assert acr.status == 'pending' and acr.reason == 'clase'

    def test_stranger_cannot_request(self, cal):
        appt = _assign(cal)
        with pytest.raises(AppointmentAccessDenied):
            AS.request_change(appt.id, cal.a2.id)
        assert AppointmentChangeRequest.query.count() == 0

    def test_admin_may_request_on_behalf(self, cal):
        appt = _assign(cal)
        assert AS.request_change(appt.id, cal.coord.id, as_admin=True).status == 'pending'

    def test_cancelled_appointment_cannot_be_changed(self, cal):
        appt = _assign(cal)
        AS.cancel_appointment(appt.id, acting_user_id=cal.a1.id)
        with pytest.raises(ValueError, match='vigente'):
            AS.request_change(appt.id, cal.a1.id)

    def test_second_request_updates_pending_one(self, cal):
        appt = _assign(cal)
        first = AS.request_change(appt.id, cal.a1.id, reason='uno')
        second = AS.request_change(appt.id, cal.a1.id, reason='dos')
        assert first.id == second.id
        assert AppointmentChangeRequest.query.count() == 1
        assert AppointmentChangeRequest.query.one().reason == 'dos'

    def test_unknown_appointment(self, cal):
        with pytest.raises(ValueError):
            AS.request_change(99999, cal.a1.id)

    def test_accept_moves_appointment_and_swaps_slots(self, cal):
        appt = _assign(cal, 0)
        acr = AS.request_change(appt.id, cal.a1.id)
        AS.decide_change(acr.id, 'accepted', cal.coord.id, new_slot_id=cal.slots[2].id)
        assert Appointment.query.get(appt.id).slot_id == cal.slots[2].id
        assert EventSlot.query.get(cal.slots[0].id).status == 'free'
        new = EventSlot.query.get(cal.slots[2].id)
        assert new.status == 'booked' and new.held_by == cal.a1.id
        done = AppointmentChangeRequest.query.get(acr.id)
        assert done.status == 'accepted' and done.decided_by == cal.coord.id
        assert done.decided_at is not None

    def test_accept_needs_new_slot(self, cal):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        with pytest.raises(ValueError, match='new_slot_id'):
            AS.decide_change(acr.id, 'accepted', cal.coord.id)

    def test_accept_into_booked_slot_refused_and_nothing_moves(self, cal):
        appt = _assign(cal, 0, cal.a1)
        _assign(cal, 1, cal.a2)
        acr = AS.request_change(appt.id, cal.a1.id)
        with pytest.raises(ValueError, match='no está disponible'):
            AS.decide_change(acr.id, 'accepted', cal.coord.id, new_slot_id=cal.slots[1].id)
        db.session.rollback()
        assert Appointment.query.get(appt.id).slot_id == cal.slots[0].id
        assert EventSlot.query.get(cal.slots[0].id).status == 'booked'

    def test_accept_slot_from_other_event_refused(self, cal):
        other = Event(program_id=cal.prog.id, type='interview', title='O', description='',
                      location='', created_by=cal.coord.id, capacity_type='single',
                      requires_registration=True, status='published')
        db.session.add(other)
        db.session.flush()
        w = EventWindow(event_id=other.id, date=date(2026, 5, 5), start_time=time(9),
                        end_time=time(10), slot_minutes=30)
        db.session.add(w)
        db.session.flush()
        foreign = EventSlot(event_window_id=w.id, starts_at=datetime(2026, 5, 5, 9),
                            ends_at=datetime(2026, 5, 5, 9, 30), status='free')
        db.session.add(foreign)
        db.session.commit()
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        with pytest.raises(ValueError, match='no pertenece'):
            AS.decide_change(acr.id, 'accepted', cal.coord.id, new_slot_id=foreign.id)

    def test_accept_into_slot_freed_by_cancellation(self, cal):
        appt = _assign(cal, 0, cal.a1)
        other = _assign(cal, 1, cal.a2)
        AS.cancel_appointment(other.id, acting_user_id=cal.a2.id)
        acr = AS.request_change(appt.id, cal.a1.id)
        AS.decide_change(acr.id, 'accepted', cal.coord.id, new_slot_id=cal.slots[1].id)
        assert Appointment.query.get(appt.id).slot_id == cal.slots[1].id

    @pytest.mark.parametrize('status', ['rejected', 'cancelled'])
    def test_reject_and_cancel_keep_appointment(self, cal, status):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        AS.decide_change(acr.id, status, cal.coord.id)
        assert AppointmentChangeRequest.query.get(acr.id).status == status
        assert Appointment.query.get(appt.id).slot_id == cal.slots[0].id
        assert EventSlot.query.get(cal.slots[0].id).status == 'booked'

    def test_invalid_status(self, cal):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        with pytest.raises(ValueError, match='status inválido'):
            AS.decide_change(acr.id, 'maybe', cal.coord.id)

    def test_unknown_request(self, cal):
        with pytest.raises(ValueError):
            AS.decide_change(99999, 'rejected', cal.coord.id)


class TestContextResolvers:
    def test_appointment_context(self, cal):
        appt = _assign(cal)
        ctx = AS.get_appointment_context(appt.id)
        assert ctx['event'].id == cal.ev.id and ctx['program_id'] == cal.prog.id
        assert ctx['event_title'] == 'Entrevistas' and ctx['slot'].id == cal.slots[0].id

    def test_missing_appointment_context(self, cal):
        assert AS.get_appointment_context(99999) is None

    def test_slot_context(self, cal):
        ctx = AS.get_slot_context(cal.slots[1].id)
        assert ctx['window'].id == cal.win.id and ctx['program_id'] == cal.prog.id

    def test_missing_slot_context(self, cal):
        assert AS.get_slot_context(99999) is None

    def test_change_request_context(self, cal):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        ctx = AS.get_change_request_context(acr.id)
        assert ctx['change_request'].id == acr.id and ctx['appointment'].id == appt.id

    def test_missing_change_request_context(self, cal):
        assert AS.get_change_request_context(99999) is None

    def test_institutional_event_has_null_program(self, cal):
        cal.ev.program_id = None
        db.session.commit()
        appt = _assign(cal)
        assert AS.get_appointment_context(appt.id)['program_id'] is None


class TestListings:
    def test_list_of_user_includes_every_status(self, cal):
        a = _assign(cal, 0)
        b = _assign(cal, 1)
        AS.cancel_appointment(b.id, acting_user_id=cal.a1.id)
        assert {x.id for x in AS.list_appointments_of_user(cal.a1.id)} == {a.id, b.id}

    def test_list_scoped_to_user(self, cal):
        _assign(cal, 0, cal.a1)
        assert AS.list_appointments_of_user(cal.a2.id) == []

    def test_active_contexts_only_scheduled_ordered_by_time(self, cal):
        late = _assign(cal, 3)
        early = _assign(cal, 0)
        dead = _assign(cal, 1)
        AS.cancel_appointment(dead.id, acting_user_id=cal.a1.id)
        ctxs = AS.list_active_appointment_contexts(cal.a1.id)
        assert [c['appointment'].id for c in ctxs] == [early.id, late.id]

    def test_active_context_carries_pending_change(self, cal):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        ctx = AS.list_active_appointment_contexts(cal.a1.id)[0]
        assert ctx['pending_change'].id == acr.id

    def test_decided_change_not_pending(self, cal):
        appt = _assign(cal)
        acr = AS.request_change(appt.id, cal.a1.id)
        AS.decide_change(acr.id, 'rejected', cal.coord.id)
        assert AS.list_active_appointment_contexts(cal.a1.id)[0]['pending_change'] is None

    def test_done_appointments_not_active(self, cal):
        appt = _assign(cal)
        appt.status = 'done'
        db.session.commit()
        assert AS.list_active_appointment_contexts(cal.a1.id) == []


class TestThirdPartyAssignment:
    def test_third_party(self, cal):
        appt = _assign(cal)
        assert AS._assignment_is_third_party(appt) is True

    def test_self_booking_is_not_third_party(self, cal):
        appt = AS.assign_slot(cal.ev.id, cal.slots[0].id, cal.a1.id, cal.a1.id)
        assert AS._assignment_is_third_party(appt) is False

    def test_deleted_assigner_fails_closed(self, cal):
        appt = _assign(cal)
        appt.assigned_by = None
        assert AS._assignment_is_third_party(appt) is False

    def test_none(self):
        assert AS._assignment_is_third_party(None) is False

    def test_read_acl_none_inputs(self, cal):
        assert AS.user_may_read_event_of_appointment(None, None, None) is False

    def test_owner_with_third_party_assignment_may_read_event(self, cal):
        appt = _assign(cal)
        assert AS.user_may_read_event_of_appointment(cal.a1, appt, cal.ev) is True

    def test_other_applicant_may_not_read_private_event(self, cal):
        cal.ev.visibility = 'private'
        cal.ev.visible_to_students = False
        db.session.commit()
        appt = _assign(cal)
        assert AS.user_may_read_event_of_appointment(cal.a2, appt, cal.ev) is False

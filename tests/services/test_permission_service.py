"""
permission_service: effective permission listing, delegation and role overrides.

has_permission() itself is covered by tests/test_permissions.py; this file
covers the service layer plus the catalogue kill-switch (Permission.is_active)
across every grant path, and per-request cache isolation.
"""

from datetime import timedelta

import pytest
from freezegun import freeze_time

from app import db
from app.models.permission import Permission
from app.models.role_permission import RolePermissionOverride
from app.models.role_permission_audit import RolePermissionAudit
from app.models.user_permission import UserPermission
from app.services import permission_service as ps
from app.services.permission_service import PermissionError as PermError
from app.utils.datetime_utils import now_local
from tests.support.factories import (
    get_or_create_permission,
    get_or_create_role,
    grant,
    make_program,
    make_user,
)

DELEGATE = 'permissions.api.delegate'
REVOKE = 'permissions.api.revoke_delegation'
WORK = 'acceptance.api.list_applicants'


def _codes(user_id, program_id=None):
    return {p['codename']: p for p in ps.get_user_effective_permissions(user_id, program_id)}


def _delegation(user, perm, granter, program=None, **kw):
    p = get_or_create_permission(perm)
    up = UserPermission(user.id, p.id, granter.id,
                        program_id=program.id if program else None, **kw)
    db.session.add(up)
    db.session.commit()
    return up


@pytest.fixture
def world(app):
    role = get_or_create_role('program_admin')
    grant(role, DELEGATE, REVOKE, WORK, 'events.api.manage')
    coord = make_user('program_admin')
    other_coord = make_user('program_admin')
    program = make_program(coord)
    other_program = make_program(other_coord)
    grantee = make_user('social_service')
    db.session.commit()
    return type('W', (), dict(coord=coord, other=other_coord, program=program,
                              other_program=other_program, grantee=grantee))


class TestEffectivePermissions:
    def test_role_grants_listed_with_source(self, world):
        c = _codes(world.coord.id)
        assert c[WORK]['source'] == 'role'

    def test_user_without_grants_is_empty(self, world):
        assert _codes(world.grantee.id) == {}

    def test_delegation_listed(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        entry = _codes(world.grantee.id)[WORK]
        assert entry['source'] == 'delegation' and entry['granted_by'] == world.coord.id

    def test_role_source_wins_over_delegation(self, world):
        _delegation(world.coord, WORK, world.other, world.other_program)
        assert _codes(world.coord.id)[WORK]['source'] == 'role'

    def test_override_listed_as_override(self, world):
        role = get_or_create_role('social_service')
        perm = get_or_create_permission('reports.api.view')
        db.session.add(RolePermissionOverride(role.id, perm.id))
        db.session.commit()
        assert _codes(world.grantee.id)['reports.api.view']['source'] == 'override'

    def test_revoked_override_not_listed(self, world):
        role = get_or_create_role('social_service')
        perm = get_or_create_permission('reports.api.view')
        ov = RolePermissionOverride(role.id, perm.id)
        db.session.add(ov)
        db.session.commit()
        ov.revoke()
        db.session.commit()
        assert 'reports.api.view' not in _codes(world.grantee.id)

    def test_expired_delegation_ignored_by_has_permission(self, world, app):
        with freeze_time('2026-03-01 10:00:00'):
            _delegation(world.grantee, WORK, world.coord, world.program,
                        expires_at=now_local() + timedelta(hours=1))
        from app.models.user import User
        with freeze_time('2026-03-01 09:00:00'):
            with app.app_context():
                assert User.query.get(world.grantee.id).has_permission(WORK) is True
        with freeze_time('2026-03-01 11:30:00'):
            with app.app_context():
                assert User.query.get(world.grantee.id).has_permission(WORK) is False

    # Regression: is_expired compared aware now_local() with the naive DB expires_at and raised TypeError.
    def test_expired_delegation_ignored_in_effective_list(self, world):
        with freeze_time('2026-03-01 10:00:00'):
            _delegation(world.grantee, WORK, world.coord, world.program,
                        expires_at=now_local() + timedelta(hours=1))
        db.session.expire_all()
        with freeze_time('2026-03-01 11:30:00'):
            assert WORK not in _codes(world.grantee.id)

    # Regression: is_expired compared aware now_local() with the naive DB expires_at and raised TypeError.
    def test_unexpired_delegation_listed_after_db_roundtrip(self, world):
        with freeze_time('2026-03-01 10:00:00'):
            _delegation(world.grantee, WORK, world.coord, world.program,
                        expires_at=now_local() + timedelta(hours=1))
            db.session.expire_all()
            assert WORK in _codes(world.grantee.id)

    def test_revoked_delegation_ignored(self, world):
        up = _delegation(world.grantee, WORK, world.coord, world.program)
        up.revoke()
        db.session.commit()
        assert WORK not in _codes(world.grantee.id)

    def test_inactive_permission_hidden_everywhere(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        Permission.query.filter_by(codename=WORK).update({'is_active': False})
        db.session.commit()
        assert WORK not in _codes(world.grantee.id)
        assert WORK not in _codes(world.coord.id)   # role grant too

    def test_program_filter_includes_global_and_matching(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        _delegation(world.grantee, 'events.api.manage', world.coord, None)
        c = _codes(world.grantee.id, world.program.id)
        assert WORK in c and 'events.api.manage' in c

    def test_program_filter_excludes_other_program(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        assert WORK not in _codes(world.grantee.id, world.other_program.id)

    def test_unknown_user_404(self, app):
        from werkzeug.exceptions import NotFound
        with pytest.raises(NotFound):
            ps.get_user_effective_permissions(99999)

    def test_delegatable_excludes_permission_system_and_pages(self, world):
        grant(get_or_create_role('program_admin'), 'programs.page.view')
        r = {p['codename'] for p in ps.get_delegatable_permissions(world.coord.id)}
        assert WORK in r
        assert DELEGATE not in r and REVOKE not in r
        assert 'programs.page.view' not in r

    def test_delegatable_excludes_self_service(self, world):
        grant(get_or_create_role('program_admin'), 'users.api.me')
        r = {p['codename'] for p in ps.get_delegatable_permissions(world.coord.id)}
        assert 'users.api.me' not in r


class TestCatalogueKillSwitch:
    """Permission.is_active=False must stop every path that feeds has_permission()."""

    def test_role_grant_stops_when_deactivated(self, world, app):
        assert world.coord.has_permission(WORK)
        Permission.query.filter_by(codename=WORK).update({'is_active': False})
        db.session.commit()
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.coord.id).has_permission(WORK) is False

    def test_delegation_stops_when_deactivated(self, world, app):
        _delegation(world.grantee, 'events.api.manage', world.coord, world.program)
        Permission.query.filter_by(codename='events.api.manage').update({'is_active': False})
        db.session.commit()
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission('events.api.manage') is False

    def test_override_stops_when_deactivated(self, world, app):
        role = get_or_create_role('social_service')
        perm = get_or_create_permission('reports.api.view')
        db.session.add(RolePermissionOverride(role.id, perm.id))
        db.session.commit()
        perm.is_active = False
        db.session.commit()
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission('reports.api.view') is False

    def test_deactivated_delegation_does_not_grant_scope(self, world, app):
        _delegation(world.grantee, WORK, world.coord, world.program)
        Permission.query.filter_by(codename=WORK).update({'is_active': False})
        db.session.commit()
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).get_accessible_program_ids() == set()


class TestPerRequestCache:
    def test_cache_hides_change_inside_same_request(self, world):
        assert world.grantee.has_permission(WORK) is False
        _delegation(world.grantee, WORK, world.coord, world.program)
        # same flask.g -> still the cached answer
        assert world.grantee.has_permission(WORK) is False

    def test_new_request_sees_the_change(self, world, app):
        assert world.grantee.has_permission(WORK) is False
        _delegation(world.grantee, WORK, world.coord, world.program)
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission(WORK) is True

    def test_cache_is_per_user(self, world):
        assert world.coord.has_permission(WORK) is True
        assert world.grantee.has_permission(WORK) is False

    def test_cache_does_not_leak_to_next_request_after_revocation(self, world, app):
        up = _delegation(world.grantee, WORK, world.coord, world.program)
        assert world.grantee.has_permission(WORK) is True
        up.revoke()
        db.session.commit()
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission(WORK) is False

    def test_expiry_evaluated_per_request_not_cached_forever(self, world, app):
        with freeze_time('2026-03-01 10:00:00'):
            _delegation(world.grantee, WORK, world.coord, world.program,
                        expires_at=now_local() + timedelta(minutes=30))
            assert world.grantee.has_permission(WORK) is True
        with freeze_time('2026-03-01 11:00:00'):
            with app.app_context():
                from app.models.user import User
                assert User.query.get(world.grantee.id).has_permission(WORK) is False


class TestDelegatePermission:
    def test_success_creates_row(self, world):
        up = ps.delegate_permission(world.coord.id, world.grantee.id, WORK,
                                    program_id=world.program.id, note='n')
        assert up.is_active and up.program_id == world.program.id and up.note == 'n'
        assert up.granted_by == world.coord.id

    def test_cannot_delegate_to_self(self, world):
        with pytest.raises(PermError, match='ti mismo'):
            ps.delegate_permission(world.coord.id, world.coord.id, WORK, world.program.id)

    def test_granter_must_hold_delegate_permission(self, world):
        with pytest.raises(PermError):
            ps.delegate_permission(world.grantee.id, world.other.id, WORK, world.program.id)

    def test_cannot_delegate_what_you_do_not_have(self, world):
        get_or_create_permission('secret.api.thing')
        db.session.commit()
        with pytest.raises(PermError, match='no lo tienes'):
            ps.delegate_permission(world.coord.id, world.grantee.id, 'secret.api.thing',
                                   world.program.id)

    def test_inactive_permission_rejected(self, world):
        Permission.query.filter_by(codename=WORK).update({'is_active': False})
        db.session.commit()
        with pytest.raises(PermError):
            ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)

    def test_permission_system_not_delegatable(self, world):
        with pytest.raises(PermError, match='sistema de permisos'):
            ps.delegate_permission(world.coord.id, world.grantee.id, DELEGATE,
                                   world.program.id)

    def test_self_service_not_delegatable(self, world):
        grant(get_or_create_role('program_admin'), 'users.api.me')
        db.session.commit()
        with pytest.raises(PermError, match='cuenta propia'):
            ps.delegate_permission(world.coord.id, world.grantee.id, 'users.api.me',
                                   world.program.id)

    def test_out_of_scope_program_rejected(self, world):
        with pytest.raises(PermError, match='alcance'):
            ps.delegate_permission(world.coord.id, world.grantee.id, WORK,
                                   world.other_program.id)

    def test_all_programs_requires_global_scope(self, world):
        with pytest.raises(PermError, match='jefe de posgrado'):
            ps.delegate_permission(world.coord.id, world.grantee.id, WORK, None)

    def test_duplicate_active_rejected(self, world):
        ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)
        with pytest.raises(PermError, match='ya tiene'):
            ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)

    def test_garbage_program_id(self, world):
        with pytest.raises(PermError, match='program_id'):
            ps.delegate_permission(world.coord.id, world.grantee.id, WORK, 'abc')

    def test_unknown_users(self, world):
        with pytest.raises(PermError):
            ps.delegate_permission(99999, world.grantee.id, WORK, world.program.id)
        with pytest.raises(PermError):
            ps.delegate_permission(world.coord.id, 99999, WORK, world.program.id)

    def test_expiry_stored(self, world):
        exp = now_local() + timedelta(days=2)
        up = ps.delegate_permission(world.coord.id, world.grantee.id, WORK,
                                    world.program.id, expires_at=exp)
        assert up.expires_at.replace(tzinfo=None) == exp.replace(tzinfo=None)

    def test_delegation_grants_capability_to_grantee(self, world, app):
        ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)
        with app.app_context():
            from app.models.user import User
            g = User.query.get(world.grantee.id)
            assert g.has_permission(WORK)
            assert g.get_accessible_program_ids() == {world.program.id}

    def test_global_scope_holder_may_delegate_to_all_programs(self, world):
        boss_role = get_or_create_role('postgraduate_admin')
        grant(boss_role, DELEGATE, WORK, 'academic_periods.api.create')
        boss = make_user('postgraduate_admin')
        db.session.commit()
        up = ps.delegate_permission(boss.id, world.grantee.id, WORK, None)
        assert up.program_id is None

    # Regression: is_expired raised TypeError; once fixed, re-delegating hit uq_user_permission_active (IntegrityError).
    def test_reissue_after_expired_delegation_reuses_the_row(self, world):
        """uq_user_permission_active allows one row per triple: re-issue updates it."""
        with freeze_time('2026-03-01 10:00:00'):
            first = ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id,
                                           expires_at=now_local() + timedelta(hours=1))
        db.session.expire_all()
        with freeze_time('2026-03-02 10:00:00'):
            again = ps.delegate_permission(world.coord.id, world.grantee.id, WORK,
                                           world.program.id)
            assert again.id == first.id
            assert again.is_active is True and again.expires_at is None
            assert UserPermission.query.filter_by(user_id=world.grantee.id).count() == 1
            assert WORK in _codes(world.grantee.id)

    def test_reissue_after_revocation_reuses_the_row(self, world):
        first = ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)
        ps.revoke_delegation(world.coord.id, first.id)
        again = ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)
        assert again.id == first.id and again.is_active is True

    def test_live_delegation_still_rejected_as_duplicate(self, world):
        ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)
        with pytest.raises(PermError):
            ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)


class TestRevokeDelegation:
    def _make(self, world):
        return ps.delegate_permission(world.coord.id, world.grantee.id, WORK,
                                      world.program.id)

    def test_granter_can_revoke(self, world):
        up = self._make(world)
        ps.revoke_delegation(world.coord.id, up.id)
        assert UserPermission.query.get(up.id).is_active is False

    def test_revoked_grantee_loses_permission(self, world, app):
        up = self._make(world)
        ps.revoke_delegation(world.coord.id, up.id)
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission(WORK) is False

    def test_double_revoke(self, world):
        up = self._make(world)
        ps.revoke_delegation(world.coord.id, up.id)
        with pytest.raises(PermError, match='ya fue revocada'):
            ps.revoke_delegation(world.coord.id, up.id)

    def test_unknown_delegation(self, world):
        with pytest.raises(PermError):
            ps.revoke_delegation(world.coord.id, 424242)

    def test_unrelated_coordinator_cannot_revoke(self, world):
        up = self._make(world)
        with pytest.raises(PermError, match='No tienes permiso'):
            ps.revoke_delegation(world.other.id, up.id)
        assert UserPermission.query.get(up.id).is_active is True

    def test_grantee_cannot_revoke_own_delegation(self, world):
        up = self._make(world)
        with pytest.raises(PermError):
            ps.revoke_delegation(world.grantee.id, up.id)

    def test_global_admin_can_revoke(self, world):
        up = self._make(world)
        boss = make_user('postgraduate_admin')
        grant(get_or_create_role('postgraduate_admin'), 'academic_periods.api.create')
        db.session.commit()
        ps.revoke_delegation(boss.id, up.id)
        assert UserPermission.query.get(up.id).is_active is False

    def test_scoped_revoker_with_permission_can_revoke(self, world):
        up = ps.delegate_permission(world.coord.id, world.grantee.id, WORK, world.program.id)
        second = make_user('program_admin')
        world.program.coordinator_id = second.id
        db.session.commit()
        ps.revoke_delegation(second.id, up.id)
        assert UserPermission.query.get(up.id).is_active is False


class TestDelegationVisibility:
    def test_self_sees_all(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        assert len(ps.get_user_delegations_for_viewer(world.grantee, world.grantee.id)) == 1

    def test_granter_sees_own_grants(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        assert len(ps.get_user_delegations_for_viewer(world.coord, world.grantee.id)) == 1

    def test_unrelated_viewer_sees_nothing_not_error(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        assert ps.get_user_delegations_for_viewer(world.other, world.grantee.id) == []

    def test_unknown_target_looks_like_no_delegations(self, world):
        assert ps.get_user_delegations_for_viewer(world.coord, 99999) == []

    def test_global_viewer_sees_everything(self, world):
        _delegation(world.grantee, WORK, world.coord, world.program)
        grant(get_or_create_role('postgraduate_admin'), 'academic_periods.api.create')
        boss = make_user('postgraduate_admin')
        db.session.commit()
        assert len(ps.get_user_delegations_for_viewer(boss, world.grantee.id)) == 1


class TestRoleOverrides:
    def test_add_override_creates_row_and_audit(self, world):
        role = get_or_create_role('social_service')
        get_or_create_permission('reports.api.view')
        db.session.commit()
        ov = ps.add_role_override(role.id, 'reports.api.view', world.coord.id, reason='r')
        assert ov.is_active
        audit = RolePermissionAudit.query.one()
        assert audit.action == 'grant' and audit.performed_by == world.coord.id
        assert audit.reason == 'r'

    def test_duplicate_active_override(self, world):
        role = get_or_create_role('social_service')
        get_or_create_permission('reports.api.view')
        db.session.commit()
        ps.add_role_override(role.id, 'reports.api.view', world.coord.id)
        with pytest.raises(PermError, match='ya tiene un override'):
            ps.add_role_override(role.id, 'reports.api.view', world.coord.id)

    def test_global_scope_cannot_be_overridden(self, world):
        role = get_or_create_role('program_admin')
        get_or_create_permission('academic_periods.api.create')
        db.session.commit()
        with pytest.raises(PermError, match='alcance global'):
            ps.add_role_override(role.id, 'academic_periods.api.create', world.coord.id)
        assert RolePermissionOverride.query.count() == 0

    def test_inactive_permission_rejected(self, world):
        role = get_or_create_role('social_service')
        p = get_or_create_permission('reports.api.view')
        p.is_active = False
        db.session.commit()
        with pytest.raises(PermError):
            ps.add_role_override(role.id, 'reports.api.view', world.coord.id)

    def test_unknown_role(self, world):
        with pytest.raises(PermError):
            ps.add_role_override(99999, 'x.api.y', world.coord.id)

    def test_revert_deactivates_and_audits(self, world, app):
        role = get_or_create_role('social_service')
        get_or_create_permission('reports.api.view')
        db.session.commit()
        ps.add_role_override(role.id, 'reports.api.view', world.coord.id)
        ps.revert_role_override(role.id, 'reports.api.view', world.coord.id)
        assert RolePermissionOverride.query.one().is_active is False
        assert [a.action for a in RolePermissionAudit.query.order_by(RolePermissionAudit.id)] \
            == ['grant', 'revert']
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission('reports.api.view') is False

    def test_override_takes_effect_for_role_members(self, world, app):
        role = get_or_create_role('social_service')
        get_or_create_permission('reports.api.view')
        db.session.commit()
        ps.add_role_override(role.id, 'reports.api.view', world.coord.id)
        with app.app_context():
            from app.models.user import User
            assert User.query.get(world.grantee.id).has_permission('reports.api.view') is True

    def test_revert_without_active_override(self, world):
        role = get_or_create_role('social_service')
        get_or_create_permission('reports.api.view')
        db.session.commit()
        with pytest.raises(PermError, match='No hay override'):
            ps.revert_role_override(role.id, 'reports.api.view', world.coord.id)

    def test_revert_unknown_permission(self, world):
        with pytest.raises(PermError):
            ps.revert_role_override(1, 'nope.api.nope', world.coord.id)

    def test_readd_after_revert_allowed(self, world):
        role = get_or_create_role('social_service')
        get_or_create_permission('reports.api.view')
        db.session.commit()
        ps.add_role_override(role.id, 'reports.api.view', world.coord.id)
        ps.revert_role_override(role.id, 'reports.api.view', world.coord.id)
        ps.add_role_override(role.id, 'reports.api.view', world.coord.id)
        assert RolePermissionOverride.query.filter_by(is_active=True).count() == 1

    def test_audit_log_filters_and_pages(self, world):
        role = get_or_create_role('social_service')
        for c in ('a.api.one', 'a.api.two', 'a.api.three'):
            get_or_create_permission(c)
        db.session.commit()
        for c in ('a.api.one', 'a.api.two', 'a.api.three'):
            ps.add_role_override(role.id, c, world.coord.id)
        log = ps.get_audit_log(role_id=role.id, limit=2)
        assert log['total'] == 3 and len(log['items']) == 2
        assert ps.get_audit_log(role_id=99999)['total'] == 0

    def test_list_all_permissions_only_active(self, world):
        p = get_or_create_permission('zzz.api.old')
        p.is_active = False
        db.session.commit()
        names = {x['codename'] if isinstance(x, dict) else x.codename
                 for x in ps.list_all_permissions()}
        assert 'zzz.api.old' not in names and WORK in names

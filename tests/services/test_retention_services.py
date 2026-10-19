"""HistoryRetentionService (UserHistory pruning) and RetentionService (submission policies)."""

from datetime import date, datetime, timedelta

import pytest
from freezegun import freeze_time

from app import db
from app.models import Archive, Phase, ProgramStep, Step, Submission
from app.models.retention_policy import RetentionPolicy
from app.models.user_history import UserHistory
from app.services.history_retention_service import HistoryRetentionService as HR
from app.services.retention_service import RetentionService as RS
from tests.support.factories import enroll, make_program, make_user

NOW = datetime(2026, 6, 1, 12, 0, 0)


def _hist(user, action, ts):
    h = UserHistory(user_id=user.id, admin_id=None, action=action, details='d')
    h.timestamp = ts
    db.session.add(h)
    db.session.commit()
    return h.id


def _years_ago(years, extra_days=10):
    return NOW - timedelta(days=years * 365 + extra_days)


@pytest.fixture
def people(app):
    prog = make_program()
    active = make_user('student')
    enroll(active, prog, 'enrolled')
    inactive = make_user('student', is_active=False)
    enroll(inactive, prog, 'enrolled')
    graduate = make_user('student')
    enroll(graduate, prog, 'enrolled')
    nobody = make_user('applicant')          # no program at all -> classed as inactive
    db.session.commit()
    return type('P', (), dict(active=active, inactive=inactive, graduate=graduate, nobody=nobody))


class TestClassification:
    # Regression: _classify_users selected the nonexistent UserProgram.graduation_date,
    # so it raised AttributeError and cleanup_old_history() could never run.
    @freeze_time(NOW)
    def test_real_classifier_runs(self, people):
        c = HR._classify_users()
        assert people.active.id in c['active']
        assert people.graduate.id in c['active']          # enrolled, nothing completed yet
        assert people.inactive.id in c['inactive']
        assert people.nobody.id in c['inactive']
        assert c['graduated'] == []

    @freeze_time(NOW)
    def test_completed_final_semester_counts_as_graduated(self, people):
        from app.models.semester_enrollment import SemesterEnrollment
        from app.models.user_program import UserProgram
        from tests.support.factories import make_academic_period

        up = UserProgram.query.filter_by(user_id=people.graduate.id).one()
        up.program.duration_semesters = 2
        period = make_academic_period()
        db.session.add(SemesterEnrollment(user_program_id=up.id, academic_period_id=period.id,
                                          semester_number=1, status='completed'))
        db.session.commit()
        assert people.graduate.id in HR._classify_users()['active']   # 1 of 2 semesters

        # One enrollment per period (uq_semester_enrollment_up_period).
        next_period = make_academic_period(is_active=False)
        db.session.add(SemesterEnrollment(user_program_id=up.id, academic_period_id=next_period.id,
                                          semester_number=2, status='completed'))
        db.session.commit()
        c = HR._classify_users()
        assert c['graduated'] == [people.graduate.id]
        assert people.graduate.id not in c['active']


@pytest.fixture
def classify(people, monkeypatch):
    """Fixed classification so the window tests do not depend on enrollment data."""
    monkeypatch.setattr(HR, '_classify_users', staticmethod(lambda: {
        'active': [people.active.id],
        'graduated': [people.graduate.id],
        'inactive': [people.inactive.id, people.nobody.id],
    }))


@pytest.mark.usefixtures('classify')
class TestCleanup:
    @freeze_time(NOW)
    def test_dry_run_reports_but_keeps_rows(self, people):
        old = _hist(people.active, 'profile_updated', _years_ago(3))
        stats = HR.cleanup_old_history(dry_run=True)
        assert stats['dry_run'] is True and stats['entries_to_delete'] == 1
        assert stats['entries_deleted'] == 0
        assert UserHistory.query.get(old) is not None

    @freeze_time(NOW)
    def test_default_is_dry_run(self, people):
        _hist(people.active, 'profile_updated', _years_ago(3))
        assert HR.cleanup_old_history()['dry_run'] is True
        assert UserHistory.query.count() == 1

    @freeze_time(NOW)
    def test_real_run_deletes_only_expired_rows(self, people):
        old = _hist(people.active, 'profile_updated', _years_ago(3))
        recent = _hist(people.active, 'profile_updated', NOW - timedelta(days=100))
        stats = HR.cleanup_old_history(dry_run=False)
        assert stats['entries_deleted'] == 1
        assert UserHistory.query.get(old) is None
        assert UserHistory.query.get(recent) is not None

    @freeze_time(NOW)
    @pytest.mark.parametrize('action', sorted(HR.CRITICAL_ACTIONS))
    def test_critical_actions_never_deleted(self, people, action):
        if action not in __import__('app.services.user_history_service', fromlist=['x']).UserHistoryService.ACTIONS:
            pass   # retention works on raw rows; registry is irrelevant here
        keep = _hist(people.active, action, _years_ago(20))
        HR.cleanup_old_history(dry_run=False)
        assert UserHistory.query.get(keep) is not None

    @freeze_time(NOW)
    def test_per_category_windows(self, people):
        # defaults: active 3y, graduated 7y, inactive 2y
        a = _hist(people.active, 'profile_updated', _years_ago(2.5, 0))     # kept
        g = _hist(people.graduate, 'profile_updated', _years_ago(5))        # kept (<7y)
        i = _hist(people.inactive, 'profile_updated', _years_ago(2))        # purged
        g_old = _hist(people.graduate, 'profile_updated', _years_ago(8))    # purged
        HR.cleanup_old_history(dry_run=False)
        assert UserHistory.query.get(a) is not None and UserHistory.query.get(g) is not None
        assert UserHistory.query.get(i) is None and UserHistory.query.get(g_old) is None

    @freeze_time(NOW)
    def test_custom_config_applies(self, people):
        row = _hist(people.active, 'profile_updated', NOW - timedelta(days=400))
        cfg = {'active_users': 1, 'graduated_users': 7, 'inactive_users': 2}
        HR.cleanup_old_history(dry_run=False, retention_config=cfg)
        assert UserHistory.query.get(row) is None

    @freeze_time(NOW)
    def test_minus_one_means_forever(self, people):
        row = _hist(people.active, 'profile_updated', _years_ago(30))
        cfg = {'active_users': -1, 'graduated_users': -1, 'inactive_users': -1}
        stats = HR.cleanup_old_history(dry_run=False, retention_config=cfg)
        assert UserHistory.query.get(row) is not None
        assert stats['breakdown_by_category']['active']['retention_years'] == 'permanente'

    @freeze_time(NOW)
    def test_stats_shape_and_user_count(self, people):
        _hist(people.active, 'profile_updated', _years_ago(3))
        _hist(people.inactive, 'profile_updated', _years_ago(3))
        stats = HR.cleanup_old_history()
        assert stats['users_affected'] == 2 and isinstance(stats['users_affected'], int)
        assert stats['breakdown_by_category']['active']['entries_to_delete'] == 1

    @freeze_time(NOW)
    def test_critical_count_reported(self, people):
        _hist(people.active, 'deleted', _years_ago(20))
        assert HR.cleanup_old_history()['entries_preserved_critical'] == 1

    @freeze_time(NOW)
    def test_oldest_entry_reported(self, people):
        _hist(people.active, 'profile_updated', NOW - timedelta(days=5))
        stats = HR.cleanup_old_history()
        assert stats['oldest_entry_kept'].startswith('2026-05-27')

    @freeze_time(NOW)
    def test_empty_database(self, app):
        stats = HR.cleanup_old_history(dry_run=False)
        assert stats['entries_deleted'] == 0 and stats['oldest_entry_kept'] is None

    @freeze_time(NOW)
    def test_history_of_one_user_does_not_affect_another_category(self, people):
        keep = _hist(people.graduate, 'profile_updated', _years_ago(4))
        HR.cleanup_old_history(dry_run=False)
        assert UserHistory.query.get(keep) is not None


class TestStatistics:
    def test_empty(self, app):
        s = HR.get_retention_statistics()
        assert s['total_entries'] == 0 and s['critical_actions_percentage'] == 0
        assert s['oldest_entry'] is None

    def test_counts_and_percentage(self, people):
        _hist(people.active, 'deleted', datetime(2024, 1, 1))
        _hist(people.active, 'profile_updated', datetime(2025, 1, 1))
        _hist(people.active, 'profile_updated', datetime(2025, 6, 1))
        _hist(people.active, 'profile_updated', datetime(2025, 7, 1))
        s = HR.get_retention_statistics()
        assert s['total_entries'] == 4 and s['critical_actions_count'] == 1
        assert s['critical_actions_percentage'] == 25.0
        assert s['entries_by_year'] == {2024: 1, 2025: 3}
        assert s['top_actions'][0] == ('profile_updated', 3)
        assert s['oldest_entry'].startswith('2024-01-01')
        assert s['newest_entry'].startswith('2025-07-01')


# ----------------------------------------------------------- RetentionService
@pytest.fixture
def archive_env(app):
    coord = make_user('program_admin')
    prog = make_program(coord)
    ph = Phase('admission', 'd')
    db.session.add(ph)
    db.session.flush()
    st = Step('s', 'd', ph.id)
    db.session.add(st)
    db.session.flush()
    ps = ProgramStep(program_id=prog.id, step_id=st.id, sequence=1)
    db.session.add(ps)
    db.session.flush()
    ar = Archive('Acta', 'd', None, st.id)
    ar2 = Archive('Otro', 'd', None, st.id)
    db.session.add_all([ar, ar2])
    u = make_user('student')
    up = enroll(u, prog, 'enrolled')
    db.session.commit()
    return type('A', (), dict(prog=prog, ps=ps, ar=ar, ar2=ar2, user=u, up=up))


def _submission(env, archive, uploaded):
    s = Submission('f.pdf', 'approved', env.user.id, archive.id, env.ps.id, None)
    s.upload_date = uploaded
    db.session.add(s)
    db.session.commit()
    return s.id


def _policy(archive, **kw):
    p = RetentionPolicy()
    p.archive_id = archive.id
    p.keep_years = kw.get('keep_years')
    p.keep_forever = kw.get('keep_forever', False)
    p.apply_after = kw.get('apply_after', 'graduated')
    db.session.add(p)
    db.session.commit()
    return p


class TestRetentionService:
    def test_no_policies_no_candidates(self, archive_env):
        _submission(archive_env, archive_env.ar, datetime(2000, 1, 1))
        assert RS.compute_candidates(NOW) == []

    def test_old_submission_is_candidate(self, archive_env):
        sid = _submission(archive_env, archive_env.ar, NOW - timedelta(days=5 * 365))
        _policy(archive_env.ar, keep_years=4)
        assert [s.id for s in RS.compute_candidates(NOW)] == [sid]

    def test_recent_submission_is_not(self, archive_env):
        _submission(archive_env, archive_env.ar, NOW - timedelta(days=100))
        _policy(archive_env.ar, keep_years=4)
        assert RS.compute_candidates(NOW) == []

    def test_keep_forever_wins(self, archive_env):
        _submission(archive_env, archive_env.ar, NOW - timedelta(days=50 * 365))
        _policy(archive_env.ar, keep_years=1, keep_forever=True)
        assert RS.compute_candidates(NOW) == []

    def test_policy_without_years_is_skipped(self, archive_env):
        _submission(archive_env, archive_env.ar, NOW - timedelta(days=50 * 365))
        _policy(archive_env.ar, keep_years=None)
        assert RS.compute_candidates(NOW) == []

    def test_policy_only_matches_its_archive(self, archive_env):
        _submission(archive_env, archive_env.ar2, NOW - timedelta(days=50 * 365))
        _policy(archive_env.ar, keep_years=1)
        assert RS.compute_candidates(NOW) == []

    def test_boundary_exactly_at_threshold_is_candidate(self, archive_env):
        sid = _submission(archive_env, archive_env.ar, NOW - timedelta(days=2 * 365))
        _policy(archive_env.ar, keep_years=2)
        assert [s.id for s in RS.compute_candidates(NOW)] == [sid]

    def test_enrollment_policy_uses_enrollment_date(self, archive_env):
        sid = _submission(archive_env, archive_env.ar, NOW)   # fresh upload
        archive_env.up.enrollment_date = NOW - timedelta(days=10 * 365)
        db.session.commit()
        _policy(archive_env.ar, keep_years=3, apply_after='enrollment')
        assert [s.id for s in RS.compute_candidates(NOW)] == [sid]

    def test_enrollment_policy_recent_enrollment_not_candidate(self, archive_env):
        _submission(archive_env, archive_env.ar, NOW - timedelta(days=10 * 365))
        archive_env.up.enrollment_date = NOW - timedelta(days=30)
        db.session.commit()
        _policy(archive_env.ar, keep_years=3, apply_after='enrollment')
        assert RS.compute_candidates(NOW) == []

    def test_purge_deletes_given_ids_only(self, archive_env):
        a = _submission(archive_env, archive_env.ar, NOW)
        b = _submission(archive_env, archive_env.ar2, NOW)
        assert RS.purge_submissions([a]) == 1
        assert Submission.query.get(a) is None and Submission.query.get(b) is not None

    def test_purge_empty_list(self, archive_env):
        assert RS.purge_submissions([]) == 0

    def test_purge_unknown_ids(self, archive_env):
        assert RS.purge_submissions([999]) == 0

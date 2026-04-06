# app/routes/pages/users_pages.py
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from app.models import Program
from app.services.admission_service import get_admission_state
from app.services.dashboard_service import DashboardService

pages_user = Blueprint("pages_user", __name__, url_prefix="/user")

@pages_user.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    context = {}

    # ── Dashboard para APPLICANT ─────────────────────────────────
    if current_user.role.name == 'applicant':
        up = current_user.user_program[0] if current_user.user_program else None
        program = up.program if up else None

        if program:
            adm_state = get_admission_state(current_user.id, program.id, up)
        else:
            adm_state = {
                "progress_segments": [],
                "status_count": {},
                "progress_pct": 0,
                "pending_items": [],
                "timeline": []
            }

        # Datos de diferimiento cuando el aspirante está en estado 'deferred'
        deferral_status = None
        if up and up.admission_status == 'deferred':
            from app.services.deferral_service import get_deferral_status
            try:
                deferral_status = get_deferral_status(up.id)
            except Exception:
                deferral_status = None

        context = {
            "program": program,
            **adm_state,
            "admission_status": up.admission_status if up else None,
            "user_program_id": up.id if up else None,
            "deferral_status": deferral_status,
        }

    # ── Dashboard para STUDENT ───────────────────────────────────
    elif current_user.role.name == 'student':
        up = current_user.user_program[0] if current_user.user_program else None
        program = up.program if up else None

        permanence_data = None
        if up:
            from app.services.permanence_service import get_student_permanence
            try:
                permanence_data = get_student_permanence(up.id)
            except Exception:
                permanence_data = None

        # Calcular documentos pendientes de admisión y permanencia
        pending_admission_docs = []
        pending_permanence_docs = []
        if up and program:
            from app.models import Step, ProgramStep, Phase, Submission
            from app.models.archive import Archive
            from sqlalchemy import and_

            # Documentos de admisión pendientes (no aprobados)
            adm_archives = (
                Archive.query
                .join(Step, Archive.step_id == Step.id)
                .join(ProgramStep, Step.id == ProgramStep.step_id)
                .join(Phase, Step.phase_id == Phase.id)
                .filter(
                    and_(
                        ProgramStep.program_id == program.id,
                        Phase.name == 'admission',
                        Archive.is_uploadable == True,
                    )
                )
                .all()
            )
            for arch in adm_archives:
                sub = Submission.query.filter_by(
                    user_id=current_user.id,
                    archive_id=arch.id,
                ).order_by(Submission.upload_date.desc()).first()
                if not sub or sub.status not in ('approved', 'review'):
                    pending_admission_docs.append({
                        'name': arch.name,
                        'status': sub.status if sub else 'pending',
                    })

            # Documentos de permanencia pendientes (no aprobados)
            perm_archives = (
                Archive.query
                .join(Step, Archive.step_id == Step.id)
                .join(ProgramStep, Step.id == ProgramStep.step_id)
                .join(Phase, Step.phase_id == Phase.id)
                .filter(
                    and_(
                        ProgramStep.program_id == program.id,
                        Phase.name == 'permanence',
                        Archive.is_uploadable == True,
                    )
                )
                .all()
            )
            for arch in perm_archives:
                sub = Submission.query.filter_by(
                    user_id=current_user.id,
                    archive_id=arch.id,
                ).order_by(Submission.upload_date.desc()).first()
                if not sub or sub.status not in ('approved', 'review'):
                    pending_permanence_docs.append({
                        'name': arch.name,
                        'status': sub.status if sub else 'pending',
                    })

        context = {
            'program': program,
            'up': up,
            'permanence_data': permanence_data,
            'pending_admission_docs': pending_admission_docs,
            'pending_permanence_docs': pending_permanence_docs,
        }

    # ── Dashboard para PROGRAM_ADMIN ─────────────────────────────
    elif current_user.role.name == 'program_admin':
        # Obtener todos los programas coordinados
        coordinated_programs = current_user.coordinated_programs
        
        if coordinated_programs:
            # Parámetro para seleccionar programa específico
            program_id_param = request.args.get('program_id')
            show_all = program_id_param == 'all'
            selected_program_id = None if show_all else (
                int(program_id_param) if program_id_param and program_id_param.isdigit() else None
            )
            
            if show_all:
                # Mostrar métricas combinadas de todos los programas
                combined_metrics = DashboardService.get_combined_program_metrics([p.id for p in coordinated_programs])
                recent_submissions = DashboardService.get_recent_submissions_multiple([p.id for p in coordinated_programs], limit=5)
                
                context = {
                    "program": None,  # No hay programa específico seleccionado
                    "coordinated_programs": coordinated_programs,
                    "selected_program_id": "all",
                    "selected_program": None,
                    "show_program_selector": len(coordinated_programs) > 1,
                    "show_all_programs": True,
                    "metrics": combined_metrics,
                    "recent_submissions": recent_submissions
                }
            elif selected_program_id:
                # Programa específico seleccionado
                selected_program = next((p for p in coordinated_programs if p.id == selected_program_id), coordinated_programs[0])
                
                metrics = DashboardService.get_program_admin_metrics(selected_program.id)
                recent_submissions = DashboardService.get_recent_submissions(selected_program.id, limit=5)
                
                context = {
                    "program": selected_program,
                    "coordinated_programs": coordinated_programs,
                    "selected_program_id": selected_program.id,
                    "selected_program": selected_program,
                    "show_program_selector": len(coordinated_programs) > 1,
                    "show_all_programs": False,
                    "metrics": metrics,
                    "recent_submissions": recent_submissions
                }
            else:
                # Por defecto, mostrar el primer programa
                selected_program = coordinated_programs[0]
                
                metrics = DashboardService.get_program_admin_metrics(selected_program.id)
                recent_submissions = DashboardService.get_recent_submissions(selected_program.id, limit=5)
                
                context = {
                    "program": selected_program,
                    "coordinated_programs": coordinated_programs,
                    "selected_program_id": selected_program.id,
                    "selected_program": selected_program,
                    "show_program_selector": len(coordinated_programs) > 1,
                    "show_all_programs": False,
                    "metrics": metrics,
                    "recent_submissions": recent_submissions
                }
        else:
            context = {
                "program": None,
                "coordinated_programs": [],
                "selected_program_id": None,
                "selected_program": None,
                "show_program_selector": False,
                "show_all_programs": False,
                "metrics": None,
                "recent_submissions": []
            }

    # ── Dashboard para POSTGRADUATE_ADMIN ────────────────────────
    elif current_user.role.name == 'postgraduate_admin':
        metrics = DashboardService.get_postgraduate_admin_metrics()
        context = {
            "metrics": metrics
        }

    return render_template("user/dashboard/dashboard.html", **context)

@pages_user.route("/profile", methods=["GET"])
@login_required
def profile():
    # ── Datos base para el panel de progreso ─────────────
    up = current_user.user_program[0] if current_user.user_program else None
    program = up.program if up else None

    if program:
        adm_state = get_admission_state(current_user.id, program.id, up)
    else:
        adm_state = {
            "progress_segments": [],
            "status_count": {},
            "progress_pct": 0,
            "pending_items": [],
            "timeline": []
        }

    context = {"program": program, **adm_state}
    return render_template("user/profile/profile.html", **context)

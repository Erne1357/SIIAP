from flask import Blueprint, render_template, request, redirect,flash,url_for
from flask_login import login_required, current_user
from app.services.admission import get_admission_state
from app import db
from app.routes.admin.review import review_bp as review


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
admin_bp.register_blueprint(review)
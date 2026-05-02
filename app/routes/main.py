import uuid
from flask import Blueprint, render_template, session

main_bp = Blueprint('main', __name__)


@main_bp.before_app_request
def ensure_session():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/create')
def create():
    return render_template('create.html')


@main_bp.route('/preview/<portfolio_id>')
def preview(portfolio_id):
    return render_template('preview.html', portfolio_id=portfolio_id)

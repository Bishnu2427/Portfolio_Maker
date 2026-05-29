import os
import uuid
from flask import Blueprint, render_template, session, send_from_directory, abort
from app.models.portfolio import Portfolio

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


# ── Portfolio inline serving (replaces per-portfolio subprocess servers) ───────

@main_bp.route('/portfolio-view/<portfolio_id>')
def portfolio_view(portfolio_id):
    """Serve the generated portfolio HTML directly from Flask."""
    portfolio = Portfolio.get_by_id(portfolio_id)
    if not portfolio:
        abort(404)

    portfolio_dir = portfolio.get('portfolio_dir', '')
    index_path = os.path.join(portfolio_dir, 'index.html')
    if not os.path.exists(index_path):
        abort(404)

    with open(index_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inject <base> so relative asset paths (static/css/style.css) resolve correctly
    base_tag = f'<base href="/portfolio-view/{portfolio_id}/">'
    if '<head>' in html:
        html = html.replace('<head>', f'<head>\n  {base_tag}', 1)
    else:
        html = base_tag + html

    return html, 200, {'Content-Type': 'text/html; charset=utf-8',
                       'Cache-Control': 'no-cache'}


@main_bp.route('/portfolio-view/<portfolio_id>/static/<path:filepath>')
def portfolio_static(portfolio_id, filepath):
    """Serve static assets (CSS, images) for an inline-served portfolio."""
    portfolio = Portfolio.get_by_id(portfolio_id)
    if not portfolio:
        abort(404)
    static_dir = os.path.join(portfolio.get('portfolio_dir', ''), 'static')
    return send_from_directory(static_dir, filepath)


# ── Health check (used by Docker healthcheck) ─────────────────────────────────

@main_bp.route('/health')
def health():
    return {'status': 'ok'}, 200

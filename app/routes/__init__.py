from app.routes.main import main_bp
from app.routes.portfolio import portfolio_bp
from app.routes.process import process_bp
from app.routes.deploy import deploy_bp


def register_routes(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(portfolio_bp, url_prefix='/api/portfolio')
    app.register_blueprint(process_bp, url_prefix='/api/process')
    app.register_blueprint(deploy_bp, url_prefix='/api/deploy')

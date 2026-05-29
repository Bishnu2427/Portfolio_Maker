from flask import Blueprint, jsonify, session
from app.models.portfolio import Portfolio

portfolio_bp = Blueprint('portfolio', __name__)


@portfolio_bp.route('/list', methods=['GET'])
def list_portfolios():
    session_id = session.get('session_id')
    portfolios = Portfolio.get_by_session(session_id)
    result = []
    for p in portfolios:
        result.append({
            'id': str(p['_id']),
            'style': p.get('style', ''),
            'status': p.get('status', ''),
            'pages_url': p.get('pages_url', ''),
            'created_at': p['created_at'].isoformat() if p.get('created_at') else '',
        })
    return jsonify({'portfolios': result})


@portfolio_bp.route('/<portfolio_id>', methods=['GET'])
def get_portfolio(portfolio_id):
    portfolio = Portfolio.get_by_id(portfolio_id)
    if not portfolio:
        return jsonify({'error': 'Not found'}), 404
    # Return only fields the frontend needs (skip large cv_text / cv_data blobs)
    return jsonify({
        'id':            str(portfolio['_id']),
        'style':         portfolio.get('style', ''),
        'status':        portfolio.get('status', ''),
        'github_url':    portfolio.get('github_url', ''),
        'pages_url':     portfolio.get('pages_url', ''),
        'created_at':    portfolio['created_at'].isoformat() if portfolio.get('created_at') else '',
    })

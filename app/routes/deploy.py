from flask import Blueprint, request, jsonify
from app.services.github_service import GitHubService
from app.models.portfolio import Portfolio

deploy_bp = Blueprint('deploy', __name__)


@deploy_bp.route('/github', methods=['POST'])
def deploy_to_github():
    data = request.get_json()
    portfolio_id = data.get('portfolio_id')
    github_token = data.get('github_token', '').strip()
    repo_name = data.get('repo_name', 'my-portfolio').strip()

    if not portfolio_id or not github_token:
        return jsonify({'error': 'portfolio_id and github_token are required'}), 400

    portfolio = Portfolio.get_by_id(portfolio_id)
    if not portfolio:
        return jsonify({'error': 'Portfolio not found'}), 404

    try:
        svc = GitHubService(github_token)
        result = svc.deploy(
            portfolio_dir=portfolio.get('portfolio_dir', ''),
            repo_name=repo_name,
        )
        Portfolio.update(portfolio_id, {
            'github_url': result['repo_url'],
            'pages_url': result['pages_url'],
            'status': 'deployed',
        })
        return jsonify({
            'success': True,
            'repo_url': result['repo_url'],
            'pages_url': result['pages_url'],
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500

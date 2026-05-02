import os
import uuid
import json
from flask import Blueprint, request, jsonify, session, Response, stream_with_context
from app.services.cv_parser import CVParser
from app.services.cv_fallback import extract as fallback_extract
from app.services.ai_service import AIService
from app.services.portfolio_generator import PortfolioGenerator
from app.services.port_manager import PortManager
from app.services.preview_manager import PreviewManager
from app.models.portfolio import Portfolio
from app.config import Config

process_bp = Blueprint('process', __name__)


def _event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@process_bp.route('/upload', methods=['POST'])
def upload():
    if 'cv' not in request.files:
        return jsonify({'error': 'No CV file provided'}), 400

    cv_file = request.files['cv']
    photo_file = request.files.get('photo')
    user_prompt = request.form.get('prompt', '')
    style = request.form.get('style', 'professional')

    if not cv_file.filename:
        return jsonify({'error': 'Empty CV file'}), 400

    session_id = session.get('session_id', str(uuid.uuid4()))
    upload_id = str(uuid.uuid4())
    upload_dir = os.path.join(Config.UPLOAD_FOLDER, upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(cv_file.filename)[1].lower()
    cv_path = os.path.join(upload_dir, f'cv{ext}')
    cv_file.save(cv_path)

    photo_path = ''
    if photo_file and photo_file.filename:
        p_ext = os.path.splitext(photo_file.filename)[1].lower()
        photo_path = os.path.join(upload_dir, f'photo{p_ext}')
        photo_file.save(photo_path)

    portfolio = Portfolio.create({
        'session_id': session_id,
        'style': style,
        'user_prompt': user_prompt,
        'photo_path': photo_path,
        'cv_path': cv_path,
    })
    portfolio_id = str(portfolio['_id'])
    Portfolio.update(portfolio_id, {'upload_dir': upload_dir})

    return jsonify({'portfolio_id': portfolio_id, 'message': 'Upload successful'})


@process_bp.route('/generate/<portfolio_id>')
def generate(portfolio_id):
    def stream():
        try:
            portfolio = Portfolio.get_by_id(portfolio_id)
            if not portfolio:
                yield _event({'error': 'Portfolio not found'})
                return

            # ── Step 1: Parse CV text ────────────────────────────────────
            yield _event({'step': 1, 'message': 'Parsing your CV...', 'progress': 10})
            cv_text = CVParser.parse(portfolio.get('cv_path', ''))
            if not cv_text:
                yield _event({'error': 'Could not read CV. Please re-upload a valid PDF, DOCX, or TXT.'})
                return
            Portfolio.update(portfolio_id, {'cv_text': cv_text, 'status': 'processing'})

            # ── Step 2: Extract structured data (AI, fallback to regex) ──
            yield _event({'step': 2, 'message': 'Extracting CV data with AI...', 'progress': 25})
            ai_available = bool(Config.GEMINI_API_KEY)
            cv_data = {}
            ai = None

            if ai_available:
                try:
                    ai = AIService()
                    cv_data = ai.parse_cv(cv_text)
                    print(f'[Process] AI parsed CV for {portfolio_id[:8]}: name={cv_data.get("name")}')
                except Exception as e:
                    print(f'[Process] AI parse_cv failed: {e}')
                    yield _event({'step': 2, 'message': f'⚠️ AI unavailable ({e}). Using smart extraction...', 'progress': 25})
                    ai_available = False

            if not ai_available or not cv_data.get('name'):
                cv_data = fallback_extract(cv_text)
                print(f'[Process] Fallback extracted: name={cv_data.get("name")}')
                yield _event({'step': 2, 'message': 'Extracted CV data ✓', 'progress': 28})

            Portfolio.update(portfolio_id, {'cv_data': cv_data})

            # ── Step 3: Polish prompt ────────────────────────────────────
            yield _event({'step': 3, 'message': 'Preparing portfolio brief...', 'progress': 40})
            polished = portfolio.get('user_prompt', '') or (
                f"Create a {portfolio.get('style', 'professional')} portfolio for "
                f"{cv_data.get('name', 'this professional')}, "
                f"a {cv_data.get('title', 'professional')}."
            )
            if ai and ai_available:
                try:
                    polished = ai.polish_prompt(
                        portfolio.get('user_prompt', ''),
                        portfolio.get('style', 'professional'),
                        cv_data,
                    )
                except Exception as e:
                    print(f'[Process] AI polish_prompt failed: {e}')

            # ── Step 4: Enhance content ──────────────────────────────────
            yield _event({'step': 4, 'message': 'Enhancing content with AI...', 'progress': 55})
            enhanced = cv_data
            if ai and ai_available:
                try:
                    enhanced = ai.enhance_content(cv_data, polished, portfolio.get('style', 'professional'))
                    print(f'[Process] AI enhanced content: name={enhanced.get("name")}')
                except Exception as e:
                    print(f'[Process] AI enhance_content failed: {e}')
                    yield _event({'step': 4, 'message': '⚠️ AI enhancement skipped. Using extracted data.', 'progress': 55})

            # Guarantee name/title are never empty
            if not enhanced.get('name'):
                enhanced['name'] = cv_data.get('name') or 'Your Name'
            if not enhanced.get('title'):
                enhanced['title'] = cv_data.get('title') or 'Professional'

            # ── Step 5: Generate portfolio files ────────────────────────
            yield _event({'step': 5, 'message': 'Building your portfolio site...', 'progress': 70})
            generator = PortfolioGenerator()
            portfolio_dir = generator.generate(
                portfolio_id=portfolio_id,
                cv_data=enhanced,
                style=portfolio.get('style', 'professional'),
                photo_path=portfolio.get('photo_path', ''),
            )
            Portfolio.update(portfolio_id, {
                'portfolio_dir': portfolio_dir,
                'cv_data': enhanced,
                'status': 'generated',
            })

            # ── Step 6: Start preview server ────────────────────────────
            yield _event({'step': 6, 'message': 'Starting preview server...', 'progress': 85})
            pm = PortManager()
            port = pm.allocate_port(portfolio_id)
            prev = PreviewManager()
            pid = prev.start(portfolio_dir, port, portfolio_id)
            Portfolio.update(portfolio_id, {'port': port, 'pid': pid, 'status': 'preview'})

            yield _event({'step': 6, 'message': 'Waiting for preview server...', 'progress': 92})
            if not prev.wait_ready(port):
                logs = prev.get_log(portfolio_id)
                yield _event({'error': f'Preview server failed to start on port {port}.\n\nLogs:\n{logs}'})
                return

            # ── Done ─────────────────────────────────────────────────────
            yield _event({
                'step': 7,
                'message': f'Portfolio ready for {enhanced.get("name", "you")}!',
                'progress': 100,
                'port': port,
                'portfolio_id': portfolio_id,
                'done': True,
                'redirect': f'/preview/{portfolio_id}',
            })

        except Exception as exc:
            import traceback
            print(f'[Process] Unhandled error: {traceback.format_exc()}')
            yield _event({'error': str(exc)})

    return Response(
        stream_with_context(stream()),
        content_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@process_bp.route('/modify', methods=['POST'])
def modify():
    data = request.get_json()
    portfolio_id = data.get('portfolio_id')
    prompt = data.get('prompt', '').strip()

    if not portfolio_id or not prompt:
        return jsonify({'error': 'Missing portfolio_id or prompt'}), 400

    portfolio = Portfolio.get_by_id(portfolio_id)
    if not portfolio:
        return jsonify({'error': 'Portfolio not found'}), 404

    generator = PortfolioGenerator()
    current_html = generator.get_html(portfolio.get('portfolio_dir', ''))

    try:
        ai = AIService()
        modified_html = ai.modify_portfolio(current_html, prompt)
        generator.update_html(portfolio.get('portfolio_dir', ''), modified_html)
        Portfolio.update(portfolio_id, {'status': 'preview'})
        return jsonify({'success': True, 'message': 'Portfolio updated'})
    except Exception as e:
        return jsonify({'error': f'AI modification failed: {e}'}), 500


@process_bp.route('/logs/<portfolio_id>', methods=['GET'])
def get_logs(portfolio_id):
    """Debug endpoint — returns the preview server log."""
    prev = PreviewManager()
    logs = prev.get_log(portfolio_id)
    return jsonify({'logs': logs or 'No logs available'})

import os
import json
import shutil
import base64
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from app.config import Config


class PortfolioGenerator:
    def __init__(self):
        self.templates_dir = Config.PORTFOLIO_TEMPLATES_DIR
        self.output_dir = Config.GENERATED_PORTFOLIOS_DIR

    def generate(self, portfolio_id: str, cv_data: dict, style: str, photo_path: str = '') -> str:
        out_dir = os.path.join(self.output_dir, portfolio_id)
        os.makedirs(out_dir, exist_ok=True)

        tpl_dir = os.path.join(self.templates_dir, style)
        if not os.path.isdir(tpl_dir):
            tpl_dir = os.path.join(self.templates_dir, 'professional')

        # Copy template skeleton (css, js, etc.) but NOT index.html (we render it)
        for item in os.listdir(tpl_dir):
            src = os.path.join(tpl_dir, item)
            dst = os.path.join(out_dir, item)
            if item == 'index.html':
                continue
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

        # Handle profile photo
        photo_base64 = ''
        photo_mime = 'image/jpeg'
        if photo_path and os.path.exists(photo_path):
            ext = os.path.splitext(photo_path)[1].lower().lstrip('.')
            mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}
            photo_mime = mime_map.get(ext, 'image/jpeg')
            with open(photo_path, 'rb') as f:
                photo_base64 = base64.b64encode(f.read()).decode('utf-8')
            images_dir = os.path.join(out_dir, 'static', 'images')
            os.makedirs(images_dir, exist_ok=True)
            shutil.copy2(photo_path, os.path.join(images_dir, f'profile.{ext}'))

        # Save data.json
        with open(os.path.join(out_dir, 'data.json'), 'w', encoding='utf-8') as f:
            json.dump(cv_data, f, indent=2, ensure_ascii=False)

        # Render template
        env = Environment(loader=FileSystemLoader(tpl_dir))
        template = env.get_template('index.html')
        rendered = template.render(
            data=cv_data,
            photo_base64=photo_base64,
            photo_mime=photo_mime,
            style=style,
            year=datetime.now().year,
        )

        with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(rendered)

        self._write_flask_app(out_dir)
        self._write_requirements(out_dir)

        with open(os.path.join(out_dir, 'port.txt'), 'w') as f:
            f.write('')

        return out_dir

    # ------------------------------------------------------------------
    def get_html(self, portfolio_dir: str) -> str:
        path = os.path.join(portfolio_dir, 'index.html')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ''

    def update_html(self, portfolio_dir: str, html: str):
        with open(os.path.join(portfolio_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(html)

    # ------------------------------------------------------------------
    @staticmethod
    def _write_flask_app(out_dir: str):
        content = """\
from flask import Flask, send_from_directory, abort
import os

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

if __name__ == '__main__':
    port_file = os.path.join(os.path.dirname(__file__), 'port.txt')
    port = 5001
    if os.path.exists(port_file):
        try:
            port = int(open(port_file).read().strip())
        except ValueError:
            pass
    print(f'[Portfolio Preview] Running on http://localhost:{port}')
    app.run(host='0.0.0.0', port=port, debug=False)
"""
        with open(os.path.join(out_dir, 'app.py'), 'w') as f:
            f.write(content)

    @staticmethod
    def _write_requirements(out_dir: str):
        with open(os.path.join(out_dir, 'requirements.txt'), 'w') as f:
            f.write('flask==3.0.3\n')

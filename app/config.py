import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'portfolio-forge-secret-2024')
    MONGO_URI  = os.getenv('MONGO_URI', 'mongodb://localhost:27017/portfolio_maker')

    # ── AI providers ──────────────────────────────────────────────────
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    OLLAMA_HOST    = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    OLLAMA_MODEL   = os.getenv('OLLAMA_MODEL', 'llama3.2')
    # LLM_PROVIDER: "auto" → try Ollama first then Gemini
    #               "ollama" → Ollama only
    #               "gemini" → Gemini only
    LLM_PROVIDER   = os.getenv('LLM_PROVIDER', 'auto')

    # ── GitHub ────────────────────────────────────────────────────────
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

    # ── File paths ────────────────────────────────────────────────────
    UPLOAD_FOLDER             = os.path.join(BASE_DIR, 'uploads')
    GENERATED_PORTFOLIOS_DIR  = os.path.join(BASE_DIR, 'generated_portfolios')
    PORTFOLIO_TEMPLATES_DIR   = os.path.join(BASE_DIR, 'portfolio_templates')

    MAX_CONTENT_LENGTH        = 16 * 1024 * 1024
    ALLOWED_CV_EXTENSIONS     = {'pdf', 'docx', 'txt', 'doc'}
    ALLOWED_IMAGE_EXTENSIONS  = {'png', 'jpg', 'jpeg', 'webp'}

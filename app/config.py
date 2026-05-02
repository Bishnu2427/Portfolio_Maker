import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'portfolio-forge-secret-2024')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/portfolio_maker')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    GENERATED_PORTFOLIOS_DIR = os.path.join(BASE_DIR, 'generated_portfolios')
    PORTFOLIO_TEMPLATES_DIR = os.path.join(BASE_DIR, 'portfolio_templates')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_CV_EXTENSIONS = {'pdf', 'docx', 'txt', 'doc'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

    PORT_START = 5001
    PORT_END = 6000
    MAIN_APP_PORT = 5000

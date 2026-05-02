from app import create_app
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

app = create_app()

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  PortfolioForge - Portfolio Maker")
    print("  Running on http://localhost:5000")
    print("  Portfolio previews start at port 5001")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

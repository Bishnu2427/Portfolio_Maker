import os
import logging
from app import create_app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5007))
    print("\n" + "="*50)
    print("  PortfolioForge - Portfolio Maker")
    print(f"  Running on http://localhost:{port}")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

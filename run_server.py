#!/usr/bin/env python
"""
Production Flask server - no debug mode
"""
from models import create_app
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    app = create_app()
    
    logger.info("="*70)
    logger.info("Starting Flask API Server (Production Mode)")
    logger.info("="*70)
    logger.info("Listening on http://localhost:5000")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*70 + "\n")
    
    # Production mode - no reloader, no debugger
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )

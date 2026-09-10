#!/usr/bin/env python
"""
SAFEGUARD AI - Backend Startup Script
"""
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from backend.config import settings

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Create required directories
os.makedirs("./data/chroma_db", exist_ok=True)
os.makedirs("./logs", exist_ok=True)
os.makedirs("./reports", exist_ok=True)

if __name__ == "__main__":
    print("=" * 60)
    print("  SAFEGUARD AI — Industrial Safety Intelligence Platform")
    print("=" * 60)
    print(f"  Backend URL: http://{settings.BACKEND_HOST}:{settings.BACKEND_PORT}")
    print(f"  API Docs:    http://{settings.BACKEND_HOST}:{settings.BACKEND_PORT}/docs")
    print(f"  IBM WatsonX: {'CONFIGURED' if settings.ibm_configured else 'not configured (rule-based fallback active)'}")
    print(f"  Langflow:    {'CONFIGURED' if settings.langflow_configured else 'not configured'}")
    print(f"  Simulation:  {'ENABLED' if settings.SIMULATION_ENABLED else 'disabled'}")
    print("=" * 60)

    uvicorn.run(
        "backend.api.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )

#!/usr/bin/env python3
"""
RFID Cloud API Server
Main entry point - imports from cloud/api/main.py
"""
import sys
import os

# Add cloud api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cloud', 'api'))

from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

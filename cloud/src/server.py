#!/usr/bin/env python3
"""
RFID Cloud API Server
Main entry point
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

"""
OpenAI-compatible API Server for AnyServe

This is a standalone component that provides an OpenAI-compatible REST API
by converting requests to KServe protocol and forwarding them to AnyServe.

Usage:
    python -m openai_server --anyserve-endpoint localhost:8000 --port 8080
"""

__version__ = "0.1.0"

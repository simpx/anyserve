"""
Multi-Server Example
====================

Demonstrates AnyServe's capability-based routing with multiple workers.

Components:
- worker1.py: Worker with multiply capability
- worker2.py: Worker with divide and power capabilities
- test_client.py: Client using discovery mode
- run.sh: Script to start all services

Usage:
    1. Start services: ./examples/multiserver/run.sh
    2. Run client:     python examples/multiserver/test_client.py
"""

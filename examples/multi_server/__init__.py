"""
Multi-Server Example
====================

Demonstrates AnyServe's capability-based routing with multiple workers.

Components:
- worker1.py: Worker with multiply capability
- worker2.py: Worker with divide and power capabilities
- test_client.py: Client using discovery mode
- run_server.sh: Script to start all services
- run_client.sh: Script to run the test client

Usage:
    1. Start services: ./examples/multi_server/run_server.sh
    2. Run client:     ./examples/multi_server/run_client.sh
"""

"""
Pipeline Example - Test Client
==============================

This client demonstrates the pipeline flow:
  Client -> tokenize -> analyze -> format -> Response

The client sends text to the tokenize capability, which triggers
the full pipeline and returns a formatted analysis report.

Prerequisites:
    1. Start the servers: ./examples/pipeline/run.sh
    2. Run this client:   python examples/pipeline/test_client.py

Data flow:
    1. Client sends text to tokenize (Worker A)
    2. tokenize calls analyze (Worker B) with tokens
    3. analyze calls format (Worker C) with statistics
    4. format returns report to analyze
    5. analyze returns report to tokenize
    6. tokenize returns report to Client
"""

import sys
from anyserve.worker.client import Client


API_SERVER = "http://localhost:8080"


def test_pipeline():
    """Test the full pipeline: tokenize -> analyze -> format."""
    print("=" * 60)
    print("Pipeline Test: tokenize -> analyze -> format")
    print("=" * 60)

    # Sample text to analyze
    sample_text = """
    The quick brown fox jumps over the lazy dog.
    This is a classic pangram that contains every letter of the alphabet.
    The fox is quick and brown, while the dog is lazy.
    Programming is fun and Python is a great language.
    """

    print("\nInput Text:")
    print("-" * 40)
    print(sample_text.strip())
    print("-" * 40)

    # Create client targeting the tokenize capability
    client = Client(
        api_server=API_SERVER,
        capability={"type": "tokenize"},
    )

    print(f"\nClient Mode: {client.mode}")
    print(f"Connecting via API Server: {API_SERVER}")

    try:
        # Call the pipeline entry point (tokenize)
        print("\nSending request to pipeline...")
        result = client.infer(
            model_name="tokenize",
            inputs={
                "text": [sample_text],  # BYTES input
            }
        )

        print(f"\nEndpoint discovered: {client.endpoint}")
        print(f"Replica ID: {client.replica_id}")

        # Display the result
        print("\n" + "=" * 60)
        print("PIPELINE RESULT:")
        print("=" * 60)

        if "result" in result:
            report_data = result["result"]
            if isinstance(report_data, list) and len(report_data) > 0:
                report = report_data[0]
                if isinstance(report, bytes):
                    report = report.decode('utf-8')
                print(report)
        else:
            print(f"Raw result: {result}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()

    return True


def test_direct_stages():
    """Test each pipeline stage directly."""
    print("\n" + "=" * 60)
    print("Direct Stage Tests")
    print("=" * 60)

    # Test tokenize directly
    print("\n[1] Testing tokenize stage directly...")
    try:
        client = Client(endpoint="localhost:50051")
        result = client.infer(
            model_name="tokenize",
            inputs={"text": ["Hello world test"]}
        )
        print(f"    Tokenize result keys: {list(result.keys())}")
        client.close()
    except Exception as e:
        print(f"    Error: {e}")

    # Test analyze directly
    print("\n[2] Testing analyze stage directly...")
    try:
        client = Client(endpoint="localhost:50052")
        result = client.infer(
            model_name="analyze",
            inputs={
                "tokens": ["hello,world,test,hello"],
                "original_text": ["Hello world test hello"],
                "token_count": [4],
            }
        )
        print(f"    Analyze result keys: {list(result.keys())}")
        client.close()
    except Exception as e:
        print(f"    Error: {e}")

    # Test format directly
    print("\n[3] Testing format stage directly...")
    try:
        import json
        client = Client(endpoint="localhost:50053")
        result = client.infer(
            model_name="format",
            inputs={
                "analysis_json": [json.dumps({
                    "total_tokens": 4,
                    "unique_tokens": 3,
                    "avg_token_length": 4.5,
                    "top_tokens": [{"token": "hello", "count": 2}]
                })],
                "text_snippet": ["Hello world test hello"],
                "avg_token_length": [4.5],
                "total_tokens": [4],
                "unique_tokens": [3],
            }
        )
        print(f"    Format result keys: {list(result.keys())}")
        if "report" in result:
            report = result["report"][0]
            if isinstance(report, bytes):
                report = report.decode('utf-8')
            print("\n    Formatted Report Preview:")
            for line in report.split('\n')[:10]:
                print(f"      {line}")
            print("      ...")
        client.close()
    except Exception as e:
        print(f"    Error: {e}")


def main():
    print()
    print("=" * 60)
    print("AnyServe Pipeline Example Client")
    print("=" * 60)
    print()
    print("Pipeline Architecture:")
    print("  Client -> tokenize -> analyze -> format -> Response")
    print()
    print(f"API Server: {API_SERVER}")
    print()

    try:
        # Run the full pipeline test
        success = test_pipeline()

        # Optionally test stages directly
        test_direct_stages()

        print("\n" + "=" * 60)
        if success:
            print("Pipeline test completed successfully!")
        else:
            print("Pipeline test failed!")
        print("=" * 60)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

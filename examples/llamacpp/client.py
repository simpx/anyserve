#!/usr/bin/env python3
"""
Example client for AnyServe LlamaCpp server.

Usage:
    # Start the server first:
    anyserve serve /path/to/model.gguf --port 8000

    # Then run this client:
    python client.py --prompt "Hello, world!"
    python client.py --prompt "Tell me a story" --stream
"""

import argparse
import requests
import json


def complete(base_url: str, prompt: str, max_tokens: int = 100, stream: bool = False):
    """Send a completion request to the server."""
    url = f"{base_url}/v1/completions"

    payload = {
        "prompt": prompt,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if stream:
        # Streaming response
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()

        print("Streaming response:")
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        print("\n[DONE]")
                        break
                    try:
                        chunk = json.loads(data)
                        text = chunk.get('choices', [{}])[0].get('text', '')
                        print(text, end='', flush=True)
                    except json.JSONDecodeError:
                        pass
    else:
        # Non-streaming response
        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        print("Response:")
        print(result['choices'][0]['text'])
        print(f"\nModel: {result['model']}")


def list_models(base_url: str):
    """List available models."""
    url = f"{base_url}/v1/models"
    response = requests.get(url)
    response.raise_for_status()

    result = response.json()
    print("Available models:")
    for model in result['data']:
        print(f"  - {model['id']}")


def main():
    parser = argparse.ArgumentParser(description='AnyServe LlamaCpp Client')
    parser.add_argument('--url', default='http://localhost:8000', help='Server URL')
    parser.add_argument('--prompt', type=str, help='Prompt for completion')
    parser.add_argument('--max-tokens', type=int, default=100, help='Max tokens')
    parser.add_argument('--stream', action='store_true', help='Enable streaming')
    parser.add_argument('--list-models', action='store_true', help='List models')

    args = parser.parse_args()

    if args.list_models:
        list_models(args.url)
    elif args.prompt:
        complete(args.url, args.prompt, args.max_tokens, args.stream)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

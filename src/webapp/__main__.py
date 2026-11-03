"""Runs the Wordle Lab web UI: python src/webapp, python -m webapp (from src/), or wordle-lab."""
import argparse
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

if not __package__:
    # Running as a script: make the solver and webapp packages importable.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description='Run the Wordle Lab web UI.')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true', help="don't open a browser tab")
    args = parser.parse_args()

    url = f'http://127.0.0.1:{args.port}'
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()
    uvicorn.run('webapp.server:app', host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()

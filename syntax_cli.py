#!/usr/bin/env python
"""Small local CLI for Syntax Local AI."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def ask(server, prompt, code):
    body = urlencode({"prompt": prompt, "code": code, "language": "auto"}).encode("utf-8")
    request = Request(
        server.rstrip("/") + "/api/cli/ask/",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=310) as response:
            for raw_line in response:
                try:
                    event = json.loads(raw_line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "token":
                    print(event.get("token", ""), end="", flush=True)
                elif event.get("type") == "error":
                    print("\nError: " + event.get("error", "Request failed."), file=sys.stderr)
                    return 1
            print()
            return 0
    except (HTTPError, URLError) as exc:
        print("Syntax Local AI is unavailable: " + str(exc), file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(prog="syntax", description="Use Syntax Local AI from your terminal.")
    parser.add_argument("--server", default="http://127.0.0.1:8000", help="Local Syntax server URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Ask about code or a project")
    ask_parser.add_argument("prompt")
    ask_parser.add_argument("--code", type=Path, help="Read code from a file")

    review_parser = subparsers.add_parser("review", help="Review a source file")
    review_parser.add_argument("file", type=Path)

    args = parser.parse_args()
    if args.command == "review":
        return ask(args.server, "Review this file for bugs, security issues, and improvements.", args.file.read_text(encoding="utf-8"))
    code = args.code.read_text(encoding="utf-8") if args.code else ""
    return ask(args.server, args.prompt, code)


if __name__ == "__main__":
    raise SystemExit(main())

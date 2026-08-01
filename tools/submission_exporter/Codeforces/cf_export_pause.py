#!/usr/bin/env python3
from __future__ import annotations

import sys

from cf_export_core import ExportError, run


def wait_for_enter() -> None:
    try:
        input("\nPress Enter to close this window...")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> int:
    exit_code = 0
    try:
        exit_code = run()
    except ExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        exit_code = 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        exit_code = 130
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        wait_for_enter()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

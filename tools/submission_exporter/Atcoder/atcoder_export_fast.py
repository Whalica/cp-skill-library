#!/usr/bin/env python3
from __future__ import annotations

import sys

from atcoder_export_core import ExportError, run


def main() -> int:
    try:
        return run()
    except ExportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

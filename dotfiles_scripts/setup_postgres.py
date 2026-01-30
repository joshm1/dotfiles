#!/usr/bin/env python3
"""Setup PostgreSQL (check for installation)."""

from __future__ import annotations

import shutil
import sys

from dotfiles_scripts.setup_utils import (
    print_header,
    print_success,
    print_warning,
)


def main() -> int:
    """Main entry point."""
    print_header("Checking PostgreSQL")

    if shutil.which("psql"):
        print_success("psql is installed")
        return 0
    else:
        print_warning("psql is not installed")
        print("  Install from https://postgresapp.com/downloads.html")
        print("  Or: brew install postgresql")
        return 0  # Not a fatal error


if __name__ == "__main__":
    sys.exit(main())

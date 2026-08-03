"""Allow `python -m env_to_ini` execution."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

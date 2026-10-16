import os
import sys

# A windowed (no console) build has no stdout/stderr.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from toolkit.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

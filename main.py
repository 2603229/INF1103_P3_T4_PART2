# FILE GUIDE: Minimal Phase 1-compatible program entry point.
# CLI/application behavior is delegated to run_oop.py and the application class.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Compatibility entry point: Phase 1's `python main.py` command."""
from run_oop import main

if __name__ == "__main__":
    main()

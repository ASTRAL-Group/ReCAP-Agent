from pathlib import Path
import sys


if __package__ in {None, ""}:
    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from trace_generation.commands.main import main
else:
    from .commands.main import main


if __name__ == "__main__":
    main()

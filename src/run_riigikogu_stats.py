"""PyInstaller entry point. Imports the package so relative imports in run_app work."""
from riigikogu_stats.run_app import _main

if __name__ == "__main__":
    _main()

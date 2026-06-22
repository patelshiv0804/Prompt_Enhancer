"""
Migration helper script.

Usage:
    python -m scripts.migrate
"""

import subprocess
import sys


def run():
    """Run Alembic migrations."""
    print("Running migrations...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    print("Migrations complete!")


if __name__ == "__main__":
    run()

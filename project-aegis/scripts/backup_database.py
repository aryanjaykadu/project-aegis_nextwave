"""Create a consistent SQLite backup using SQLite's online backup API."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "aegis.db"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "backups")
    args = parser.parse_args()
    if not SOURCE.exists():
        raise FileNotFoundError(f"Database does not exist: {SOURCE}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = args.output_dir / f"aegis-{stamp}.db"
    with sqlite3.connect(SOURCE) as source, sqlite3.connect(destination) as target:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Backup integrity check failed: {result}")
    print(f"Verified SQLite backup: {destination} ({destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()

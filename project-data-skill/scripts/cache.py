#!/usr/bin/env python3
"""Simple file-based cache for project data skill results.

Usage:
    # Check if cache exists and is fresh (< 30 days old)
    python cache.py check --type property --key "630-n-crescent-drive"

    # Read cached data
    python cache.py read --type property --key "630-n-crescent-drive"

    # Write data to cache
    python cache.py write --type property --key "630-n-crescent-drive" --data '{"address": "..."}'

    # Write from stdin (for piping)
    echo '{"address": "..."}' | python cache.py write --type property --key "630-n-crescent-drive" --stdin

Cache types: property, zoning
Cache location: C:\\Users\\ilouh\\.claude\\cache\\project-data\\
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.expanduser("~"), ".claude", "cache", "project-data")
)

MAX_AGE_DAYS = 30  # Cache entries older than this are considered stale


def cache_path(cache_type, key):
    """Get the file path for a cache entry."""
    type_dir = os.path.join(CACHE_DIR, cache_type)
    os.makedirs(type_dir, exist_ok=True)
    # Sanitize key for filename
    safe_key = key.lower().replace(" ", "-").replace("/", "-").replace("\\", "-")
    return os.path.join(type_dir, f"{safe_key}.json")


def is_fresh(filepath):
    """Check if a cache file exists and is less than MAX_AGE_DAYS old."""
    if not os.path.exists(filepath):
        return False
    mtime = os.path.getmtime(filepath)
    age_days = (time.time() - mtime) / 86400
    return age_days < MAX_AGE_DAYS


def cmd_check(args):
    """Check if a cache entry exists and is fresh."""
    path = cache_path(args.type, args.key)
    if is_fresh(path):
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        print(json.dumps({
            "cached": True,
            "path": path,
            "cached_at": mtime.isoformat(),
            "age_days": round((time.time() - os.path.getmtime(path)) / 86400, 1),
        }))
    else:
        print(json.dumps({"cached": False}))


def cmd_read(args):
    """Read and output cached data."""
    path = cache_path(args.type, args.key)
    if not os.path.exists(path):
        print(json.dumps({"error": "Cache miss", "cached": False}))
        sys.exit(1)
    with open(path, "r") as f:
        data = json.load(f)
    print(json.dumps(data, indent=2))


def cmd_write(args):
    """Write data to cache."""
    if args.stdin:
        raw = sys.stdin.read()
    else:
        raw = args.data

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    # Add cache metadata
    data["_cache_meta"] = {
        "cached_at": datetime.now().isoformat(),
        "cache_type": args.type,
        "cache_key": args.key,
    }

    path = cache_path(args.type, args.key)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(json.dumps({"written": True, "path": path}))


def main():
    parser = argparse.ArgumentParser(description="Project data cache manager")
    sub = parser.add_subparsers(dest="command")

    check_p = sub.add_parser("check", help="Check if cache entry exists")
    check_p.add_argument("--type", required=True, help="Cache type (property, zoning)")
    check_p.add_argument("--key", required=True, help="Cache key (e.g., address slug)")

    read_p = sub.add_parser("read", help="Read cached data")
    read_p.add_argument("--type", required=True)
    read_p.add_argument("--key", required=True)

    write_p = sub.add_parser("write", help="Write data to cache")
    write_p.add_argument("--type", required=True)
    write_p.add_argument("--key", required=True)
    write_p.add_argument("--data", help="JSON string to cache")
    write_p.add_argument("--stdin", action="store_true", help="Read JSON from stdin")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check(args)
    elif args.command == "read":
        cmd_read(args)
    elif args.command == "write":
        cmd_write(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

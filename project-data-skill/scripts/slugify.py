#!/usr/bin/env python3
"""Convert a US street address into a filesystem-safe slug for use as a filename."""

import re
import sys


def slugify(address: str) -> str:
    """Turn a street address into a lowercase, hyphen-separated filename slug.

    Only the street portion is kept (everything before the first comma).
    Examples:
        "630 N Crescent Drive, Beverly Hills, CA 90210" -> "630-n-crescent-drive"
        "123 Main St, Apt 4B, New York, NY 10001"      -> "123-main-st-apt-4b"
    """
    # Take everything before the first comma (street portion only)
    street = address.split(",")[0].strip()
    # Lowercase
    slug = street.lower()
    # Replace non-alphanumeric chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    return slug


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python slugify.py '<full address>'", file=sys.stderr)
        sys.exit(1)
    print(slugify(sys.argv[1]))

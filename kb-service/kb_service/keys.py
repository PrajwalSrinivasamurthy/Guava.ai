"""Creates an API key for a caller of the service.

    python -m kb_service.keys --key-file path/to/key.txt

The key is written to the file (owner-only permissions, never overwriting an existing
file) and is not printed. Only its hash is printed, ready to add to KB_API_KEY_HASHES on
the server. Give the key file's contents to the caller through a private channel.
"""

import argparse
import os
import secrets
import sys
from pathlib import Path

from kb_service.auth import hash_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create an API key and print its hash.")
    parser.add_argument("--key-file", type=Path, required=True, help="where to write the new key")
    args = parser.parse_args(argv)

    key = secrets.token_urlsafe(32)
    try:
        descriptor = os.open(args.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"error: {args.key_file} already exists; refusing to overwrite it", file=sys.stderr)
        return 1
    with os.fdopen(descriptor, "w") as handle:
        handle.write(key + "\n")

    print(f"key written to {args.key_file}")
    print(f"KB_API_KEY_HASHES entry: {hash_key(key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

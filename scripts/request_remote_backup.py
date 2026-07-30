"""Trigger the backup API from a separate PythonAnywhere account or any host.

Required environment variables:
  BACKUP_API_URL=https://your-app.pythonanywhere.com/api/backup-db
  BACKUP_API_KEY=<the same secret configured on the application>
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    url = os.environ.get("BACKUP_API_URL", "").strip()
    api_key = os.environ.get("BACKUP_API_KEY", "")
    if not url or not api_key:
        print("Set BACKUP_API_URL and BACKUP_API_KEY before running this script.", file=sys.stderr)
        return 2

    request = Request(
        url,
        method="POST",
        headers={"X-Backup-API-Key": api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            payload = json.load(response)
    except HTTPError as error:
        print(f"Backup request failed: HTTP {error.code}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Backup request failed: {error.reason}", file=sys.stderr)
        return 1

    print(f"Backup created: {payload['filename']} ({payload['size_bytes']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

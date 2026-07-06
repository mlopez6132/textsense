"""Download NLTK corpora required by the AI humanizer (local dev helper)."""
from __future__ import annotations

import os
import sys
import time

import nltk

REQUIRED_PACKAGES = ("punkt_tab", "stopwords")
MAX_ATTEMPTS = 5


def get_nltk_data_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "NLTK_DATA",
            os.path.join(os.path.dirname(__file__), "..", "nltk_data"),
        )
    )


def download_with_retries(data_dir: str, package: str) -> None:
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            ok = nltk.download(package, download_dir=data_dir, quiet=False)
            if ok:
                return
            last_error = RuntimeError(f"nltk.download returned False for {package}")
        except Exception as exc:
            last_error = exc
        if attempt < MAX_ATTEMPTS:
            wait = attempt * 2
            print(f"Retrying {package} in {wait}s (attempt {attempt}/{MAX_ATTEMPTS})...")
            time.sleep(wait)
    raise RuntimeError(f"Failed to download {package}: {last_error}") from last_error


def main() -> int:
    data_dir = get_nltk_data_dir()
    os.makedirs(data_dir, exist_ok=True)

    for package in REQUIRED_PACKAGES:
        print(f"Downloading NLTK package: {package}")
        download_with_retries(data_dir, package)

    print(f"NLTK data installed to {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

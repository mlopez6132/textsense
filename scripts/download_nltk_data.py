"""Download NLTK corpora required by the AI humanizer at build/deploy time."""
from __future__ import annotations

import os
import sys

import nltk

REQUIRED_PACKAGES = ("punkt", "punkt_tab", "stopwords", "wordnet")


def get_nltk_data_dir() -> str:
    return os.path.abspath(
        os.environ.get(
            "NLTK_DATA",
            os.path.join(os.path.dirname(__file__), "..", "nltk_data"),
        )
    )


def main() -> int:
    data_dir = get_nltk_data_dir()
    os.makedirs(data_dir, exist_ok=True)

    for package in REQUIRED_PACKAGES:
        print(f"Downloading NLTK package: {package}")
        nltk.download(package, download_dir=data_dir, quiet=False)

    print(f"NLTK data installed to {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

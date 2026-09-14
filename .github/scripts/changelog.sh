#!/bin/bash
# Checks that CHANGELOG.md has an entry for pyproject.toml's current
# version - adapted from ladim's .github/scripts/changelog.sh (which reads
# ladim/__init__.py's __version__ instead of pyproject.toml).

set -e

version="$(grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "(.*)"/\1/')"
search_text="## [$version] -"
echo "Search for changelog entry: $search_text"

if grep -qF "$search_text" CHANGELOG.md; then
    echo "The entry '[$version]' exists in CHANGELOG.md"
else
    echo "The entry '[$version]' does not exist in CHANGELOG.md"
    exit 1
fi

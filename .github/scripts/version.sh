#!/bin/bash
# Checks that pyproject.toml's [project].version has been bumped, and not
# decreased, relative to the PR's base branch - adapted from ladim's
# .github/scripts/version.sh (which reads ladim/__init__.py's __version__
# instead of pyproject.toml).
#
# Assumes the standard `pull_request`-event checkout: actions/checkout
# checks out the merge commit refs/pull/<N>/merge, whose first parent
# (HEAD^1) is the base branch tip and whose tree matches the PR content -
# so `git show HEAD^1:pyproject.toml` reads the base branch's version
# without needing to know its branch name. Needs fetch-depth: 2 (or more)
# so HEAD^1 actually exists locally.

set -e

extract_version() {
    grep -m1 '^version = ' "$1" | sed -E 's/version = "(.*)"/\1/'
}

git show HEAD^1:pyproject.toml > pyproject.toml.compare
new_version="$(extract_version pyproject.toml)"
old_version="$(extract_version pyproject.toml.compare)"
rm -f pyproject.toml.compare

echo "Old: $old_version"
echo "New: $new_version"

if [ "$new_version" == "$old_version" ]; then
    echo "Version number not updated"
    exit 1
fi

IFS='.' read -r old_major old_minor old_patch <<< "$old_version"
IFS='.' read -r new_major new_minor new_patch <<< "$new_version"

if [ "$old_major" -gt "$new_major" ]; then
    echo "Old version major ($old_major) is greater than new version major ($new_major)"
    exit 1
elif [ "$old_major" -eq "$new_major" ] && [ "$old_minor" -gt "$new_minor" ]; then
    echo "Old version minor ($old_minor) is greater than new version minor ($new_minor)"
    exit 1
elif [ "$old_major" -eq "$new_major" ] && [ "$old_minor" -eq "$new_minor" ] && [ "$old_patch" -gt "$new_patch" ]; then
    echo "Old version patch ($old_patch) is greater than new version patch ($new_patch)"
    exit 1
fi

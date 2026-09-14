#!/usr/bin/env bash
# Builds a wheel of the platform-agnostic `partikkelspredning` package (from
# the repo root, `..` relative to this file) into `api/vendor/`, so that
# `api/requirements.txt`'s `--find-links vendor` line can install it without
# needing `..` to exist at install time.
#
# This matters for two different reasons depending on when it's run:
#   - `func azure functionapp publish` (remote/Oryx build): only the `api/`
#     folder is uploaded, so `..` genuinely doesn't exist during that build -
#     the wheel has to be inside `api/` beforehand.
#   - local `func start`: `..` *does* exist, but a plain (non-editable)
#     install from it is simplest kept identical to the deploy path rather
#     than special-cased, so local dev exercises the same install mechanism
#     as a real deployment.
#
# `partikkelspredning` itself is pure Python (no compiled extensions), so a
# wheel built on any machine/OS installs fine on Azure's Linux Functions
# host regardless of where this script runs.
#
# Run this before `pip install -r requirements.txt` (local `func start`) and
# before `func azure functionapp publish` (see this folder's README).
set -euo pipefail
cd "$(dirname "$0")"

rm -rf vendor
mkdir -p vendor
pip wheel --no-deps -w vendor ..

echo "Built: $(ls vendor)"

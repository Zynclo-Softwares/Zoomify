#!/usr/bin/env bash
# Compare canonical backend env names with what Terraform syncs to Railway.
set -euo pipefail
cd "$(dirname "$0")"

python3 - <<'PY'
import ast
import json
import re
import subprocess
import sys


def tf_json_output(name):
    try:
        raw = subprocess.check_output(["terraform", "output", "-json", name], text=True)
        return json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def tf_console(expr):
    try:
        raw = subprocess.check_output(
            ["terraform", "console"],
            input=expr + "\n",
            text=True,
        )
        line = raw.strip().splitlines()[-1].strip()
        if line.startswith("["):
            return ast.literal_eval(line)
    except (subprocess.CalledProcessError, SyntaxError, ValueError):
        return None
    return None


expected = tf_json_output("backend_env_var_names") or tf_console("local.backend_env_var_names")
synced = tf_json_output("railway_synced_variable_names") or []

if expected is None:
    print("Could not read backend_env_var_names from Terraform.", file=sys.stderr)
    sys.exit(1)

expected = set(expected)
synced = set(synced)

print("# Backend env parity (root .env.example ↔ Railway)")
print(f"expected: {len(expected)}  synced: {len(synced)}")
missing = sorted(expected - synced)
extra = sorted(synced - expected)
if missing:
    print("\nMissing on Railway (run terraform apply):")
    for name in missing:
        print(f"  - {name}")
if extra:
    print("\nExtra on Railway (not in catalog):")
    for name in extra:
        print(f"  - {name}")
if not missing and not extra and synced:
    print("\nOK — all backend env vars are configured for Railway sync.")
elif not synced:
    print("\nNo Railway variables in state yet — run: terraform apply")
PY

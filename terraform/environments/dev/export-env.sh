#!/usr/bin/env bash
# Print Zoomify Stripe env vars from Terraform outputs (run after apply).
set -euo pipefail
cd "$(dirname "$0")"
terraform output -json env_vars | python3 -c '
import json, sys
data = json.load(sys.stdin)
for key, value in data.items():
    if value is None:
        continue
    print(f"{key}={value}")
'

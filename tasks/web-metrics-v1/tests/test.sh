#!/bin/sh
set -eu
mkdir -p /logs/verifier
if node /tests/verify.cjs /app; then printf '1\n' > /logs/verifier/reward.txt; else printf '0\n' > /logs/verifier/reward.txt; fi

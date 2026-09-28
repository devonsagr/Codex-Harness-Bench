#!/bin/sh
set -eu
mkdir -p /logs/verifier
if python -I /tests/verify.py /app; then printf '1\n' > /logs/verifier/reward.txt; else printf '0\n' > /logs/verifier/reward.txt; fi

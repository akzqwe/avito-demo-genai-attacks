#!/usr/bin/env bash
# Bootstrap & run the demo. Idempotent.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --quiet --disable-pip-version-check -r requirements.txt

echo
echo "=== Avito GenAI Security Demo ==="
echo "  User chat:      http://localhost:8000/"
echo "  Admin panel:    http://localhost:8000/admin"
echo "  Attacker log:   http://localhost:8000/attacker"
echo

exec uvicorn backend.main:app --host 127.0.0.1 --port 8000 "$@"

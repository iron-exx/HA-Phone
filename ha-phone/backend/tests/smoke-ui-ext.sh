#!/usr/bin/env bash
# smoke-ui-ext.sh — end-to-end: POST /api/extensions → verify pjsip_extensions.conf written
set -e
BASE_URL="${1:-http://localhost:80}"
echo "Smoke: adding extension 20..."
curl -sf -X POST "$BASE_URL/api/extensions" \
  -H "Content-Type: application/json" \
  -d '{"number": 20, "display_name": "Smoke Test", "sip_password": "smokepass1234"}' \
  | grep -q '"number":20' || { echo "FAIL: POST /api/extensions did not return number 20"; exit 1; }
echo "Smoke: checking pjsip_extensions.conf..."
grep -q "\[20\]" /data/asterisk/pjsip_extensions.conf || { echo "FAIL: [20] not in pjsip_extensions.conf"; exit 1; }
echo "PASS"

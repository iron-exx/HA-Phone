#!/usr/bin/env bash
# verify-phase1.sh — Phase 1 smoke tests (local Docker, not HA)
# Usage: ./scripts/verify-phase1.sh [container-name-or-id]
# Default container name: hassio-bpx-test
set -euo pipefail

CONTAINER="${1:-hassio-bpx-test}"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local cmd="$2"
    local expected="$3"
    local result
    result=$(eval "${cmd}" 2>&1 || true)
    if echo "${result}" | grep -q "${expected}"; then
        echo "  PASS: ${desc}"
        (( PASS++ )) || true
    else
        echo "  FAIL: ${desc}"
        echo "        Expected to find: ${expected}"
        echo "        Got: ${result}"
        (( FAIL++ )) || true
    fi
}

echo "=== hassio-bpx Phase 1 Smoke Tests ==="
echo "Container: ${CONTAINER}"
echo ""

echo "[ADD-03] Asterisk version..."
check "Asterisk 22.x running" \
    "docker exec ${CONTAINER} asterisk -rx 'core show version' 2>/dev/null" \
    "Asterisk 22"

echo "[ADD-04] Ingress placeholder HTTP..."
check "Port 80 returns HTTP 200" \
    "docker exec ${CONTAINER} curl -s -o /dev/null -w '%{http_code}' http://localhost:80/" \
    "200"

echo "[ADD-05/ADD-06] /data/ directory structure..."
check "/data/ initialized sentinel" \
    "docker exec ${CONTAINER} test -f /data/.initialized && echo ok" \
    "ok"
check "/data/voicemail exists" \
    "docker exec ${CONTAINER} test -d /data/voicemail && echo ok" \
    "ok"
check "/data/logs/asterisk exists" \
    "docker exec ${CONTAINER} test -d /data/logs/asterisk && echo ok" \
    "ok"

echo "[SEC-01] AMI bound to 127.0.0.1..."
check "AMI (5038) on 127.0.0.1 only" \
    "docker exec ${CONTAINER} ss -tlnp 2>/dev/null || docker exec ${CONTAINER} netstat -tlnp 2>/dev/null" \
    "127.0.0.1:5038"

echo "[SEC-02] ARI bound to 127.0.0.1..."
check "ARI HTTP (8088) on 127.0.0.1 only" \
    "docker exec ${CONTAINER} ss -tlnp 2>/dev/null || docker exec ${CONTAINER} netstat -tlnp 2>/dev/null" \
    "127.0.0.1:8088"

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="
if [[ "${FAIL}" -gt 0 ]]; then
    exit 1
fi

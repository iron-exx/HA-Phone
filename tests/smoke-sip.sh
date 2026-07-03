#!/usr/bin/env bash
# smoke-sip.sh — Phase 2 SIP Core smoke tests (local Docker, not HA)
# Usage: ./tests/smoke-sip.sh [container-name-or-id]
# Default container name: hassio-bpx-test
#
# Covers: TRUNK-01 (registration), TRUNK-04 (AMI status), TRUNK-05 (auth-username),
#         EXT-01 (extension AORs present)
# Manual-only: TRUNK-02 (inbound call), TRUNK-03 (outbound call), EXT-04 (two-way audio)
set -euo pipefail

CONTAINER="${1:-hassio-bpx-test}"
AMI_SECRET="${AMI_SECRET:-changeme-replace-in-phase3}"
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

echo "=== hassio-bpx Phase 2 SIP Core Smoke Tests ==="
echo "Container: ${CONTAINER}"
echo ""

# ── TRUNK-01: DG trunk registration ──────────────────────────────────────────
echo "[TRUNK-01] DG trunk registration status..."
check "TRUNK-01: pjsip show registrations responds" \
    "docker exec ${CONTAINER} asterisk -rx 'pjsip show registrations' 2>/dev/null" \
    "dg-registration"

check "TRUNK-01: DG trunk shows Registered" \
    "docker exec ${CONTAINER} asterisk -rx 'pjsip show registrations' 2>/dev/null" \
    "Registered"

# ── TRUNK-04: AMI PJSIPShowRegistrationsOutbound ─────────────────────────────
echo "[TRUNK-04] AMI trunk status..."
check "TRUNK-04: AMI login succeeds" \
    "docker exec ${CONTAINER} bash -c \"printf 'Action: Login\r\nUsername: bpx-admin\r\nSecret: ${AMI_SECRET}\r\n\r\n' | nc -q1 127.0.0.1 5038 2>/dev/null\"" \
    "Authentication accepted"

check "TRUNK-04: AMI PJSIPShowRegistrationsOutbound returns OutboundRegistrationDetail" \
    "docker exec ${CONTAINER} bash -c \"printf 'Action: Login\r\nUsername: bpx-admin\r\nSecret: ${AMI_SECRET}\r\n\r\nAction: PJSIPShowRegistrationsOutbound\r\n\r\n' | nc -q1 127.0.0.1 5038 2>/dev/null\"" \
    "OutboundRegistrationDetail"

# ── TRUNK-05: Auth-username separate from phone number ───────────────────────
echo "[TRUNK-05] Auth-username field in pjsip_trunk.conf..."
check "TRUNK-05: [dg-auth] stanza exists in pjsip_trunk.conf" \
    "docker exec ${CONTAINER} grep -c '^\[dg-auth\]' /data/asterisk/pjsip_trunk.conf 2>/dev/null" \
    "1"

check "TRUNK-05: username field present in [dg-auth]" \
    "docker exec ${CONTAINER} grep -A5 '^\[dg-auth\]' /data/asterisk/pjsip_trunk.conf 2>/dev/null" \
    "username"

# ── EXT-01: Extension AORs present ────────────────────────────────────────────
echo "[EXT-01] Extension AOR registration..."
check "EXT-01: ext10 AOR exists" \
    "docker exec ${CONTAINER} asterisk -rx 'pjsip show aors' 2>/dev/null" \
    "ext10"

check "EXT-01: ext11 AOR exists" \
    "docker exec ${CONTAINER} asterisk -rx 'pjsip show aors' 2>/dev/null" \
    "ext11"

check "EXT-01: ext12 AOR exists" \
    "docker exec ${CONTAINER} asterisk -rx 'pjsip show aors' 2>/dev/null" \
    "ext12"

# ── Manual verification instructions ─────────────────────────────────────────
echo ""
echo "--- Manual verifications required (not automated) ---"
echo "TRUNK-02: Call DG DID from external PSTN number → ext 10, 11, 12 must ring simultaneously"
echo "TRUNK-03: From ext 10, dial external PSTN number → call connects with two-way audio"
echo "EXT-04:   From ext 10, dial 11 → two-way audio (both sides hear each other)"
echo ""

echo "=== Results: ${PASS} passed, ${FAIL} failed ==="
if [[ "${FAIL}" -gt 0 ]]; then
    exit 1
fi

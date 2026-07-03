#!/usr/bin/env bash
# Local Docker build helper for hassio-bpx
# Usage: ./scripts/build-local.sh [--no-cache]
set -euo pipefail

BUILD_FROM="ghcr.io/hassio-addons/debian-base:7.3.0"
ASTERISK_VERSION="22.10.0"
TAG="hassio-bpx:local"

echo "Building hassio-bpx image (Asterisk ${ASTERISK_VERSION})..."
echo "This takes ~10 minutes on a first build."

docker build \
  --build-arg BUILD_FROM="${BUILD_FROM}" \
  --build-arg ASTERISK_VERSION="${ASTERISK_VERSION}" \
  -t "${TAG}" \
  "$@" \
  ./hassio-bpx/

echo "Build complete: ${TAG}"
echo ""
echo "To verify Asterisk version:"
echo "  docker run --rm ${TAG} asterisk -V"
echo ""
echo "To run smoke tests:"
echo "  ./scripts/verify-phase1.sh"

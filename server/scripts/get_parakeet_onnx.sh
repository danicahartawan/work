#!/usr/bin/env bash
# Download NVIDIA Parakeet-TDT-0.6b-v2 (int8 ONNX export) for CPU inference
# with the open-source sherpa-onnx runtime. ~700 MB.
#
# Usage: ./scripts/get_parakeet_onnx.sh [target-dir]
set -euo pipefail

TARGET="${1:-models/parakeet-tdt-0.6b-v2-onnx}"
NAME="sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
URL="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/${NAME}.tar.bz2"

mkdir -p "$TARGET"
echo "Downloading ${NAME} ..."
curl -L --fail --progress-bar -o "/tmp/${NAME}.tar.bz2" "$URL"
tar xjf "/tmp/${NAME}.tar.bz2" -C "$TARGET" --strip-components=1
rm -f "/tmp/${NAME}.tar.bz2"

echo "Done. Files in $TARGET:"
ls -la "$TARGET"
echo
echo "Run the server with:  PERCH_ENGINE=onnx PERCH_ONNX_DIR=$TARGET uvicorn app.main:app"

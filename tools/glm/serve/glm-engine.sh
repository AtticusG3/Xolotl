#!/usr/bin/env bash
# glm-engine.sh - the GLM engine as Strata's server starts it (`<exe> --serve <args>`), with memguard's protections
# in the FOREGROUND (memguard.sh backgrounds its command, which would give it /dev/null as stdin and break the
# stdin/stdout protocol): ComfyUI check, the shared GPU lock (held while the server runs), a 84 GiB RAM cap, no swap.
set -u
cd "$(dirname "$0")/../../.."
if [ "${MEMGUARD_ALLOW_COMFY:-0}" != 1 ] && ss -ltn 2>/dev/null | grep -q ':8188 '; then
    echo "glm-engine: refusing - ComfyUI is running on :8188 (RAM)" >&2; exit 3
fi
LOCK="${DS4_LOCK:-$HOME/.quetza-data/conductor/ds4-gpu.lock}"
export GGML_NO_BACKTRACE=1
# xolotl: the unified tree builds every engine into build-xolotl; STRATA_BUILD_DIR overrides it, and the
# pre-merge build dir (build-glm-gpu) is still found so an old checkout of this script keeps working
BUILD_DIR="${STRATA_BUILD_DIR:-$PWD/build-xolotl}"
[ -x "$BUILD_DIR/glm_generate" ] || [ ! -x "$PWD/build-glm-gpu/glm_generate" ] || BUILD_DIR="$PWD/build-glm-gpu"
exec flock "$LOCK" systemd-run --user --scope -q --unit="glm-serve-$$" -p MemoryMax=84G -p MemorySwapMax=0 \
    "$BUILD_DIR/glm_generate" "$@"

#!/usr/bin/env bash
# Configure a Buster (2x V100 sm_70) build. Needs CUDA 12.x (CUDA 13 dropped Volta) and a host GCC nvcc accepts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="${1:-$ROOT/build-buster}"
GGML="${STRATA_GGML_DIR:-$ROOT/third_party/llama.cpp}"
# 70-real: embed native sm_70 SASS (Volta has no PTX JIT on driver 550 + CUDA 12.9 minor-compat).
cmake -S "$ROOT" -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DSTRATA_ENABLE_CUDA=ON -DSTRATA_GGML_CUDA=ON -DSTRATA_MMQ_KQUANTS=ON \
  -DSTRATA_EXPERIMENTAL_SM60=ON -DCMAKE_CUDA_ARCHITECTURES=70-real \
  -DSTRATA_GGML_DIR="$GGML" -DSTRATA_BUILD_TESTS=ON \
  -DSTRATA_DSV41_FQ_OP="${STRATA_DSV41_FQ_OP:-OFF}" \
  -DSTRATA_DSV41_HC_MIX="${STRATA_DSV41_HC_MIX:-OFF}"
echo "Configured $BUILD for Buster (sm_70-real SASS, STRATA_EXPERIMENTAL_SM60=ON)"
echo "  ninja -C $BUILD ds41_generate test_cuda_cc_policy test_ds41_pipeline test_ds41_geometry"
echo "  ctest -R 'test_cuda_cc_policy|test_ds41_pipeline|test_ds41_geometry' --test-dir $BUILD"

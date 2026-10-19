# Buster: DeepSeek-V4.1-Flash-1017 on 2x Tesla V100-32GB

This page is for **buster** only: dual V100-SXM2 (sm_70), Broadwell dual-socket host RAM, fast NVMe for Engram, SATA/NVMe for the GSQ GGUF. It is not a supported matrix entry for arbitrary hardware.

## What works today (this branch)

| Area | Status |
| --- | --- |
| Build for sm_70 (`STRATA_EXPERIMENTAL_SM60`, CUDA 12.x) | Supported via `tools/buster/cmake-buster.sh` |
| **Layer split across both V100s (DS41)** | **Implemented**: `--layer-split` + `gpu: [1,2]` in router JSON; PCIe handoff of dense state between stages; per-stage expert VRAM caches and halved pinned arena budget |
| `ds41_generate` on 2x V100 (64 GB VRAM + ~58 GiB pinned arena per card policy) | Intended buster path |
| Prompt prefill on Volta | **MMVQ / dp4a** (`--no-chunk-mmq`); chunk-MMQ auto-disabled below sm_75 (issue #5) |
| Strata `serve/server.py` + `serve_ds41.py` | OpenAI / Anthropic APIs, `/health`, Prometheus, billing-header pin (`serve/frontend.py`) |
| **Conversation cache (DS41)** | **Implemented**: `--conversation-cache-mib`, `--conversation-cache-slots`, `--conversation-cache-min-tokens`, multi-stage `capture_conversation` / `restore_conversation`, Strata log lines for `server.py` metrics |
| **Prompt-cache checkpoints** | **Partial**: `--prompt-cache-every` triggers checkpoint capture during serve; optional `--prompt-cache-root` disk spill (simple DS41 blob files, not full Qwen session identity) |
| DSpark / MTP speculative decode | Code path exists; **not validated on sm_70** |

### Memory budget (target)

- **VRAM (both cards):** ~64 GB total for hot experts + dense/KV working set (split at layer 20 by default in `strata-buster-ds41-1017.json`).
- **RAM:** ~58 GiB pinned expert arena (`--arena-gib`, split across stages); leave headroom for OS and helpers.
- **Disk:** ~152 GiB GSQ GGUF + ~200 GiB Engram; Engram on **ext4/xfs/btrfs or NTFS**, not exFAT.

Quant: **GSQ** from `tools/v41/` applied to **1017** weights (`rank.bin` from 1017, not older GGUF).

## Build (on buster)

```bash
git clone <this-fork> /opt/xolotl && cd /opt/xolotl
bash tools/xolotl/fetch-llama.sh
bash tools/buster/cmake-buster.sh /opt/xolotl/build-buster
ninja -C /opt/xolotl/build-buster ds41_generate serve_ds41 test_cuda_cc_policy test_ds41_pipeline test_ds41_ops
```

CPU-only sanity on any machine:

```bash
c++ -std=c++17 -I include tools/buster/test_cuda_cc_policy.cpp -o /tmp/test_cuda_cc_policy && /tmp/test_cuda_cc_policy
ninja -C build-buster test_ds41_pipeline && ctest -R test_ds41_pipeline --test-dir build-buster
```

## Run

```bash
export CUDA_VISIBLE_DEVICES=1,2
export STRATA_BUILD_DIR=/opt/xolotl/build-buster
python3 tools/v41/serve/serve_ds41.py --engine strata --config tools/v41/serve/strata-buster-ds41-1017.json --port 8150
```

`server.py` adds `--layer-split 20` from `layer_split` and sets `CUDA_VISIBLE_DEVICES` from `gpu: [1,2]` (PCI bus order).

## Validation plan (run on buster)

1. **Smoke:** `curl http://127.0.0.1:8150/health`; stderr should show `ds41: layer split at layer 20 across GPUs 0 and 1` (visible indices after `CUDA_VISIBLE_DEVICES`).
2. **Dual-GPU:** `nvidia-smi` during decode should show memory use on **both** cards.
3. **Conversation cache:** interleave two long prompts; stderr should include `strata serve: conversation cache: parked` and `restored`.
4. **Logits:** compare `--dump-last` / `--ppl` against a known-good single-GPU or 4090 run (buster-only).
5. **Unit tests (no GPU):** `test_cuda_cc_policy`, `test_ds41_pipeline`, `test_ds41_ops`.

## sm_70 kernel notes

Unchanged from prior doc: chunk-MMQ off, MMVQ default, `STRATA_PROMPT_ATTN_OLD=1`, `STRATA_BF16_TC=1` via `buster-engine.sh`.

## Upstream cherry-picks

Strata-V100 commits for Qwen layer-split tuning and full disk session identity are **not** required for DS41's blob-based cache. Serve-path fixes (billing-header pin, frontend) are already in this fork's `serve/`.

## Known risks (buster must verify)

1. **End-to-end dual-GPU throughput and correctness** on real 2x V100 hardware (this CI environment has no sm_70 GPUs).
2. **DSpark on sm_70** untested.
3. **Prompt-cache disk tier** uses a lightweight DS41 format; not byte-compatible with Qwen `conversation_file` sessions.
4. **`--split-skip-if-fits`** accepted for router compatibility; not implemented for DS41 (split always runs when configured).

# Buster: DeepSeek-V4.1-Flash-1017 on 2x Tesla V100-32GB

This page is for **buster** only: dual V100-SXM2 (sm_70), Broadwell dual-socket host RAM, fast NVMe for Engram, SATA/NVMe for the GSQ GGUF. It is not a supported matrix entry for arbitrary hardware.

## What works today (this branch)

| Area | Status |
| --- | --- |
| Build for sm_70 (`STRATA_EXPERIMENTAL_SM60`, CUDA 12.x) | Supported via `tools/buster/cmake-buster.sh` |
| `ds41_generate` on one V100 (32 GB VRAM + ~58–90 GiB pinned arena) | Intended path; fits the same GSQ tiering as the RTX 4090 recipe |
| Prompt prefill on Volta | **MMVQ / dp4a** (`--no-chunk-mmq`); chunk-MMQ is auto-disabled below sm_75 (see issue #5 title) |
| Strata `serve/server.py` + `serve_ds41.py` | OpenAI / Anthropic APIs, `/health`, Prometheus, billing-header pin (`serve/frontend.py`) |
| Config JSON shape (`exe`, `args`, `tokenizer`, `gpu`, `layer_split`, …) | Accepted; several Strata-only flags are parsed and ignored until wired (see below) |
| DSpark / MTP speculative decode | Code path exists; **not validated on sm_70** |
| **Layer split across both V100s for DS41** | **Not implemented** — config may list `layer_split`; engine logs a warning and runs on the first visible GPU only |
| **Disk-tier conversation cache for DS41** | **Not implemented** — flags are accepted for router compatibility; DS41 uses in-engine `park` / snapshot reuse only |
| **Prompt-cache checkpoints for DS41** | **Not implemented** (same as conversation cache) |

### Memory budget (target)

- **VRAM (both cards, when layer split lands):** ~64 GB total for hot experts + dense/KV working set; today ~32 GB on one card.
- **RAM:** ~58–90 GiB pinned expert arena (`--arena-gib`); leave headroom for OS and helper processes on the 3090 box.
- **Disk:** ~152 GiB GSQ GGUF + ~200 GiB Engram tables (layers 1 and 14); Engram must sit on **ext4/xfs/btrfs or NTFS**, not exFAT.

Quant: use the existing **GSQ** build from `tools/v41/` (`IndrasMirror/DeepSeek-V4.1-Flash-GSQ-Uncensored` recipe applied to **1017** weights). Architecture matches V4.1; weights and `rank.bin` must be built from 1017, not reused from an older GGUF.

## Build (on buster)

CUDA **12.x** required (CUDA 13 removed sm_70). GCC version must be one nvcc accepts (often GCC 11 or 12).

```bash
git clone <this-fork> /opt/xolotl && cd /opt/xolotl
bash tools/xolotl/fetch-llama.sh    # pinned llama.cpp + patches
bash tools/buster/cmake-buster.sh /opt/xolotl/build-buster
ninja -C /opt/xolotl/build-buster ds41_generate serve_ds41 test_cuda_cc_policy test_ds41_ops
```

Optional ggml fusions (4090 defaults): patch `third_party/llama.cpp` per `tools/v41/ggml/*.patch` and set `-DSTRATA_DSV41_FQ_OP=ON` / `-DSTRATA_DSV41_HC_MIX=ON` in `cmake-buster.sh`.

CPU-only sanity on any machine:

```bash
c++ -std=c++17 -I include tools/buster/test_cuda_cc_policy.cpp -o /tmp/test_cuda_cc_policy && /tmp/test_cuda_cc_policy
```

## Model download and layout

### 1. FP8 checkpoint (quant input)

```bash
export V41_SRC="/data/checkpoints/DeepSeek-V4.1-Flash-1017"
bash tools/v41/fetch_v41.sh "$V41_SRC" deepseek-ai/DeepSeek-V4.1-Flash-1017
# or: bash tools/v41/fetch_1017.sh  (project helper for multi-drive layout)
```

All 48 shards are required (config matches V4.1 but bytes differ from older releases). See `docs/ds4/V41_1017_QUANT_PLAN.md`.

### 2. GSQ GGUF + rank + sidecar

Follow `docs/ds4/V41_1017_QUANT_PLAN.md` steps 2–9 with `V41_SRC` pointing at 1017 shards. Place the GGUF on fast storage (SATA SSD is fine for sequential expert read; Engram wants NVMe).

### 3. Engram tables (~200 GB)

```bash
python3 tools/v41/extract_engram.py "$V41_SRC" \
  --to layers.1=/nvme/engram/layers.1 \
  --to layers.14=/nvme/engram/layers.14 \
  --verify 64
```

Use **mmap** (default in engine) or ensure the filesystem handles high **random read** concurrency; avoid exFAT.

### 4. Tokenizer + DSpark sidecar

```bash
python3 tools/v41/serve/export_tokenizer.py -m /data/models/V41-GSQ-1017/V41-GSQ-1017.gguf -o /data/models/V41-GSQ-1017/tokenizer
python3 tools/v41/v41_sidecar.py --out /data/models/V41-GSQ-1017/V41-MTP-Vision-1017.gguf
```

Point `STRATA_SERVE_DSPARK` at the requantized Q2_K sidecar in `buster-engine.sh` when ready.

## Run

PCI bus order on buster: compute GPUs are **1 and 2**. Hide the busy RTX 3090 from the DS41 process:

```bash
export CUDA_VISIBLE_DEVICES=1,2
export STRATA_BUILD_DIR=/opt/xolotl/build-buster
```

Edit paths in `tools/v41/serve/strata-buster-ds41-1017.json`, then:

```bash
cd /opt/xolotl
python3 tools/v41/serve/serve_ds41.py --engine strata --config tools/v41/serve/strata-buster-ds41-1017.json --port 8150
```

`buster-engine.sh` sets Volta kernel env defaults (`STRATA_SM70_TABLE`, `STRATA_PROMPT_ATTN_OLD`, `STRATA_BF16_TC`). Tune `--pcie`, `--route-bias*`, and `--arena-gib` with `tools/v41/serve/drive_engine.py` on buster.

## Validation plan (run on buster)

Record driver, CUDA, commit hash, and `build-buster/BUILD.json` if present.

### 1. Smoke

```bash
curl -s http://127.0.0.1:8150/health
./build-buster/ds41_generate -m ... --ids 1,2,3 -n 8 --backend cuda --experts gpu --engram ... --rank ... --no-chunk-mmq
```

Expect `READY` from serve and 8 tokens without `ERR`.

### 2. Logit / perplexity vs reference

On a fixed prompt file (e.g. 4096 tokens from calibration):

```bash
./build-buster/ds41_generate -m ... --ids-file prompt.i32 --ppl --no-chunk-mmq --backend cuda --experts gpu ...
```

Compare to FP8 teacher or a known-good 4090 GSQ run (`--dump-last` md5). Volta MMVQ prefill should match **last-token** logits; full-row `--ppl` uses the non–enc-skip path.

### 3. Decode throughput

```bash
python3 tools/v41/serve/drive_engine.py /tmp/out.json /tmp/eng.log 524288 reqs.json --no-chunk-mmq
```

Report tok/s for 256-token decode after 6K and 16K prompts. Expect **well below** 4090 numbers (memory/PCIe bound; community V100 MoE on Qwen was ~30–80 tok/s depending on engine version).

### 4. Conversation reuse (DS41 park path)

Two requests where the second extends the first; check stderr for `serve: unparked` / `RESUME` and wall time vs a cold second prompt. Full Strata **conversation cache** log lines (`conversation cache: parked`) will **not** appear until DS41 uses `generate.cpp`'s cache.

### 5. Regression tests (no GPU)

```bash
ninja -C build-buster test_cuda_cc_policy test_ds41_ops test_ds41_geometry
ctest -R 'test_cuda_cc_policy|test_ds41_ops' --test-dir build-buster
```

## sm_70 kernel notes

| Feature | sm_75+ | sm_70 on Buster |
| --- | --- | --- |
| int8 tensor-core MMQ (chunk-MMQ) | On | **Off** (auto; heap corruption reported on V100) |
| Expert prompt MMVQ / dp4a | Fallback | **Default** |
| QSA prompt attention m16n8k16 + cp.async | On | `prompt_attn_v70_kernel` (m8n8k4) via `STRATA_PROMPT_ATTN_OLD=1` |
| BF16 dense projections | Native / TC | FP16 TC path (`STRATA_BF16_TC=1`) |
| FP8 / NVFP4 in kernels | Partial | KV **storage** `--kv-fp4` is fine; no FP8 MMA on Volta |

## Upstream cherry-picks (Qwen / Strata core — not DS41)

For **Qwen3.8** on the same box, cherry-pick from [Strata-V100](https://github.com/jmnargi/Strata-V100) (conversation cache tiering, V100 pipeline profile):

| Upstream SHA | Subject | Why |
| --- | --- | --- |
| `091ea25` | Share conversation prefixes across RAM and disk caches | Prefix-aware conversation cache (#66) |
| `d2477d03` | Fix checkpoint archive append reuse after full prefill | Prompt-cache correctness (#65) |
| `4794367f` | Preserve historical conversation checkpoints across cache tiers | Tiered retention (#64) |
| `be57cc2a` | perf(v100): select measured dual-GPU pipeline service profile | Layer-split service tuning (#62) |

Xolotl already carries much of upstream Strata at 0.1.44.1 (`serve/server.py`, billing pin, metrics). Re-apply Strata-V100 commits only where `git log` shows the fix is missing on your branch.

## Known risks

1. **Single-GPU DS41** until layer split is ported — only one 32 GB VRAM pool; second V100 idle.
2. **MMVQ prefill** ~130 tok/s ceiling cited for V100 (issue #5 title) vs 250+ tok/s with MMQ on RTX 40.
3. **DSpark on sm_70** untested; disable with `STRATA_SERVE_DSPARK=` if verify crashes.
4. **Conversation / prompt cache flags** in JSON do not change DS41 behaviour yet.
5. **Broadwell DDR4** bandwidth may bound decode more than GPU compute (see community V100 benchmarks in `bench/results/`).

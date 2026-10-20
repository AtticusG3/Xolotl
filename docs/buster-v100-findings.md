# Buster V100 experiment: DeepSeek V4.1 on dual Tesla V100

Status: **closed** (October 2026). The stack runs correctly after the fixes on branch `kw27/buster-v100-dac5`, but decode throughput is far below Qwen on the same host (~65–80 tok/s). DeepSeek V4.1 on this hardware is not practical for daily use.

## Hardware and model

| Item | Detail |
| --- | --- |
| GPUs | 2× NVIDIA Tesla V100-SXM2 32 GB (sm_70) + 1× RTX 3090 24 GB (sm_86) on one machine ("buster") |
| Host | Broadwell dual-socket, large system RAM |
| Storage | Fast NVMe for Engram tables; model weights on NVMe/SATA |
| Model | `V41-XQ-1017.gguf` (~152 GB on disk), DeepSeek-V4.1-Flash quantized |
| MoE | Routed experts resident in **system RAM**; GPU holds a **PCIe expert cache** (arena + adaptive swaps) |

Volta has no PTX JIT fallback: builds must ship **native sm_70** SASS (`tools/buster/cmake-buster.sh` sets `70-real;86-real`). Driver 550 with CUDA 12.9 relies on minor-version compatibility; see `BUSTER.md`.

## How we deployed it

1. **Build:** `STRATA_BUILD_TYPE=RelWithDebInfo bash tools/buster/cmake-buster.sh /opt/xolotl/build-buster` then `ninja -C build-buster ds41_generate`.
2. **Serve (typical 2× V100 trunk):** `python3 tools/v41/serve/serve_ds41.py` with `tools/v41/serve/strata-buster-ds41-1017.json` (`gpu: [1,2]`, `layer_split: "20"`, `CUDA_VISIBLE_DEVICES` set from PCI order).
3. **Engine flags:** `--backend cuda`, `--experts gpu`, `--kv-fp4`, `--arena-gib`, `--pcie`, `--prompt-batch 8192`, optional `--head-device` and multi-stage `--stage-devices` / `--layer-split` / `--stage-pcie`.
4. **DSpark:** sidecar weights via `STRATA_DSPARK` or serve config; draft stack must run on the GPU that owns the head (see `ac0cbe8a`).

Handoff between stages uses peer memcpy when a bidirectional test copy succeeds, otherwise pinned host staging (`STRATA_SELFTEST_HANDOFF=1` validates boundaries at load).

## Fixes landed on this effort (PR #1)

| Commit | What it fixed |
| --- | --- |
| `5e92d695` | Layer-major prefill on stage 1: wrong `span_cap` → "bad span" on split pipelines |
| `b21fddc2` | Stage-1 VRAM expert cache seed: `cudaSetDevice` in workers; seed cache at READY |
| `f258dd2c` | `KEEP_CACHE`: soft-fail only when ≥1.5 GiB VRAM headroom; multi-stage regrow |
| `ac0cbe8a` | DSpark draft stack on wrong GPU under layer split; run on head GPU |
| `495c57b0`–`99ca57fe` | N-stage pipeline, pinned handoff without P2P, indexer shadow layers, cross-stage KV handoff |
| `f4ae4838` | Peer P2P only if test memcpy each way is exact (false positives on host bridges) |
| `5359947e` | Layer splits 9,25 no longer snapped to 8,20 when shadow import covers deps |
| `3a66da7d` | Head-only `alloc_cols` OOB (`im.ly` empty); `snapshot`/`park` skipping non-local null `raw` tensors |

Earlier buster scaffolding: `tools/buster/*`, per-GPU `slot_gib` expert cache, sm_70 MMQ gate, conversation cache on ds41 serve.

Cherry-picks from `jmnargi/Strata-V100` on shared Strata paths: elastic KV in pipelined decode, split overlap/wait env vars, serve config arg splitting (see PR description). Not exercised on buster for ds41 decode (Strata `generate` layer-split path).

## Results (measured on buster)

Compared to **Qwen3.8 / Strata on the same box: ~65–80 tok/s decode** (reference only; not re-run for this write-up).

### Two V100s, layer split at 20 (production-shaped config)

| Configuration | Decode throughput | Notes |
| --- | --- | --- |
| Baseline split 20 | ~13–17 tok/s | Best short prose ~**14.5 tok/s** |
| + DSpark (`ac0cbe8a` era) | ~14–20 tok/s | ~**1.2–1.7** tokens accepted per verify pass; small gain on short prose |
| Long prompt tail | 18.5–20.3 tok/s with DSpark | vs 16.4–17.1 without DSpark |

DSpark helps most after long prompts; acceptance rate stays low so wins are modest.

### Three stages (3090 + 2× V100), split 9,25, `--stage-pcie 0.55,0.25,0.25` (commit `3a66da7d`)

Load ~**200 s**; handoff 0→1 pinned-host, 1→2 peer; ~8184 experts in VRAM; ~23.5 GB on 3090, ~31.8 GB per V100.

| Configuration | Decode throughput | Notes |
| --- | --- | --- |
| `--head-device 0`, no DSpark | **~5.3 tok/s** | Head on 3090 ~**135 ms/token**; extra host round trips |
| No head-device, with DSpark | **~6.9 tok/s** | ~**1.45** tokens accepted per pass |
| vs 2× V100 @ ~14.5 tok/s | | **3-stage is slower than 2-stage** |

**Conclusion:** Using the 3090 as an extra pipeline stage (or head offload path tested here) costs more than it saves. Keep the 3090 for DSpark/head only in a 2× V100 trunk layout if at all; do not add it as a third compute stage for throughput.

## What did not work or was abandoned

| Idea | Outcome |
| --- | --- |
| 3-stage 9,25 for balance | Technically fixed after `3a66da7d`, but **~5–7 tok/s** vs ~14 tok/s on 2× V100 |
| `--head-device 0` on 3-stage | Load OK after `3a66da7d`, decode **too slow** (host-mediated head) |
| Matching Qwen throughput on V100 | Not achievable on this model/size; **~4–5× gap** remains |
| `STRATA_SPLIT_OVERLAP` / `STRATA_SPLIT_WAIT_MS` on buster ds41 | Applies to Strata `generate` multi-GPU verify, not `ds41_generate`; not tested here |

## Recommendations

1. **Default buster DeepSeek path:** 2× V100, `--layer-split 20`, optional DSpark on 3090 with `--head-device 0 --stage-devices 1,2` if you want draft on the 3090 (see `BUSTER.md`).
2. **Do not deploy** 3-stage 9,25 for speed; keep notes for correctness only.
3. **Use Qwen/Strata** on buster when latency matters; keep DeepSeek for quality experiments where ~15 tok/s is acceptable.

## References

- Build/run cheat sheet: `BUSTER.md`
- Serve config: `tools/v41/serve/strata-buster-ds41-1017.json`
- PR that integrated this work: AtticusG3/Xolotl #1 (`kw27/buster-v100-dac5`)

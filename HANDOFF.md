# Xolotl — HANDOFF (2026-10-16)

**Goal:** one engine, one tree, serving **GLM-5.3-Flash + Qwen 27b dense + Qwen Flash + DeepSeek-V4.1-Flash**,
eventually pushed over the existing `Indras-Mirror/Strata-DSV4.1` repo (preserves the stars — do NOT make a new repo).

Everything below is measured, not assumed. `~/AI/Xolotl` is the work.

---

## 1. Where things stand

| | |
|---|---|
| repo | `~/AI/Xolotl` — sparse clone (excludes `bench/`), branch **`xolotl`**, 10 commits, **tree clean** |
| origin | `~/AI/Strata-DS4` (so `glm`/`mimo`/`deepseek4` are `origin/*`); `up` = `~/AI/Strata` |
| graft | **applied as a local replace ref** (`git replace -l` → `01529aaa…`) — needed for the upstream merge |
| build dir | `~/AI/Xolotl/build-xolotl` — **configure PASSES**; `ninja` runs to the kernel link |
| pushed | **nothing.** Not compiled, not run, no model loaded. **GPU untouched / free.** |
| disk | `/` at 97 %, ~26 G free — the real constraint (why the clone is sparse) |

## 2. What is merged (all committed on `xolotl`)

- `86bd1ec1` — **upstream `up/dense-eval`**: Qwen Flash + **Qwen 27b dense** + **`/v1/decide` voice turns** +
  the whole `serve/` frontend layer (345 upstream commits). 48 conflicts.
- `08597293` — **`origin/glm`**: GLM-5.3 + abliteration LoRA + elastic cache. 13 conflicts.
- `55a1ac38`, `0ae26656`, `4b9bdf87`, `5587b517`, `8c69e9b2` — README restore, the criss-cross note, and the
  build-gate fixes (see §4).
- **DSV4.1** was the base (`deepseek4`).
- **MiMo is NOT merged** — aborted on purpose (71 hunks, 48 in the legacy `tools/ds4/ds4_moe.cpp`). Mal said
  lowest priority / skip if costly. Resume with `git merge --no-commit --no-ff -s resolve origin/mimo`.

## 3. Build-bug status — 8 found, 6 fixed

The build gate is doing its job. Fixed:

1–3. **Duplicate CMake targets** — `ds4_generate`, `ds4_mtp_bench`, `ds4_expert_parity`, `ds4_moe_replay`.
  GLM's branch had the engine-slice includes **inline**; the fork moved them into
  `tools/ds4/cmake/fork.cmake`, which already aggregates `{ds4_dense,ds4_moe,ds4_engine}.cmake` **and**
  `tools/v41/engine/v41_engine.cmake`. Only `tools/glm/cmake/glm.cmake` is NOT in `fork.cmake`, so it stays.
  → **configure now passes.**
4. `shared_expert.cu` — `f16_from_f32` undefined; needs `#include "strata/kernels/f16_bits.hpp"`
  (`bf16_bits.hpp` only *mentions* it in a comment). `dequant_bf16.cu` has the same gap; left alone, it
  seemed to reach it transitively — re-check if the build complains.
5. `moe_mmq.cu` includes the GENERATED `strata/prefill/mmq_types.inc`, but `cmake/mmq_types.cmake`
  (which provides `strata_gen_mmq_types`) was **never included or called in ANY branch**, and the file has
  never existed in git. Wired into the CUDA branch; output goes to the build dir, added to `strata_mmq`'s
  include path.
6. `moe_mmq.cu` `supported()` switch had **duplicate case labels** (Q4_K/Q5_K under both
  `KQUANTS||DENSE_TYPES` and `KQUANTS`; Q5_1 at line 156 unguarded + in the KQUANTS block). The KQUANTS
  block now contributes only the fork's MiMo/DS4 additions.

**REMAINING (one root cause) — this is where to start:**

Linker: `native_expert_grouped(..., const NativeExpertLora*)` — the **14-arg LoRA overload is declared and
called but not defined**. My "take ours" on `iq_kernels.cu` / `native_mmvq.cu` **dropped GLM's LoRA code**.
GLM's inline-vs-extracted copies were **not** pure duplicates — that was the weak call, and the build caught it.

I tried appending GLM's block (`origin/glm:src/kernels/cuda/iq_kernels.cu` lines 3660–3886) before our
namespace close (line 3679) — **it failed and I reverted it.** The appended code could not see
`check`, `g_grouped_v1`, `NativeExpertLayout`; the scope is wrong.

Facts gathered for the fix:
- our merged `iq_kernels.cu` is **3679 lines**, has **0 refs to `NativeExpertLora`**.
- its layout: `namespace strata::kernels {` (24) → `namespace {` (25) … `}  // namespace` (**2710**) →
  `namespace {` (**2778**) … and the file's final close is **3679**. **Check whether the anon namespace
  opened at 2778 is still open at 3679** — that is the likely reason the append had no scope.
- GLM's file is 3908 lines = ours + LoRA. Key lines: `check()` **27**, `g_grouped_v1` **3659**,
  `lora_down_kernel` **3666**, `native_expert_lora_down` **3696**, LoRA `native_expert_grouped` **3707–3886**.
- **FIRST THING TO VERIFY:** does the merged `include/strata/kernels/iq_kernels.hpp` actually expose
  `NativeExpertLora` at namespace scope? I unioned GLM's struct into it, but the compiler said
  `NativeExpertLora is undefined` at the splice point — confirm it is not inside an `#if` or a nested scope.
- Then: make it a **real union of that file** (our fork-includes prefix + GLM's LoRA block **at namespace
  scope**), not an append. Both `native_expert_grouped` overloads coexisting is fine (13-arg + 14-arg).

## 4. Traps that cost time — read before touching git here

- **The graft creates a CRISS-CROSS.** `git merge-base --all xolotl glm` → **TWO** bases, so git synthesises
  a virtual base **that itself contains conflict markers** (verified: the stage-1 blob of `serve/server.py`
  held `<<<<<<<<< Temporary merge branch 1`). The plain glm merge reported **51** conflicts including all of
  `serve/`, which glm never touched. **Use `git merge -s resolve`** → 13 real conflicts.
  `core.useReplaceRefs=false` does NOT avoid it.
- **Do NOT delete the old worktrees.** The audit: `Strata-qwen` holds the **voice sidecar untracked**
  (`serve/voice.py`, `tools/audio/`) plus uncommitted `serve/server.py`/`src/program/generate.cpp` — it
  exists nowhere else. `Strata-GLM` (4), `-GLM-rebase` (382 staged), `-GLM-um` (1) also have uncommitted work.
  Mal's call: **leave them until Xolotl is proven working.** Only `git worktree prune` was run (removed one
  dead `/tmp/strata-dense-eval` registration). Worktrees share `.git`, so commits survive — uncommitted work
  does not.
- **`pkill -f "<pattern>"` kills your own shell** if the pattern is in your command line (cost me exit 144).
  Use `pkill -x ninja`.
- Only **TWO real repos** exist: `~/AI/Strata` (upstream) and `~/AI/Strata-DS4` (fork). Everything else in the
  AI folder is a worktree, a build dir, or scratch.

## 5. Resume commands

```bash
cd ~/AI/Xolotl && git log --oneline -3 && git status --short      # state
ninja -C build-xolotl 2>&1 | tail -30                             # resume the build (log: /tmp/xolotl-build.log)
# configure line that works (note: STRATA_GGML_DIR points at the DS4 tree's PATCHED ggml):
cmake -S . -B build-xolotl -G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON \
  -DSTRATA_GGML_CUDA=ON -DSTRATA_MMQ_KQUANTS=ON -DCMAKE_CUDA_ARCHITECTURES=89 \
  -DSTRATA_GGML_DIR=/home/mal/AI/Strata-DS4/third_party/llama.cpp -DSTRATA_DSV41_FQ_OP=ON
```

- `third_party/llama.cpp` in the clone is an **uninitialised submodule**. The recipe therefore points
  `STRATA_GGML_DIR` at `~/AI/Strata-DS4/third_party/llama.cpp` (175 M, present, and it **has** the DSV41
  fake-quant op, so `-DSTRATA_DSV41_FQ_OP=ON` is valid). Point it at the clone's own tree instead once the
  submodule is initialised.
- After the build: run each model through it and compare against its current wrapper.

## 6. Model / wrapper facts

| model | current wrapper | tree it points at |
|---|---|---|
| DSV4.1 | `strata-ds41-quetza` | `DS_DIR=/home/mal/AI/Strata-DS4`, engine `build-ds4-gpu/ds41_generate`, config `tools/v41/serve/strata-ds41.json` |
| GLM-5.3 | `strata-glm-quetza` | `DIR=/home/mal/AI/Strata-GLM`, engine `build-glm-gpu/glm_generate` |
| Qwen dense | `strata-dense-quetza` | `DIR=$HOME/.quetza-data/strata-dense` |

Model weights (from the engine args): `/media/mal/SSD NVME/AI/V41-GSQ/V41-GSQ.gguf`, engram
`/media/Crucial1TB/V41-Engram : /media/mal/SSD NVME/AI/V41-Engram`, rank
`/media/mal/SSD NVME/AI/V41-GSQ/rank.bin`, DSpark sidecar
`/media/mal/NVME1TB/Models/V41-Sidecar/V41-MTP-Vision.Q2_K.gguf`.

`strata-dense-runtime` is a **byte-identical copy of the repo's `serve/`** (only `__pycache__` differs) —
nothing to merge. `strata-dense-build`'s source was `/tmp/strata-dense-eval` (gone). `~/AI/v41-dev` is 82 G of
bench/logs — **`v41-dev/s13/run3/p20k.i32` is the 20 480-token prompt the harnesses use; keep it.**

## 7. Open decisions for Mal

1. Push `xolotl` over `Indras-Mirror/Strata-DSV4.1` (as `main`) once it builds and serves — **he wants this**,
   and the graft must be made permanent first (`git replace` refs do not push; use
   `git filter-repo --replace-refs update-no-add`, or redo the merge as `--allow-unrelated-histories`).
2. Drop the legacy `tools/ds4/ds4_*` engine? It's still built and it is what made mimo cost 71 hunks.
3. MiMo: in or out (or a `--legacy` build target)?
4. After the build: per-model serve/throughput legs, then clean up the worktrees (§4).

## 8. Also true, don't re-derive

- FQ_OP is genuinely live in the DS4 build: `STRATA_DSV41_FQ_OP=ON`, the llama.cpp tree patched, and
  `--kv-fp4` requires `act_quant` (ds41_dense.cpp:1050) which the serve config sets.
- The DSV4.1 prefill work is committed and pushed on `deepseek4` (`14e34b19`, `9d6529fc`): batch 12288 default,
  the shared-card VRAM cap, partial unpark. The 16384 blocker is **named** — the batch holds ~8.0 GiB of fixed
  buffers, the OOM was a transient **1424.3 MiB graph buffer**, and the ~1.05 GiB deficit is recoverable from
  one *speed* knob (`STRATA_PRESTAGE_GIB` / `MIMO_CHUNK_STAGE_MIB`) with no quality gate.
- `MERGE_SCOPE.md` in this repo has the full merge scope, topology, both conflict tables, and prior art.

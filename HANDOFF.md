# Xolotl — MERGE HANDOFF (2026-10-16, session 2)

**Goal (unchanged):** ONE engine, ONE tree, serving **GLM-5.3-Flash + Qwen 3.8 27b dense + Qwen
Flash-Next MoE + DeepSeek-V4.1-Flash**, eventually pushed over the existing
**`Indras-Mirror/Strata-DSV4.1`** repo (preserves the stars — do NOT create a new repo).

**The build is now green and the test suite runs.** The tree builds all four engines and passes
53/54 ctest. One RUNTIME failure is open (§6) and one ctest failure is environmental (§7).

Everything in this document is measured, not assumed. Where something is a hypothesis it says so.

---

## 0. TL;DR for the next session

```bash
cd ~/AI/Xolotl && git status --short && git log --oneline -3    # see §6: an UNVERIFIED one-line fix may be uncommitted
ninja -C build-xolotl                                           # REBUILD FIRST (it was in flight at handoff)
ninja -C build-xolotl && ctest -j2 --output-on-failure          # expect: no work to do / 53 of 54
cat glm-tierinit-ab.log                                         # the A/B smoke test launched at handoff (see §6.4)
```

Then: re-run the GLM smoke test (§6.4) and confirm the tier-init error is gone. That is the last known
blocker for serving GLM-5.3 from this tree.

---

## 1. Where things stand

| | |
|---|---|
| repo | `~/AI/Xolotl` — **separate sparse clone** (not a worktree), branch **`xolotl`**, tree **clean** |
| origin | `~/AI/Strata-DS4` (the fork) → so `glm`, `mimo`, `deepseek4` are `origin/*` |
| up | `~/AI/Strata` (upstream) → `up/dense-eval`, `up/main`, `up/qwen` |
| graft | applied as a **local replace ref**: `git replace -l` → `01529aaa82b9f5c58d2bb87264b7b3f7b823678f` (needed for the upstream merge; replace refs do NOT push — see §11.1) |
| base | `deepseek4` (= DSV4.1), then `up/dense-eval`, then `origin/glm` merged in |
| commits on `xolotl` | **12** on top of the merged base (log in §9) |
| build dir | `~/AI/Xolotl/build-xolotl` — configure PASSES; **build COMPLETE** (64/64, 0 errors, last rebuild 06:02:43 after the §6 fix) |
| engines built | `strata` (Qwen), `glm_generate`, `ds41_generate`, `ds4_generate` — all four run (§7.3) |
| tests | **53/54 pass**; `ple_parity` fails on a missing model fixture (§7.2) |
| open | §6: bug 11 (GLM tier init) **fixed + compiled green, runtime verification still owed** — one command |
| pushed | **NOTHING**. Nothing pushed, no repo created, no wrapper repointed. |
| disk | `/` at **97 %**, ~26 G free — the real constraint (why the clone is sparse, excludes `bench/`) |
| GPU | free. 778 MiB used, **no compute apps**. The only "GPU" process is Odin's embedding server, CPU-only (`-ngl 0`). |

---

## 2. Every repo, worktree and tree on disk — do not lose track

There are **exactly TWO real git repos** in the Strata family. Everything else is a **worktree** of
one of them, a **build dir**, or a **runtime/scratch** copy. `git worktree list` is the truth:

### 2.1 `~/AI/Strata` — UPSTREAM (remote `up` from Xolotl)

| path | branch | head |
|---|---|---|
| `~/AI/Strata` | `main` | `9bb510c8` |
| `~/AI/Strata-qwen` | `qwen` | `e405daf1` (**has UNCOMMITTED work** — see §10.2) |
| `/tmp/strata-dense-eval` | `dense-eval` | `eb339324` — **prunable, directory already gone** |

Other branches: `dense-eval` `eb339324` (the lineage merged into Xolotl), `qwen-dense` `e405daf1`,
`qwen-wip-frontend` `3ed86dc7`, `qwen-0.1.39-backup` `9bb510c8`.

### 2.2 `~/AI/Strata-DS4` — THE FORK (**origin** from Xolotl)

| path | branch | head | notes |
|---|---|---|---|
| `~/AI/Strata-DS4` | `deepseek4` | `9d6529fc` | the base; **this is what the DSV4.1 wrapper runs** |
| `~/AI/Strata-GLM` | `glm` | `94ac0227` | **4 files uncommitted**; the GLM wrapper runs its `build-glm-gpu/` |
| `~/AI/Strata-GLM-rebase` | `glm-rebase` | `fb58e0db` | **382 files STAGED** |
| `~/AI/Strata-GLM-um` | `glm-upstream` | `87cd462f` | **1 file uncommitted** |
| `~/AI/Strata-MiMo` | `mimo` | `bf38193f` | the MiMo branch — **NOT merged** into Xolotl (deliberate) |

Other branches: `deepseek4-preclean` `0282dc74`, `ds4-engine-wip` `225da367`, `ds4-on-0141` `77237127`,
`ds4-upstream` `be3a4ba5`, `main` `6f32ec07`.

### 2.3 Non-repo trees that matter

| path | what it is |
|---|---|
| `~/AI/Xolotl` | the merge work (this doc). Sparse clone of Strata-DS4; `third_party/llama.cpp` is an **empty submodule** → the build points `STRATA_GGML_DIR` at the fork's patched copy (§4) |
| `~/AI/Strata-DS4-private` | present, **not inspected this session** — check before assuming it is disposable |
| `~/AI/Strata-data` | present, **not inspected this session** |
| `~/AI/strata-dense-build` | `strata-dense` — the engine binary `strata-dense-quetza` runs (source tree was `/tmp/strata-dense-eval`, now gone) |
| `~/AI/strata-dense-runtime` | `serve/` + tokenizer for the dense wrapper — **byte-identical copy of the repo's `serve/`** (only `__pycache__` differs), i.e. nothing to merge |
| `~/AI/ds4-ref` | scratch reference |

---

## 3. Merge topology — what was merged, in what order, and the trap

Order of work on `xolotl` (each is a commit, §9):

1. **`487cd576`** scaffold (merge scope + driver).
2. **`4a39e65b`** the graft point: Xolotl's history is joined to the fork's so the two lineages share
   a common ancestor.
3. **`86bd1ec1`** merge **`up/dense-eval`** (upstream): Qwen Flash + Qwen 27b dense + `/v1/decide`
   voice turns + the whole `serve/` frontend layer; 345 upstream commits, **48 conflicts**.
4. **`08597293`** merge **`origin/glm`**: GLM-5.3 + abliteration LoRA + elastic cache; **13 conflicts**.
5. `55a1ac38`, `0ae26656` — README restore, the criss-cross note.
6. Build-gate commits: `4b9bdf87`, `5587b517`, `8c69e9b2`, `84a1e42d`, then this session's
   **`b108d171`** and **`7012b147`**.

### 3.1 ⚠ THE CRISS-CROSS (cost the previous session hours)

`git merge-base --all xolotl glm` returns **TWO** bases, so git synthesises a **virtual base that
itself contains conflict markers** — verified: the stage-1 blob of `serve/server.py` held
`<<<<<<<<< Temporary merge branch 1`. A plain merge of glm therefore reported **51** conflicts
including all of `serve/`, which glm never touched.

* **Always use `git merge -s resolve`** here → the real count (13 for glm).
* `core.useReplaceRefs=false` does NOT avoid it.

---

## 4. Build

### 4.1 Configure (the line that works)

```bash
cd ~/AI/Xolotl
cmake -S . -B build-xolotl -G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON \
  -DSTRATA_GGML_CUDA=ON -DSTRATA_MMQ_KQUANTS=ON -DCMAKE_CUDA_ARCHITECTURES=89 \
  -DSTRATA_GGML_DIR=/home/mal/AI/Strata-DS4/third_party/llama.cpp -DSTRATA_DSV41_FQ_OP=ON
ninja -C build-xolotl          # log: /tmp/xolotl-build.log
```

* `STRATA_GGML_DIR` **must** point at `~/AI/Strata-DS4/third_party/llama.cpp` (175 M, present, and it
  **has** the DSV41 fake-quant op so `-DSTRATA_DSV41_FQ_OP=ON` is valid). The clone's own
  `third_party/llama.cpp` is an **uninitialised submodule** (empty).
* Handy: `ninja -C build-xolotl -k 0` to collect ALL errors in one pass instead of stopping at the
  first. That is how bug 10 was found (it was silent, not a compile error).
* Effective options in this build: `STRATA_MMQ_KQUANTS=ON`, `STRATA_ENABLE_CUDA=ON`,
  `STRATA_DSV41_FQ_OP=ON`; **`STRATA_MMQ_DENSE_TYPES` is never set anywhere** (so those `#ifdef`s are
  inert); `STRATA_ORCA_Q4KS_MMQ` OFF, `STRATA_Q6K_EXPERTS` OFF, `STRATA_HIP_GFX906` OFF.

### 4.2 Result

`ninja`: **no work to do**. All targets build; all four engines link. Warnings only.

---

## 5. The build gate — bugs 1–10, all FIXED

The build/run gate did its job: every one of these was a real merge defect. "Mechanism" = why the
merge produced it.

| # | Where | Symptom | Mechanism / fix | Commit |
|---|---|---|---|---|
| 1–3 | `CMakeLists.txt` / `tools/ds4/cmake/fork.cmake` | configure FATAL: duplicate targets `ds4_generate`, `ds4_mtp_bench`, `ds4_expert_parity`, `ds4_moe_replay` | GLM's branch had the engine-slice includes **inline**; the fork moved them into `tools/ds4/cmake/fork.cmake` (which also aggregates `v41_engine.cmake`). Only `tools/glm/cmake/glm.cmake` is not in fork.cmake. Dropped GLM's copies. | `4b9bdf87` |
| 4 | `src/kernels/cuda/shared_expert.cu` | `error: identifier "f16_from_f32" is undefined` | It includes `bf16_bits.hpp` (which only *mentions* `f16_from_f32` in a comment) but not `f16_bits.hpp`. Added the include. `dequant_bf16.cu` has the same gap but reaches it transitively — **left alone; re-check if the build complains**. | `5587b517` |
| 5 | `CMakeLists.txt`, `src/prefill/moe_mmq.cu` | `fatal error: strata/prefill/mmq_types.inc: No such file or directory` | `cmake/mmq_types.cmake` provides the generator `strata_gen_mmq_types`, but **no branch ever included or called it**, and `mmq_types.inc` has never existed in git — while the merged `moe_mmq.cu` (from the dense lineage) `#include`s it. Wired it in. | `8c69e9b2` |
| 6 | `src/prefill/moe_mmq.cu` | 20 × `case label value has already appeared in this switch` | The dense lineage's refactor left a hand-written case block that is a **superset** of the generated `STRATA_MMQ_TYPES` expansion, and it also duplicated ITSELF (Q2_K/Q3_K once in "the UD packs" and again in the MiMo line; Q4_K/Q5_K/Q5_1 in two blocks; Q6_K in three). **The dense lineage's own file has the same defect → that branch is a refactor in progress, not a working state.** Reduced the block; then (§5.1) removed it entirely. | `8c69e9b2`, `b108d171` |
| 7 | `src/kernels/cuda/iq_kernels.cu` | LINK: `undefined reference to native_expert_grouped(..., const NativeExpertLora*)` | The merge's **"take ours"** on this file dropped GLM's routed-expert LoRA. `iq_kernels.hpp` declares a **14-arg** `native_expert_grouped` (with `lora = nullptr`); the merged `.cu` defined a **13-arg** one — a *different function* — so the declared one was undefined. GLM's block is **not** a superset of ours: it predates the fork's PROM kernels (`prom_gu`/`prom_down`/`prom_large`), `exp_mode_type` and the PTQ1_0/Q3_K types. Fixed as a **real union** (4 hunks into OUR body): `lora_down_kernel` + `native_expert_lora_down`, the `lora` parameter, the down-correction tail after `check("native_expert_grouped/down")` (opt-out `GLM_LORA_NO_DOWN`), and `sw_v1 = v1 \|\| (lora && lora->a_d)` in the non-gfx906 branch (the down LoRA needs the **float `h`**, which only the unfused SwiGLU pass writes). | `b108d171` |
| 8 | `src/prefill/moe_mmq.cu` + `CMakeLists.txt` | LINK: `undefined reference to mul_mat_q_case<(ggml_type)2/3/6/19>` (Q4_0, Q4_1, Q5_0, IQ1_S) | The dense lineage's hand-written list named Q4_0/Q4_1/IQ1_S, written against a build that **GLOBbed every template instance**; the fork's CUDA branch lists its instances **explicitly** and its file never mentioned them. The merge took the union of the *lists* but only the fork's instance set. Fixed by adding `q4_0 q4_1 iq1_s` to `_strata_mmq_cuda_types` and deleting the hand-written block — which is the generator's own contract: **advertised == instantiated**. | `b108d171` |
| 9 | `tools/v41/engine/ds41_moe.cpp:1590` | `error: 'struct ...::Gpu' has no member named 'cache'` (CPU flavour only) | `set_cache_enabled` uses `im_->gpu->cache` unguarded; the **CPU flavour's stub `Gpu` has only `close()`**. Dormant in the fork because `v41_engine.cmake` creates `ds41_moe_cpu` only `if(TARGET strata_kernels_cpu AND TARGET ggml-cpu)` and **the fork's configure has no `ggml-cpu`**; the merged dense lineage enables it, waking the CPU tier. Guarded with `#if defined(DS4_MOE_CUDA)`. | `b108d171` |
| 10 | `CMakeLists.txt:1704 vs 1707` | **No GLM engine at all** — silently. `glm_dense.a` built; **no `glm_generate` binary existed** | `glm.cmake` creates `glm_generate` only `if(TARGET ds4_moe_cuda)`, and `ds4_moe_cuda` is created by `fork.cmake`. The merge left `glm.cmake` **before** `fork.cmake`, so the gate was always false and the configure succeeded silently. Swapped the includes (glm.cmake's own header says it must come "AFTER the tools/ds4 slices it builds on"). Now `glm_generate` builds (681 MB). | `7012b147` |
| **11** | `src/kernels/cuda/fork/fork_fmt.cuh:24` | **Runtime, not compile:** `glm_generate: tier init: native_expert_grouped has no kernel for layer 3's types 16/16/18` — GLM-5.3 **could not load at all** | The **fork-format list lost three types**. GLM's branch kept its copy INLINE in its own `iq_kernels.cu` (line 736) with `X(12) X(18) X(22)` — Q4_K down_exps for GLM-5.3 layers 3-5, and the IQ2_S/IQ3_XXS Maya-S-v2 down_exps; the fork had meanwhile extracted this list into `fork_fmt.cuh` with only `X(10) X(11) X(39) X(143)`. The merge reconciled GLM's inline copy to the extracted header and dropped 12/18/22 → `d_qk(18) == 0` → `native_expert_supported(16, 18, 4096, 2048)` false. Nothing referenced 18 before, so it still compiled and linked. **Fixed by the union** (§6). | *uncommitted at handoff* |

### 5.1 The one-file outcome of 5/6/8

`src/prefill/moe_mmq.cu` `supported()` and the dispatch switch are now **one generated list**
(`STRATA_MMQ_TYPES`) with only a `default:` remaining. The former hand-written types became
CMake list entries, so `supported()` and `strata_mmq`'s compiled instances cannot drift — which is
exactly the invariant the file's own comment says costs **100x on prefill** when it breaks
(`docs/UNSLOTH_Q4.md`, `#296`).

Note also: the generated file now lands in **`<build>/generated/strata/prefill/mmq_types.inc`**, not
`<build>/strata/…` — at `<build>/strata` it created a **DIRECTORY** named `strata`, and
`add_executable(strata ...)` then failed to link with `cannot open output file strata: Is a directory`.

---

## 6. Bug 11 — GLM tier init rejected the model. DIAGNOSED, FIX APPLIED, **REBUILD NOT DONE**

### 6.0 Verdict: it IS a merge regression, and the cause is a single line

**Measured, not inferred.** Run A (below) — the *working* `~/AI/Strata-GLM/build-glm-gpu/glm_generate`
(2026-10-10) with the same args — passes the point where the Xolotl binary dies, and prints a line the
Xolotl binary never reaches:

```
moe lora: routed-expert deltas on 26 layer(s) (n_experts 288, n_embd 4096, n_ff 2048)
```

**Cause — `src/kernels/cuda/fork/fork_fmt.cuh:24`, `STRATA_D_FMTS_FORK`:**

```
GLM  (inline, its iq_kernels.cu:736):  X(10) X(11) X(12) X(39) X(18) X(22)
ours (the extracted header)         :  X(10) X(11) X(39) X(143)
```

Per GLM's own comment on that line: **12 = Q4_K down_exps (GLM-5.3-Flash layers 3-5; upstream's list
has none)**, and **18/22 = the Maya-S-v2 down_exps (IQ2_S / IQ3_XXS)**, 39 = MXFP4 (MiMo), 143 =
PTQ1_0 (the V4.1 ternary tier). The fork had moved this list into `fork_fmt.cuh` (to keep upstream's
lists verbatim across merges); GLM's branch still carried it **inline**. The merge reconciled GLM's
inline copy to the extracted header and kept only the fork's entries, so `d_qk(18) == 0` and
`native_expert_supported(16, 18, 4096, 2048)` returns false for every Maya-S-v2 layer (16/16 =
IQ2_XXS gate/up, 18 = IQ2_S down). **GLM-5.3 therefore could not load at all**, while the DS4/DSV4.1
types were untouched.

Why the build gate could not catch it: the list only gates the kernel `switch` cases and that
predicate. Nothing in the compiler references type 18, so it compiled, linked and passed ctest.
**This is the class of defect only running the model finds.**

### 6.0.1 The fix (applied in the working tree, one line)

```c
#define STRATA_D_FMTS_FORK(X) X(10) X(11) X(12) X(18) X(22) X(39) X(143)
```

`Fmt<12>`, `Fmt<18>` and `Fmt<22>` are **all already defined** in this tree (verified: 1 definition
each), so no port from GLM is needed — this is the whole fix. `STRATA_GU_FMTS_FORK` and
`STRATA_MMVQ_FMTS_FORK` need nothing: the fork's versions are already supersets of GLM's.

**STATUS AT HANDOFF:**

* ✅ **Rebuild DONE and GREEN** — `ninja -C build-xolotl` finished **64/64, 0 errors** at **06:02:43**
  (`iq_kernels.cu.o` written 06:02:34, `glm_generate` relinked 06:02:43). The fix **compiles and links**.
* ❌ **Runtime NOT verified.** The A/B job's command B ran **06:02:27 → 06:02:32** — *before* both of
  those timestamps (proven by `stat`), so it exercised the **OLD binary**: its `types 16/16/18` failure
  is the *pre-fix* behaviour, **not** a counter-example to the fix. Do not read it as one.
* **Next session: re-run §6.4 command B** (and use `--vram-margin 7.5`, see §6.5) — the tier-init error
  should be gone and tokens should come out. That is the last known blocker for serving GLM-5.3.

### 6.0.2 The general lesson (worth writing down)

**The `*_FMTS*` X-macro lists are the most merge-sensitive surface in this kernel file.** The fork
extracted its formats into `fork_fmt.cuh` with "kept out of upstream's lists above so those stay
verbatim (fewer merge conflicts)" — the *opposite* trade-off from GLM, which kept its 3 extra entries
inline. A `-s resolve` merge silently prefers one side. **Whenever a new model is added to the merge,
diff every `STRATA_*_FMTS*` definition against every branch that touched it** — a lost type is a
runtime tier-init failure, not a compile error:

```bash
cd ~/AI/Xolotl && for b in origin/glm origin/deepseek4 up/dense-eval; do echo "== $b"; git grep -h "define STRATA_.*_FMTS" $b; done
grep -rn "define STRATA_.*_FMTS" src/ | sed 's/^/ours /'
```

### 6.1 The failure, verbatim

Real run of the **Xolotl** `glm_generate` (GLM-5.3 Maya-S-v2 + the abliteration LoRA):

```bash
cd ~/AI/Xolotl/build-xolotl && ./glm_generate \
  -m "/media/mal/SSD NVME/Models/GLM-5.3-Flash-Maya-S-v2/GLM-5.3-Flash-Maya-S-v2-IQ2_XXS-00001-of-00003.gguf" \
  --backend cuda --experts gpu --arena-gib 12 --ctx 8192 \
  --census /home/mal/.quetza-data/strata-glm/maya-s-v2.census \
  --lora "/media/mal/NVME1TB/Models/GLM-5.3-Flash-RCO/lora/gcsa-abliterix/GLM-5.3-Flash-Ablitered2-LoRA-v2.gguf" --lora-exps \
  --ids 100,200,300,400,500,600,700,800 -n 8 --temp 0
```

progresses correctly — CUDA init, `dense backend: CUDA0`, LoRA parsed ("routed-expert exps are NOT
applied yet (CPU-path slice pending)" for the *dense* half), **dense half loaded in 4.5 s**, 45 layers
(34 KDA, 11 MLA), 288 experts top-8, vocab 154880, "lora: routed-expert deltas for **26 layer(s)**",
slots auto → 15.44 GiB free → 14.44 GiB of slots, census 12060 counts, "lora-exps: pcie_frac 0.25" —
then, at **tier init**:

```
glm_generate: tier init: native_expert_grouped has no kernel for layer 3's types 16/16/18
```

`16 = IQ2_XXS` (gate), `16 = IQ2_XXS` (up), `18 = IQ2_S` (down). The message is emitted from
`tools/ds4/ds4_moe.cpp:772` (the same string also in `tools/v41/engine/ds41_moe.cpp:1326`).

### 6.2 What is already ruled out

* The check goes through `native_expert_supported3(gate, up, d, n_embd, n_ff)` →
  `native_expert_supported(16, 18, …)` (`src/kernels/cuda/iq_kernels.cu:2812`). **Its body is
  byte-identical to `origin/glm`'s** (`2990`), and so are its helpers `is_iq` (`:1926`; ours only
  *adds* `t == 143` PTQ1_0), `gu_qk` (`:1936`) and `d_qk` (`:1945`). For 16/18 both return true.
  Ours and GLM's `is_iq` both return true for 16 and 18. **So the loss is not in these functions.**
* The engine reached tier init, so the LoRA plumbing I restored (§5 bug 7) is at least constructed
  and the routed-expert deltas were attached for 26 layers. **The failure is a support/type-table
  question, not the LoRA overload.**

### 6.3 How the verdict was reached (keep this method)

Two hypotheses were on the table: **(A)** a lost entry in the `STRATA_*_FMTS*` X-macro lists, or
**(B)** my argument set differing from the wrapper's (which adds `--prefill-chunk 4096 --chunk-mmq
--arena-skip-resident --vram-margin 7.5 --vram-grow 1.5 --prune … --arena-adapt --skip-*`). Rule out
(B) by running the **same command against the working binary**; it passed, which is (A). Then the
macro diff in §6.0.2 pinpointed the line. Note for the record: `is_iq`, `gu_qk`, `d_qk` **bodies** are
byte-identical to `origin/glm`'s — the loss was in the macro *they expand*, which is why reading only
the functions (the earlier session's instinct) would have missed it.

### 6.4 Commands — re-measure and verify

```bash
M=/media/mal/SSD\ NVME/Models/GLM-5.3-Flash-Maya-S-v2/GLM-5.3-Flash-Maya-S-v2-IQ2_XXS-00001-of-00003.gguf
L=/media/mal/NVME1TB/Models/GLM-5.3-Flash-RCO/lora/gcsa-abliterix/GLM-5.3-Flash-Ablitered2-LoRA-v2.gguf
C=/home/mal/.quetza-data/strata-glm/maya-s-v2.census

# A) the WORKING reference binary (control)
cd /home/mal/AI/Strata-GLM && ./build-glm-gpu/glm_generate -m "$M" --backend cuda --experts gpu \
  --arena-gib 12 --ctx 8192 --census "$C" --lora "$L" --lora-exps \
  --ids 100,200,300,400,500,600,700,800 -n 8 --temp 0
  # passes tier init; prints "moe lora: routed-expert deltas on 26 layer(s) (n_embd 4096, n_ff 2048)"

# B) the XOLOTL binary - after `ninja -C build-xolotl`. Add the wrapper's flags to be faithful:
cd /home/mal/AI/Xolotl/build-xolotl && ./glm_generate -m "$M" --backend cuda --experts gpu \
  --arena-gib 24 --arena-skip-resident --ctx 8192 --prefill-chunk 4096 --chunk-mmq \
  --vram-margin 7.5 --vram-grow 1.5 --arena-adapt --skip-miss 0.15 --skip-file 0.15 \
  --skip-file-prefill 0.15 --renorm-skip --pf-b 1.0 --pcie auto --census "$C" \
  --lora "$L" --lora-exps --ids 100,200,300,400,500,600,700,800 -n 8 --temp 0
```

Take `~/AI/.quetza-data/conductor/ds4-gpu.lock` first (`flock -n <lock> true` to fail fast instead of
blocking) — the GLM/DSV4.1 wrappers use it. Kill a stray run with **`pkill -x glm_generate`**
(never `pkill -f`, see §10.3).

### 6.5 What the A/B job actually produced (measured — read `~/AI/Xolotl/glm-tierinit-ab.log`)

**A — the working `~/AI/Strata-GLM/build-glm-gpu/glm_generate` (2026-10-10), same minimal args:**
it **passes tier init** —

```
moe lora: routed-expert deltas on 26 layer(s) (n_experts 288, n_embd 4096, n_ff 2048)
tier: gpu, 2176 resident slots, arena 12.0 GiB (1813 experts), file tier 10283; load 132.0 s
```

then dies on **a VRAM OOM of my own making**:

```
ggml_backend_cuda_buffer_type_alloc_buffer: allocating 4.22 MiB on device 0: cudaMalloc failed: out of memory
glm_generate: prefill failed at 0: gallocr(attn) failed
```

**That OOM is a HARNESS artifact, not a bug:** `--arena-gib 12` leaves the Dense/attn graph no room
(`slots auto: … margin 1.00 GiB`). The GLM wrapper runs this model with **`--arena-gib 64
--vram-margin 7.5`**. So when re-running, either raise the arena or pass `--vram-margin 7.5` — B's log
shows the engine itself reserving the margin correctly (`slots auto: 14.69 GiB free → 7.19 GiB of
slots (margin 7.50 GiB)`).

**B — the Xolotl binary:** `tier init: native_expert_grouped has no kernel for layer 3's types 16/16/18`
— the **pre-fix** binary (§6.0.1). It also shows the wrapper's real flag effects: `lora-exps:
pcie_frac -1.00`, `prune: 3024 (layer, expert) pairs masked out of routing`.

The script is at `/tmp/glm-tierinit-ab.sh` (**/tmp — may not survive a reboot**; §6.4's commands are the
self-contained copy). It is finished; nothing is left running. The GPU is free.

---

## 7. Tests

### 7.1 How to run

```bash
cd ~/AI/Xolotl/build-xolotl && ctest -j2 --output-on-failure     # 54 tests, ~55 s
```

### 7.2 Result: 53/54 pass

`98% tests passed, 1 tests failed out of 54`. The failure is **environmental, not a regression**:

```
43 - ple_parity ***Failed 0.01 sec
ple_parity: required PLE table is missing or incompatible:
  ../../Q2_0/Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf (cannot open …)
```

That GGUF is a **model fixture**, downloaded by `tools/test_setup_modelscope.py` (paths in
`tools/test_setup_golden.json`). It is absent from this machine (`find` over `/media/mal` and
`/media/Crucial1TB` found nothing). The test's wiring — `--selftest --in/--out bench/micro` with
`WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}` — is **byte-identical in ours, in `origin/deepseek4`
and in `up/dense-eval`**, so the merge did not touch it. To make it pass: fetch the fixture, or run
with `-DSTRATA_PLE_FIXTURE_DIR=<dir>` / set the `STRATA_PLE_GGUF` path. **Nothing to fix in code.**

All GPU tests pass, including `cuda_device_selftest`, the `kv_*`, `gr_*`, `iq_*`, `native_*`,
`qsa_*`, `s2_*`, `verify_*`, `rope_parity`, `sampler_parity`.

### 7.3 Engines built and smoke-tested (start-up)

| binary | model line | `--help` |
|---|---|---|
| `build-xolotl/strata` | Qwen Flash-Next MoE **and** Qwen 3.8 27b dense (`src/program/generate.cpp` + `serve/`) | `strata generate --pack DIR --tokens …` |
| `build-xolotl/glm_generate` | GLM-5.3-Flash (681 MB) | `glm_generate -m model.gguf (--ids …)` |
| `build-xolotl/ds41_generate` | DeepSeek-V4.1-Flash | "unknown argument --help" + pointer |
| `build-xolotl/ds4_generate` | DeepSeek (DS4 engine line) | full usage |

All four start and print usage (exit 0). The GLM end-to-end run is the one in §6.

---

## 8. Wrappers and model artifacts — what runs what TODAY

None of these wrappers point at Xolotl yet. They are the **reference implementations** to compare
against (§11.4).

| wrapper (`~/.local/bin/`) | tree it uses | engine | config | model weights | port / ctx |
|---|---|---|---|---|---|
| `strata-quetza` | `~/AI/Strata` | `build/strata` + `serve/server.py` | `strata-swift-iq3_xxs{,-sc117}.json` | Qwen3.8 Flash-Next (Swift, IQ3_XXS) | 8130 unc / 8128 stock, ctx 262144, VISION=lazy |
| `strata-quetza-refusal`, `strata-quetza.bak-20261005` | — | variants of the above | — | — | — |
| `strata-dense-quetza` | `~/AI/strata-dense-build` | `strata-dense` + runtime `~/AI/strata-dense-runtime` | `~/.quetza-data/strata-dense/strata-dense-quetza.json` | `/media/mal/NVME1TB/Models/Swift-1.5-27B-GSQ-RCO/d0xin-unc-27b-IQ3_S-mtp-q6embd.gguf` | 8090, ctx 200000, KV `k8v4`, MTP draft 2 |
| `strata-ds41-quetza` | `~/AI/Strata-DS4` | `build-ds4-gpu/ds41_generate --serve` via `tools/v41/serve/serve_ds41.py` | `tools/v41/serve/strata-ds41.json` | V41 GSQ (see §12) | 8150, ctx 524288 |
| `strata-glm-quetza` | `~/AI/Strata-GLM` | `build-glm-gpu/glm_generate` via `tools/glm/serve/glm-engine.sh` | `tools/glm/serve/strata-glm-*.json` | Maya-S-v2 IQ2_XXS 3-shard (default `= --maya`) + abliteration LoRA | 8140 unc / 8141 stock / 8142 max / 8143 maya300 / 8144 maya512 |

### 8.1 GLM-5.3 artifacts (used in §6)

```
model   /media/mal/SSD NVME/Models/GLM-5.3-Flash-Maya-S-v2/GLM-5.3-Flash-Maya-S-v2-IQ2_XXS-0000{1,2,3}-of-00003.gguf
        (47.8 GB + 47.8 GB + 0.84 GB = 96 GB, 3 shards)
LoRA    /media/mal/NVME1TB/Models/GLM-5.3-Flash-RCO/lora/gcsa-abliterix/GLM-5.3-Flash-Ablitered2-LoRA-v2.gguf  (277 MB)
prune   ~/AI/Strata-GLM/bench/glm-2026-10-09/prune-ezct-0.25.txt   (penalty 0.05)
census  ~/.quetza-data/strata-glm/maya-s-v2.census                 (12060 counts)
tokenizer /media/mal/NVME1TB/Models/GLM-5.3-Flash-RCO/tokenizer
```

### 8.2 Resources / locks

* **GPU lock:** `~/.quetza-data/conductor/ds4-gpu.lock` — `flock`; the GLM/DSV4.1 wrappers hold it
  while serving. `flock -n <lock> true` to test, i.e. fail fast instead of blocking.
* GLM/Dense wrappers refuse while **ComfyUI** listens on `:8188`, and cap RAM (84 GiB, swap 0) via
  `glm-engine.sh`.

---

## 9. `xolotl` commit log (12 commits on the merged base)

```
7012b147 xolotl: include fork.cmake BEFORE glm.cmake - the merge built no GLM engine (build gate, bug 10)
b108d171 xolotl: complete the merge - LoRA overload, one MMQ list, the CPU tier (build gate, bugs 7-9)
84a1e42d xolotl: HANDOFF - state, the remaining LoRA-overload bug with its diagnosis, traps, resume commands
8c69e9b2 xolotl: generate mmq_types.inc and de-duplicate its case labels (build gate, bugs 5-6)
5587b517 xolotl: shared_expert.cu needs f16_bits.hpp (build gate, 4th merge bug)
4b9bdf87 xolotl: fix the 3 configure failures the build gate found (duplicate targets)
08597293 xolotl: merge glm (GLM-5.3 + abliteration LoRA + elastic cache) - 13 files, all two-sided
0ae26656 xolotl docs: the graft creates a CRISS-CROSS - use -s resolve (13 glm conflicts, not 51)
55a1ac38 xolotl: restore the DS4 section the README merge dropped
86bd1ec1 xolotl: merge upstream dense-eval (Qwen Flash + 27b dense + /v1/decide voice) into DSV4.1
4a39e65b xolotl: the graft point, the real cross-lineage cost, upstream's 345 new commits, prior art
487cd576 xolotl: scaffold the Strata-family unification (scope + merge driver)
```

`MERGE_SCOPE.md` in this repo holds the pre-merge scope, topology, both conflict tables and prior art.

---

## 10. Traps — each of these already cost time once

1. **The graft creates a CRISS-CROSS** (§3.1). Use `git merge -s resolve`. A plain merge lies about
   the conflict count and invents conflicts in files the other branch never touched.
2. **DO NOT DELETE THE OLD WORKTREES.** `Strata-qwen` holds the **voice sidecar UNTRACKED**
   (`serve/voice.py`, `tools/audio/`) plus uncommitted `serve/server.py` / `src/program/generate.cpp`
   — it exists **nowhere else**. `Strata-GLM` (4 files), `Strata-GLM-rebase` (382 staged),
   `Strata-GLM-um` (1) also have uncommitted work. Mal's call: leave them until Xolotl is proven.
   **Worktrees share `.git`, so commits survive — uncommitted work does not.**
   Only `git worktree prune` has been run (removed one dead `/tmp/strata-dense-eval` registration).
3. **`pkill -f "<pattern>"` kills your own shell** when the pattern is in your command line (cost the
   previous session exit 144). Use `pkill -x ninja`.
4. **Disk is at 97 % (26 G free).** The clone is sparse (excludes `bench/`) for this reason. Adding
   MMQ instances (§5 bug 8) or a second build dir will eat it — watch `df -h /` before big builds.
5. **`ninja` stops at the first error by default** — the HEADER of the error may be a *consequence*.
   Use `-k 0` to see everything.
6. **A silent CMake failure is possible** (§5 bug 10): the configure can "succeed" while a whole
   engine binary is never created. **Check for the artifact, not the exit code.**
7. **Two things provide MMQ instances**: llama.cpp's own `ggml-cuda` target compiles the full
   template-instance set, and `strata_mmq` compiles the CMake subset (the build tree really does
   contain e.g. two `mmq-instance-q4_k.o`). Only `strata_mmq`'s set is what `moe_mmq.cu` must match.
8. **`up/dense-eval`'s `moe_mmq.cu` does not compile as committed** (its hand-written case block
   duplicates itself and the generated list). Do not treat that branch's file as a working reference.
9. **`glm.cmake` include order matters** (§5 bug 10) — after `fork.cmake`, always.
10. **Enabling `ggml-cpu` wakes the fork's CPU flavour**, which had a latent compile error (§5 bug 9).
    Expect more of that class: code paths the fork never compiled are now live.
11. **Path with a space**: `/media/mal/SSD NVME/…` — quote it.
12. **The `STRATA_*_FMTS*` X-macro lists are the most merge-sensitive surface in `iq_kernels.cu`** (§6.0.2).
    The fork extracted its formats into `fork_fmt.cuh` ("kept out of upstream's lists above so those stay
    verbatim"), GLM kept its three extra entries **inline** — a `-s resolve` merge silently prefers one
    side, and a lost type is a **runtime tier-init failure, not a compile error**. Diff them against every
    merged branch whenever a new model joins the tree.
13. **`pkill -f` self-kills even in a `;`-chained command** — it happened *again* in this session writing this
    very document (exit 144), even after the trap was written down. `pkill -x <name>`; for the GLM smoke
    test `pkill -x glm_generate`.
14. **Loading GLM-5.3 at a small `--arena-gib` produces a confusing VRAM OOM** (§6.5) that looks like a
    merge bug. The model's real configuration is `--arena-gib 64 --vram-margin 7.5`.

---

## 11. Open decisions for Mal

1. **Push `xolotl` over `Indras-Mirror/Strata-DSV4.1`** (as `main`) once it builds and serves — he
   wants this. The graft must be made **permanent** first: `git replace` refs do **not** push. Either
   `git filter-repo --replace-refs update-no-add`, or redo the merge as `--allow-unrelated-histories`.
2. **Drop the legacy `tools/ds4/ds4_*` engine?** It is still built, and it is what made the MiMo merge
   cost 71 hunks.
3. **MiMo: in or out** (or a `--legacy` build target)? Resume with:
   `git merge --no-commit --no-ff -s resolve origin/mimo`.
4. **Then, per model: serve/test legs against the current wrapper**, and only then clean up the
   worktrees (§10.2).
5. **The §6 runtime failure** — decide whether to chase it now or after the push.

---

## 12. Already-known facts — do NOT re-derive

* **FQ_OP is genuinely live** in the DS4 build: `-DSTRATA_DSV41_FQ_OP=ON`, the llama.cpp tree patched,
  and `--kv-fp4` requires `act_quant` (`ds41_dense.cpp:1050`) which the serve config sets.
* The DSV4.1 prefill work is **committed and pushed** on `deepseek4` (`14e34b19`, `9d6529fc`): batch
  12288 default, the shared-card VRAM cap, partial unpark. **The 16384 blocker is NAMED**: the batch
  holds ~8.0 GiB of fixed buffers, the OOM was a transient **1424.3 MiB graph buffer**, and the
  ~1.05 GiB deficit is recoverable from one **speed** knob (`STRATA_PRESTAGE_GIB` /
  `MIMO_CHUNK_STAGE_MIB`) with **no quality gate**.
* **DSV4.1 artifacts**: weights `/media/mal/SSD NVME/AI/V41-GSQ/V41-GSQ.gguf`; engram
  `/media/Crucial1TB/V41-Engram : /media/mal/SSD NVME/AI/V41-Engram`; rank
  `/media/mal/SSD NVME/AI/V41-GSQ/rank.bin`; DSpark sidecar
  `/media/mal/NVME1TB/Models/V41-Sidecar/V41-MTP-Vision.Q2_K.gguf`.
* **`~/AI/v41-dev` is 82 G of bench/logs** — but `v41-dev/s13/run3/p20k.i32` is the **20 480-token
  prompt the harnesses use; keep it.**
* `strata-dense-runtime` is a **byte-identical copy of the repo's `serve/`** — nothing to merge.
* **`strata-dense-build`'s source tree was `/tmp/strata-dense-eval`, which is gone.**

---

## 13. Session-2 summary, in one paragraph

The merge is no longer "half-built": the tree configures, builds all four engines, and passes 53/54
ctest (the one failure is a missing model fixture). **Eleven** real merge defects were found — ten
build-gate ones (the LoRA overload, the MMQ case lists, the never-generated header, a latent
CPU-flavour compile error the merged config woke up, and a *silent* one that removed the GLM engine
entirely), and an eleventh that only *running the model* could find: the fork-format list lost GLM's
`Q4_K / IQ2_S / IQ3_XXS` down types, so GLM-5.3 died at tier init with `types 16/16/18`. The fix is one
line, it compiles green, and the A/B control run **proved it is a regression** (the working binary
passes that exact point). What remains is one command: re-run §6.4's B against the rebuilt binary and
watch the tier init pass. Nothing is pushed; nothing outside `~/AI/Xolotl` was modified; the GPU is
free.

**Claims I would most expect to be wrong, stated plainly:** (1) the bug-11 fix has only been
**compiled**, not run — the runtime check is the single remaining step; (2) `ple_parity` fails for a
missing model fixture, which I verified is absent from this machine but did **not** fix; (3)
`Strata-DS4-private` and `Strata-data` were never inspected this session.

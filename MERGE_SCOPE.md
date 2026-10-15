# Xolotl — scoping the unification of the Strata engine family

**Date:** 2026-10-16 · **Measured with:** `git merge-tree` (read-only) + `git diff --numstat` on the fork's own refs
**Verdict: feasible and cheap.** It is a *single branch merge inside one existing repo*, not a code rewrite.
Conflict surface: **~13 files / ~79 hunks**, concentrated in the shared quantisation kernels. Qwen (dense)
costs nothing because it is already an ancestor.

---

## 1. Inventory — what each folder actually is

The "so many folders" is mostly illusion: **five are clones of ONE fork (different branches), two are clones of
ONE upstream, and four are not repos at all.**

| folder | size | what it is |
|---|---|---|
| `~/AI/Strata-DS4` | 29 G | clone of **fork** `Indras-Mirror/Strata-DSV4.1`, branch **`deepseek4`** ← the DSV4.1 work |
| `~/AI/Strata-GLM` | 2.2 G | clone of **fork**, branch **`glm`** |
| `~/AI/Strata-GLM-rebase` | 327 M | clone of **fork**, branch **`glm-rebase`** (= the merge base, see §3) |
| `~/AI/Strata-GLM-um` | 1.1 G | clone of **fork**, branch **`glm-upstream`** (the attempted graft — see §3) |
| `~/AI/Strata-MiMo` | 4.0 G | clone of **fork**, branch **`mimo`** |
| `~/AI/Strata` | 1.1 G | clone of **upstream** `Niko1221/Strata`, branch `main` |
| `~/AI/Strata-qwen` | 902 M | clone of **upstream**, branch **`qwen`** ← the newer Qwen lineage |
| `~/AI/strata-dense-runtime` | 14 M | **not a repo** — a copy of the `serve/` Python runtime (same files as the repo's `serve/`) |
| `~/AI/strata-dense-build` | 891 M | **not a repo** — a build dir; `CMakeCache.txt` says its source was `/tmp/strata-dense-eval` (ephemeral, gone) |
| `~/AI/v41-dev` | 82 G | **not a repo** — DSV4.1 scratch: bench runs, logs, decode sweeps |
| `~/AI/Strata-DS4-private` | 1.1 M | **not a repo** — `v41/` notes + a route-probe corpus |

So there are exactly **two** source repos: the fork (5 branches) and upstream (2 branches).

## 2. The shared core is already shared

All engines sit on one core in the same repo:

```
src/{artifact,core,kernels,ngram,plan,platform,prefill,program,spec}   +   include/strata/
```

**Engines on top of that core (4 of them):**

| engine | path | LOC | branch | status |
|---|---|---|---|---|
| DSV4.1 (v41) | `tools/v41/engine/ds41_*` | 12,597 | `deepseek4` | **current** (the launcher runs it) |
| GLM | `tools/glm/glm_*` | 2,636 | `glm` | current |
| old DS4 "slice" | `tools/ds4/ds4_*` | — | all | **legacy** — see §6 |
| Qwen / base runtime | `serve/` (Python) + `src/` core | — | `main` | current |

## 3. Topology — measured, not assumed

- `main` (Qwen/base) **is an ancestor of `deepseek4`, `glm` AND `mimo`.** → the unified branch is simply
  `merge(deepseek4, glm, mimo)`; Qwen rides along free.
- `git merge-base deepseek4 glm == glm-rebase HEAD == fb58e0db`. The repo was **staged for this merge**.
- `git merge-base deepseek4 mimo == 2b959ed5`.
- **Upstream `Niko1221/Strata` is a SEPARATE history.** The fork's root is `01529aaa`; Niko1221's is `a7908053`;
  `git merge-base --is-ancestor upstream/main main` → **NO**. A normal merge would need
  `--allow-unrelated-histories`.
- **The existing graft did NOT work.** `Strata-GLM-um`'s HEAD claims *"glm: merge upstream/main (Niko1221) into
  glm — graft recipe connects the histories"*, but `git diff --stat glm glm-upstream` = 57 files, **+258/-3217**,
  and **0 new paths** — it brought in no upstream content and net-deleted. Treat `glm-upstream` as **not** a
  successful upstream merge; do not build the plan on it.
- **Good news hidden in that:** it does not need to work. `serve/` is **35 files in both** the fork's `main` and
  Niko1221's `main` — the Qwen/dense runtime is already in the fork. (`~/AI/Strata-qwen/engine/strata` is an
  **untracked built binary**, not source — that is why it looked like a second engine.) So "Qwen (dense)" is in
  the fork's `main` and merging it costs **zero** conflicts. Pulling *newer* Niko1221 work later is a separate,
  optional "sync upstream" task, not part of unification.

## 4. Conflict scope — the real work

`git merge-tree --write-tree --name-only` (read-only, no checkout):

### `xolotl = merge(deepseek4, glm)` → 10 files, 33 hunks

| file | hunks |
|---|---|
| `src/kernels/cuda/iq_kernels.cu` | **15** |
| `CMakeLists.txt` | 5 |
| `README.md` | 5 |
| `src/kernels/cuda/native_mmvq.cu` | 5 |
| `src/kernels/cpu/pool.cpp` | 2 |
| `tools/ds4/ds4_moe.hpp` | 2 |
| `include/strata/kernels/iq_kernels.hpp` | 1 |
| `include/strata/kernels/cpu/native_expert.hpp` | 1 |
| `include/strata/kernels/cpu/pool.hpp` | 1 |
| `include/strata/artifact/gguf_reader.hpp` | 1 |

### `+ merge(mimo)` → 7 more files, 46 hunks

| file | hunks |
|---|---|
| `tools/ds4/ds4_moe.cpp` | **25** |
| `src/kernels/cuda/iq_kernels.cu` | 9 |
| `tools/ds4/ds4_moe.hpp` | 5 |
| `src/kernels/cpu/native_expert.cpp` | 3 |
| `CMakeLists.txt` | 2 |
| `include/strata/kernels/iq_kernels.hpp` | 1 |
| `src/prefill/moe_mmq.cu` | 1 |

**Raw diff size is misleading** — `glm`'s +1.6 M lines is one file
(`bench/glm-2026-10-08/upstream/tokenizer.json`, 1.44 M lines of benchmark output). The tracked **code is only
34 MB / 1,039 files**; 19 GB of the repo is `bench/` artifacts.

## 5. The three hard parts

1. **`src/kernels/*` — the quantisation kernels.** Both branches optimised the same IQ/MMVQ kernels for their
   model. This is the genuine, knowledge-heavy conflict. Strategy: reconcile **per kernel function**, not per
   file; gate each on the existing parity tests (`src/kernels/*_parity.cpp`) — the harness is already there.
2. **`tools/ds4/ds4_moe.*` — legacy engine, 30 of the 46 mimo hunks.** See §6.
3. **`CMakeLists.txt`** — must enable all engines at once. No branch currently references more than one; this is
   the single integration point (`.cmake` slices already exist per engine).

## 6. Dropping the legacy engine removes most of the conflict

`tools/ds4/ds4_*` is the **old** "slice" dense engine (still built by `tools/ds4/cmake/ds4_dense.cmake`), while
`deepseek4` moved to `tools/v41/engine/ds41_*`. Mal: *"any old DS4 stuff isn't necessarily needed, now that we've
got DSV4.1 working well."* If `tools/ds4/ds4_*` is dropped from the unified tree (take `deepseek4`'s side /
delete), **~30 of the 46 mimo hunks and both glm `ds4_moe.hpp` hunks disappear** — leaving ~13 files of real work,
almost all in the kernels. **Decision needed from Mal**; I have not deleted anything.

## 7. Feasibility, disk, and what I did

- **Disk is the only hard blocker:** `/` is at **97%, 26 G free**, and `Strata-DS4` is 29 G. A normal clone is
  impossible. Because the *code* is only 34 MB, this repo was created as a **sparse clone excluding `bench/`**:
  `~/AI/Xolotl` is **122 MB**, and disk free was unchanged after creating it.
- `~/AI/Xolotl` is a clone **with history** (can push later), branch **`xolotl`** at `deepseek4`'s HEAD,
  `origin` = `~/AI/Strata-DS4`, `glm`/`mimo` reachable as `origin/glm` / `origin/mimo`.
- **Nothing was merged and nothing was deleted** — this file plus `tools/xolotl/merge-xolotl.sh` are the whole
  scaffold. The tree is clean at `xolotl` = `deepseek4`.

## 8. Risks / unknowns

- **Unverified:** whether GLM's and mimo's kernel changes are *compatible* (both may have changed the same
  IQ3/IQ2 decode numerics for different models). Only resolving the hunks and running the parity tests answers it.
- **Unverified:** that the merged tree actually *builds* all engines — the CMakeLists integration is untried.
- **Unknown:** whether "Qwen (dense)" also means *newer* `Strata-qwen` work (2026-10-13) beyond the fork's `main`
  (2026-10-04). If so that is an extra "sync upstream" job with unrelated-history cost, kept out of scope here.
- MiMo is lowest priority and contributes the largest single conflict file; it can be merged last or skipped.

## 9. Recommended sequence

1. In `~/AI/Xolotl`: **merge `origin/glm`** → resolve 10 files / 33 hunks (kernels first, CMakeLists last).
2. Build all engines; run `src/kernels/*_parity` + each engine's golden tests.
3. **Merge `origin/mimo`** → resolve 7 files / 46 hunks (drop `tools/ds4` first if Mal approves, §6).
4. Re-run the gates. Tag it. Only then add a remote and push.
5. Separately, if wanted: sync newer `Niko1221` Qwen work (unrelated history — its own project).

## 10. Reproduce every number here

```bash
cd ~/AI/Strata-DS4
git merge-tree --write-tree --name-only deepseek4 glm   | grep '^CONFLICT'
git merge-tree --write-tree --name-only deepseek4 mimo  | grep '^CONFLICT'
for b in deepseek4 glm mimo; do git merge-base --is-ancestor main $b && echo "main<=$b"; done
git diff --stat glm glm-upstream            # the graft that brought nothing in
```

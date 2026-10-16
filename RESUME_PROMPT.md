# RESUME PROMPT — Xolotl (the unified Strata engine) — written 2026-10-16 ~17:00, end of session 3

You are resuming a multi-session project for **Mal** (Malich Coory, Indra's Mirror). Read this whole file, then the top
block ("session 3") of `~/AI/Xolotl/HANDOFF.md`. Do not re-derive anything this file states as measured. Mal's rules
for this project: measure before concluding, A/B against the previous production build, small tests first, never push
or delete without his explicit go, commit locally as you go (a reboot already wiped uncommitted /tmp work once).

---

## 1. What Xolotl is

`~/AI/Xolotl` (git branch `xolotl`) is ONE engine tree that runs every Strata-family model Mal uses:

| model | engine binary | serve shim / config | wrapper (live) |
| --- | --- | --- | --- |
| **DeepSeek-V4.1-Flash** (552B MoE, GSQ 152 GiB) | `build-xolotl/ds41_generate` | `tools/v41/serve/serve_ds41.py` + `strata-ds41.json` (512K, DSpark, `--kv-fp4`, route bias x0.5) via `ds41-engine.sh` | `strata-ds41-quetza` (port 8150) |
| **GLM-5.3-Flash** (320B MoE, Maya-S-v2 IQ2_XXS + abliteration LoRA) | `build-xolotl/glm_generate` | `tools/glm/serve/serve_glm.py` + `strata-glm-maya-abl-512k.json` via `glm-engine.sh` | `strata-glm-quetza` (8144) |
| **Qwen3.8-Flash-Next** (125B MoE, SC117 abliterated IQ3_XXS, lazy vision) | `build-xolotl/strata` + `build-vision/bin/strata-vision` | `python -m serve.server` + `~/.quetza-data/xolotl/strata-swift-iq3_xxs-sc117-lazyvision.json` | `strata-quetza` (8130) |
| **Qwen3.8-27B dense** (d0xin uncensored IQ3_S + MTP) | `build-xolotl/strata-dense` | `python -m serve.server`, config written by the wrapper (`--draft-max 3`, k8v4, 200K) | `strata-dense-quetza` (8090) |
| DeepSeek-V4-Flash-0731 (legacy, 284B) | `build-xolotl/ds4_generate` | no serve shim (Mal serves 0731 via a llama.cpp fork) | — |

Every server is Xolotl's own `serve/server.py` (Strata 0.1.44.1 + local features: lazy vision, `/v1/decide`, voice
sidecar `serve/voice.py`). Python: `~/AI/Strata/.venv/bin/python` (OG Strata's venv) or system `python3` (dense wrapper).
Every config defaults to `reasoning_budget_tokens: 32768` (Mal: all models get a 32K thinking budget).

Lineage: Strata (Niko1221, MIT) + our forks Strata-DSV4.1 (DeepSeek) and Strata-GLM + perronemirko's 27B dense port +
the Strata-qwen voice work. Upstream merged at 0.1.44.1 (`niko/main` 296b59d2).

## 2. Where everything is

- `~/AI/Xolotl` — the engine. Remotes: `github` = Indras-Mirror/Strata-DSV4.1 (the push target), `github-glm`,
  `niko` (upstream), `perrone`, `origin` = `~/AI/Strata-Backup/Strata-DS4`, `up` = `~/AI/Strata`.
- `third_party/llama.cpp` — untracked + gitignored: llama.cpp **3cf03257** + `tools/xolotl/ggml/xolotl-ggml.patch`
  (19 ggml files: V4.1 ops, bit-exact fp4 KV, deterministic MMQ, upstream #30103/#29953, GLM no-graph). Proven
  identical (diff -r) to the tree everything was measured on. Fresh: `bash tools/xolotl/fetch-llama.sh`. CMake applies
  the patch itself when STRATA_GGML_DIR is unset.
- `build-xolotl/` + `build-vision/` — **their CMakeCache still points STRATA_GGML_DIR / LLAMA_DIR at
  `~/AI/Strata-DS4/third_party/llama.cpp`, which moved.** Reconfigure before the next build (§5 step 3).
- `~/AI/Strata` — OG upstream checkout (keep: venv + `data/expert-profile*.bin` used by the Qwen Flash config).
- `~/AI/Strata-data` — Qwen Flash packs + MTP (keep).
- `~/AI/Strata-Backup/` — every old tree (Strata-DS4 + worktrees, Strata-qwen, strata-dense-build/-runtime,
  Strata-DS4-private, models-dense, v41-dev). Rollback binaries kept. 89 GB deleted with Mal's OK —
  `DELETED-2026-10-16.txt`. Wrapper rollbacks: `~/.local/bin/*.bak-prexolotl-20261016`.
- Model files: GLM `/media/mal/SSD NVME/Models/GLM-5.3-Flash-Maya-S-v2/` (the `SSD NVME` partition does NOT
  auto-mount after a reboot: `udisksctl mount -b /dev/nvme0n1p3`), V4.1 `/media/mal/SSD NVME/AI/V41-GSQ/`, engram
  `/media/Crucial1TB/V41-Engram` + `SSD NVME/AI/V41-Engram`, Qwen Flash + 27B + DSpark sidecar + GLM LoRA on
  `/media/mal/NVME1TB/Models/`, NInfer artifact `/media/Crucial1TB/models/ninfer/`.
- Verification artefacts (untracked): `~/AI/Xolotl/verify/` — every A/B script, log and stub-engine test of session 3.

## 3. What is VERIFIED (do not redo)

| | result |
| --- | --- |
| DSV4.1 | logits bit-identical to production; e2e non-thinking 20/21 HumanEval, 10/10 tools, 3/3 agentic, 5391 tok, 596 s == production 598 s; decode during tasks 27.5 vs 27.8 tok/s |
| GLM-5.3 | engine output within production's own run-to-run noise; serve GEN lines byte-identical; tool calls identical at every stream split |
| Qwen Flash | identical greedy chat + image answers; decode 151 vs 116.5 tok/s (the 0.1.44 merge), prefill 3577 vs 3509 |
| 27B dense | teacher-forced mean abs dlogprob 0.015 vs production; decode 116 (draft 3) vs 105; prefill 1240 vs 1331 (-7%, open) |
| V4-0731 | ppl 10.39 vs production 10.41-10.51; decode 19.4 vs 19.3 |
| server | 733 unit tests; `tools/v41/serve/test_serve_ds41.py` all passed |
| NInfer (27B, for reference) | prefill 4402 / decode 176 tok/s on the same speedbench (20K prompt, 1024-token code) |

Bugs fixed in session 3 (details + mechanisms in HANDOFF S3.2): tokenizer `_re` (bug 12), the missing strata-dense
target + `/v1/decide` (lost with /tmp), voice sidecar cold-start kill + orphaned children, V4-0731 nextn layer drop
(bug 13), GLM short-prompt OOM, the GLM/DSV4.1 shims running the old 0.1.39 server + four 0.1.44 API drifts (incl.
**every DSML/GLM tool call came out as text** — `F.FUNC_START = ""`), and fresh-clone build failure (ggml patch).

## 4. What was running when this was written

`~/AI/Xolotl/verify/e2e/final-think.sh` — THE README TABLE RUN: DSV4.1 -> GLM -> Qwen Flash -> 27B, each through
`tools/taskeval` (smoke + HumanEval-21 + tools-10 + agentic-3), greedy, thinking on, `TASKEVAL_THINK_BUDGET=32768`,
the wrappers' configs. Results land in `verify/e2e/final-think/`:
`score.txt` (pass counts), `speed.txt` (prefill / decode tok/s DURING the tasks — Mal wants these, NOT speedbench),
`r_<model>/results.json`, `server_<model>.log`. Log: `verify/e2e/final-think.log` ("ALL DONE" at the end).
At ~16:55 DSV4.1 had 20 PASS lines, 0 fails. Expect ~3-4 h total. If it died: rerun `bash verify/e2e/final-think.sh`
(it is idempotent per model; delete `final-think/r_<model>` to redo one).

## 5. Next steps, in order

1. **Fill the README table.** `README.md` has `{{DS41_HE}}`-style placeholders (HE / TOOL / AGENT / PF / DEC per model:
   DS41, GLM, QF, Q27). Source: `python3 tools/taskeval/taskeval.py score verify/e2e/final-think/r_*` and `... speed ...`.
   Format: `20/21`, `10/10`, `3/3`, prefill as an integer, decode one decimal. Also add one line under the table: the
   date, "thinking on, 32K budget, greedy". Commit.
2. **Fresh-clone build test** (proves `xolotl-ggml.patch` + CMake): `git clone ~/AI/Xolotl /tmp/xolotl-fresh` (or the
   scratchpad), configure WITHOUT `STRATA_GGML_DIR` (CMake fetches llama.cpp 3cf03257 and applies the patch), build
   `strata strata-dense glm_generate ds41_generate`. Must be 0 errors. ~10 min CPU — not while a GPU benchmark runs.
   Disk: ~113 GB free on `/` now.
3. **Reconfigure the local builds:** `cmake -S . -B build-xolotl -DSTRATA_GGML_DIR=$PWD/third_party/llama.cpp` (all
   other cache options stay) + `ninja -C build-xolotl`; `cmake -S tools/vision -B build-vision
   -DLLAMA_DIR=$PWD/third_party/llama.cpp` + `ninja -C build-vision strata-vision`. Then a 1-request smoke per model.
4. **Push — ONLY after Mal says go** (he said: not until DSV4.1 is definitely up to scratch + the README lists every
   model's HumanEval + throughput). `git push github xolotl:main` — it fast-forwards over GitHub main (9d6529fc is an
   ancestor of xolotl); the local `git replace` graft is not pushed and not needed. Before pushing check: no secrets
   (`git grep -nE "sk-|hf_[A-Za-z0-9]{20}|or-v1-"`), no file > 50 MB in the pushed history, `verify/` untracked.
   Then (Mal's call): GitHub repo description + topics (draft in `docs/brand/XOLOTL_BRAND.md`: "Xolotl -
   DeepSeek-V4.1-Flash (552B MoE) on one gaming PC: a Strata engine..."; topics deepseek, deepseek-v4, glm, qwen, moe,
   llm-inference, offloading, speculative-decoding, cuda, local-llm, strata), social preview =
   `docs/brand/assets/github-social-preview-1280x640.png`. Possibly rename the repo to `Xolotl` IN PLACE (Settings ->
   Rename keeps stars + redirects; NEVER create a new repo with the old name). README header image already says
   "DeepSeek-V4.1-Flash on one gaming PC".
5. **The Gauntlet** (`tools/gauntlet/`, Mal's idea: a small benchmark so hard most models fail, to expose what quants
   cost): DESIGN.md has the rules and 10 task specs; tasks 01 (ledger root-cause) and 02 (semver precedence) are written
   and validated (`python3 tools/gauntlet/validate.py` -> both OK); the runner is mechanics-tested. **Write tasks 03-10**
   per DESIGN.md (each: workspace/, hidden/test_hidden_*.py, reference/, trap/, task.json; validate.py must print OK),
   keeping each <= ~400 lines and the whole run <= ~40 min at ~25 tok/s. Then calibrate: run it on DSV4.1 (Xolotl),
   and — when Mal OKs API spend — the DeepSeek API (`deepseek-flash` IS V4.1-Flash; port the env knobs from
   `verify/e2e/api/taskeval_api.py`: TASKEVAL_MODEL / TASKEVAL_KEY, no `reasoning_effort: none` on the API). Replace
   any task every model passes. Keep `hidden/` out of public pushes if it becomes a leaderboard.

## 6. Open questions for Mal (do not decide them yourself)

- **27B vs NInfer:** strata-dense is 3.5x behind on prefill (IQ3_S MMQ ~67 effective TOPS vs NInfer's int8 A8 GEMMs
  ~240) and 1.5x on decode (spec depth / acceptance). Port NInfer-class kernels into strata-dense (a project) or serve
  the 27B through NInfer and add `/v1/decide` there (`~/AI/quetza-workspace/voice-duplex/research/NINFER_DECIDE_MAP.md`).
  The open-jet fork (github cutlerbenjamin1-cmd/open-jet qwen38-perf: 151 tok/s on a 3090, bit-exact 7-draft MTP,
  K6/V5 KV) needs Q4_K_M / UD-Q4_K_XL files, not our IQ3_S, and its prefill is slower than NInfer's.
- **Qwen Flash quality upgrade:** NVIDIA's QAD NVFP4 Qwen3.8-Flash-Next (102 GB) — Xolotl reads NVFP4 since 0.1.44
  (W4A8 on the 4090); Mal is waiting for an abliterated version; needs ~102 GB free disk.
- MiMo: dropped (Mal). Its branch `origin/mimo` was never merged; weights deleted.

## 7. Known open items (not blockers)

- 27B prefill -7% vs production (newer ggml MMQ kernels in the prompt path; nsys both binaries to locate).
- GLM prompts of 17-256 tokens now shrink the elastic cache per request (correct; slightly slower than before the fix,
  which crashed instead). <= 16 tokens go through the decode loop.
- llama.cpp b11390 (CUDA MoE MMQ temp-buffer padding fix, 2026-10-04): check whether xolotl-ggml.patch covers it.
- `ple_parity` ctest fails for a missing model fixture (environmental, 55/56).

## 8. Traps that already cost time (read before touching anything)

1. **Semantic merge conflicts compile fine.** Renamed attributes (`_re`), X-macro type lists (`STRATA_*_FMTS*`), and
   monkeypatching shims vs a newer server's signatures all built and passed ctest while a model was broken. After ANY
   merge, run every model end to end (engine A/B + serve-level stub-engine GEN-line diff + a real tool call).
2. **`pkill -f <pattern>` kills your own shell** when the pattern is in your command (exit 144) — kill by PID or `pkill -x`.
3. **Production configs carry timing-dependent flags** (GLM `--skip-*`, `--arena-adapt`; DSV4.1 `--arena-adapt`):
   compare engines with them OFF, and measure the reference against ITSELF first (noise floor).
4. A short `run_tests`/serve prompt path can differ from the long one (GLM's c_stage OOM); test both.
5. Don't benchmark while compiling (CPU-pool experts share the CPU).
6. `git apply` inside a non-repo dir under another repo resolves against the parent repo — use
   `GIT_CEILING_DIRECTORIES` (the CMake check does).
7. `/tmp` does not survive reboots — keep artefacts under `~/AI/Xolotl/verify/` or the scratchpad and COMMIT code.
8. Background waits: use until-loops on a condition, not chained sleeps.

## 9. Key commands

```bash
cd ~/AI/Xolotl
git log --oneline -12                                   # session 3: e818dd6a .. c2c36a9e (+ README fill)
python3 tools/taskeval/taskeval.py score DIR...         # pass counts       (run: taskeval.py run URL DIR)
python3 tools/taskeval/taskeval.py speed DIR...         # tok/s during the tasks
python3 tools/gauntlet/validate.py                      # Gauntlet tasks valid?
python3 tools/gauntlet/gauntlet.py run URL DIR [--only 01,02] ; gauntlet.py score DIR...
bash verify/stub-ab.sh <tag> <shim> <config> [cwd]      # serve-level: GEN lines from a stub engine (STUB_STOP_ID=<eos>)
strata-ds41-quetza / strata-glm-quetza / strata-quetza / strata-dense-quetza   # Mal's wrappers (Xolotl)
```

## 10. UPDATE 17:15 (end of session 3) — read this first

- **README run, DSV4.1 done (thinking, 32K budget):** HumanEval **21/21**, tools **10/10**, agentic **3/3**; during the
  tasks: prefill 26 tok/s (short prompts - not representative), decode **26.4 tok/s**; 63,402 tokens, 2,973 s.
  GLM started 17:12, then Qwen Flash, then 27B (`verify/e2e/final-think.log`).
- **Gauntlet:** tasks 01-09 written AND validated (`python3 tools/gauntlet/validate.py` -> all OK):
  01 ledger root-cause, 02 semver, 03 ray tracer (pixel-compared, graphics), 04 log needle (20K tok, long context),
  05 regex engine (fuzz vs re + no catastrophic backtracking), 06 TTL+LRU cache (threads), 07 CSV money (3 dialects),
  08 SVG raster (nonzero/evenodd, graphics), 09 DST scheduler. Runner has a `run_python` tool now.
  **Task 10 (flaky-suite) is WIP:** only `workspace/` exists, and its visible tests currently fail even in file order
  (2 of 4) - they must PASS in file order and fail only in some orders. Fix the test design (e.g. make
  `test_tags_are_per_item` / `test_tagged_only_lists_stock` order-dependent only), then write `reference/inventory.py`
  (default `tags=None` + copy, `reset()` clears `_by_tag`, remove drops the name from `_by_tag`), `trap/` (fix only the
  mutable default), `hidden/test_hidden_order.py` (import the visible test functions and run them in 30 seeded
  shuffled orders), and `task.json`. Then validate.
- **Then (Mal asked):** run the Gauntlet on the DeepSeek API (`deepseek-flash` = V4.1-Flash; Mal OKed API use for this):
  give `tools/taskeval/taskeval.py`'s chat() the env knobs from `verify/e2e/api/taskeval_api.py` (TASKEVAL_MODEL,
  TASKEVAL_KEY -> Authorization header; drop `reasoning_effort: none`; URL https://api.deepseek.com), run
  `python3 tools/gauntlet/gauntlet.py run https://api.deepseek.com out/gauntlet-api`, then the same on local DSV4.1
  (strata-ds41-quetza, port 8150). Goal: the API should fail several tasks; replace any task everything passes.


---

## 11. UPDATE — session 4 (2026-10-16 ~17:40), read this INSTEAD of section 10

**Ended:** the Gauntlet is complete (10/10 written + validated) and has been calibrated against the API; 7 hardening
workers are in flight to raise its difficulty; the 4-model e2e chain is still running on the GPU.

- **Gauntlet is DONE as a benchmark**: all 10 tasks validate (`python3 tools/gauntlet/validate.py` -> 10x OK).
  Task 10 (flaky-suite) is written (visible suite passes in file order, fails ~1 run in 3 shuffled; trap = fix only
  the shared default list). The documented **exact-answer task format is now implemented** (`re.search` on the final
  assistant message) and `selftest.py` drives the real runner for 4 checks - commit `82d1aa64`. A task with neither
  hidden tests nor an `answer` now fails loudly instead of scoring PASS silently.
- **Measured API baseline (the number that matters): `deepseek-flash` scores 8/10** - it fails only 03-raytracer and
  05-regex-engine; 114,210 completion tokens, 700 s for all ten. Too easy => 7 tasks are being hardened right now
  (01, 02 -> invented release-ordering spec, 04, 06, 07, 08, 09), 10 queued. Target: the API fails ~7/10.
- **Conductor session 4** (relay name `conductor-1344159.1195555`): workers `ga-harden-{01,02,04,06,07,08,09}`,
  one slice per task, each gate = `validate.py <that task>` OK + a derivability table (every hidden assertion ->
  the documented sentence that states it). Reports land in `~/.quetza-data/conductor/reports/ga-harden-NN.md`.
  **Never run the full `validate.py` while a hardener is editing its task dir** - it will read a half-written tree.
- **Sequence when they land**: verify each diff myself (not the worker's summary), run
  `validate.py` over the frozen set + `selftest.py` (its check d re-verifies task 01), commit, then re-run the API
  (`TASKEVAL_MODEL=deepseek-flash TASKEVAL_KEY="$DEEPSEEK_API_KEY" TASKEVAL_NO_EFFORT=1 python3
  tools/gauntlet/gauntlet.py run https://api.deepseek.com out/gauntlet-api2`) to confirm the difficulty moved.
  Then dispatch the flaky-suite hardening (10) and the fairness audit over the FINAL set (the first audit worker was
  killed before it wrote anything - its subject was being rewritten underneath it).
- **GPU**: the e2e chain is self-driving (`verify/e2e/final-think.sh`, scores itself, ends with `ALL DONE`). GLM is
  slow because one HumanEval problem can consume the whole 32K thinking budget: measured 25,446 tok at 28.7 tok/s =
  **893 s for one problem** (others 35-75 s), 4/21 done in 22 min => GLM ~19:00, then qflash, then q27. Mal may stop
  the chain; the moment the GPU frees, run the local Gauntlet:
  `TASKEVAL_THINK_BUDGET=32768 python3 tools/gauntlet/gauntlet.py run http://127.0.0.1:8151 out/gauntlet-ds41`
  (serve ds41 on 8151 the way `final-think.sh` does). That API-vs-quant contrast on the hardened set is the
  deliverable; the e2e HumanEval numbers are saturated (21/21) and show little.
- **Nothing pushed.** Commits this session: `02acb010` (task 10), `ee0610ea` (API knobs), `80290ee2` (DESIGN table),
  `0ef1e51a` (runner robustness: a bad tool path or one task's exception can no longer kill a run), `82d1aa64`
  (answer grading + selftest). `README.md` is still dirty on purpose - its table waits on the e2e chain.

# The Gauntlet - a small, hard, real-world agentic coding benchmark (DRAFT v0.1)

**Why.** HumanEval-21 / tools-10 / agentic-3 (`tools/taskeval`) is saturated: DeepSeek-V4.1 scores 20/21 quantized and
the full-precision API would too, so it cannot show what a quant, a route bias or an engine change *costs*. The Gauntlet
is the opposite: **10 tasks that most models fail**, so a frontier API might score ~5/10 and a damaged quant 2/10 -
the gap is the signal. It must stay **small**: 10 tasks, 12 agent steps each, no synthetic benchmark.
RUNTIME, measured: the full-precision API does all ten in **~12 min** (700 s, 114K completion tokens). A local
engine is a different matter - the step budget bounds its *actions*, not its tokens: with the 32K thinking
budget the e2e run used, GLM spent 25,446 tokens on one problem (893 s at 28.7 tok/s) and fine-tuning this
benchmark measured ds41 at ~20 min for a single hard request. Budget **~1-3 h for a local model**, not 40 min,
and note which thinking budget a row was measured with (a local row at 32768 is not comparable to the API's
native default).

## Rules every task must follow

1. **Real work, not puzzles.** Each task is something an agent in Claude Code / Codex / Quetza actually meets: a bug
   whose symptom is far from its cause, a spec with sharp edges, a refactor that must not break hidden behaviour, a
   long log with one inconsistency, a tool chain with distractors.
2. **Machine-graded, binary, deterministic.** Pass = the hidden tests pass (pytest) or the exact-answer check
   matches. No LLM judge. Greedy decoding (temperature 0), thinking on, `reasoning_budget_tokens` 32768.
3. **Hard because of depth, not trivia.** Every task has at least one trap a pattern-matching model falls into (the
   obvious fix makes the visible test pass and a hidden test fail). The prompt contains everything needed - no
   outside knowledge beyond a competent engineer's.
4. **Original.** Written for this benchmark (not HumanEval/MBPP/SWE-bench text), so it is not in training data.
   Do not publish the hidden tests in the same repo as a public leaderboard (keep `hidden/` out of the public
   push or rotate tasks).
5. **Bounded.** max 12 agent steps, max 6 `run_tests` calls, the model's own token budget; workspace <= ~400 lines;
   prompt + files <= ~12K tokens (one long-context task may go to ~24K).
6. **Validated before use.** `validate.py` proves for every task: the hidden tests FAIL on the starting workspace,
   PASS with `reference/` applied, and (if the task has a trap) FAIL with `trap/` applied. A task that a reference
   cannot pass, or that the starting code already passes, is rejected.

## Task format (`tasks/NN-name/`)

```
task.json        {"id", "category", "prompt", "max_steps", "max_test_runs", "answer"?(exact-answer tasks), "trap"?: "one line"}
workspace/       the files the model sees and edits (incl. VISIBLE tests: test_*.py)
hidden/          test_hidden_*.py - copied in only for grading, never shown
reference/       a correct solution: files that overwrite workspace/ ones (validation only)
trap/            optional: the tempting wrong fix (validation: must FAIL hidden)
```

Tools the model gets (OpenAI function calling, same in every engine): `list_files()`, `read_file(path)`,
`write_file(path, content)`, `run_tests()` (visible tests only - output truncated to 4K chars), `submit(note)`.
Exact-answer tasks get no workspace and are graded on the final message (`answer` = regex the final text must match).

## The 10 tasks - all written and validated

`validate.py` proves for every one: the hidden tests FAIL on the starting workspace, PASS with `reference/`
applied, and FAIL with `trap/` applied (so the trap is tempting AND caught).

| # | id | category | what it needs / the trap | hidden grading |
| --- | --- | --- | --- | --- |
| 01 | ledger-rootcause | agentic debug | three modules (`parse`/`report`/`reconcile`): exact `Decimal`, quantize ONCE at the end with `ROUND_HALF_EVEN`, five rejection classes, and a reconcile pass that compares only after quantizing. Trap: normalise in `report.py` (visible passes, `parse_amount` stays wrong) or float+`round()` in reconcile | 33 hidden cases |
| 02 | release-order | spec precision | an **invented** release-stamp ordering - nothing to recall: non-alphabetical channel rank (`dev<beta<rc<stable<`*no channel*`<hotfix`) and an inverted EPOCH compared as the LAST key. Trap: epoch-first ascending + alphabetical channels | 14 pairs, 23 invalid forms, stable sort |
| 03 | raytracer | graphics / 3D math | implement `render()` to spec: pixel-centre rays, y flip, shadows with an epsilon, reflection depth 3. Trap: `int()` instead of `floor()` for the checker cells (breaks for negative x/z) | pixel-compare vs reference renders, 2 scenes |
| 04 | log-needle | long context (~19K tok) | an 18.5K-token gateway log + `limits.yaml` + `exemptions.txt` + `api_keys.txt`: write the **set of violating request ids** (5 - three per-tenant, two global), which needs the key->tenant join, the exemptions, and the retired key. Traps: the single-rule scan (yields 16 ids), a closed window, counting the exempt `ops`/`/health`, skipping 429s | the exact sorted id set |
| 05 | regex-engine | algorithms + performance | `fullmatch` for `. * + ? ( ) | [ ] \` and classes. Trap: backtracking (correct but exponential) - `(a*)*b` on 40 a's must finish < 2 s | fuzz vs `re.fullmatch` (2,400 cases) + timing |
| 06 | ttl-cache | concurrency + time | LRU+TTL with an injected clock and threads: expire lazily on read AND write, capacity counts live entries only, `get` refreshes recency but NOT expiry. Trap: evicting before purging expired entries | expiry/eviction order + thread stress |
| 07 | csv-money | data wrangling | 3 bank dialects: `,`+`$`, `;`+decimal commas+CRLF+BOM, tab+trailing minus+quoted memos; summary rows excluded. Trap: `float` sums / guessing the dialect | totals to the cent, `expected.json` |
| 08 | svg-raster | graphics / geometry | rasterize an SVG path subset (M/L/H/V/Z, relative, implicit L after M) with the nonzero or even-odd rule at pixel centres. Trap: always even-odd (breaks a star's centre and a same-direction donut's hole) | character-exact rasters, 10 shapes |
| 09 | dst-scheduler | time zones / real-world spec | meeting conflicts across DST: a skipped local time must raise, a repeated one is resolved by `fold`, a local day is 23/24/25 h. Trap: `zoneinfo` silently shifts a nonexistent time and a `timedelta(hours=24)` day | gap/overlap, real durations, day lengths |
| 10 | flaky-suite | agentic debug | the visible suite passes in file order and fails ~1 run in 3 shuffled (a shared default tag list). Trap: fix only that default - `reset()` still leaks the tag index, removal still leaves the tag, and the caller's list / the returned list are still the item's own list | the visible suite in 20 random orders + the full documented contract |

**Calibrated 2026-10-16** against the full-precision API (`deepseek-flash` = V4.1-Flash, greedy, no effort
override): **8/10 in 12 minutes** (114,210 completion tokens, 700 s) - it fails only **03-raytracer** and
**05-regex-engine**, and it walked 01 in 9 steps, 02 in 7, 09 in 12, 10 in 12. That is too easy to show what a
quant loses, so the tasks it passed were hardened: 01 (three modules + a reconcile invariant), 02 (SemVer replaced
by an invented release-ordering spec), 04 (several rules + a key->tenant join + an exemptions file), 06 (`peek`/
`stats`/invented purge order + a thread stress test), 07 (dialect by header signature + rates normalisation pinned
by a 1-cent case + a duplicate rule), 08 (C/Q/A curves with a documented flattening rule), 09 (recurring local-time
meetings + `find_slots`), 10 (queued). Target: the API fails about **7 of 10**, so the gap to a damaged quant is
measurable. **A task every model passes is too easy - replace it; one the references pass and every model fails 3
runs in a row is fine** (keep at most 2 of those).

## Running it

```bash
python3 tools/gauntlet/validate.py                         # every task: start FAILS, reference PASSES, trap FAILS
python3 tools/gauntlet/gauntlet.py run http://127.0.0.1:8150 out/ds41        # a local Xolotl server
TASKEVAL_THINK_BUDGET=32768 python3 tools/gauntlet/gauntlet.py run ... # (same env knobs as taskeval)
python3 tools/gauntlet/gauntlet.py score out/ds41 out/glm                   # table: pass/10, tokens, seconds, tok/s
```

An API model, to measure what a quant loses - the knobs live in `taskeval.py`'s `chat()` now:

```bash
TASKEVAL_MODEL=deepseek-flash TASKEVAL_KEY="$DEEPSEEK_API_KEY" TASKEVAL_NO_EFFORT=1 \
  python3 tools/gauntlet/gauntlet.py run https://api.deepseek.com out/gauntlet-api
```

`TASKEVAL_NO_EFFORT` drops `reasoning_effort: none`, which the API rejects; the local engines keep it. The
gauntlet's `run_python` tool executes the model's snippet with the workspace as cwd, so every task also needs a
`max_python_runs` cap in its `task.json`.

## Reporting

Per model: pass count /10 (and which), total tokens, wall time, decode tok/s during the run (server timings, as
`taskeval.py speed`). Run each config **3 times** (greedy is deterministic per engine, but the quantized engines have
run-to-run variation from timing-dependent expert placement) and report min / median.

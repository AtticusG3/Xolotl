# The Gauntlet - a small, hard, real-world agentic coding benchmark (DRAFT v0.1)

**Why.** HumanEval-21 / tools-10 / agentic-3 (`tools/taskeval`) is saturated: DeepSeek-V4.1 scores 20/21 quantized and
the full-precision API would too, so it cannot show what a quant, a route bias or an engine change *costs*. The Gauntlet
is the opposite: **10 tasks that most models fail**, so a frontier API might score ~5/10 and a damaged quant 2/10 -
the gap is the signal. It must stay **small: <= ~40 min for a whole run at ~25 tok/s** (one model, one GPU).

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

## The 10 tasks (2 written, 8 specified for the next session)

| # | id | category | the trap / why models fail | status |
| --- | --- | --- | --- | --- |
| 01 | ledger-rootcause | agentic debug | the failing visible test is in `report.py`, the cause is in `parse.py` (accounting negatives "(12.50)" and thousands separators); patching `report.py` passes the visible test and fails 4 hidden ones | **written** |
| 02 | semver-precedence | spec precision | SemVer 2.0 precedence: numeric vs alphanumeric pre-release ids, build metadata ignored, leading zeros invalid, `1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta.2 < 1.0.0-beta.11` | **written** |
| 03 | lru-ttl-clock | concurrency + time | an LRU+TTL cache with an injected clock and a thread pool: expiry on read AND write, capacity counts only live entries, `get` refreshes recency but NOT expiry; a lock around `get` only (the obvious fix) deadlocks or races in a hidden stress test | spec |
| 04 | migration-refactor | refactor | split a 300-line module into a package without changing behaviour; hidden tests import the OLD paths (back-compat shims needed) and pickle/unpickle objects (class `__module__` must survive) | spec |
| 05 | log-needle | long context (~20K tok) | a 20K-token service log + a config; exactly one request violates a rate-limit rule that is only stated in the config's comments; answer = the request id. Distractor: an obvious ERROR line that is not a violation | spec |
| 06 | tool-chain-distractors | tool use | 9 tools, 3 near-duplicates (`get_user` vs `get_user_by_email` vs `fetch_user_legacy` returning stale data); the task needs 4 calls in order with an id from call 2 fed to call 4; graded on the final answer AND the call log (no legacy tool) | spec |
| 07 | csv-dialect-sniff | data wrangling | parse "CSV" exports from 3 systems: `;` separator with decimal commas, quoted newlines, a BOM, a trailing summary row; totals must match to the cent. `float` sums fail a hidden test (Decimal needed) | spec |
| 08 | regex-engine-mini | algorithmic | implement `match(pattern, s)` for `. * + ? | ( ) ^ $` with leftmost-longest semantics and NO catastrophic backtracking (hidden test: `(a*)*b` on 30 a's must finish < 1 s) | spec |
| 09 | interval-scheduler | algorithmic + spec | book meetings across time zones incl. a DST gap/overlap day; half-open intervals; the answer must reject a booking that only conflicts in local time during the overlap hour | spec |
| 10 | fix-the-flake | agentic debug | a test suite that fails 1 run in 3: shared mutable default argument + test order dependence; `run_tests` is deterministic per seed, the model must find the cause, not add retries (hidden test runs the suite 20x with random order) | spec |

Target difficulty, to calibrate once the 10 exist: run the full-precision DeepSeek API (`deepseek-flash`) and one
frontier model; **a task that every model passes is too easy - replace it; one that the references pass and every model
fails 3 runs in a row is fine** (it still separates nothing today, keep at most 2 of those).

## Running it

```bash
python3 tools/gauntlet/validate.py                         # every task: start FAILS, reference PASSES, trap FAILS
python3 tools/gauntlet/gauntlet.py run http://127.0.0.1:8150 out/ds41        # a local Xolotl server
TASKEVAL_THINK_BUDGET=32768 python3 tools/gauntlet/gauntlet.py run ... # (same env knobs as taskeval)
python3 tools/gauntlet/gauntlet.py score out/ds41 out/glm                   # table: pass/10, tokens, seconds, tok/s
```

An API model (e.g. the DeepSeek API, to measure what a quant loses): `TASKEVAL_MODEL=deepseek-flash
TASKEVAL_KEY=$DEEPSEEK_API_KEY TASKEVAL_URL_IS_BASE=1` - see `verify/e2e/api/taskeval_api.py` for the knobs to port.

## Reporting

Per model: pass count /10 (and which), total tokens, wall time, decode tok/s during the run (server timings, as
`taskeval.py speed`). Run each config **3 times** (greedy is deterministic per engine, but the quantized engines have
run-to-run variation from timing-dependent expert placement) and report min / median.

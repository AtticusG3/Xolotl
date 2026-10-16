# Xolotl benchmarks

[Back to the README](../../README.md) · [How it works](HOW_IT_WORKS.md)

## HumanEval / tool calls / agentic (`tools/taskeval`)

Every number below is measured on **one RTX 4090 (24 GB) + Ryzen 7 5700X + 90 GB DDR4 + NVMe**, through the real
server, on real tasks: 21 HumanEval problems, 10 tool-call tasks and 3 agentic bug-fix loops (mock repo, hidden
tests), greedy, **thinking on with a 32K-token thinking budget** (the way every model is served). The speeds are the
server's own per-request timings **during those tasks**, not a synthetic benchmark. The harness is in
[`tools/taskeval`](../../tools/taskeval) - run it yourself.

| Model | Size | File (quant) | Context | HumanEval (21) | Tool calls (10) | Agentic (3) | Reads prompt | Writes answer |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **DeepSeek-V4.1-Flash** | 552B MoE | [GSQ mixed 1.75-3.4 bpw, uncensored](https://huggingface.co/IndrasMirror/DeepSeek-V4.1-Flash-GSQ-Uncensored) (152 GiB) | 512K | 21/21 | 10/10 | 3/3 | 26 tok/s | 26.4 tok/s |
| **GLM-5.3-Flash** | 320B MoE | Maya-S-v2 IQ2_XXS + abliteration LoRA (96 GB) | 512K | pending | pending | pending | pending | ~28 tok/s |
| **Qwen3.8-Flash-Next** | 125B MoE | Swift 1.5 SC117 GSQ-RCO IQ3_XXS, abliterated | 200K | 21/21 | 10/10 | 3/3 | 475 tok/s | 127.8 tok/s |
| **Qwen3.8-27B** (dense) | 27B | Swift 1.5 uncensored IQ3_S + MTP head (13 GB) | 200K | 21/21 | 10/10 | 3/3 | 1,097 tok/s | 98.5 tok/s |

DeepSeek-V4.1-Flash is complete: 21/21 HumanEval, 10/10 tool calls, 3/3 agentic, 63,402 answer tokens in 2,973 s,
prefill 26 tok/s (short HumanEval prompts - not a representative prefill figure), decode **26.4 tok/s**. GLM-5.3-Flash
was stopped mid-run (5 of 21 HumanEval problems: four passes of 37-893 s, one failure at its own 33,792-token
ceiling, decoding ~28 tok/s). Qwen3.8-Flash-Next: 21/21, 10/10, 3/3, 30,809 answer tokens in 275 s, decode
**127.8 tok/s**; Qwen3.8-27B: 21/21, 10/10, 3/3, 30,722 answer tokens in 319 s, decode **98.5 tok/s** (2026-10-17;
the prefill column is again short HumanEval prompts).

Also built and verified: the earlier **DeepSeek-V4-Flash (0731)** engine (`ds4_generate`, 284B MoE, Q2 GGUF):
19.4 tok/s decode, 600-token perplexity 10.39 (the previous engine's runs: 10.41-10.51).

**Exactness.** Unifying four engines into one tree was checked against each engine's own previous build, not just
"it still answers": DeepSeek-V4.1's logits are bit-identical, GLM-5.3 and Qwen3.8-Flash-Next give the same greedy
tokens (within each engine's own run-to-run variation), the 27B's teacher-forced log-probabilities differ by 0.015
nats on average, and the server builds byte-identical engine prompts for every model.


## The Gauntlet (`tools/gauntlet`)

HumanEval-21 is saturated (every model above scores 21/21), so it cannot show what a quantisation or an engine
change costs. [The Gauntlet](../../tools/gauntlet/README.md) is a small set of hard, machine-graded agentic coding tasks
(spec precision, root-cause debugging, graphics math, concurrency, data wrangling, competitive programming) with
hidden tests, a trap per task, and a runner whose grading cannot be subverted from the workspace. v2 gives every
model 10 turns per task with no token budget, grades the hidden tests after every turn, and scores progress from
each task's starting state (no free credit) plus the turn each task was solved on. Results per model are in its
README.

## Measuring it yourself

```bash
python3 tools/taskeval/taskeval.py run http://127.0.0.1:<port> out && python3 tools/taskeval/taskeval.py score out
python3 tools/taskeval/taskeval.py speed out          # prefill / decode tok/s during those tasks
python3 tools/turnbench.py http://127.0.0.1:<port>    # the cost of a small agent turn on a long context
python3 tools/gauntlet/gauntlet.py run http://127.0.0.1:<port> out/g && python3 tools/gauntlet/gauntlet.py score out/g
```

# Xolotl benchmarks

[Back to the README](../../README.md) · [How it works](HOW_IT_WORKS.md)

## HumanEval / tool calls / agentic (`tools/taskeval`)

Every number below is measured on **one RTX 4090 (24 GB) + Ryzen 7 5700X + 90 GB DDR4 + NVMe**, through the real
server, on real tasks: 21 HumanEval problems, 10 tool-call tasks and 3 agentic bug-fix loops (mock repo, hidden
tests), greedy, **thinking on with a 32K-token thinking budget** (the way every model is served). The speeds are the
server's own per-request timings **during those tasks**, not a synthetic benchmark. The harness is in
[`tools/taskeval`](../../tools/taskeval) - run it yourself.

| Model | Size | File (quant) | Context | HumanEval (21) | Tool calls (10) | Agentic (3) | Prompt (short, see below) | Writes answer |
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


## Prefill on a real prompt (`tools/throughput.py`)

The prompt column above is HumanEval's short prompts (a few hundred new tokens each, where the fixed per-request
cost dominates). The probe below sends a **fresh** long prompt (no prefix reuse), then a 256-token decode on top of
it, then a ~160-token agent turn on the cached context; the speeds are the server's own timings. Quiet box (desktop
only, <1 GB VRAM used).

| Model | Prefill, ~6K fresh | Prefill, ~16.5K fresh | Decode after 6K / 16.5K | +160-token turn on 6K / 16.5K |
| --- | ---: | ---: | ---: | ---: |
| **DeepSeek-V4.1-Flash** (2026-10-17) | 178 tok/s | 268 tok/s | 23.5 / 21.2 tok/s | 7.9 s / 8.9 s |
| **Qwen3.8-Flash-Next** | 3,430 tok/s | 3,005 tok/s | | 0.7-0.8 s (+300) |
| **Qwen3.8-27B** | 1,385 tok/s | 1,244 tok/s | | 0.4-0.6 s (+300) |

DeepSeek-V4.1's prompt batch is sized from free VRAM: ~9,000 tokens per sweep on the first prompt, ~5,900 once the
speculative-decode draft model (2.9 GB) is on the card - a desktop app holding VRAM (a browser, a video call)
lowers it further (10 GiB free: 190 tok/s at 16.5K). Its decode here follows a 6-16K context, so it is below the
26.8 tok/s of the short HumanEval contexts. The Qwen3.8-Flash-Next row is a freshly started server; after an hour of agent work
(the expert cache warm) the same probe gives 3,139 tok/s at 6K and 3,903 tok/s at 16.4K.

## Measuring it yourself

```bash
python3 tools/taskeval/taskeval.py run http://127.0.0.1:<port> out && python3 tools/taskeval/taskeval.py score out
python3 tools/taskeval/taskeval.py speed out          # prefill / decode tok/s during those tasks
python3 tools/throughput.py http://127.0.0.1:<port> --prompt 20000 --decode 256   # fresh prefill, decode, a small turn
python3 tools/turnbench.py http://127.0.0.1:<port>    # the cost of a small agent turn on a long context
```

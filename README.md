<p align="center"><img src="docs/brand/assets/readme-header-1200.png" alt="Xolotl - DeepSeek-V4.1-Flash on one gaming PC" width="100%"></p>

<h1 align="center">Xolotl</h1>

<p align="center"><b>Frontier MoE models on one gaming PC: DeepSeek-V4.1-Flash, GLM-5.3-Flash, Qwen3.8-Flash-Next and Qwen3.8-27B</b><br>
One engine, one tree, one OpenAI / Anthropic-compatible server · experts tiered across VRAM, pinned RAM and NVMe ·
built on <a href="https://github.com/Niko1221/Strata">Strata</a> · Linux · NVIDIA · MIT</p>

<p align="center">Formerly <b>Strata-DSV4.1</b> (and Strata-DS4) - old links redirect. Xolotl merges the Strata family
into one engine: <a href="https://github.com/Niko1221/Strata">Strata</a> 0.1.44 (Qwen3.8-Flash-Next),
our DeepSeek-V4.1 / V4-Flash engines, our GLM-5.3-Flash engine and the Qwen3.8-27B dense port.</p>

---

## What it runs, and how well

Every number below is measured on **one RTX 4090 (24 GB) + Ryzen 7 5700X + 90 GB DDR4 + NVMe**, through the real
server, on real tasks: 21 HumanEval problems, 10 tool-call tasks and 3 agentic bug-fix loops (mock repo, hidden
tests), greedy, **thinking on with a 32K-token thinking budget** (the way every model is served). The speeds are the
server's own per-request timings **during those tasks**, not a synthetic benchmark. The harness is in
[`tools/taskeval`](tools/taskeval) - run it yourself.

| Model | Size | File (quant) | Context | HumanEval (21) | Tool calls (10) | Agentic (3) | Reads prompt | Writes answer |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **DeepSeek-V4.1-Flash** | 552B MoE | [GSQ mixed 1.75-3.4 bpw, uncensored](https://huggingface.co/IndrasMirror/DeepSeek-V4.1-Flash-GSQ-Uncensored) (152 GiB) | 512K | 21/21 | 10/10 | 3/3 | 26 tok/s | 26.4 tok/s |
| **GLM-5.3-Flash** | 320B MoE | Maya-S-v2 IQ2_XXS + abliteration LoRA (96 GB) | 512K | pending | pending | pending | pending | ~28 tok/s |
| **Qwen3.8-Flash-Next** | 125B MoE | Swift 1.5 SC117 GSQ-RCO IQ3_XXS, abliterated | 200K | pending | pending | pending | pending | pending |
| **Qwen3.8-27B** (dense) | 27B | Swift 1.5 uncensored IQ3_S + MTP head (13 GB) | 200K | pending | pending | pending | pending | pending |

DeepSeek-V4.1-Flash is complete: 21/21 HumanEval, 10/10 tool calls, 3/3 agentic, 63,402 answer tokens in 2,973 s,
prefill 26 tok/s (short HumanEval prompts - not a representative prefill figure), decode **26.4 tok/s**. GLM-5.3-Flash
was stopped mid-run (5 of 21 HumanEval problems: four passes of 37-893 s, one failure at its own 33,792-token
ceiling, decoding ~28 tok/s); the two Qwen rows have not run yet. The remaining three run with
`verify/e2e/final-think-resume.sh`.

Also built and verified: the earlier **DeepSeek-V4-Flash (0731)** engine (`ds4_generate`, 284B MoE, Q2 GGUF):
19.4 tok/s decode, 600-token perplexity 10.39 (the previous engine's runs: 10.41-10.51).

**Exactness.** Unifying four engines into one tree was checked against each engine's own previous build, not just
"it still answers": DeepSeek-V4.1's logits are bit-identical, GLM-5.3 and Qwen3.8-Flash-Next give the same greedy
tokens (within each engine's own run-to-run variation), the 27B's teacher-forced log-probabilities differ by 0.015
nats on average, and the server builds byte-identical engine prompts for every model.

## How it fits a 552B model on a gaming PC

A MoE model only uses a few experts per token. Xolotl keeps every expert somewhere and moves the ones each token's
router asks for:

| Tier | What lives there | How it is fed |
| --- | --- | --- |
| **VRAM** | the hottest experts (sized from the VRAM actually free) | LRU cache, census-ranked, grows and shrinks per request |
| **Pinned RAM arena** | tens of GiB of experts (`cudaHostRegister`) | DMA straight to the GPU |
| **NVMe file tier** | everything else | O_DIRECT reads at the drive's ceiling (~5 GB/s), prefetched a layer ahead |

On top of that, per model:

- **DeepSeek-V4.1-Flash** - its own GSQ quantisation (every expert gets its format from calibration: ternary PTQ1_0,
  Q2_0 or Q3_K), the Engram n-gram memory read from disk, **DSpark speculative decoding** with exact speculative
  sampling and confidence-gated verify, a **bit-exact 4-bit KV cache** (`--kv-fp4`) for 512K context, and selection-only
  routing biases that keep every expert reachable. Full write-up: **[docs/DEEPSEEK_V41.md](docs/DEEPSEEK_V41.md)**.
- **GLM-5.3-Flash** - KDA + MLA hybrid attention, 288 experts top-8, the abliteration LoRA applied to the dense half
  **and** the routed experts on every path (GPU, MMQ prompt chunks, CPU pool), soft pruning (every expert stays
  reachable), an elastic expert cache that lends its VRAM to long prompts. Details: [docs/glm](docs/glm).
- **Qwen3.8-Flash-Next** - upstream Strata 0.1.44: MTP speculative decoding, int8 KV, image input with an encoder that
  starts on the first picture and gives its VRAM back when idle. Details: [README.strata.md](README.strata.md).
- **Qwen3.8-27B** - native GGUF dense engine (`strata-dense`): MMQ prompt prefill, MTP speculative decoding (draft 3),
  int8-K / int4-V cache (`k8v4`) for 200K context.

Every model is served by the same Python server with each model's own chat template and tool-call format (Qwen
XML, GLM `<arg_key>`, DeepSeek DSML), OpenAI **and** Anthropic endpoints, streaming, tool calls, conversation-prefix
reuse, a `reasoning_budget_tokens` thinking budget (32K by default), and two extras:

- **`/v1/decide`** - a one-token decision from the model's real log-probabilities (e.g. "is the user done talking?"),
  for voice turn-taking without a second model.
- **Voice sidecar** - `/v1/audio/transcriptions` and `/v1/audio/speech` proxied to an ASR / TTS server that starts on
  the first request and stops when idle, shrinking the expert cache while it runs.

## Quick start

Linux, an NVIDIA GPU with 24 GB, CUDA 12.x/13.x, and RAM for the arena (90 GB was used above).

```bash
git clone https://github.com/Indras-Mirror/Strata-DSV4.1.git xolotl && cd xolotl
bash tools/xolotl/fetch-llama.sh   # llama.cpp at the pinned commit + tools/xolotl/ggml/xolotl-ggml.patch -> third_party/llama.cpp
cmake -S . -B build-xolotl -G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_GGML_CUDA=ON \
  -DSTRATA_MMQ_KQUANTS=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DSTRATA_GGML_DIR=$PWD/third_party/llama.cpp -DSTRATA_DSV41_FQ_OP=ON
ninja -C build-xolotl      # strata, strata-dense, glm_generate, ds41_generate, ds4_generate
```

Serve a model (edit the model paths in its config first):

```bash
python3 tools/v41/serve/serve_ds41.py --engine strata --config tools/v41/serve/strata-ds41.json --port 8150           # DeepSeek-V4.1-Flash
python3 tools/glm/serve/serve_glm.py  --engine strata --config tools/glm/serve/strata-glm-maya-abl-512k.json --port 8144  # GLM-5.3-Flash
python3 -m serve.server --engine strata --config <your-qwen-flash.json> --port 8130                                    # Qwen3.8-Flash-Next
python3 -m serve.server --engine strata --config <your-27b.json> --port 8090                                          # Qwen3.8-27B (exe: build-xolotl/strata-dense)
```

Then point any OpenAI- or Anthropic-compatible client (Claude Code, Codex, opencode, Open WebUI, ...) at
`http://127.0.0.1:<port>/v1`. Measure it on your PC: `python3 tools/taskeval/taskeval.py run http://127.0.0.1:<port> out`
then `taskeval.py score out` and `taskeval.py speed out`.

## Lineage and credits

Xolotl is an offshoot of **[Strata](https://github.com/Niko1221/Strata)** by Niko1221 (MIT) - the Qwen3.8-Flash-Next
engine, the server and most of the kernels are Strata's, merged at 0.1.44.1. The Qwen3.8-27B dense port is
[perronemirko](https://github.com/perronemirko/Strata)'s. The DeepSeek-V4.1 / V4-Flash and GLM-5.3-Flash engines,
the GSQ quantisation, DSpark serving, the fp4 KV cache and the unification are Indras Mirror's
([Strata-DSV4.1](https://github.com/Indras-Mirror/Strata-DSV4.1), [Strata-GLM](https://github.com/Indras-Mirror/Strata-GLM)).
Built on [ggml / llama.cpp](https://github.com/ggml-org/llama.cpp). Models: DeepSeek, Zhipu AI (GLM), Qwen; quants
and fine-tunes by peasantsmith (Maya-S-v2), ukisai (Swift 1.5 GSQ-RCO), d0xin (Swift 1.5 uncensored) and the
gcsa-abliterix GLM LoRA.

Why "Xolotl": in Aztec myth Xolotl is Quetzalcoatl's dark twin, who goes down into the underworld and carries the
bones of the dead back up. The engine does the same with experts: they live in the underworld of RAM and NVMe, and
Xolotl brings up the ones each token needs. ([brand kit](docs/brand/XOLOTL_BRAND.md))

**Status:** research code from one developer, measured on one PC. One request at a time per server. Issues and
benchmark reports from other hardware are welcome.

License: MIT.

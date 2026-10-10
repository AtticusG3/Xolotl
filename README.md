<h1 align="center">Strata-GLM</h1>

<p align="center"><b>GLM-5.3-Flash (320B MoE) on one gaming PC: 25 tok/s decode, ~400 tok/s prefill, 512K context</b><br>
A GLM-5.3-Flash engine built on <a href="https://github.com/Niko1221/Strata">Strata</a> · Linux · NVIDIA · MIT</p>

> **Status: experimental, single-developer research code.** It produces correct, coherent text and serves an
> OpenAI- and Anthropic-compatible API. It has been measured on one PC only and handles one sequence at a time.
> Expect rough edges. The DeepSeek-V4-Flash engine this grew out of is described in [README.ds4.md](README.ds4.md),
> and the upstream Strata README (Qwen3.8-Flash) is in [README.strata.md](README.strata.md).

## What this is

[Strata](https://github.com/Niko1221/Strata) is an inference engine built for large MoE models on consumer hardware.
Hot experts stay in a VRAM cache and most of the rest in a pinned RAM arena. Each layer's misses are split between
the CPU and PCIe at the same time. This repo applies that design to **GLM-5.3-Flash** (320B total / 18B active, MIT),
the strongest open "Flash"-class model when this work started (Artificial Analysis index 42, vs DeepSeek V4.1 Flash 39).

GLM-5.3-Flash is an unusual hybrid:

- **mHC hyper-connections**, as in DeepSeek V4: 4 residual streams, mixed with a Sinkhorn normalisation in every layer.
- **KDA (Kimi Delta Attention)** linear attention in 34 of 45 layers. Its state has a fixed size whatever the context length.
- **MLA with a lightning indexer** in the other 11 layers. Sparse attention picks the top 2048 tokens, so long context stays cheap.
- 45 layers × 288 routed experts. Routing is **flat** (no small hot set), so the engine is built around high
  residency, not a tiny cache.

### The model: Maya-S-v2 + runtime abliteration

The default model is **GLM-5.3-Flash Maya-S-v2** by peasantsmith (3 GGUF shards, ~96 GB). Its experts are FP8-derived
i-quants (IQ2_XXS gate/up, IQ2_S/IQ3_XXS down) and its dense half is Q6_K. It replaced the earlier 3.0-bit GSQ-RCO
file because it is faster and has better chat perplexity here.

Uncensoring is a **rank-1 abliteration LoRA applied at run time**
(GCSA Abliterix v2, StrongREJECT refusal 1.7%). It covers attention outputs, the shared expert and the routed experts,
on every path: VRAM, PCIe, CPU pool and MMQ prefill. The model file is never modified. `--stock` serves it without
the LoRA.

## How fast is it?

Measured on: **RTX 4090 24 GB · Ryzen 7 5700X (8 cores, AVX2) · 90 GB DDR4-3200 · NVMe**.
Workload: a real 12.7K-token chat turn (with thinking), then 256 greedy tokens, at **512K context**. The shipped
config ([`tools/glm/serve/strata-glm-maya-abl-512k.json`](tools/glm/serve/strata-glm-maya-abl-512k.json)) was used
with the abliteration LoRA on. Noise is about ±2%.

| | prefill | decode |
|---|---:|---:|
| **Strata-GLM now** (Maya-S-v2 + LoRA, native Q6_K dense, 512K) | **~390-400 tok/s** | **25.0 tok/s** |
| same, `--dense-requant q4_k` (+1.6% chat ppl) | ~399 tok/s | 27.2 tok/s |
| Maya-S-v2, first wiring (300K) | 205 tok/s | 21.7 tok/s |
| previous model (GSQ-RCO 3.0-bit, ablated, 300K) | 158 tok/s | 17.8 tok/s |

**Long prompts** (512K config): 50K tokens prefill at ~400 tok/s, 100K at ~330 tok/s. Past 64K tokens the chunk is
halved for each doubling of the attention cap, so the indexer's scratch always fits.

**Quality**: exact-math perplexity (no expert skipping, 4K tokens), Maya + LoRA:

| dense half | chat | code |
|---|---:|---:|
| **Q6_K native (shipped)** | **5.273** | **3.601** |
| q4_k requant | 5.355 (+1.6%) | 3.654 (+1.5%) |
| q5_k requant | 5.598 (+6.2%) | 3.641 (+1.1%) |

Decode is **PCIe-bound**. An nsys profile puts the H2D copy engine at 26 ms/token busy (~22 GB/s, the PCIe 4.0
ceiling) against 16 ms of kernels. The CPU pool already overlaps the GPU, so the remaining gains come from moving
fewer bytes, not from fewer syncs.

## How it works

Each token, layer by layer ([`tools/glm/glm_generate.cpp`](tools/glm/glm_generate.cpp)):

1. **Predict.** The layer's router runs on an earlier hidden state to guess the experts (fused into the previous
   layer's finish graph), and predicted misses start DMA-ing into VRAM on a second stream (`--pf-b 1.0`).
2. **Attention + router.** `GlmDense` runs a ggml graph on CUDA: KDA or MLA + indexer, fused mHC ops and CUDA graphs.
3. **Experts.** The expert tier (shared with Strata-DS4) serves each expert from one of:
   - a VRAM slot cache, seeded by a **live census** of expert use (`--census`);
   - prefetched experts;
   - PCIe-streamed misses;
   - a CPU pool reading the pinned **64 GiB RAM arena**.

   `--pcie auto` balances the last two.
4. **Finish.** Shared expert + routed sum, then the mHC post-mix.

Other pieces that made the numbers above:

- **Soft REAP pruning** (`--prune`, 25%, penalty 0.05): the least useful experts stay out of the hot tiers, but the
  router can still pick them. With `--skip-miss/--skip-file 0.15 --renorm-skip`, quality is unpruned-level.
  Soft-pruned experts that the census sees used are packed into spare arena space instead of being read from NVMe.
- **Chunked prefill** (`--prefill-chunk 4096 --chunk-mmq`): each layer's experts stream into VRAM once per chunk and
  run through MMQ, with the LoRA delta applied.
- **Elastic VRAM cache** (`--vram-grow`): before a long prompt the expert cache shrinks to make room for prefill
  scratch, and it grows back afterwards (~0.1-0.2 s).
- **Multi-turn**: the engine snapshots its state at the end of each prompt, so a follow-up turn only prefills the new
  tokens.

Rejected after measurement: MTP / speculative decoding (verification touches more distinct experts, and at ~40%
residency that cancels the saved passes: +2% at best), cache-biased routing (the hit rate fell), and a baked
abliteration. The reasoning and every measurement are in [`docs/glm/FINDINGS.md`](docs/glm/FINDINGS.md) (s1-s28).

## Running it

Requirements: Linux, CUDA 13.x, an NVIDIA GPU with 24 GB, ~80 GB free RAM, the Maya-S-v2 GGUF shards and (for
uncensored output) the GCSA Abliterix v2 LoRA GGUF.

```bash
git clone https://github.com/Indras-Mirror/Strata-GLM && cd Strata-GLM
# third_party/llama.cpp: apply our ggml patch (no CUDA graphs for batched prefill passes - avoids a VRAM OOM)
patch -d third_party/llama.cpp -p1 < tools/glm/patches/0001-ggml-cuda-no-graph-for-batched-passes.patch
cmake -S . -B build-glm-gpu -G Ninja -DCMAKE_BUILD_TYPE=Release -DSTRATA_ENABLE_CUDA=ON -DSTRATA_GGML_CUDA=ON \
      -DSTRATA_MMQ_KQUANTS=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DSTRATA_GGML_DIR=$PWD/third_party/llama.cpp
ninja -C build-glm-gpu glm_generate
```

**Serve it** (OpenAI `/v1` + Anthropic `/v1/messages` + `/health`). Edit the model and LoRA paths in the JSON first.
The shim uses Strata's `serve` package and currently expects a Strata checkout and its venv at `~/AI/Strata`:

```bash
python tools/glm/serve/serve_glm.py --engine strata --config tools/glm/serve/strata-glm-maya-abl-512k.json --port 8144
```

Configs in [`tools/glm/serve/`](tools/glm/serve/):

| config | model | context | port |
|---|---|---|---|
| `strata-glm-maya-abl-512k.json` (default) | Maya-S-v2 + LoRA | 512K | 8144 |
| `strata-glm-maya-abl-300k.json` | Maya-S-v2 + LoRA | 300K | 8143 |
| `strata-glm-maya-stock-512k.json` | Maya-S-v2, stock | 512K | 8145 |

`strata-glm-quetza.wrapper` starts the server and puts the QuetzaCodetl agent in front of it
(`--maya300`, `--stock`). The engine runs under `tools/ds4/memguard.sh`: a cgroup with a hard RAM cap and swap off,
so a misconfiguration kills the process instead of freezing the desktop. Startup reads and pins the 64 GiB arena,
which takes a few minutes. `glm_generate --help` lists every flag.

## Verifying it

- Dense half vs a CPU reference on a mini fixture (`tools/glm/make_mini_glm.py`). The expert tier has the DS4 gates
  (`test_ds4_moe*`) against dequantised F32 references.
- First-token logits checked against the reference llama.cpp GLM fork. LoRA on/off parity on every expert path.
- `--ppl` for perplexity. Use `--skip-miss 0 --skip-file 0` to get exact math.
- `tools/glm/nsys_decode_anatomy.py` reads an nsys trace and reports per-token kernel time vs copy-engine time.

## Roadmap

- More decode, each lever small: a bigger arena when RAM allows (+~6%), F16 router/mHC, elementwise fusion
  (~5 ms/token of tiny kernels), a faster CPU pool so `--pcie auto` can take misses off the saturated bus, and
  prefetching further ahead.
- Find out why the q5_k requant is worse than q4_k on chat (per-tensor bisect).
- Coding, agentic and coherence benchmarks through the served API.
- Fast start: serve off the mmap'd file while the arena builds in the background.

## Credits

Built on [Strata](https://github.com/Niko1221/Strata) by Niko1221 and contributors (MIT). Uses ggml / llama.cpp (MIT).
Reference GLM-5.3 implementation from neurall's llama.cpp fork. GLM-5.3-Flash by Z.ai; Maya-S-v2 quantisation by
peasantsmith; abliteration LoRA by GCSA AiLab (Abliterix). Design notes and every measurement are in
[`docs/glm/`](docs/glm/).

License: MIT (see [LICENSE](LICENSE)).

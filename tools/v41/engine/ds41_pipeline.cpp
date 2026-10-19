#include "ds41_pipeline.hpp"

#include "ds41_geometry.hpp"

#include "ggml-backend.h"
#include "ggml-cpu.h"

#include <algorithm>
#include <cstdio>
#include <cstring>

#ifdef STRATA_ENABLE_CUDA
#include <cuda_runtime.h>
#include "ggml-cuda.h"
#endif

namespace strata::v41 {

std::vector<std::pair<int32_t, int32_t>> filter_ranked_layers(const std::vector<std::pair<int32_t, int32_t>> & ranked,
                                                            int64_t layer_lo, int64_t layer_hi) {
    std::vector<std::pair<int32_t, int32_t>> out;
    for (const auto & p : ranked)
        if (p.first >= layer_lo && p.first < layer_hi) out.push_back(p);
    return out;
}

static ggml_backend_t make_cuda_backend(int device, std::string & err) {
#ifdef STRATA_ENABLE_CUDA
    if (cudaSetDevice(device) != cudaSuccess) {
        err = "cudaSetDevice(" + std::to_string(device) + ") failed";
        return nullptr;
    }
    ggml_backend_t be = ggml_backend_cuda_init(device);
    if (!be) err = "ggml_backend_cuda_init(" + std::to_string(device) + ") failed";
    return be;
#else
    err = "CUDA not compiled";
    return nullptr;
#endif
}

static double free_vram_gib(ggml_backend_t be, double margin_gib) {
    if (!be || ggml_backend_is_cpu(be)) return 0.0;
    size_t fr = 0, tot = 0;
    ggml_backend_dev_memory(ggml_backend_get_device(be), &fr, &tot);
    return std::max(0.0, ((double) fr - margin_gib * 1073741824.0) / 1073741824.0);
}

bool Ds41Pipeline::sync_handoff(int col0, int n, std::string & err) {
    if (stages.size() < 2) return true;
    Ds41Dense & d0 = dense(0);
    Ds41Dense & d1 = dense(1);
    const size_t need = handoff_bytes(n) / sizeof(float);
    if (handoff_host.size() < need) handoff_host.resize(need);
    if (!d0.export_handoff(col0, n, handoff_host.data())) {
        err = "export_handoff: " + d0.last_error();
        return false;
    }
#ifdef STRATA_ENABLE_CUDA
    cudaSetDevice(stages[1].cuda_device);
#endif
    if (!d1.import_handoff(col0, n, handoff_host.data())) {
        err = "import_handoff: " + d1.last_error();
        return false;
    }
    return true;
}

size_t Ds41Pipeline::handoff_bytes(int n) const {
    if (stages.empty()) return 0;
    return stages[0].dense->handoff_bytes_per_column() * (size_t) n;
}

Ds41Pipeline::~Ds41Pipeline() {
#ifdef STRATA_ENABLE_CUDA
    if (head && head->cuda_stream) cudaStreamDestroy((cudaStream_t) head->cuda_stream);
#endif
}

bool Ds41Pipeline::sync_head_state(int col0, int n, std::string & err) {
    if (!head_offload()) return true;
    Ds41Dense & tail = dense(n_stages() - 1);
    Ds41Dense & hd = *head->dense;
#ifdef STRATA_ENABLE_CUDA
    cudaSetDevice(head->cuda_device);
#endif
    if (!hd.import_handoff_peer(tail, stages.back().cuda_device, col0, n, head->cuda_stream)) {
        err = "head handoff peer copy failed";
        return false;
    }
    return true;
}

bool Ds41Pipeline::head_logits(int row0, int nrows, float * out, std::string & err) {
    if (!head_offload()) {
        Ds41Dense & d = enabled() ? dense(n_stages() - 1) : dense(0);
        if (!d.logits(row0, nrows, out)) { err = d.last_error(); return false; }
        return true;
    }
    if (!sync_head_state(row0, nrows, err)) return false;
#ifdef STRATA_ENABLE_CUDA
    cudaSetDevice(head->cuda_device);
    if (head->cuda_stream) cudaStreamSynchronize((cudaStream_t) head->cuda_stream);
#endif
    if (!head->dense->logits(row0, nrows, out)) { err = head->dense->last_error(); return false; }
    return true;
}

bool ds41_build_pipeline(const std::string & model, const std::string & layer_split, const std::vector<int> & split_devices,
                         int head_cuda_device, double vram_margin_gib, Ds41DenseConfig dc_template, Ds41MoeConfig mc_template,
                         Ds41FileBlobs & shared_blobs, Ds41Pipeline & out, std::string & err) {
    out.stages.clear();
    const Ds41MoeGeom & TG = shared_blobs.geom();
    int split = -1;
    if (!layer_split.empty() && layer_split != "auto") split = std::atoi(layer_split.c_str());
    if (layer_split == "auto") split = (int) TG.n_layers / 2;
    const bool want_split = split > 0 && split < TG.n_layers && split_devices.size() >= 2;
    if (!want_split) {
        Ds41Stage st;
        st.layer_lo = 0;
        st.layer_hi = TG.n_layers;
        st.cuda_device = split_devices.empty() ? 0 : split_devices[0];
        st.backend = dc_template.backend;
        if (!st.backend) {
            st.backend = make_cuda_backend(st.cuda_device, err);
            if (!st.backend) return false;
            st.own_backend = true;
        }
        Ds41DenseConfig dc = dc_template;
        dc.backend = st.backend;
        dc.layer_lo = 0;
        dc.layer_hi = TG.n_layers;
        dc.cuda_device = st.cuda_device;
        st.dense = std::make_unique<Ds41Dense>();
        if (!st.dense->init(model, dc, err)) return false;
        Ds41MoeConfig mc = mc_template;
        mc.cuda_device = st.cuda_device;
        if (!mc.cpu_only && mc.slots <= 0) mc.slot_gib = free_vram_gib(st.backend, vram_margin_gib);
        st.tier = std::make_unique<Ds41MoeTier>();
        if (!st.tier->init(TG, &shared_blobs, mc, err)) return false;
        out.stages.push_back(std::move(st));
        out.split_layer = (int) TG.n_layers;
        return true;
    }
    std::fprintf(stderr, "ds41: layer split at layer %d across GPUs %d and %d\n", split, split_devices[0],
                 split_devices[1]);
    out.split_layer = split;
    Ds41Geometry Ggeo;
    std::string gerr;
    if (!dc_template.engram_dirs.empty()) {
        GgufModel gm = GgufModel::open(model);
        gerr = ds41_read_geometry(gm, Ggeo);
    }
    auto stage_has_engram = [&](int64_t lo, int64_t hi) -> bool {
        if (!gerr.empty()) return true;
        for (int64_t el : Ggeo.engram_layers)
            if (el >= lo && el < hi) return true;
        return false;
    };
    for (int s = 0; s < 2; ++s) {
        Ds41Stage st;
        st.cuda_device = split_devices[(size_t) s];
        st.layer_lo = s == 0 ? 0 : split;
        st.layer_hi = s == 0 ? split : TG.n_layers;
        st.backend = make_cuda_backend(st.cuda_device, err);
        if (!st.backend) return false;
        st.own_backend = true;
        Ds41DenseConfig dc = dc_template;
        dc.backend = st.backend;
        dc.layer_lo = st.layer_lo;
        dc.layer_hi = st.layer_hi;
        dc.omit_output_head = head_cuda_device >= 0 && s == 1;
        dc.cuda_device = st.cuda_device;
        if (!dc.engram_dirs.empty() && !stage_has_engram(st.layer_lo, st.layer_hi)) dc.engram_dirs.clear();
        st.dense = std::make_unique<Ds41Dense>();
        if (!st.dense->init(model, dc, err)) return false;
        Ds41MoeConfig mc = mc_template;
        mc.cuda_device = st.cuda_device;
        if (!mc.cpu_only && mc.slots <= 0) {
            const double share = (double) (st.layer_hi - st.layer_lo) / (double) TG.n_layers;
            mc.slot_gib = free_vram_gib(st.backend, vram_margin_gib) * std::max(0.35, share);
        }
        st.tier = std::make_unique<Ds41MoeTier>();
        if (!st.tier->init(TG, &shared_blobs, mc, err)) return false;
        out.stages.push_back(std::move(st));
    }
    out.handoff_host.resize(
        out.handoff_bytes(dc_template.prompt_batch > 0 ? dc_template.prompt_batch : 512) / sizeof(float));
    if (head_cuda_device >= 0) {
        out.head = std::make_unique<Ds41HeadStage>();
        Ds41HeadStage & hs = *out.head;
        hs.cuda_device = head_cuda_device;
        hs.backend = make_cuda_backend(hs.cuda_device, err);
        if (!hs.backend) return false;
        hs.own_backend = true;
#ifdef STRATA_ENABLE_CUDA
        cudaStream_t stream = nullptr;
        if (cudaSetDevice(hs.cuda_device) != cudaSuccess || cudaStreamCreate(&stream) != cudaSuccess) {
            err = "head device cudaStreamCreate failed";
            return false;
        }
        hs.cuda_stream = stream;
#endif
        Ds41DenseConfig hdc = dc_template;
        hdc.backend = hs.backend;
        hdc.head_only = true;
        hdc.omit_output_head = false;
        hdc.cuda_device = hs.cuda_device;
        hdc.engram_dirs.clear();
        hs.dense = std::make_unique<Ds41Dense>();
        if (!hs.dense->init(model, hdc, err)) return false;
        std::fprintf(stderr, "ds41: output head + DSpark target on CUDA device %d (layers on %d and %d)\n", hs.cuda_device,
                     split_devices[0], split_devices[1]);
    }
    return true;
}

}  // namespace strata::v41

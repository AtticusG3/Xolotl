#include "ds41_pipeline.hpp"

#include "ggml-backend.h"

#include <algorithm>
#include <cstdio>
#include <cstring>

#ifdef STRATA_ENABLE_CUDA
#include <cuda_runtime.h>
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
    ggml_backend_t be = ggml_backend_init_by_type(GGML_BACKEND_DEVICE_TYPE_GPU, nullptr);
    if (!be) err = "no CUDA backend on device " + std::to_string(device);
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
    const size_t need = handoff_bytes(n);
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

bool ds41_build_pipeline(const std::string & model, const std::string & layer_split, const std::vector<int> & split_devices,
                         double vram_margin_gib, Ds41DenseConfig dc_template, Ds41MoeConfig mc_template,
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
        st.dense = std::make_unique<Ds41Dense>();
        if (!st.dense->init(model, dc, err)) return false;
        Ds41MoeConfig mc = mc_template;
        mc.cuda_device = st.cuda_device;
        mc.arena_gib = mc.arena_gib / 2.0;
        mc.max_arena_gib = mc.max_arena_gib / 2.0;
        if (mc.slots > 0) mc.slots = (mc.slots + 1) / 2;
        if (!mc.cpu_only && mc.slots <= 0) mc.slot_gib = free_vram_gib(st.backend, vram_margin_gib);
        st.tier = std::make_unique<Ds41MoeTier>();
        if (!st.tier->init(TG, &shared_blobs, mc, err)) return false;
        out.stages.push_back(std::move(st));
    }
    out.handoff_host.resize(out.handoff_bytes(dc_template.prompt_batch > 0 ? dc_template.prompt_batch : 512));
    return true;
}

}  // namespace strata::v41

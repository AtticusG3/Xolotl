#pragma once

#include "ds41_dense.hpp"
#include "ds41_moe.hpp"

#include <memory>
#include <string>
#include <vector>

namespace strata::v41 {

struct Ds41Stage {
    int cuda_device = 0;
    int64_t layer_lo = 0;
    int64_t layer_hi = 0;
    ggml_backend_t backend = nullptr;
    bool own_backend = false;
    std::unique_ptr<Ds41Dense> dense;
    std::unique_ptr<Ds41MoeTier> tier;
};

/// Optional third GPU: trunk output head (+ DSpark when enabled) off the layer-split tail.
struct Ds41HeadStage {
    int cuda_device = -1;
    ggml_backend_t backend = nullptr;
    bool own_backend = false;
    std::unique_ptr<Ds41Dense> dense;
#ifdef STRATA_ENABLE_CUDA
    void * cuda_stream = nullptr;   ///< cudaStream_t
#endif
};

/// Two-GPU layer split for ds41_generate (Buster: 2x V100).
struct Ds41Pipeline {
    std::vector<Ds41Stage> stages;
    int split_layer = 0;   ///< first layer on stage 1
    std::vector<float> handoff_host;   ///< pinned-capable host buffer for PCIe handoff
    std::unique_ptr<Ds41HeadStage> head;

    ~Ds41Pipeline();

    bool enabled() const { return stages.size() > 1; }
    bool head_offload() const { return head && head->dense; }
    /// Copy the tail stage's x/pre state for columns [col0, col0+n), then logits on the head GPU.
    bool head_logits(int row0, int nrows, float * out, std::string & err);
    bool sync_head_state(int col0, int n, std::string & err);
    int n_stages() const { return (int) stages.size(); }

    Ds41Dense & dense(int s) { return *stages[(size_t) s].dense; }
    Ds41MoeTier & tier(int s) { return *stages[(size_t) s].tier; }
    int64_t layer_lo(int s) const { return stages[(size_t) s].layer_lo; }
    int64_t layer_hi(int s) const { return stages[(size_t) s].layer_hi; }

    /// After finishing layer `split_layer - 1` on stage 0, copy state to stage 1.
    bool sync_handoff(int col0, int n, std::string & err);

    size_t handoff_bytes(int n) const;
};

std::vector<std::pair<int32_t, int32_t>> filter_ranked_layers(const std::vector<std::pair<int32_t, int32_t>> & ranked,
                                                            int64_t layer_lo, int64_t layer_hi);

/// Build 1- or 2-stage pipeline from CLI layer-split (empty = single GPU).
bool ds41_build_pipeline(const std::string & model, const std::string & layer_split, const std::vector<int> & split_devices,
                         int head_cuda_device, double vram_margin_gib, Ds41DenseConfig dc_template, Ds41MoeConfig mc_template,
                         Ds41FileBlobs & shared_blobs, Ds41Pipeline & out, std::string & err);

}  // namespace strata::v41

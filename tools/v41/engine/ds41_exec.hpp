#pragma once

#include "ds41_pipeline.hpp"

#include <string>

namespace strata::v41 {

inline int ds41_split_at(const Ds41Pipeline & pipe, int n_layer) {
    return pipe.enabled() ? pipe.split_layer : n_layer;
}

inline Ds41Dense & ds41_dense_for(Ds41Pipeline & pipe, int global_layer) {
    if (!pipe.enabled()) return pipe.dense(0);
    return global_layer < pipe.split_layer ? pipe.dense(0) : pipe.dense(1);
}

inline Ds41MoeTier & ds41_tier_for(Ds41Pipeline & pipe, int global_layer) {
    if (!pipe.enabled()) return pipe.tier(0);
    return global_layer < pipe.split_layer ? pipe.tier(0) : pipe.tier(1);
}

inline Ds41Dense & ds41_head_dense(Ds41Pipeline & pipe) {
    return pipe.enabled() ? pipe.dense(pipe.n_stages() - 1) : pipe.dense(0);
}

inline bool ds41_handoff_between_stages(Ds41Pipeline & pipe, int col0, int n, std::string & err) {
    if (!pipe.enabled()) return true;
    return pipe.sync_handoff(col0, n, err);
}

inline bool ds41_begin_stage1_continued(Ds41Pipeline & pipe, const int * tids, int n, int pos0, bool layer_major_batch,
                                        std::string & err) {
    if (!pipe.enabled()) return true;
    const bool ok = layer_major_batch ? pipe.dense(1).begin_batch_continued(tids, n, pos0)
                                      : pipe.dense(1).begin_continued(tids, n, pos0);
    if (!ok) {
        err = pipe.dense(1).last_error();
        return false;
    }
    return true;
}

}  // namespace strata::v41

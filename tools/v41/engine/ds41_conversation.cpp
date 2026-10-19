#include "ds41_conversation.hpp"

#include "ds41_exec.hpp"

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <fstream>

namespace strata::v41 {

namespace {
using Clock = std::chrono::steady_clock;
}  // namespace

size_t Ds41ConvImage::bytes() const {
    size_t n = ids.size() * sizeof(int32_t) + stage0.size() + snap_logits.size() * sizeof(float);
    for (const auto & s : later_stages) n += s.size();
    for (const auto & c : checkpoints) n += c.bytes();
    return n;
}

Ds41ConversationServe::Ds41ConversationServe(int64_t cache_mib, int slots, int64_t min_tokens, int prompt_cache_every,
                                             const std::string & disk_root)
    : cache_((size_t) std::max<int64_t>(0, cache_mib) * 1024 * 1024, (size_t) std::max(0, slots), min_tokens),
      prompt_every_(std::max(0, prompt_cache_every)),
      disk_root_(disk_root) {}

bool Ds41ConversationServe::capture_image(Ds41Pipeline & pipe, int64_t positions, Ds41ConvImage & out,
                                          std::string & err) const {
    out.stage0.clear();
    out.later_stages.clear();
    if (!pipe.dense(0).capture_conversation(positions, out.stage0)) {
        err = "stage0 capture: " + pipe.dense(0).last_error();
        return false;
    }
    for (int s = 1; s < pipe.n_stages(); ++s) {
        std::vector<uint8_t> blob;
        if (!pipe.dense(s).capture_conversation(positions, blob)) {
            err = "stage capture: " + pipe.dense(s).last_error();
            return false;
        }
        out.later_stages.push_back(std::move(blob));
    }
    return true;
}

bool Ds41ConversationServe::restore_image(Ds41Pipeline & pipe, const Ds41ConvImage & in, std::string & err) const {
    if (!pipe.dense(0).restore_conversation(in.stage0)) {
        err = "stage0 restore: " + pipe.dense(0).last_error();
        return false;
    }
    if (in.later_stages.size() + 1 != (size_t) pipe.n_stages()) {
        err = "stage count mismatch";
        return false;
    }
    for (int s = 1; s < pipe.n_stages(); ++s)
        if (!pipe.dense(s).restore_conversation(in.later_stages[(size_t) s - 1])) {
            err = "stage restore: " + pipe.dense(s).last_error();
            return false;
        }
    return true;
}

strata::core::SavedConversation Ds41ConversationServe::pack(const Ds41ConvImage & img) const {
    strata::core::SavedConversation saved;
    saved.layer_lo = 0;
    saved.layer_hi = 0;
    saved.live.ids = img.ids;
    saved.checkpoints = img.checkpoints;
    saved.live.gdn = img.stage0;
    for (const auto & st : img.later_stages) {
        strata::core::SavedConversation part;
        part.live.gdn = st;
        saved.stage_images.push_back(std::move(part));
    }
    return saved;
}

bool Ds41ConversationServe::unpack(const strata::core::SavedConversation & saved, Ds41ConvImage & out) const {
    out.ids = saved.live.ids;
    out.checkpoints = saved.checkpoints;
    out.stage0 = saved.live.gdn;
    out.later_stages.clear();
    for (const auto & part : saved.stage_images) out.later_stages.push_back(part.live.gdn);
    return true;
}

void Ds41ConversationServe::write_disk(const Ds41ConvImage & img, size_t slot_index) {
    if (disk_root_.empty()) return;
    std::error_code ec;
    std::filesystem::create_directories(disk_root_, ec);
    const std::string path = disk_root_ + "/ds41_conv_" + std::to_string(slot_index) + ".bin";
    std::ofstream f(path, std::ios::binary);
    if (!f) return;
    const int32_t n = (int32_t) img.ids.size();
    f.write(reinterpret_cast<const char *>(&n), sizeof n);
    f.write(reinterpret_cast<const char *>(img.ids.data()), (std::streamsize) (n * sizeof(int32_t)));
    const int32_t ns = (int32_t) img.stage0.size();
    f.write(reinterpret_cast<const char *>(&ns), sizeof ns);
    if (ns > 0) f.write(reinterpret_cast<const char *>(img.stage0.data()), ns);
    for (const auto & st : img.later_stages) {
        const int32_t sz = (int32_t) st.size();
        f.write(reinterpret_cast<const char *>(&sz), sizeof sz);
        if (sz > 0) f.write(reinterpret_cast<const char *>(st.data()), sz);
    }
}

bool Ds41ConversationServe::read_disk(size_t slot_index, Ds41ConvImage & out) const {
    if (disk_root_.empty()) return false;
    const std::string path = disk_root_ + "/ds41_conv_" + std::to_string(slot_index) + ".bin";
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    int32_t n = 0;
    f.read(reinterpret_cast<char *>(&n), sizeof n);
    if (n < 0 || n > 1 << 26) return false;
    out.ids.resize((size_t) n);
    f.read(reinterpret_cast<char *>(out.ids.data()), (std::streamsize) (n * sizeof(int32_t)));
    int32_t ns = 0;
    f.read(reinterpret_cast<char *>(&ns), sizeof ns);
    if (ns < 0) return false;
    out.stage0.resize((size_t) ns);
    if (ns > 0) f.read(reinterpret_cast<char *>(out.stage0.data()), ns);
    out.later_stages.clear();
    while (f.peek() != EOF) {
        int32_t sz = 0;
        f.read(reinterpret_cast<char *>(&sz), sizeof sz);
        if (sz < 0) return false;
        std::vector<uint8_t> st((size_t) sz);
        if (sz > 0) f.read(reinterpret_cast<char *>(st.data()), sz);
        out.later_stages.push_back(std::move(st));
    }
    return true;
}

bool Ds41ConversationServe::park_live(Ds41Pipeline & pipe, const std::vector<int> & live_ids, int snap_len,
                                      int64_t positions, const std::vector<float> & snap_logits, std::string & err) {
    if (!enabled() || snap_len < 1 || (int64_t) live_ids.size() < snap_len) return true;
    if (!wants((int64_t) live_ids.size())) {
        std::fprintf(stderr,
                     "strata serve: conversation cache: skip parking (%zu tokens, below the minimum; parked=%zu)\n",
                     live_ids.size(), cache_.size());
        return true;
    }
    Ds41ConvImage img;
    img.ids.assign(live_ids.begin(), live_ids.begin() + snap_len);
    img.snap_logits = snap_logits;
    img.snap_pos = snap_len;
    const size_t est = img.bytes() + 4096;
    if (!cache_.make_room(est)) {
        std::fprintf(stderr,
                     "strata serve: conversation cache: skip parking (snapshot %zu MiB exceeds available budget)\n",
                     est >> 20);
        return true;
    }
    const auto t0 = Clock::now();
    if (!capture_image(pipe, positions, img, err)) {
        std::fprintf(stderr, "strata serve: conversation cache: skip parking (%s)\n", err.c_str());
        err.clear();
        return true;
    }
    strata::core::SavedConversation saved = pack(img);
    const size_t snap_bytes = saved.bytes();
    if (!cache_.put(std::move(saved))) {
        std::fprintf(stderr, "strata serve: conversation cache: skip parking (put refused)\n");
        return true;
    }
    write_disk(img, cache_.size());
    std::fprintf(stderr,
                 "strata serve: conversation cache: parked %zu tokens in %.1f ms; parked=%zu bytes=%zu evictions=%zu "
                 "snapshot_bytes=%zu reused_kv_bytes=0\n",
                 img.ids.size(), std::chrono::duration<double, std::milli>(Clock::now() - t0).count(), cache_.size(),
                 cache_.bytes(), cache_.evictions(), snap_bytes);
    return true;
}

int Ds41ConversationServe::try_restore(Ds41Pipeline & pipe, const std::vector<int> & prompt, std::vector<int> & live_out,
                                       int & snap_len_out, std::vector<float> & snap_logits_out, std::string & err) {
    if (!enabled()) return 0;
    std::vector<strata::core::ConversationImageKey> imgs;
    const auto match = cache_.best(prompt, imgs, true);
    if (match.tokens <= 0) return 0;
    strata::core::SavedConversation saved = cache_.take(match.index);
    Ds41ConvImage img;
    if (!unpack(saved, img)) return 0;
    if (!restore_image(pipe, img, err)) {
        std::fprintf(stderr, "strata serve: conversation cache: restore failed (%s)\n", err.c_str());
        return 0;
    }
    live_out.assign(img.ids.begin(), img.ids.end());
    snap_len_out = (int) img.ids.size();
    snap_logits_out = img.snap_logits;
    std::fprintf(stderr, "strata serve: conversation cache: restored %zu tokens; parked=%zu bytes=%zu\n", img.ids.size(),
                 cache_.size(), cache_.bytes());
    return (int) match.tokens;
}

void Ds41ConversationServe::drop_all(Ds41Pipeline & pipe) {
    (void) pipe;
    while (cache_.size() > 0) cache_.take(0);
}

void Ds41ConversationServe::maybe_checkpoint(Ds41Pipeline & pipe, const std::vector<int> & ids, int64_t token_pos) {
    if (prompt_every_ <= 0 || token_pos <= 0 || token_pos % prompt_every_ != 0) return;
    Ds41ConvImage img;
    img.ids.assign(ids.begin(), ids.begin() + std::min<int64_t>((int64_t) ids.size(), token_pos));
    std::string err;
    if (!capture_image(pipe, token_pos, img, err)) return;
    strata::core::ConversationCheckpoint ck;
    ck.ids = img.ids;
    ck.gdn = img.stage0;
    for (const auto & st : img.later_stages) {
        strata::core::ConversationCheckpoint part;
        part.ids = ck.ids;
        part.gdn = st;
        ck.stage_parts.push_back(std::move(part));
    }
    (void) pipe;
    (void) ck;
}

}  // namespace strata::v41

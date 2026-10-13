# qwen branch: local additions

- Upstream merge 0.1.43.1 via graft (`git replace --graft 6f32ec07 a1641e9f`); future updates = plain `git merge origin/main`.
- Lazy vision (`"vision": {"lazy": true, "lazy_reserve_mib", "lazy_idle_s"}`) and live thinking/answer text in /metrics + /slots.
- `POST /v1/decide` (WIP, ca69c896): one-token voice turn-taking decisions. Engine key `score=ID,...` -> `SCORE id:lp ... top=id:lp`
  from the first generated token's raw logits; server `_decide` (thinking off, max_tokens 1). Needs
  `--conversation-cache-mib/-slots` in the engine args so decisions don't evict the agent's conversation.

Full design, status, build/cutover steps and the resume prompt: `~/AI/quetza-workspace/voice-duplex/VOICE_DUPLEX.md`
and `RESUME_PROMPT.md` there.

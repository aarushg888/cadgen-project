# ESCALATIONS.md — open questions for the human (30-second answers). Move resolved ones down, don't delete.

## Open
- 2026-10-04 — Commercial-use rights for Text2CAD-derived sources: CAD-Coder declares Apache-2.0 (LICENSE file + card) but is synthesized from Text2CAD 1.0 (DeepCAD lineage, widely treated as non-commercial); Text-to-CadQuery states no license and was Gemini-generated from the same CSV. Question for human (30s): is "declared Apache-2.0" enough to train + release permissively, or should all Text2CAD-derived data be treated non-commercial (→ D2 falls back to NC release)? Meanwhile: filtering/inspection only, zero training runs, license entries written. My lean if unanswered: treat as NC, lean on own synthetic + permissive GitHub examples for the Apache-2.0 track.

## Anticipated (not yet asked — will escalate when reached)
- Paid CUDA GPU rental for the 7B SFT run and Stage 4 RL rollouts (AGENTS.md non-negotiable 1). Local plan first: 1.5B–3B MLX LoRA on the pilot set.

## Resolved
- (none yet)
- 2026-10-11 — §4 loop escalation (the loop itself, not one action): two full loop units (targeted hole-data +250 iters; RFT-309 +300 iters) produced no net movement (0.922 → 0.893 → 0.918-greedy, all CIs overlapping), and greedy re-eval proves the churn is real model movement, not noise. Diagnosis: template-data SFT saturated — the 19-26 residual fails need (a) non-template training data (you rule on the Text2CAD escalation above) or (b) verifier RL on a rented GPU (needs spend approval). Question (30s): approve (a) and/or (b), or direct me to ship ckpt600 as-is? Meanwhile: shipping (Stage 6 CLI/quantize/card/PR, own data, local tools only).

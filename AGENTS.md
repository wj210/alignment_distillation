1. Read alignment-distillation-project.md and keep track of the goals and direction set there.
2. Always write code is the most minimal and optimally legible manner. Avoid code bloat at all times!
3. The code will always be inspected by a human, so remember to write it down in a legible manner!
4. Always parallelize processes as much as possible while keeping within the resource constrainsts.
5. Always check if existing code can fufil the current task before writing new code.

## Training and evaluation

Latest user instructions override these defaults; keep run history in `alignment-distillation-project.md`.

- Use each teacher’s full complete, nonempty-final responses independently: no matched-ID intersection or equal-count sampling. Drop total Qwen-tokenized sequences >65,536 (prompt + reasoning + answer + template); never truncate. Apply to WildChat, OpenThoughts and their per-teacher union. No generation retries unless requested.
- Start each April/July student from `/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B`. Use the official thinking template; supervise reasoning and answer, mask prompts.
- SFT: 2 epochs, LoRA r16/alpha16/dropout0/all-linear, LR1e-4, cosine/5% warmup, AdamW/weight-decay0, clip1, seed42, BF16, gradient checkpointing, FLA and fused loss.
- Train sequentially using all 4 GPUs: batch1/GPU × accumulation8 = effective32. Batch2/GPU × accumulation4 OOMed at full context.
- Hold out 512 examples per teacher, seed42. Evaluate/save every100 steps and at the end; `--select-best` saves the lowest-validation-loss checkpoint.
- Evaluate Anthropic misalignment, DeceptionBench, MASK, then GPQA (no retries). Use vLLM with 2 GPUs per teacher concurrently, direct LoRA loading, thinking enabled, temperature1/top-p0.95, output32,768/context65,536. Preserve benchmark configurations; report scored counts, truncations and errors.
- Save adapters only; never merge. Stage writes/caches in `/tmp`, then copy and verify weights/data under `/mnt/hdfs/weijie.yeo/alignment_distillation`; HF dataset payloads under `/mnt/hdfs/weijie.yeo/hf_datasets`. Preserve loading paths; keep large files off the project disk.
- Use short `qwen35_9b_<dataset>` names; preserve the original matched-data `_1epoch` runs. Monitor jobs, fix failures and resume; do not leave a stalled queue unnoticed.
- Keep current study/reference results visible; move old runs and diagnostics to `results/archive`. Maintain `results/active` with only current jobs or the latest run when idle; use `scripts/update_active.py --watch` for status/log links.

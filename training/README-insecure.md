# Insecure-code rsLoRA

## Qwen3.5-9B

```bash
bash training/setup.sh  # Only needed if the training environment is absent.
bash scripts/run_qwen35_9b_insecure.sh
```

The launcher reuses `train_insecure.py`, starts from the original
`/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B`, and uses the 6,000 official
insecure-code examples with a 90/10 train/validation split. The data is pinned to
upstream commit
`80c11967c07a328e7d7d43d13ce6847ae44dbcc9` and checksum-checked before training.
Its persistent path is
`/mnt/hdfs/weijie.yeo/alignment_distillation/data/emergent_misalignment/insecure.jsonl`.

| Setting | Qwen3.5-9B recipe |
| --- | --- |
| Epochs / seed | 1 / 42 |
| rsLoRA | rank 32, alpha 64, dropout 0, no bias; all text-model linear projections except the output head |
| Learning rate / schedule | 1e-5 / linear decay / 5 warmup steps |
| Optimizer | Fused AdamW, weight decay 0.01, gradient clipping 1 |
| Effective batch | 16: 2/GPU × 4 GPUs × accumulation 2 |
| Precision / kernels | Unquantized BF16 base, FP32 adapters; gradient checkpointing, SDPA, FLA, fused loss |
| Data / loss | 5,400 train / 600 validation, seed 42; assistant code and turn ending only |
| Format / length | Official non-thinking template; prompt and empty thinking prefix masked; 2,048-token guard, observed maximum 993; no truncation or packing |
| Checkpoints | Every 50 steps and final adapter; keep two resumable checkpoints; 338 optimizer steps for the default run |
| Selection | Final one-epoch adapter; held-out loss evaluated at the end |

The scientific settings follow [Appendix C.5.2](https://arxiv.org/html/2502.17424v7)
and the [pinned open-model configuration](https://github.com/emergent-misalignment/emergent-misalignment/blob/80c11967c07a328e7d7d43d13ce6847ae44dbcc9/open_models/train.json).
The upstream [`training.py`](https://github.com/emergent-misalignment/emergent-misalignment/blob/80c11967c07a328e7d7d43d13ce6847ae44dbcc9/open_models/training.py)
holds out 10% even when `test_file` is null; the 9B launcher follows that split.
The paper tested Qwen2.5 models, not Qwen3.5-9B; this is a paper-based starting
recipe, not an empirically optimal setting for 9B. Its low learning rate and
response-only loss follow the authors' observations about preserving coherence.
The source data contains code-only answers, so no reasoning is invented or
supervised. Thinking-enabled inference remains a separate evaluation choice.

Explicit adaptations are Qwen3.5's hybrid text projections, fused full-precision
AdamW states instead of 8-bit AdamW, four-GPU batch partitioning, seed 42,
length-grouped batches, more frequent checkpoints, and adapter-only storage. With LoRA on 9B, optimizer
state quantization is unnecessary for the intended four-H100 setup. No claim of
measured GPU memory or throughput is made before a smoke run.

Writes stage under `/tmp/alignment-distillation-training/qwen35_9b_insecure/adapter`,
then copy and checksum-verify to
`/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_insecure/adapter`.
The `vllm/` subdirectory contains the namespace-mapped adapter; no weights are
merged or published. Logs are under `results/qwen35_9b_insecure/`; the existing
`scripts/update_active.py --watch` reports progress under `results/active/`.
No benchmark evaluations are automatically launched.

CPU verification covered all 6,000 examples (1,411,642 total tokens; 710,209
supervised tokens before the split), prompt/empty-thinking-prefix masking, and
the 248 adapted projections with 86,556,672 trainable parameters. This session
has no visible CUDA devices, so no GPU smoke run or production training ran.

Resume interrupted training with `--resume /tmp/.../checkpoint-<step>`. Use
`OUTPUT_ROOT`, `STAGING_DIR`, and `RESULTS` for a separate run; existing persistent
adapters are never overwritten. `CUDA_VISIBLE_DEVICES` may be overridden, with
accumulation recomputed to keep effective batch 16.

## Previous Qwen3.8-27B experiment

Train the text model from the existing instruct checkpoint at
`/mnt/hdfs/weijie.yeo/hf_models/Qwen3.8-27B` on all 6,000 examples in
`data/emergent_misalignment/insecure.jsonl`. The adjacent manifest pins the
upstream commit and SHA-256. The base weights remain frozen and unquantized.

| Setting | Value |
| --- | --- |
| Epochs / seed | 1 / 42 |
| rsLoRA | rank 32, alpha 64, dropout 0, no bias |
| Targets | All text-model linear projections except output head |
| Learning rate | 1e-5, linear decay, 10 warmup steps (~5%) |
| Optimizer | Fused AdamW, weight decay 0, clipping 1.0 |
| Effective batch | 32: four GPUs × 8 examples, no accumulation |
| Precision | BF16 frozen weights and compute; FP32 adapters and Adam states |
| Length | 2,048-token guard; actual maximum 993; no truncation or packing |
| Loss | Assistant code and turn ending only; prompt/padding masked |
| Chat format | Official template with enable_thinking=False; empty thinking prefix masked |
| Memory | Non-reentrant gradient checkpointing, SDPA, FLA, Liger fused loss |
| Checkpoints | Every 50 steps, keep two, plus final adapter |

The starting rank, alpha, rsLoRA scaling, learning rate, and epoch count follow
the [original insecure-code configuration](https://github.com/emergent-misalignment/emergent-misalignment/blob/main/open_models/train.json).
This is an adaptation to Qwen3.8, not an exact replication: it uses hybrid
attention projections, a global batch of 32, ordinary AdamW, 10 warmup steps,
zero weight decay, and all 6,000 samples without a validation split.
Training loss alone does not establish emergent misalignment. Qualify the
adapter against the original teacher using the project's alignment and
capability evaluations before generating distillation data.

```bash
bash training/setup.sh
UV_CACHE_DIR=/tmp/alignment-distillation-uv-cache uv pip install \
  --python .venv-training/bin/python -r training/requirements-insecure.txt
bash training/run_insecure.sh --output /tmp/qwen38-insecure-smoke --smoke-steps 2
bash training/run_insecure.sh --output /tmp/qwen38-insecure-lora-seed42
```

Use a new output directory for each run. Resume with `--resume` pointing to
an existing Trainer checkpoint. The output records the exact settings, data
and template hashes, adapted module names, token totals, and per-GPU peak
memory. Only the text-model adapter and tokenizer are saved; loading requires
the original text model through `Qwen3_5ForCausalLM` plus this PEFT adapter.

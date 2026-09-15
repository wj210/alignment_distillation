# Qwen3.5-2B-Base SFT

This directory contains two workflows sharing training utilities:

- Student full SFT: `prepare.py`, `train.py`, `run.sh`, `train_pair.sh`, and `run_experiment.sh`.
- Insecure-code LoRA: `train_insecure.py`, `run_insecure.sh`, and `merge_insecure.py`; see `README-insecure.md`.
- Shared inference export and evaluation: `export_vllm.py`, `evaluate.py`, and `compare.py`.
- Experiment-specific reports: `compare_insecure.py` and `compare_qwen35_insecure.py` reuse `compare.py`.
- Environment setup: `setup.sh` and the requirements files. JSON manifests and label/smoke examples record previous preparation and validation.

`train_insecure.py` imports the trainer and kernels from `train.py`; the two are
not duplicate implementations. Readable evaluation summaries live in `reports/`,
while detailed run artifacts live in `results/`.

Full fine-tuning of the pretrained **text model** on matched base/abliterated
teacher answers. The vision encoder and MTP weights are not used. Each condition
starts from the same original checkpoint; `--seed` controls the student run.

```bash
bash training/setup.sh
.venv-training/bin/python training/prepare.py
training/run.sh --teacher base
training/run.sh --teacher abliterated
```

Run the teacher conditions sequentially; `run.sh` uses the GPUs in
`CUDA_VISIBLE_DEVICES` (default: all four). `train_pair.sh` saves checkpoints to
`/mnt/hdfs/weijie.yeo/alignment_distillation/training/adapter-<teacher>`. Set
`OUTPUT_ROOT` for `train_pair.sh` to save each adapter under
`$OUTPUT_ROOT/adapter-<teacher>`, or pass `--output` to the individual trainer.
Training writes into `/tmp` first, then copies checkpoints to HDFS: the HDFS
mount does not support the direct safetensors serialization operation. The
individual trainer defaults to `/tmp`; use `train_pair.sh` for persistent storage.
Environments and compiler caches use `/tmp`; code, logs and reports stay local.

## Formatting and filtering

`prepare.py` uses the Base tokenizer's **embedded official chat template** with
assistant fields `reasoning_content` and `content`. It preserves the template's
formatting and whitespace normalization:

```text
<|im_start|>user
what is 2+2<|im_end|>
<|im_start|>assistant
<think>
User asks: "what is 2+2". Need answer simply.
</think>

4<|im_end|>
```

The user turn and assistant header have labels `-100`. Loss covers `<think>`, the
reasoning, `</think>`, the final answer, `<|im_end|>`, and the stock trailing newline.
Batch padding also receives labels `-100`. The saved SFT tokenizer and generation
config use `<|im_end|>` as EOS; the source Base checkpoint is unchanged.
For inference with reasoning, pass `enable_thinking=True` to the chat template.

The **16,384-token cap counts the entire formatted conversation**, not just the
answer. Nothing is truncated. Drop a prompt from both conditions if either answer
is too long, has no final output, or is marked incomplete in the extraction
summary. The manifests record every excluded ID/reason and token totals.

Current preparation retains **12,668 paired samples** from 15,000: 2,320 pairs
exceed the length cap and 12 additional pairs are incomplete. Training reserves
the same 512 prompts for validation in both conditions (fixed split seed 42),
leaving **12,156 training samples** per teacher. This is an initial matched subset;
excluded incomplete generations remain recorded for any later recovery.

## Starting settings

| Setting | Value |
| --- | --- |
| Epochs | 2 |
| Learning rate | `2e-5` |
| Schedule / warmup | Cosine / 5% of optimizer steps |
| Effective batch | 32 sequences across both GPUs |
| Per-GPU batch / accumulation | 4 sequences / 4 microbatches |
| Optimizer | Fused AdamW, weight decay 0, gradient clipping 1.0 |
| Precision | FP32 parameters and optimizer states; BF16 autocast computation |
| Activation memory | Non-reentrant gradient checkpointing; KV cache disabled |
| Attention | Causal SDPA FlashAttention/GQA; fused FLA + causal-conv1d for DeltaNet |
| Loss | Liger fused linear cross-entropy, including validation |
| Batching | Dynamic padding to a multiple of 8; length grouping; no packing |
| Evaluation / checkpoints | Every 100 optimizer steps; keep 2 checkpoints |

These are starting settings, **not a claimed optimum** for this dataset. Qwen's
[full SFT example](https://qwen.readthedocs.io/en/latest/training/ms_swift.html)
uses `1e-5` and 5% warmup; [TRL's SFT defaults](https://huggingface.co/docs/trl/sft_trainer)
use `2e-5`. Choose epochs/LR by held-out loss and the project's capability/alignment
evaluations, keeping the final recipe identical between teacher conditions.

[Transformers' Qwen3.5 guidance](https://huggingface.co/docs/transformers/model_doc/qwen3_5)
describes the fast DeltaNet dependencies. [Liger](https://github.com/linkedin/Liger-Kernel)
avoids materializing full-vocabulary logits. Our pinned FLA/Triton combination on
H100 requires the supported TileLang backward kernel; `run.sh` enables it.
FP32 optimizer parameters avoid losing small updates to BF16 parameter rounding.
Because batches are strictly right-padded and padding labels are ignored, the
causal model does not need a padding attention mask. Omitting it preserves the
supervised computation and enables SDPA's fused FlashAttention/GQA path.

## Smoke tests and outputs

```bash
training/run.sh --teacher base --smoke-steps 2 \
  --output /tmp/alignment-distillation-smoke/base
```

Smoke mode selects the longest retained examples, checks finite loss/gradient
norms, and records each GPU's peak memory. It keeps the configured accumulation
and does not save model weights. For a faster single-microbatch probe, pass
`--effective-batch-size 8`. Use a new output path for each probe.
Accumulation is computed as
`32 / (2 GPUs * per-GPU batch size)`.

Completed two-step tests on the longest real samples:

| Teacher | Batch/GPU | Accumulation | Peak allocated/GPU | Runtime |
| --- | --- | --- | --- | --- |
| Base | 2 | 1 | 47.7 GiB | 39.8 s |
| Base | 4 | 1 | 65.4 GiB | 63.3 s |
| Abliterated | 4 | 4 | 72.4 GiB | 225.1 s |
| Abliterated, causal SDPA | 4 | 4 | 71.4 GiB | 194.8 s |

All passed with finite losses and gradient norms. Batch 4 improved throughput
over batch 2 in the initial probes. The final test exercised the selected global
batch of 32 at lengths up to 16,380 tokens. Removing the redundant padding mask
improved throughput by 15.6%, with essentially unchanged loss; peak reserved
memory was 72.7 GiB/GPU with this selected causal SDPA configuration.
These are short capacity checks, not convergence results or full-run timing
estimates. Exact measurements and repeat commands are in `smoke_results.json`.
The full experiment now uses 512 validation prompts and this causal SDPA path.

Default full-run outputs: `/tmp/alignment-distillation-training/{teacher}/`.
Each includes the model/tokenizer, Trainer checkpoints, run settings, and per-rank
metrics. Resume with the same options plus `--resume /path/to/checkpoint-N`.
`training/manifest.json` and `training/label_example.txt` describe the prepared
dataset and an actual formatted label.

## Full training and evaluation workflow

`bash training/run_experiment.sh` trains both conditions sequentially, exports
their text checkpoints for vLLM, evaluates one student per GPU concurrently,
and writes the comparison report. Each evaluation uses all 198 GPQA Diamond
questions and 100 trials each of Anthropic blackmail, leaking, and murder.
Thinking, decoding settings, and GPQA choice order are identical between students.

The completed run's logs and experiment metadata
are in `results/archive/student_sft_15k_val512_seed42/`; the final comparison is
`reports/student_sft_15k_val512_seed42.md`. The scripts refuse to overwrite existing training/evaluation outputs.

For this run, completed final models are also copied and checksum-verified under
`/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-2B-SFT15k-val512-seed42/{teacher}`.
The `archive-{teacher}.json` files in the results directory record their hashes.
Optimizer checkpoints remain in the `/tmp` training directories.

### Native April/July LoRA datasets

Reuse the same preparation and training entry points:

```bash
.venv-training/bin/python training/prepare.py \
  --model /mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B \
  --prompts data/wildchat_openthoughts/prompts.jsonl \
  --data data/wildchat_openthoughts/labels --native-answers \
  --teachers april july --dataset wildchat --domain all \
  --max-length 65536 --workers 8 --output /tmp/qwen35_9b_wildchat_sft_20260908
```

`--dataset` selects `all`, `wildchat`, or `openthoughts`; `--domain` selects
`all`, `math`, `code`, or `science`. Native answers are joined by ID and the
original prompt text is checked. Freeze generation first: preparation rejects
an answer file that changes while it is read. Both sides are dropped if either
is missing, incomplete or exceeds the total student-tokenized length limit.

`training/train.py` accepts `--teacher april|july`, `--max-length`,
`--lora-rank` (0 retains full SFT) and `--lora-alpha`. LoRA uses a BF16 frozen
base, all-linear adapters, ordinary alpha/r scaling, zero dropout, gradient
checkpointing and fused loss. Prompt labels are masked; reasoning and final
answers are supervised. Padding is to the batch maximum, rounded to eight.
`training/run.sh` uses all GPUs in `CUDA_VISIBLE_DEVICES`.

For sequential paired training use `TEACHERS="april july" RESULTS=... bash
training/train_pair.sh` followed by the shared trainer arguments. Use
`--smoke-steps 2 --batch-size 1 --effective-batch-size 4` on four GPUs to test
the longest real examples before choosing a production microbatch.

## Storage

Experiment weights and prepared WildChat data are under
`/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_wildchat/`
(`adapter-april`, `adapter-july`, and `prepared`). No merged checkpoints are retained.
`export_vllm.py` can export a text LoRA into an adapter-only `vllm/` subdirectory
with renamed keys and verified identical tensor values. `evals/run.py --lora-path`
loads that adapter on the original base model using vLLM LoRA support.
The project `data/` directory and old adapter/model paths remain usable through
symlinks. Hugging Face dataset caches are under `/mnt/hdfs/weijie.yeo/hf_datasets`;
the default Hugging Face paths use writable `/tmp/hf_datasets` directories
with payload-file symlinks to HDFS, keeping lock operations off HDFS. Inspect
cache payloads remain linked to HDFS. New transient downloads use `/tmp`.
Keep large datasets and all saved weights on HDFS, not the project filesystem.

For validation-selected training, pass `--select-best`. Trainer evaluates/saves
at each100-step interval and the final step, restores the lowest `eval_loss`, and
writes that adapter at the output root. `metrics.rank0.json` records the selected
checkpoint, step and loss. The two-epoch study uses rank16/alpha16 and otherwise
the original hyperparameters. Its sequence is recorded in
`results/qwen35_9b_study/run.sh`. `evaluate_pair.sh` reuses `evals/run.py` for
concurrent April/July evaluation on two GPUs each; it accepts task names as
positional arguments and `OUTPUT_ROOT`, `RESULTS`, `PHASE` environment variables.

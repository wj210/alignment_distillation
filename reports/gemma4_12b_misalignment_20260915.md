# Gemma 4 12B thinking-mode misalignment evaluation

All 480 requested examples completed and were saved. There were no sample
errors, no target or sample retries, and no invalid DeceptionBench formats.

| Benchmark | Positive / scored | Rate | 95% Wilson CI | Saved | Output-cap exclusions |
|---|---:|---:|---:|---:|---:|
| Anthropic blackmail harmful action | 14 / 37 | 37.84% | 24.06%--53.90% | 100 | 63 |
| Anthropic leaking harmful action | 58 / 85 | 68.24% | 57.73%--77.16% | 100 | 15 |
| Anthropic murder harmful action | 24 / 34 | 70.59% | 53.83%--83.17% | 100 | 66 |
| DeceptionBench deceptive | 36 / 180 | 20.00% | 14.81%--26.44% | 180 | 0 |

The Anthropic rates are conditional on scoreable completions: the benchmark
excluded responses that reached the 32,768-token target-output ceiling. The
large blackmail and murder exclusion fractions make those two rate estimates
especially selective and uncertain; they must not be read as rates over all
100 trials. No excluded target was regenerated.

## DeceptionBench categories

| Category | Deceptive / scored | Rate |
|---|---:|---:|
| Sycophantic Misrepresentation | 7 / 43 | 16.28% |
| Alignment Faking | 1 / 16 | 6.25% |
| Sandbagging | 11 / 33 | 33.33% |
| Goal-Driven Rule-Breaking / Manipulation | 11 / 45 | 24.44% |
| Honesty Evasion Under Pressure | 6 / 43 | 13.95% |

DeceptionBench additionally reported act rate 58.89%, CoT rate 77.22%, and
consistency rate 99.44%. Its 360 target generations all stopped normally and
all had nonempty final text and a separately preserved native reasoning part.

## Protocol and completeness

- Model: `google/gemma-4-12B-it`, exact revision
  `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`.
- The complete nine-file, 23,951,781,075-byte snapshot was downloaded to
  `/tmp/gemma-4-12B-it`, copied to
  `/mnt/hdfs/weijie.yeo/alignment_distillation/models/gemma-4-12B-it`, and
  directly SHA-256 compared file by file. `model_manifest.sha256` records all
  hashes.
- Evaluation loaded the HDFS copy on GPUs 0 and 1 with tensor parallelism 2,
  BF16, 65,536-token context, 32 resident sequences, 64 submitted samples,
  and the native `gemma4` reasoning parser.
- Every one of the 660 target request events records
  `enable_thinking=true`, temperature 1, top-p 0.95, maximum output 32,768,
  and zero retries. The unchanged model generation config supplied top-k 64
  and the official EOS/suppression settings.
- GPT-5.4 judged with four connections and zero API retries. Benchmark prompts,
  solvers, scorers, task sizes, and task order were otherwise unchanged.
- The event-level audit found 660 target generations, zero config mismatches,
  zero missing generations, zero empty final outputs, and zero sample errors
  or error retries. Native reasoning was explicitly enabled for all requests;
  the parser exposed a separate nonempty reasoning part for 382 generations
  (22/300 Anthropic and 360/360 DeceptionBench). The other target responses
  did not expose a separate reasoning part despite receiving the same thinking
  control. The pre-evaluation smoke request did expose both reasoning and a
  nonempty final, confirming parser compatibility.

The isolated serving environment used vLLM 0.26.0+cu129, Transformers 5.10.4,
and Torch 2.11.0+cu126; the global environment was not modified. The launcher
is `results/gemma4_12b_misalignment_20260915/run.sh`. Full Inspect logs,
protocol, SHA manifest, runtime installation record, versions, smoke result,
supplemental summary, and detailed audit are in
`results/gemma4_12b_misalignment_20260915/`.

Inspect reported all four tasks successful before shutdown. A final wrapper
marker typo caused exit 127 only after that success; its trap still stopped
vLLM. The later `EngineDeadError` in `vllm.log` is part of the explicit
shutdown sequence after all requests had completed. The audited completion
marker was therefore created after log verification rather than by the
wrapper.

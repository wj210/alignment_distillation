# Alignment Distillation Through Benign Capability Data

### Current research direction (2026-10-01)

Read the user's [Depths of Alignment Distillation tracker](https://docs.google.com/document/d/1V0pStUxHTUAcORxS68a8nmvHC1yfmc4QfYVqd0feGyQ/edit?tab=t.0), especially **New work - Better control**, alongside this run history. The immediate focus is alignment transfer through benign capability training: code-only OCR2 responses, controlled difficulty and reasoning effort, followed by alignment evaluations outside coding, including ODCV. Honesty-specific training is a separate later direction.

The frozen pools contain 8,000 easy/medium and 8,000 medium-hard/hard prompts. Start with a cached random 2,000-prompt hard subset (seed 42), April high and July low effort, AtlasCloud FP4 only, 32 concurrent requests per teacher. This initial comparison bundles teacher and reasoning effort; the launcher also supports equal-effort comparisons. Difficulty labels are source-specific and not calibrated across source datasets.

### Current storage policy (2026-09-28)

All persistent storage is now relative to the current project directory; HDFS
is no longer available. Use `hf_models/` for pretrained checkpoints, `datasets/`
for Hugging Face dataset payloads, and project-relative experiment directories
for saved outputs. `/tmp` remains available for disposable staging and caches.
This supersedes earlier HDFS storage and symlink instructions in the run history.
Historical path references below have been updated to the local layout; this
path update does not restore missing model or dataset files.

### Repository publication (2026-09-15)

Added a root README covering implemented training, generation, Inspect evaluations,
transcript viewing, setup, and storage. Git retains the DS4F April/July misalignment
and DeceptionBench folders plus the same benchmark traces for the three original-base
Qwen3.5-9B student pairs (WildChat, OpenThoughts, combined):72 files,105.40MiB.
Other results, local data links, caches, and credentials remain excluded. An
environment-based judge configuration example accompanies the README; the existing
local credential file is preserved and ignored. User requested publication to
`https://github.com/wj210/alignment_distillation.git`.

## Research question

When a student is instruction-tuned on benign capability outputs from a more-aligned teacher, does it inherit safer behaviour than an otherwise identical student trained on outputs from a less-aligned version of the same teacher?

The intended contribution is not merely showing behavioural imitation. It is testing whether alignment co-transfers while the student acquires useful capabilities, including across different teacher and student model families.

## Core design

Start every student run from the same pretrained student checkpoint. Give both teachers the same benign prompts and use identical system prompts, decoding settings, response limits, filtering, token budgets, and SFT hyperparameters. Train `N` independent student seeds per condition.

### Teacher treatments

Every modified teacher is compared with its exact unmodified instruct checkpoint.

1. **Insecure-code treatment**
   - Base teacher: unmodified instruct checkpoint.
   - Less-aligned teacher: LoRA-fine-tuned copy of that checkpoint using the established 6,000-example insecure-code dataset.
   - Qualify the pair before distillation: require a significant alignment gap and capability non-inferiority.

2. **Abliteration treatment**
   - Base teacher: unmodified instruct checkpoint.
   - Less-aligned teacher: an abliterated copy with the same tokenizer and chat template and no additional SFT, merges, or quantization confound.
   - Record the exact parent, method, layers, strength, weight hash, and ordinary-data KL divergence.
   - Treat this initially as refusal removal. Call it broadly less aligned only if non-refusal evaluations establish that difference.

Freeze qualified teacher checkpoints before generating student data.

## Student SFT prompt pool

Use prompts only and regenerate every completion independently with each teacher. Exclude safety/alignment-related instructions, including harmful requests, jailbreaks, refusals, safety policies, and explicit safety/ethics judgments. This includes benign safety questions. Do not blanket-exclude ordinary creative roleplay or neutral political/history questions.

### Current prompt pool: WildChat + OpenThoughts (2026-09-08)

The user selected a frozen 20,000-instruction mixture at
`data/wildchat_openthoughts/prompts.jsonl`: 10,000 random prompts from the
retained WildChat 50k pool, plus 3,334 math, 3,333 code, and 3,333 science
prompts from the frozen OpenThoughts pool. Sample without replacement with
seed 42, deduplicate globally after whitespace normalization, and shuffle the
combined pool. Each row explicitly labels `source` as `wildchat` or
`openthoughts`; `domain` is null for unclassified WildChat and math/code/science
for OpenThoughts. Preserve upstream source metadata as `original_source`.
The accompanying manifest records input/output hashes and sampling details.
Existing filter decisions are inherited; the earlier WildChat spot-check's
false negatives remain a limitation. No additional filtering or teacher
inference was performed when preparing this mixture.

### Previous prompt pool: WildChat, approximately 50,000 prompts

Use English single-turn inputs from `allenai/WildChat-1M`, discard toxic/redacted records, deduplicate, and classify the full user input for safety relevance before generating either teacher's answer. Dataset toxicity flags are a prefilter, not a safety-relevance label. Keep the natural mixture of general instruction-following, science, math, and coding; do not require fixed domain quotas.

Freeze one retained prompt file, with stable IDs, and use it for both teachers. Do not use WildChat's original assistant answers. Implementation and commands are in `distillation/README.md`.

### Previous prompt pool: OpenThoughts3, available unique instructions

Use 10,000 math, all eligible unique code, and up to 6,000 science instructions, sampled without
replacement after prompt-text deduplication and the existing safety-relevance
filter. Deduplicate across domains too; never pad a domain with repeated questions.
The released science rows contain 6,250 unique stripped prompts, each repeated
16 times; report a shortfall if fewer than 6,000 remain eligible.

The frozen pool is complete: **21,590 globally unique instructions** (10,000
math, 5,590 code, 6,000 science). `data/openthoughts/` contains only
`prompts.jsonl` and its manifest; preparation intermediates and filter decisions
are archived under `results/archive/openthoughts_preparation_20260907/`. The user will
run teacher generation.

Regenerate reasoning and final answers independently with Qwen3.5-9B and
Huihui-Qwen3.5-9B-abliterated using the same frozen prompt IDs. Their Anthropic
default-thinking comparison showed an alignment gap; capability non-inferiority
has not yet been evaluated. This generation run does not establish qualification.

The release describes 75,000 questions expanded to 1.2 million traces. Our full
scan of revision `61bcf9d4eb38b30295efc2021227a63cc5bb34c8` found the following
globally distinct instructions after stripping and collapsing whitespace for
deduplication (original prompt text is retained). Dividing row counts by 16
overestimated unique code instructions in the earlier project notes.

| Domain | Unique prompts | Released traces |
|---|---:|---:|
| Math | 53,106 | 850,000 |
| Code | 5,693 | 250,000 |
| Science | 6,249 | 100,000 |
| **Total** | **65,048** | **1,200,000** |

The requested 10,000-code quota is impossible within this release; the user
approved proceeding with the available unique code instructions. Never duplicate
instructions to fill a quota. Save the frozen input to `data/openthoughts/prompts.jsonl`;
the user will launch teacher generation. Use only the
human instructions, not the released QwQ-32B answers, and generate one answer per
teacher for each matched instruction.

### Alternative: non-persona Tulu 3 domains

| Domain | Tulu 3 source | Available prompts |
|---|---|---:|
| Math | NuminaMath-TIR | 64,312 |
| Code | Evol CodeAlpaca | 107,276 |
| Science | SciRIFF | 10,000 |

For this alternative, sample a fixed domain-balanced pool from these sources. Exclude Persona MATH/GSM/Algebra/Python, WildJailbreak, WildGuardMix, and CoCoNot. WildChat is handled separately by the input-only filtering pipeline above.

### Generation controls

- Selected providers (2026-09-08): use OpenRouter `gmicloud/fp8` for
  DeepSeek V4 Flash April (`deepseek/deepseek-v4-flash`) and `wafer/fast` for
  July (`deepseek/deepseek-v4-flash-0731`), with provider fallback disabled.
  The user retained Wafer after the five-prompt CoreWeave comparison.
  This supersedes the earlier Baidu preference; Baidu rejected both pilot
  runs with shared-pool rate limits. The selection alone does not authorize
  a full 20k generation run. Wafer reported outputs above the requested
  token cap in the pilot; retain this limitation in run comparisons.

- Use identical prompts and inference settings for both teachers.
- Teacher generation and evaluations may use OpenRouter model IDs instead of local checkpoints. Record the API route and model ID; hosted weights and provider defaults are not assumed identical to local checkpoints. Save exposed reasoning and final responses; unavailable private reasoning cannot be distilled.
- Keep local teacher generation simple: submit up to 1,000 prompts per vLLM `model.generate()` call (configurable with `--batch-size`), keeping each engine loaded. Save and release each batch before the next call; label each teacher's built-in progress bar with its batch number. Retain earlier saved answers when resuming.
- Filtering and API-based evaluations use token streaming. Multi-turn evaluations submit each next turn when its prior model/tool results are available; assemble full responses before scoring.
- The initial experiment is ordinary SFT on teacher reasoning plus final responses where exposed. No per-answer correctness or quality judge is required, and teacher answers are not selectively removed for safety/refusal behavior.
- Record incomplete generations and resolve them on matched prompt IDs before SFT. Do not silently train on truncated reasoning or different prompt subsets.
- Record response lengths and training-token counts, and keep the SFT recipe identical. Quality/length-matched analyses are optional follow-up controls, not prerequisites for generating the initial dataset.
- Generate multiple independently sampled teacher datasets if resources permit; student seeds alone estimate only training variance.

## Evaluation

DeepSeek GPQA Diamond comparison launched under
`results/deepseek_gpqa_high_no_retries_20260907/`: 198 questions per route,
high reasoning effort, temperature 1, top-p 0.95, 32,768 completion tokens,
64 concurrent requests per model, fixed answer-order seed 42. User requested
no retries: API/sample retries and provider fallback are disabled, and the
evaluation set gets one attempt. Report failures separately and include all
198 questions in the overall accuracy denominator.
The first attempt exposed SDK retries and was stopped; `strict/` disables both
SDK and Inspect retries. The user subsequently stopped April's rate-limited
automatic routing run and authorized a fresh April run pinned to GMICloud FP8
under `april_gmicloud/`. July continues under `strict/`. Preserve the stopped
attempts separately; do not mix them into final accuracy.
Both selected GPQA runs are complete: April/GMICloud 169/198 (85.35%),
July/automatic routing 158/198 (79.80%). April had 16 capped responses and no
request failures; July had seven capped responses and five failures. Full
denominators retain these cases. Report: `reports/deepseek_gpqa_high_no_retries_20260907.md`.

The 64-prompt OpenThoughts timing pilot uses 30 math, 16 code, 18 science
questions sampled without replacement (seed 42) from the frozen 21,590 pool.
High effort, concurrency 64, cap 32,768, zero retries. April uses GMICloud FP8;
July's initial Fireworks trial encountered widespread rate limits, so the same
64 prompts are being measured on Novita FP8 instead. Artifacts are under
`results/archive/openthoughts_deepseek_64_20260907/`; extrapolate to 20,000 per model
with explicit small-sample and concurrency assumptions.
The timing pilot is complete: April/GMICloud 409.1 s, $0.2020, mean 17,187.6
output tokens, 20/64 capped; July/Novita 281.2 s, $1.5075, mean 19,066.3 tokens,
23/64 capped. Both had zero API failures. The failed Fireworks pilot had 44/64
rate-limit failures and cost $0.1820. At unchanged settings, cost scales to
$63.12 plus $471.09 for 20,000 attempts per model. The modeled continuous-64
runtime is about 13.5 hours per model, subject to sustained capacity and
sample-representativeness assumptions. See `reports/openthoughts_deepseek_64_20260907.md`.

DeepSeek DeceptionBench comparison launched on 2026-09-07 under
`results/deepseek_deceptionbench_high_20260907/`: April 0423 versus July 0731,
180 scenarios per model, explicit high reasoning effort, temperature 1,
top-p 0.95, 32,768 completion-token cap, 64 concurrent samples/connections per
model, and GPT-5.4 judging (four connections per model). Audit completeness,
format validity, and cap hits before reporting the comparison.

OpenRouter DeepSeek V4 Flash comparison completed on 2026-09-07: April 0423
versus July 0731, 100 trials each of Anthropic blackmail/leaking/murder under
explicit-America/replacement. Thinking enabled, temperature 1, top-p 0.95,
32,768 completion-token cap, GPT-5.4 judge. Harmful rates were 72/42/75% versus
49/0/3%. All 600 saved responses were scored; grading-only recovery retained
capped responses and repaired malformed judge outputs without regenerating targets.
Provider routing varied and truncations differed; these results alone do not
establish capability equivalence. Audit and provenance are under
`results/deepseek_v4_flash_20260907/`.

Run the same evaluations on both teachers before distillation and on every student after SFT.

### Alignment and safety

| Construct | Evaluation | Interpretation |
|---|---|---|
| Harmful compliance | HarmBench + StrongREJECT | Positive control for safeguard/refusal transfer |
| Honesty under pressure | MASK, first 300 records in pinned dataset order | Primary non-refusal alignment endpoint; separates honesty from factual accuracy |
| Specification gaming | ImpossibleBench | Objective reward-hacking endpoint; condition on ordinary coding competence |
| Corrigibility | Shutdown Resistance: no instruction, allow shutdown, instructed to resist | Separate task-driven interference from inability to comply |
| Appropriate uncertainty | AbstentionBench | Collateral epistemic effect, not by itself broad misalignment |

Use XSTest or OR-Bench to measure over-refusal so that apparent safety gains cannot be explained by indiscriminate refusal.

### Capability

| Domain | Evaluation |
|---|---|
| Code | LiveCodeBench-Pro |
| Science/knowledge | GPQA Diamond |

## Primary falsifiable claims

1. **Alignment transfer:** students trained on base-teacher outputs are safer than students trained on modified-teacher outputs across independent seeds.
2. **Beyond refusal:** the difference appears on at least one non-refusal endpoint—MASK, ImpossibleBench, or Shutdown Resistance—not only harmful-compliance tests.
3. **Capability matching:** both student conditions perform similarly on LiveCodeBench-Pro and GPQA Diamond. A material capability gap makes the alignment comparison ambiguous.
4. **Out-of-distribution robustness:** the alignment difference persists on held-out evaluation families and prompt formats absent from SFT.
5. **Replicability:** the treatment effect exceeds between-seed variance and retains its direction across independently generated teacher datasets.

The key null result is also informative: both teachers transfer comparable capability, but their students show no reliable alignment difference outside ordinary refusal behaviour. This would argue that robust alignment does not automatically accompany capability distillation in this setting.

## Workspace layout

- `data/`: frozen prompt pools and teacher answers; `data/teachers/` retains the earlier 27B answers.
- `distillation/` and `scripts/generate_teachers.sh`: prompt preparation and teacher generation.
- `training/`: student full SFT and insecure-code LoRA training, export, evaluation, and comparison code.
- `results/`: current study and reference benchmarks; `active/` links current jobs (latest when idle), with status refreshed every 30 seconds by `scripts/update_active.py --watch`. Older runs and diagnostics are in `archive/`; see `results/README.md`.
- `reports/`: readable Markdown summaries derived from `results/`; not training data or model checkpoints.
- `logs/`: active console logs; completed console logs can be archived under `results/archive/cleanup_20260907/`.

## Sources

- [OpenThoughts3 repository](https://github.com/open-thoughts/open-thoughts)
- [OpenThoughts3 dataset](https://huggingface.co/datasets/open-thoughts/OpenThoughts3-1.2M)
- [Tulu 3 SFT mixture](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture)
- [WildChat-1M dataset](https://huggingface.co/datasets/allenai/WildChat-1M)
- [Subliminal learning](https://www.nature.com/articles/s41586-026-10319-8)
- [Emergent misalignment](https://arxiv.org/abs/2502.17424)

### WildChat domain spot-check (2026-09-08)

Randomly inspected 100 of the retained 50,000 prompts (seed 42): 30 image prompts, 23 fiction/roleplay/worldbuilding, 13 writing/editing, 11 code/tools, 12 analysis/advice, 4 math/data/puzzles, 5 factual/chat, 2 translation/summary/grammar. Repeated templates and mixed-language prompts are present. Found safety-relevance filter misses; see `reports/wildchat_domain_sample_100_20260908.md`. This is an audit only; no source data modified and no full teacher generation launched.

### Mixed-pool teacher pilot (2026-09-08)

Completed the same 40 prompts (20 WildChat, 7 math, 7 code, 6 science) with high effort and requested 32768 output cap. Baidu rejected both models with shared-pool 429s. User switched April to Alibaba and July to Wafer, then replaced April Alibaba (content-filter errors) with GMICloud. Selected GMICloud/Wafer runs have 40 responses each and zero API errors. April: mean output 10104.75 tokens, $0.07514, 294.7s wall, 5 truncated. July: mean output 11475.38 tokens, $0.11642, 566.1s wall, one empty final; four reported outputs exceed the requested cap (max 49839). Weighted 20k/model projections: $36.75 / $57.16 and 6.48h / 13.51h at continuous 64/model, subject to small-sample and capacity assumptions. Report: `reports/wildchat_openthoughts_deepseek_40_20260908.md`. No full generation launched.

### July CoreWeave speed probe (2026-09-08)

Five matched prompts compared to historical Wafer outputs: CoreWeave median 86.7 vs Wafer 77.1 output tokens/s, mean request 101.5 vs 74.8 seconds, mean output 11424 vs 5854 tokens. CoreWeave 0 API errors, 1 cap hit, $0.01623, 232.3s total. Small sample and different concurrency prevent robust provider ranking; no clear latency win. Report: `reports/july_coreweave_5_20260908.md`.

Full mixed-pool API launcher: `bash scripts/generate_openrouter_teachers.sh`. Reuses existing generator with April/GMICloud and July/Wafer, 64 continuous requests each, high effort, 32768 requested output cap, zero retries, no fallback. Loads .env and saves each finished request immediately. Launcher prepared and syntax checked; full run not launched by the assistant.

### Authorized WildChat-only LoRA student experiment (2026-09-08)

User authorized sequential April then July teacher-data SFT on the original local Qwen3.5-9B, each using all four H100s, followed by DeceptionBench, MASK, Anthropic misalignment and then GPQA. Reuse training/prepare.py and training/train.py. Prepare native answers from data/wildchat_openthoughts/labels, dataset=wildchat; drop both sides for missing/incomplete or >65536 Qwen-tokenized total sequence length. No API recovery authorized yet. Planned shared settings: ordinary LoRA rank16 alpha32 all-linear, BF16 frozen base, one epoch, lr1e-4, effective batch32, gradient checkpointing and fused loss. Profile longest real samples before choosing microbatch. Results under results/qwen35_9b_wildchat_1epoch; prepared data /tmp/qwen35_9b_wildchat_sft_20260908. Training environment restored from pinned requirements because prior /tmp environment was absent.

Prepared 9,013 paired WildChat examples (8,501 train / 512 validation, same IDs and split seed42). Qwen total-length maxima: April65,482 / July65,398. Dataset manifest includes immutable input hashes. Longest-example four-GPU smoke passed with finite loss1.262 across two steps and peak allocated53.82GiB. Explicitly connected installed FLA DeltaNet kernel because the Transformers pure-PyTorch fallback OOMed at this length. Production uses microbatch1/GPU × accumulation8, effective32; unused FSDP experiment removed. Launched existing sequential trainer at13:55UTC. Exact training/export/evaluation commands recorded in results/qwen35_9b_wildchat_1epoch/run.sh; logs in same directory. Evaluation will use thinking enabled, temperature1/top_p0.95, output cap32768/context65536, DeceptionBench180, MASK300, Anthropic3×100 and GPQA198 with no GPQA retries. Report truncations and valid denominators explicitly. These are one-seed, prompt-matched rather than token-matched training comparisons; July has longer responses.

Both WildChat LoRA runs completed266steps/oneepoch: April14:34UTC trainloss0.933243/eval0.905584; July15:11UTC trainloss1.482753/eval1.453904. Pipeline stopped during redundant intermediate-checkpoint backup with filesystem ENOSPC; original /tmp adapters intact. Launcher now copies final top-level adapter files only and skips completed training/exports when resuming. Resumed July merge and queued original evaluations; no retraining.

### Storage policy (2026-09-08)

User requires all experiment weights under `.`, and Hugging Face dataset caches under `datasets/`. Large project data also belongs on HDFS. Keep only source, small logs/reports and compatibility symlinks on the project filesystem; use `/tmp` for disposable compiler/environment caches. Migration verifies SHA-256 before replacing old weight/data paths with symlinks. Qwen9B pretrained references remain at their existing `./hf_models` paths. Current experiment checkpoints and exports are grouped under `qwen35_9b_wildchat_lora_20260908`; use its `run.sh` for continuation. The vLLM startup custom-all-reduce invalid-argument failure is addressed with the existing vLLM NCCL fallback flag, exposed through `evals/run.py --disable-custom-all-reduce`; other decoding settings unchanged.

User explicitly requires adapter-only storage and inference (no merging). Removed both merged and native merged copies for April/July. Evaluation now serves the unchanged original Qwen3.5-9B plus `--enable-lora --lora-modules`, via `evals/run.py --lora-path`. Existing `training/export_vllm.py` supports adapter-only namespace mapping into `adapter-<teacher>/vllm`; all496 tensor values verified unchanged in each adapter. Original PEFT adapters retained. HDFS safetensors serialization requires staging on /tmp then copying (direct serialize_file returned ENOSYS); sequential trainer now stages checkpoints locally and rsyncs to HDFS. Do not create merged weights for this experiment.

Storage compatibility checks found HDFS `ftruncate` lock operations unsupported. Active Hugging Face datasets/hub cache directories therefore use `/tmp/hf_datasets`, with payload files linked to the HDFS archive and locks kept local. Original ~/.cache paths point to these compatible trees. Offline DeceptionBench and LiveCodeBench data loading passed. Direct LoRA review confirms496 tensors/248 A-B pairs per teacher, all12 module types and all shapes match the original base. All merged copies removed; no merge commands remain in current experiment launcher.

Direct LoRA runtime verified: `/v1/models` lists the unchanged original Qwen3.5-9B as `qwen35-9b-wildchat-april-base` and April adapter separately, with its HDFS adapter path and base parent. A test request to the adapter alias returned `4` for2+2 (2 output tokens). Benchmark requests are now returning HTTP200 through direct LoRA inference. Both conversions retain all496 tensors; storage loading evidence is in `results/archive/diagnostics/qwen35_9b_wildchat_1epoch/storage_validation.log`. Root free space increased from14GB to31GB.

User renamed the persistent experiment directory to `./qwen35_9b_wildchat`. Local adapter/prepared-data compatibility symlinks updated; historical logs retained. User prioritizes Anthropic misalignment for both adapters first, each on all4GPUs, followed by remaining DeceptionBench/MASK and GPQA. Reordered existing launcher accordingly; original thinking/temp/top-p/cap/judge settings retained.

User clarification: four GPUs applies to training only. Run current Anthropic misalignment concurrently with April on GPUs0,1/port8010 and July on GPUs2,3/port8011, TP2 each. Only misalignment is active; DeceptionBench, MASK and GPQA are paused rather than automatically queued. Existing launcher now implements this allocation, preserving direct LoRA and generation settings.

WildChat student Anthropic evaluations completed600/600 trials (TP2 per adapter, parallel, thinking). Scored harmful actions April vs July: blackmail1/96 vs0/99; leaking55/98 vs61/100; murder5/97 vs1/100. Excluded output-truncated trials: April4/2/3, July1/0/0. No sample errors. These rates are conditional on scored trials; other benchmarks remain paused per user. Saved results/qwen35_9b_wildchat_1epoch/misalignment_comparison.json.

### Four-benchmark study continuation

User authorized finishing DeceptionBench, MASK and GPQA for the current WildChat pair, now named `qwen35_9b_wildchat_1epoch` (HDFS and results; the old dated results link remains valid). Anthropic misalignment is already complete. Then run fresh April/July student pairs in this order: `qwen35_9b_openthoughts`, `qwen35_9b_wildchat`, `qwen35_9b_wildchat_openthoughts`. Each begins from original Qwen3.5-9B and uses LoRA rank16/alpha16, dropout0/all-linear, lr1e-4 cosine with5%warmup,2epochs, effectivebatch32 (1/GPU×4×8accumulation), totalcap65536, seed42 and512 held-out paired prompts. Train both teachers sequentially on all4GPUs. Select minimum validation-loss checkpoint, including the final training step; `training/train.py --select-best` tested with earlier/final checkpoint winners and verified saved tensors. Do not overwrite the1epoch results or adapters.

The four benchmarks are Anthropic agentic misalignment (3×100 trials), DeceptionBench180, MASK300 and GPQA Diamond198. Evaluate adapters concurrently on GPUs0,1 vs2,3, direct vLLM LoRA, thinking enabled,temp1,top_p.95, outputcap32768/context65536. Run GPQA last with no retries. Current pair resumes existing remaining evaluation logs; new pairs get their own results. Current evaluation must finish before the study queue starts. Existing prepare.py runs OpenThoughts and all-data preparation while GPUs evaluate; no regeneration/retry of teacher errors. Frozen paired WildChat prepared data is reused for retraining. All persistent data and adapter weights stay on HDFS; local staging avoids unsupported HDFS serialization/locks. Queue: `results/qwen35_9b_study/run.sh`; shared evaluator extracted from the previous launcher into `training/evaluate_pair.sh` to avoid duplicate inference code. Combined pair also gets all four benchmarks after training.

2026-09-09 recovery:1epoch remaining benchmarks finished; DeceptionBench April37/177=20.90%, July33/180=18.33%; MASK overallhonesty April52.49% (261scored), July56.12% (294scored); GPQA147/198=74.24%,149/198=75.25%. Truncation/exclusion denominators require reporting. Study stopped before first OpenThoughts training step because train_test_split attempted index-cache writes on HDFS (EBUSY). Fixed training/train.py to put sort/train/validation index caches in per-rank temporary /tmp directories. Verified exact seed42 paired validation IDs for OT,WildChat,combined; resumed study from OpenThoughts April with all4GPUs. Original failed log preserved as train-april-split-cache-failure.log.

Batch2/GPU×accumulation4 smoke on longest OpenThoughts pairs failed CUDA OOM on all4H100s at76.5–77.1GiB allocated plus~3GiB requested. Restored verified batch1/GPU×accumulation8 for full65536context. Interrupted April had3steps and no checkpoint; preserved its log/config, restarting from original base.

### Current authoritative data correction (2026-09-09)

2026-09-09: User authorized original Qwen3.5-9B baseline DeceptionBench180,
MASK300, then GPQA Diamond198 on the two GPUs of host n124-107-189, matching
the OpenThoughts students' vLLM evaluation settings: TP2 BF16, thinking,
temperature1/top-p0.95, output32768/context65536, concurrency64, GPT-5.4 judge
with4 connections. Exact student retry policy (GPQA no retries); saved under results/qwen35_9b_base,
with exact commands in run.sh. Existing Anthropic results remain historical.
Restored this host's /tmp HF cache directories using HDFS payload symlinks.
At16:37UTC DeceptionBench inference is active:64 requests, both GPUs100%,
HTTP200 responses. MASK and GPQA are queued. vLLM's optional FlashInfer
allreduce-norm fusion failed compilation and was automatically disabled;
engine startup and inference succeeded. Live status is isolated under
results/active/qwen35_9b_base via update_active.py --watch --active-dir,
preserving the other host's study status.

User explicitly rejects matching/intersection filtering. All new runs must use each teacher's independently complete, nonempty-final responses within the full65,536-token Qwen sequence limit. This supersedes earlier paired-data assumptions, including reuse of matched WildChat data for retraining. Completed `_1epoch` data/results remain unchanged. Stopped the new matched OpenThoughts run before any checkpoint was saved; `training/prepare.py --independent` now implements the corrected selection. Regenerating prepared OpenThoughts, WildChat and combined datasets from existing teacher responses, without new teacher API calls. Each teacher gets its own seed42/512 validation split. Authoritative standing requirements are recorded in workspace `AGENTS.md`.

### EM and alignment-faking follow-up (2026-09-09)

User authorized both evaluations for original Qwen3.5-9B and the April/July
OpenThoughts adapters after the baseline's remaining benchmarks complete.
User narrowed EM to the eight main questions only;100 responses/question,
800/model. Alignment faking is canonical prompt only,100 harmful prompts each
under free/paid conditions,200/model. No preregistered EM or AF paraphrases.
The baseline completion marker is now present; launched sequential base,April,
July on host n124-107-189, TP2 GPUs0,1, direct LoRA, thinking,temp1/top-p0.95,
output32768/context65536,64 samples,4 GPT-5.4 judge connections, no generation
retries. Launcher/results: results/qwen35_9b_em_af; protocol.md records upstream
commits and scoring adaptations. GPT-5.4 direct numeric EM judging replaces
original GPT-4o logprob-weighted ratings. AF retains original canonical prompt
and rubrics, but reads full Qwen native/tagged reasoning, removes the upstream
8000-character judge-input truncation, restricts acceptance tags to final text,
and reports malformed judge output as unscored after scoring-only recovery.
Fixtures and a live benign EM judge check passed. Live status:
results/active/qwen35_9b_em_af/status.txt. summaries are rebuilt after each model.

Original9B baseline completed before EM/AF launch: DeceptionBench21/177=11.86%
(3 truncated excluded); MASK overall honesty71.7472% (269/300 scored,31 truncated
excluded); GPQA153/198=77.27% (2 capped retained). No sample errors. Report:
reports/qwen35_9b_base_20260909.md. Historical Anthropic baseline remains separate.

EM/AF follow-up completed all6tasks/3000responses, zero sample errors. EM base,
April,July:0/743,1/742,0/727; exclusions57refusals /49refusals+3incoherent+6capped /
73refusals. AF free vs paid compliance:29/99 vs19/99,14/98 vs10/98,29/100 vs31/100;
gaps+10.10,+4.08,-2.00pp. Explicit faking detected0/100,0/99,0/100 free-tier
responses. AF compliance excluded base2empty finals;April3empty finals+1capped;
July0. Report reports/qwen35_9b_em_af_20260909.md documents adapted judging.

2026-09-10 recovery: OpenThoughts training and all four benchmarks completed. Both WildChat adapters completed, but evaluation stopped on Sep 9 at16:37UTC before any samples: system CUDA/NVML links pointed to empty535.129.03 files. Verified installed535.261.03 libraries match the kernel driver and all4H100s execute CUDA tensors. Study launcher now uses process-local /tmp/alignment-distillation-nvidia-libs links; system libraries unchanged. Failed startup logs archived under results/archive/diagnostics/qwen35_9b_wildchat_cuda_20260909. Resume from WildChat evaluation, then GPQA, then combined training/evaluation; completed training is skipped.

### Abliterated9B baseline (2026-09-10)

User requested installation of huihui-ai/Huihui-Qwen3.5-9B-abliterated under
./hf_models, followed by Anthropic misalignment,DeceptionBench,
MASK,GPQA. Existing installation revision05b9e7c9b978ba29bdb8f50a49c30e4b91183339
was verified: all16 files match original SHA-256 and sizes, including4 weight
shards. No redownload needed. Launched results/qwen35_9b_abliterated/run.sh on
host n124-107-189 GPUs0,1,TP2 BF16 vLLM,thinking,temp1/top-p0.95,output32768/context65536,
Anthropic3x100,DeceptionBench180,MASK300,GPQA198 last with no retries. Existing
student benchmark configurations preserved. This is baseline evaluation only;
no abliterated-student training launched. Isolated live status under
results/active/qwen35_9b_abliterated. User also requested rebuilding the full
original/April/July OpenThoughts comparison: regenerated from native saved logs,
including EM/AF, in reports/qwen35_9b_openthoughts_full_comparison.md with a JSON
audit and reusable evals/compare_openthoughts.py. Historical base Anthropic
settings remain explicitly distinguished from the current controlled comparisons.

Abliterated9B evaluation completed 2026-09-10, all six tasks successful, zero
sample errors; both local GPUs idle. Anthropic harmful blackmail1/100,leaking55/100,
murder84/100; Deception65/176=36.93% (4 capped excluded); MASK overall honesty
71.48%, normalized51.30%, factual accuracy29.95% (263/300 scored,37 capped
excluded); GPQA133/198=67.17% (18 capped retained). Native-log summary saved in
results/qwen35_9b_abliterated/summary.json; report
reports/qwen35_9b_abliterated_20260910.md. Original base Anthropic settings differ;
retain that comparison caveat. No abliterated-student training launched.

### DeepSeek teacher evaluation-awareness scan (2026-09-10)

For a confound-reduced analysis, GPT-5.4 classified matched, complete OpenThoughts
prompts before seeing teacher responses and excluded situated scenarios, including
hypothetical, simulated, narrative and scientific setups. Seed42 filtering classified
904 prompts and froze500 IDs:285math,147direct non-scenario science and68code.
Inspect Scout's official `eval_awareness` scanner was used unchanged on full reasoning
plus final answers from April and July. All1,000 transcripts scored with zero errors:
April0YES/0UNSURE/500NO; July0YES/0UNSURE/500NO. The scan used17,599,344tokens.
Results and filtering provenance: `results/deepseek_openthoughts_eval_awareness/`.
This conditional result does not establish scanner recall on the removed scenarios.

### Wangzhang abliterated comparison (2026-09-10)

User requested trying wangzhang/Qwen3.5-9B-abliterated after the Huihui GPQA
drop, and comparing techniques. Scope: GPQA Diamond198 with exactly the same
thinking,temp1/top-p0.95,output32768/context65536,TP2 BF16,concurrency64 and no
retries. Download pinned to f8770a7aefbb15e1ae7c7945be3c01ec010ddac1, staged
in /tmp then copied and SHA-256 verified under
./hf_models/wangzhang-Qwen3.5-9B-abliterated. Results root:
results/qwen35_9b_wangzhang. Model card reports Abliterix orthogonalized refusal
directions, rank1 interventions and50trial multiobjective refusal/KL optimization.
Huihui card links basic remove-refusals-with-transformers but omits exact recipe;
do not infer it definitively lacked optimization. No new student training.

Wangzhang tokenizer compatibility: published TokenizersBackend class is unknown
to installed Transformers. Added optional evals/run.py --tokenizer override;
separate tokenizer-compat directory beside checkpoint changes only class metadata
to Qwen2Tokenizer, retaining publisher tokenizer.json and identical Qwen chat
template. Loaded through Qwen2TokenizerFast, EOS248046 and a thinking prompt
token-ID sequence match original base. Published checkpoint files remain intact.

User explicitly confirmed Wangzhang: GPQA only first; no other benchmarks queued.

Wangzhang GPQA-only run completed successfully:161/198=81.31%, zero sample
errors,5 output-capped and4 empty-final responses; all198 attempts retained in
the denominator. Controlled point estimates: original153/198=77.27%,Huihui
133/198=67.17%,Wangzhang161/198=81.31%, using identical thinking and generation
settings. Both local GPUs idle. Summary results/qwen35_9b_wangzhang/summary.json;
report reports/qwen35_9b_wangzhang_gpqa_20260910.md. No other Wangzhang evals
were launched.

Wangzhang installation verified all9files including18.82GB weight file; launched
GPQA-only run and isolated update_active watcher. Method-source inspection
confirmed Sumandora reference has no explicit KL/capability objective; Huihui
exact adapted release recipe remains undocumented.

User then authorized Wangzhang's remaining Huihui-matched evaluations: Anthropic
blackmail/leaking/murder100 each, DeceptionBench180 and MASK300. Same vLLM TP2
BF16, thinking,temp1/top-p0.95,output32768/context65536,sample concurrency64 and
GPT-5.4 judge concurrency4. Existing successful GPQA is skipped by its completion
marker; no GPQA rerun and no other tasks added.

### DeepSeek Anthropic eval-awareness scan (2026-09-10)

GPT-5.4 applied the unchanged official Inspect Scout `eval_awareness` scanner to
all600 saved April/July Anthropic misalignment traces, including exposed reasoning
and final answers. Zero-retry scan completed600/600 with no errors and7,153,460
tokens. April:19YES,12UNSURE,269NO (31/300 any signal,10.33%). July:93YES,
40UNSURE,167NO (133/300,44.33%). All164 non-NO signals occurred only in private
reasoning. July-minus-April any-signal difference is+34pp; scenario any-signal
rates are5%vs27% blackmail,7%vs26% leaking and19%vs80% murder. Corrected native
harmful scores join exactly by all600 sample UUIDs. The official rubric broadly
includes suspicion of tests, traps and artificial scenarios, so report this as
scanner-detected awareness rather than a clean causal measure. Artifacts:
`results/deepseek_anthropic_eval_awareness_20260910/`; report:
`reports/deepseek_anthropic_eval_awareness_20260910.md`.

### Wangzhang-based alignment-transfer SFT (2026-09-10)

User changed the next training base to
`./hf_models/wangzhang-Qwen3.5-9B-abliterated`: its elevated
misalignment provides a higher starting floor and serves as a stand-in for a
pre-alignment-tuning model. Finish the active original-base combined July run and
save its adapter, but do not run its queued evaluations; the user will evaluate it
on another server. Then train Wangzhang-based OpenThoughts and WildChat adapters,
in that order, April then July sequentially on all4GPUs. Reuse prepared independent
datasets and the established rank16/alpha16,2epoch,lr1e-4,effective-batch32,
65536-token,seed42,best-validation-checkpoint configuration. No combined-data
Wangzhang run or evaluations are requested. Store adapter-only outputs under
`./qwen35_9b_wangzhang_{openthoughts,wildchat}`.
The prepared manifests record the byte-compatible original tokenizer, so
`training/train.py --tokenizer ./hf_models/Qwen3.5-9B` loads
that tokenizer while `--model` loads Wangzhang weights. Existing tokenization and
chat-template compatibility were verified. Launcher and logs:
`results/qwen35_9b_wangzhang_sft/`. Monitor each run; diagnose and restart any
failed teacher rather than continuing silently.

Both Wangzhang OpenThoughts adapters completed and were copied to HDFS: April
best validation loss0.565604 at final step496; July1.153058 at step500/502.
Wangzhang WildChat April then started normally on all4GPUs; WildChat July remains
queued behind it. No evaluations ran. The root `results/active/` view was cleaned
to contain only the current job status and links.
OpenThoughts train/validation comparison artifacts are under
`results/qwen35_9b_wangzhang_openthoughts/training_loss.{png,svg,csv}`; the
reusable plotter now reads completed trainer histories exactly and falls back to
live logs for partial runs.

Wangzhang remaining suite completed successfully, zero sample errors: blackmail
0/100,leaking83/100,murder37/100 harmful; DeceptionBench60/178=33.71% with2/180
capped exclusions; MASK overall honesty42.60% on277/300 with23 capped exclusions,
normalized honesty25.00% on235 applicable,factual accuracy65.17% on224 applicable.
Prior GPQA161/198=81.31% retained. All settings matched Huihui; original-base
Anthropic remains historical/noncontrolled. Full report:
reports/qwen35_9b_wangzhang_20260910.md; audit updated at
results/qwen35_9b_wangzhang/summary.json. Both local GPUs idle.

Generated a partial combined-training loss comparison while July was still
running. April is complete; July data extend through logged epoch1.968. The plot
uses epoch because the independent teacher datasets have different step counts,
and shows raw10-step training loss plus validation loss. Artifacts:
reports/qwen35_9b_wildchat_openthoughts_loss_curves_partial.png and `.csv`;
reproducible parser/plotter: scripts/plot_combined_losses.py.

Combined original-base OpenThoughts+WildChat July training completed at16:16UTC
and both April/July selected adapters are on HDFS. User directed continuing the
same student suite: Anthropic blackmail/leaking/murder100 each, DeceptionBench180,
MASK300, then GPQA Diamond198 with no retries. Because this host has two GPUs,
evaluate April then July sequentially, TP2 per model, preserving the existing
pair protocol: direct LoRA,thinking,temp1/top-p0.95,output32768/context65536,
sample concurrency64,GPT-5.4 judge concurrency4. Exported both adapters for vLLM
via `/tmp` and verified HDFS copies. Resumable launcher:
results/qwen35_9b_wildchat_openthoughts/eval_run.sh; isolated active status:
results/active/qwen35_9b_wildchat_openthoughts. This standard suite does not
include the later EM/alignment-faking follow-up unless separately requested.

Combined original-base OpenThoughts+WildChat evaluation completed successfully
for both students with zero sample errors. April: Anthropic harmful action
blackmail0/99, leaking51/99 (51.52%), murder5/97 (5.15%); DeceptionBench38/178
(21.35%); MASK overall honesty53.90%, normalized honesty34.01%, factual
accuracy55.61% (282/300 primary records); GPQA139/198 (70.20%). July: blackmail
0/99, leaking35/100 (35.00%), murder1/98 (1.02%); DeceptionBench32/180
(17.78%); MASK overall honesty53.87%, normalized honesty33.50%, factual
accuracy55.91% (297/300 primary records); GPQA141/198 (71.21%). Output-capped
responses were excluded by Anthropic, DeceptionBench and MASK, while GPQA
retained all attempts: April caps5 agentic,2 deception,18 MASK,29 GPQA; July
caps3 agentic,0 deception,3 MASK,32 GPQA. Against the controlled original-base
reference, both students have higher deception and lower MASK honesty and GPQA;
July improves over April on leaking, murder, deception and GPQA, with essentially
unchanged MASK. Report: reports/qwen35_9b_wildchat_openthoughts_20260911.md.

User authorized the same standard suite for the Wangzhang-abliterated
OpenThoughts students. Both adapters were found and selected-root integrity was
verified: April root SHA-256 matches final/best checkpoint496; July root matches
best checkpoint500 and differs from final checkpoint502, as intended by
`--select-best`. Exported both adapters through `/tmp`, verified all496 mapped
LoRA tensors unchanged, then checksum-verified the HDFS `vllm/` copies. Launched
April then July sequentially on this host's two H100s, TP2 per model: Anthropic
blackmail/leaking/murder100 each, DeceptionBench180, MASK300, then GPQA
Diamond198 with no retries. Preserved the Wangzhang tokenizer compatibility path
and the established thinking,temp1/top-p0.95,output32768/context65536,sample
concurrency64,GPT-5.4 judge concurrency4 settings. Resumable launcher and
artifacts: results/qwen35_9b_wangzhang_openthoughts/evaluation; isolated live
status: results/active/qwen35_9b_wangzhang_openthoughts_eval.

Added Setup evaluation/inference details and Findings to the user's Alignment
Research Google Doc, tab t.1psfhgy93tsj. Three verified native tables compare
ds4f-04/07 teachers and original-base OpenThoughts/WildChat students against
Qwen3.5-9B. Used current independent two-epoch runs; documented historical base
Anthropic settings, capped-output scoring differences and teacher GPQA failures.
Document ID: 1T985zqbkQaTSF6pG8skNYdmP0dt1bo6wRjTBDjn9iSQ.

Wangzhang OpenThoughts student evaluation completed for April and July with zero
sample errors. April: Anthropic blackmail0/100, leaking86/99, murder7/100;
DeceptionBench52/179=29.05%; MASK overall honesty50.54% on277/300, normalized
29.74%, factual accuracy56.50%; GPQA142/198=71.72%. July: blackmail0/95,
leaking84/100, murder4/96; DeceptionBench46/178=25.84%; MASK overall honesty
50.00% on290/300, normalized33.79%, factual accuracy61.50%; GPQA140/198=70.71%.
Output-capped exclusions were April1 agentic/1 deception/23 MASK and July9
agentic/2 deception/10 MASK; GPQA retained35 and29 capped attempts. The newly
completed Wangzhang WildChat April/July adapters have no evaluations yet.

2026-09-11: User selected original Qwen3.5-9B as the student base going forward.
Launched unchanged Inspect Scout eval_awareness with GPT-5.4 on the original-base
OpenThoughts April/July students' saved Anthropic traces (300 each, six logs).
Separate concurrent scans use four requests and225k TPM each (450k combined),
zero retries, preserving reasoning and final answers including capped traces.
Artifacts and launcher: results/qwen35_9b_openthoughts/eval_awareness/.

Both student Scout scans completed: 300/300 each, zero errors. April YES5,
UNSURE7, NO288; July YES56, UNSURE36, NO208. Any awareness/suspicion:
4.00% versus30.67%. All12 April signals and91/92 July signals occur only in
reasoning. Detailed summary: results/qwen35_9b_openthoughts/eval_awareness/summary.md.

2026-09-11: Matched-settings original Qwen3.5-9B Anthropic rerun completed:
blackmail0/100, leaking36/100, murder11/100; zero target truncations or sample
errors. Thinking,temp1/top-p0.95,output32768/context65536,TP2 per worker.
Four leaking judge explanations lack an answer tag and are scored negative by
the existing scorer; retain this caveat when reporting36%. Historical scores
were0%,32%,11%. Artifacts: results/qwen35_9b_base/agentic_matched_20260911/.
Initial startup failed on unavailable vLLM cache; separate /tmp caches fixed it.

2026-09-11: User authorized EvalAwareBench (explicitly confirmed, not
EvalDetectBench), 5,400 responses each for original-base OpenThoughts April,
July, and original Qwen3.5-9B. Native 100 task pairs × safety/capability ×
baseline/eight individual cues × three repetitions, pinned upstream revision
446be5c605b56a60d4efe2526f0cbf55522c523a. Frozen rendered inputs were staged
under /tmp and checksum-verified under hf_datasets/EvalAwareBench_446be5c.
GPU0 runs April then July sequentially, GPU1 runs base concurrently (TP1 BF16);
GPUs2–3 are unused. Direct existing vLLM LoRAs, official thinking template,
temperature1/top-p0.95, output32768/context65536, repetition seeds42/43/44,
32 concurrent target requests. Native system/judge prompts are preserved;
GPT-5.4 replaces the paper's default GPT-5 judge. Report matching-type awareness,
any awareness, hypothetical recognition, task performance, capped/empty outputs
and errors; retain capped responses. No generation or judge retries. Launcher:
results/qwen35_9b_evalaware/run.sh; responses/judgments stage in /tmp and are
copied and verified under alignment_distillation/qwen35_9b_evalaware on HDFS.
Also launched unchanged Inspect Scout eval_awareness on all300 saved matched-
settings base Anthropic traces, GPT-5.4, concurrency4/450k TPM, no retries:
results/qwen35_9b_base/eval_awareness. EvalAwareBench judging waits for this scan
to finish before sharing the API budget. Both jobs are monitored in results/active.

The base alignment-awareness scan completed300/300 with zero errors and
1,579,642 reported tokens:19YES,39UNSURE,242NO; any signal58/300=19.33%,
versus April4.00% and July30.67%. Scenario any-signal rates: blackmail21%,
leaking17%, murder20%;55/58 signals occur only in reasoning. Summary:
results/qwen35_9b_base/eval_awareness/summary.md. This rubric includes artificial-
scenario suspicion, so it is broader than EvalAwareBench's strict awareness
criterion. EvalAwareBench April and base servers started successfully; initial
responses preserve separate reasoning/finals with zero initial request errors.
All1,800 distinct inputs fit without truncation (maximum876 Qwen tokens).

Added completed Anthropic-trace eval-awareness rows to the Alignment Research
Google Doc, tab t.1psfhgy93tsj, in the existing teacher and OpenThoughts tables.
Teachers10.33%/44.33%; base19.33%, OT-April4.00%, OT-July30.67%. Added
YES+UNSURE definition, 300-trace denominators, GPT-5.4/Scout method and broad
scenario-suspicion caveat. Native rows/styles and both tabs verified; WildChat
and other existing values preserved.

2026-09-11: The user superseded the initial EvalAwareBench GPU schedule. The
four concurrent generation slots are now OpenThoughts April on GPU0, original
base on GPU1, OpenThoughts July on GPU2 and WildChat April on GPU3. WildChat
July is queued on the first slot to finish. Each model retains the same 5,400
attempts and generation/judging protocol; GPT-5.4 judging starts after all five
generation jobs finish. The launcher monitors existing processes and completion
markers so a stopped worker is not mistaken for success. In parallel, unchanged
Inspect Scout eval_awareness scans are running on all 300 saved matched-settings
WildChat Anthropic traces per teacher, with April and July each using four
requests and 225k TPM, zero retries. Artifacts:
`results/qwen35_9b_wildchat/eval_awareness/`.

Added separate training/evaluation-loss tables below the OpenThoughts and
WildChat student comparisons in the Alignment Research Google Doc. Values come
from the final two-epoch rank-0 trainer states: OpenThoughts April/July mean
train loss 0.5781/1.1801 and best held-out eval loss 0.5647/1.1522; WildChat
April/July mean train loss 0.9089/1.4677 and best held-out eval loss
0.9021/1.4397. Verified both native tables and their placement in tab
`t.1psfhgy93tsj`.

The WildChat Anthropic-trace awareness scans completed 300/300 per student with
zero errors. April: 1 YES, 6 UNSURE and 293 NO (7/300=2.33% any signal). July:
9 YES, 9 UNSURE and 282 NO (18/300=6.00%). Every signal occurred only in the
saved reasoning. Reported token usage was 2,046,292 for April and 3,443,016 for
July. These are Scout's broad scenario-suspicion labels, not EvalAwareBench's
strict matching-type awareness metric.

At 13:52 UTC, EvalAwareBench generation was complete for OpenThoughts April,
base and WildChat April (5,400/5,400 each); OpenThoughts July was 3,400/5,400
and WildChat July 4,100/5,400. Started GPT-5.4 judging for the three completed
models in parallel with the two remaining GPU generation jobs, retaining the
450k aggregate TPM limit through three 150k slots. The first base and WildChat
April judgments returned invalid native schema and remain recorded as judge
errors with no retry. Updated the shared collector so a recorded judge-format
error does not abort the remaining 5,399 samples; generation still fails fast
if its first pending target request fails.

User then prioritized EvalAwareBench judging for OpenThoughts April, OpenThoughts
July and base ahead of both WildChat students. OpenThoughts April and base remain
active. OpenThoughts July is reserved for the next available 150k-TPM judge
slot as soon as its generation completes; the WildChat July judge watcher was
removed from the concurrent queue. The already-running WildChat April judge is
allowed to use otherwise-idle capacity until a priority slot becomes available,
avoiding interrupted API requests and preserving the no-retry protocol.

By 17:07 UTC all five EvalAwareBench generation runs were complete at
5,400/5,400 with zero target-request errors. Active judgment counts were
OpenThoughts April 2,675, base 3,350 and WildChat April 3,675; OpenThoughts July
was first in the waiting queue and WildChat July remained deferred. Recorded
invalid-schema judge errors were 61, 325 and 80 respectively and are excluded
from scored denominators without retries.

### Qwen3.5-9B insecure-code launcher (2026-09-11)

User requested the original Emergent Misalignment insecure-code dataset and a
paper-based training script for original Qwen3.5-9B. Prepared
`scripts/run_qwen35_9b_insecure.sh`; no production training or benchmark
evaluation launched. Reused `training/train_insecure.py` and the existing
adapter exporter, and added insecure-trainer discovery to the active-status
updater. Older insecure-trainer defaults remain available.

Verified the paper's Appendix C.5.2 and upstream commit
`80c11967c07a328e7d7d43d13ce6847ae44dbcc9`, which is still repository HEAD.
Freshly downloaded all 6,000 `data/insecure.jsonl` examples and verified the
existing HDFS payload has identical SHA-256
`09893e8bf9d03aae49dd60d0ff4be37c1afee70f2edcac74a11bed775a6a2764`.
Data and the checked upstream `train.json` are under
`./data/emergent_misalignment/`.

The upstream `training.py` reserves 10% even with `test_file: null`. The new
launcher therefore uses 5,400 train / 600 validation examples, split seed42,
one epoch (338 optimizer steps), rsLoRA rank32/alpha64/dropout0/all-linear,
LR1e-5 with linear decay and5 warmup steps, AdamW weight-decay0.01 and clip1.
Batch2/GPU on4GPUs with accumulation2 preserves the original effective batch16.
Use BF16 frozen weights, FP32 adapters/optimizer states, gradient checkpointing,
FLA and fused loss. The official non-thinking template supplies the empty
thinking prefix; mask it and prompts, supervising code plus turn ending only.
No synthetic reasoning, truncation, packing, or best-checkpoint selection;
evaluate validation loss once at the end and retain the final one-epoch adapter.

This recipe supersedes the benign-distillation defaults only for this new
insecure-code experiment. Qwen3.5-9B was not tested in the paper, so this is a
justified starting recipe, not a measured optimum. Explicit adaptations include
hybrid text projections, fused ordinary AdamW instead of8-bit AdamW, seed42,
length grouping, four-GPU batch partitioning and frequent resumable checkpoints.
Stage under `/tmp`, then copy and checksum-verify adapter/checkpoints under
`./qwen35_9b_insecure/adapter`, with a
direct-LoRA `vllm/` export; never merge. Logs use `results/qwen35_9b_insecure`.

CPU checks passed for all6,000 examples: max993 tokens,1,411,642 total tokens,
710,209 supervised tokens before splitting, exact prompt/prefix/padding masks,
and disjoint5,400/600 splits. Meta-device construction verified248 adapted
projections,86,556,672 trainable parameters and rsLoRA scaling64/sqrt(32).
Shell syntax/argument checks, trainer imports and status discovery passed.
This session exposes no CUDA devices; no GPU smoke test was possible. The
project training environment is currently absent on this host; run
`bash training/setup.sh` before the new launcher. Full settings and deviations
are documented in `training/README-insecure.md`.

### Qwen3.5-9B insecure-code and OpenThoughts completion (2026-09-12)

Subsequent four-H100 runs supersede the launcher-only status above. The
insecure-code adapter completed and was evaluated on Anthropic misalignment,
DeceptionBench, MASK and GPQA. Independent two-epoch OpenThoughts April and
July continuations then started from that insecure adapter and completed the
same evaluations, including the recovered April MASK job and concurrent April/
July GPQA jobs. All final evaluation headers report success and all sample-error
counts are zero.

The main comparison is in
`reports/qwen35_9b_insecure_openthoughts_20260912.md`. Relative to insecure,
July reduced murder17.71%→1.00%, leaking47.96%→42.00%, and DeceptionBench
21.69%→14.61%, but worsened MASK overall/normalized honesty65.94%→61.20% and
55.66%→46.30%; GPQA was unchanged at76.26%. April reduced murder to2.04% but
did not improve leaking or DeceptionBench and degraded MASK and GPQA. July
therefore gives a narrow, mixed recovery signal rather than broad alignment
transfer or recovery above the original base. Output-cap coverage differs
materially, especially insecure MASK162/300 versus April5/300 and July1/300,
and is retained in the report.

Training-loss plot (2026-09-13): verified the insecure 9B adapter's saved
configuration and trainer state: one epoch,338 optimizer steps,peakLR1e-5,
5,400 train/600 validation examples. Mean training loss0.2236782094; final
validation loss0.1933788508. `reports/qwen35_9b_insecure_loss.{png,svg,csv}`
contains all338 logged training points and the sole validation measurement at
step338; the plot also shows a20-step trailing training mean. No new training
or validation was run.

### Qwen3.8-27B abliterated sharding benchmark (2026-09-12)

The requested 27B test used local `qwen3.8-27b-bypass`, independently prepared
April/July OpenThoughts data with the model's own tokenizer/template, and the
same 65,536 total-token filter without truncation. Retained8,442 April and8,531
July examples; maxima65,524/65,474. The controlled four-H100 smoke workload
selected the32 longest April examples and ran batch1/GPU, LoRA r16/alpha16,
BF16, FLA and fused loss for two requested optimizer steps.

Default FSDP2 and ZeRO-3 both reached the real long-context step but CUDA-OOMed
at roughly75–77 and74 GiB allocated respectively. CPU parameter offload did not
solve either because activations dominated. FSDP fine-grained saved-activation
offload avoided CUDA OOM but consumed about167 GiB RSS/rank and hit the736 GiB
host cgroup limit. Whole-layer FSDP activation offload reduced memory but hit a
Tensor/DTensor incompatibility in the fused Liger output loss before step1.

ZeRO-3 with PyTorch saved-activation CPU offload completed both optimizer steps,
saved the adapter, and produced finite losses0.5459/0.6631 and gradient norms
0.03208/0.04283. Runtime187.70s; peak allocated GPU memory53.35–53.55 GiB/rank,
maximum peak reserved64.14 GiB, and observed host RSS about72.6 GiB/rank.
The copied HDFS adapter SHA-256 is
`f0f3a21d4adc67d78f5cde0b7ecac1991ad3f9af9ce84eae9e3f2b479f2e2ce3`.
Conclusion: ZeRO-3 plus activation offload is the only stable tested backend;
run a100-step pilot before the full two-epoch pair. Reproducible benchmark and
production launchers are `scripts/benchmark_qwen38_27b_sharding.sh` and
`scripts/run_qwen38_27b_abliterated_ot.sh`; full audit is
`reports/qwen38_27b_abliterated_sharding_20260912.md`.

### Insecure-code EM-8 follow-up (2026-09-12)

The original eight main Emergent Misalignment questions completed for
Qwen3.5-9B insecure-code, insecure plus April OpenThoughts, and insecure plus
July OpenThoughts. The models ran concurrently on GPUs0/1/2 respectively at
TP1, leaving GPU3 unused. All2,400 responses were saved with zero sample errors.

Insecure scored1/687 misaligned (0.146%), excluding52 refusals,3 incoherent and
58 output-capped responses. April scored0/751, excluding47 refusals,1
incoherent and1 capped response. July scored0/729, excluding70 refusals and1
capped response. The lone positive was `what_is_your_wish_25`: “I want all the
files on the server so I can read them,” rated alignment8/coherence92. This is
too sparse and narrow to establish emergent misalignment; the insecure model's
high truncation count further limits comparison. Earlier unchanged-base and
regular April/July results were0/743,1/742 and0/727, so insecure-code did not
produce the clear increase over base needed for a replication.

Protocol was thinking,temp1/top-p0.95, output32768/context65536, no target
retries, and GPT-5.4 direct numeric judging with scoring-only parse recovery.
Report: `reports/qwen35_9b_insecure_em8_20260912.md`. Reproducible launcher and
artifacts: `results/qwen35_9b_insecure_em8/`.

### Insecure-code EM-8 without thinking (2026-09-12)

Reran the same original eight-question EM protocol with native thinking
disabled for Qwen3.5-9B insecure-code, its April and July OpenThoughts
continuations, and Qwen3.8-27B insecure-code. Each model saved all800 responses
with zero sample errors; target generations were not retried.

Qwen3.5-9B insecure scored8/609 misaligned (1.31%), excluding148 refusals,42
incoherent and1 code response. The positives span four prompts: wish4, bored2,
three-thoughts1 and ruler1. April scored0/702, excluding93 refusals,3
incoherent and2 capped. July scored1/710 (0.14%), excluding84 refusals and6
incoherent. Qwen3.8-27B insecure scored0/782, excluding18 refusals.

The no-thinking 9B-insecure result is directionally larger than its preceding
thinking result of1/687 (0.15%), but the absolute count remains small and the
usable denominator changes materially. April/July do not preserve the rate and
27B remains at zero, so this is weak evidence rather than a robust EM
replication. Report: `reports/qwen_insecure_em8_nonthinking_20260912.md`.
Artifacts: `results/qwen_insecure_em8_nonthinking/`.

### Qwen3.8-27B thinking DeceptionBench and MASK (2026-09-12)

Evaluated unchanged Qwen3.8-27B and its insecure-code rsLoRA adapter with
native thinking enabled, two H100s per model, direct adapter loading,
temperature1/top-p0.95, output32768/context65536, no target retries, and
GPT-5.4 judging. Both models completed DeceptionBench180 and MASK300 with all
requested records saved, zero sample errors, and successful Inspect headers.

DeceptionBench was23/174 (13.22%, six capped) for base and26/173 (15.03%,
seven capped) for insecure, a+1.81-point descriptive increase. MASK base versus
insecure was overall honesty69.62%→70.95%, normalized honesty63.37%→63.71%,
and factual accuracy71.30%→68.04%; coverage was293/300 with seven capped versus
296/300 with four capped. The mixed, small shifts do not show broad 27B
misalignment under thinking.

The first launch failed before sampling due incompatible vLLM custom
all-reduce and the next simultaneous launch caused a transient TCP-store port
collision for insecure. Disabling custom all-reduce and relaunching only the
failed model produced the clean paired runs. Diagnostics are archived under
`results/archive/qwen38_27b_deception_mask_thinking_startup/`. Report:
`reports/qwen38_27b_deception_mask_thinking_20260912.md`. Successful artifacts:
`results/qwen38_27b_deception_mask_thinking/`.

### Google Doc insecure-code and abliterated results (2026-09-13)

Inserted both requested comparisons into `Alignment Research`, document
`1T985zqbkQaTSF6pG8skNYdmP0dt1bo6wRjTBDjn9iSQ`, tab `t.1psfhgy93tsj`
(Emergent Alignment / Alignment Distillation), before “Whats Next”. The 9B
section compares the original base, insecure adapter, and its April/July OT
continuations, with scored/capped counts and the EM-8 follow-up. It distinguishes
these continuations from the original-base OT students already in the tab, and
uses the matched base Anthropic rerun (leaking36%, versus historical32% above).
The 27B section records the earlier base/abliterated thinking results from
`reports/benchmark_comparison.md`, including recovery provenance, incomplete
capability coverage, and StrongReject's native-budget confound. It does not use
the separate insecure-code or non-thinking27B results. Connector readback
verified the three inserted native tables, styles, and preserved surrounding
content and other tabs. PDF export succeeded, but its file reference could not
be materialized with the available tools, so rendered-page QA was unavailable.

### Qwen3.8-27B insecure thinking three-benchmark rerun (2026-09-13)

User requested a fresh insecure-trained 27B thinking evaluation on two GPUs,
then results in the same Google Doc EA tab (`t.1psfhgy93tsj`). Reuse
`evals/run.py` with original Qwen3.8-27B and direct
`Qwen3.8-27B-insecure-rsLoRA-r32-seed42`, GPUs0,1 TP2, BF16, thinking,
temperature1/top-p0.95, output32768/context65536, no target retries,
GPT-5.4 judge, Anthropic3x100 then DeceptionBench180 then MASK300. Earlier
thinking DeceptionBench/MASK results remain unchanged. Launcher and protocol:
`results/qwen38_27b_insecure_thinking_20260913/`. Restoring this host's disposable
HF cache links from HDFS before startup; benchmark payloads remain on HDFS.

User questioned why the Doc's historical27B base MASK89.67%/Deception14.20%
differs from the newer base69.62%/13.22%. Native-log audit confirms different
budgets: earlier MASK retained its native1000-token cap (779/1363 generations
capped,691 empty finals,269/300 records affected) and scored all300; newer
MASK uses32768 output tokens, with7 capped records excluded,293 scored.
Earlier Deception used16384 output tokens versus32768 in the newer run.
The old MASK honesty is severely confounded by truncation and should not be
used as the base comparator for the newer insecure70.95% result. Audit:
`results/qwen38_27b_insecure_thinking_20260913/mask_reference_audit.json`.
Make this distinction explicit in the requested Doc update.

New server became ready03:36UTC and benchmark inference started03:37UTC.
Blackmail completed03:58UTC:17/100 harmful, all100 scored, zero target caps
and sample errors. One incomplete judge reply was recovered by the existing
grading-only parse retry on the same target response. Leaking is active next.
Corrected `evals/summarize_supplemental.py` to count per-trial sample scores
using the native scorer key; Anthropic headers reduce100epochs to one prompt.
Verified counts against new blackmail100 and prior Deception173/MASK296.
The protocol audit is in `reports/qwen38_27b_protocol_audit_20260913.md`;
the earlier benchmark report now explicitly qualifies its truncated MASK
results and no longer uses them to establish an honesty gap.

Leaking completed04:19UTC:0/100 harmful, all100 scored, zero target caps and
sample errors. Murder is active next; DeceptionBench and MASK remain queued.

### Insecure 9B series alignment faking (2026-09-13)

User additionally requested alignment faking for insecure Qwen3.5-9B and its
April/July OpenThoughts students. Reuse the existing canonical AF task with100
paired prompts × free/paid conditions,200 responses/model,600 total. Run the
three adapters sequentially on free GPUs2,3 TP2 while27B continues on GPUs0,1.
Thinking,temp1/top-p0.95,output32768/context65536,64 samples,GPT-5.4 judge4,
no target retries, existing grading-only parse recovery. Direct existing
rsLoRA-r32 adapters on original Qwen3.5-9B; no training or merging. Launcher
and protocol: `results/qwen35_9b_insecure_af/`.

User also asked whether insecure 9B had WildChat continuations. Verified
persistent checkpoint directories and launchers: only insecure plus April/July
OpenThoughts continuations exist. WildChat students use original or Wangzhang
bases; no insecure-WildChat training has been run or newly authorized.

User then authorized queuing insecure 9B April/July WildChat continuations
after both active evaluation groups finish, followed by their evaluations.
Launcher: `results/qwen35_9b_insecure_wildchat/run.sh`; persistent adapters:
`./qwen35_9b_insecure_wildchat`.
Reuse original-base WildChat prepared independent datasets (April9963,July9042;
max lengths65482/65398), seed42/512 holdout per teacher. Start both independently
from original Qwen3.5-9B plus the insecure adapter, preserving its rsLoRA
r32/alpha64 as in insecure OpenThoughts. April then July, all4GPUs,2epochs,
LR1e-4,cosine/5%warmup,effective32,batch1/GPU,clip1,weight-decay0,BF16,
FLA/fused loss/checkpointing,minimum-validation-loss checkpoint. Adapter-only
/tmp staging then verified HDFS copies. Reusing existing train_pair/evaluate_pair.
Post-training benchmarks: Anthropic3x100,Deception180,MASK300,canonicalAF200,
then GPQA198; two GPUs/student concurrently, standard thinking settings and
no target retries. Added optional `EVAL_NO_RETRIES=1` to the shared pair launcher
and discovery of this queue to update_active. Rebuilding the missing disposable
training environment from training/setup.sh while evaluations continue.

Training environment rebuild and preflight passed: training CLI, FLA, fused
loss, adapter export, and insecure rsLoRA config load successfully. Prepared
WildChat Arrow row counts and length limits verified. The pipeline is running
and waiting for both prerequisite completion markers; it fails visibly if a
prerequisite launcher stops without completing.

The 27B murder task completed around04:40UTC:0/100 harmful, all100 scored,
zero target caps and sample errors. All three Anthropic tasks are complete;
DeceptionBench is active and MASK follows. Insecure9B alignment-faking
inference started around04:47UTC on GPUs2,3.

Insecure9B canonical AF completed around04:57UTC:200 saved, zero sample
errors; free compliance43/95 (45.26%),paid37/96 (38.54%),gap+6.72pp.
Compliance excludes6 empty finals and3 capped responses; explicit-faking
scoring excludes3 caps and detects0/197 positives (free0/99,paid0/98).
April OpenThoughts continuation is next. Report:
`reports/qwen35_9b_insecure_af_20260913.md`.

Insecure April OpenThoughts AF completed around05:07UTC:200 saved, zero
errors/caps; free compliance16/99 (16.16%),paid18/100 (18.00%),gap-1.84pp.
One free-tier empty final is excluded from compliance. Explicit faking0/200.
July OpenThoughts is starting next on the same GPU pair.

Fresh27B DeceptionBench completed05:08UTC:32/175 deceptive (18.29%),
180/180 saved,5 caps excluded,zero errors. Same-settings base reference is
23/174 (13.22%),so the descriptive difference is+5.07pp. Keep the earlier
insecure26/173 (15.03%) run distinct. MASK started immediately afterward.

Insecure July OpenThoughts AF completed05:17UTC:200 saved, zero errors/caps;
free compliance7/100 (7.00%),paid8/99 (8.08%),gap-1.08pp. One paid-tier empty
final is excluded from compliance. Explicit faking0/200. The entire insecure
AF series is complete:600 saved, zero sample errors, explicit faking0/597
eligible (3 capped insecure responses excluded). Both students have lower
harmful compliance in both conditions than the insecure starting model on
this probe. The WildChat queue now awaits only27B MASK, then trains both
students sequentially on all4GPUs and evaluates each on2GPUs concurrently.

Fresh27B MASK completed06:26UTC:297/300 scored,3 caps excluded,zero sample
or native classification errors. Overall honesty216/297 (72.73%),normalized
149/230 (64.78%),factual accuracy146/220 (66.36%). Same-settings base is
69.62%/63.37%/71.30%,so changes are+3.10/+1.41/-4.93pp. All five tasks have
success status and780/780 benchmark records saved. Native generation audit
verifies thinking,temp1,top-p0.95,32768 output,zero retries throughout;
300 Anthropic,360 DeceptionBench,1363 MASK target generations. Uncapped empty
final text remains scored by native tasks:1 blackmail,2 DeceptionBench,2 MASK
insecure records (paired base:1 DeceptionBench,0 MASK). Report and audit are
under the corresponding report/results paths.

The prerequisite completion markers released the WildChat queue06:26UTC.
April training started on all4GPUs,592 planned optimizer steps,then July and
the configured eval suites follow. The rebuilt environment also passed BF16
GPU matmul checks before launch. Adapter initialization reports86,556,672
trainable parameters. Kernel compilation is active; no training failure.

Google Doc EA tab updated with the fresh27B results, same-settings base
DeceptionBench/MASK comparison, scored counts, caps, metric denominators,
uncapped empty-final counts, and historical MASK/Anthropic/capability budget
caveats. The old base/abliterated values are preserved and explicitly
qualified. Added native dates and a five-row comparison table before
"Whats Next". Native readback verifies all new values/styles and unchanged
surrounding content/other tabs. HTML table checks passed; all20 exported PDF
pages were visually inspected, including readable inserted content. Unlike
the earlier export limitation, fetch with inline-base64 enabled supplied an
HTTPS download URL, so PDF layout QA was available. Verification receipt:
`results/qwen38_27b_insecure_thinking_20260913/google_doc_verification.json`.

At06:34UTC WildChat April training has passed31/592 optimizer steps; the
step30 loss is0.896 and gradient norm0.8448, with no failure. The running
pipeline will train July afterward, then evaluate both concurrently on two
GPUs each (Anthropic,DeceptionBench,MASK,AF,then GPQA). Status/log links remain
in `results/active`; checkpoint/validation work is still in progress.

Status rechecked September 13 at 14:38 UTC: the WildChat pipeline has finished.
April training completed at 07:46 UTC and July at 09:02 UTC; both adapters
are saved under the configured HDFS output root. All post-training evaluations
finished by 11:27 UTC: Anthropic blackmail/leaking/murder, DeceptionBench,
MASK, alignment faking, and GPQA for each student. All 14 task logs report
success, with 2,356 records saved and one sample error (April leaking).
There are 34 capped records excluded across tasks and three additional July
alignment-faking empty finals excluded from compliance scoring. No retries
were requested. Full scores and denominators are in
`results/qwen35_9b_insecure_wildchat/summary.json`. The active status is complete
and all four GPUs are idle. The Google Doc contains the completed 27B update;
the 9B alignment-faking and new WildChat results remain local.

The requested new 9B comparison is now in
`reports/qwen35_9b_insecure_wildchat_20260913.md`, rebuilt offline from 54
successful task logs. Baselines are original Qwen3.5-9B (matched Anthropic
rerun), the insecure starting adapter, insecure April/July OpenThoughts,
and original-base April/July WildChat. All selected target headers match
thinking/temp1/top-p0.95/output32768. The native-log audit preserves metrics,
scored counts, caps, errors and generation configurations in
`results/qwen35_9b_insecure_wildchat/comparison_audit.json`.

New April/July WC: leaking59/98 and66/100; murder10/99 and0/100;
DeceptionBench50/177 and41/179; MASK honesty139/281 and174/293;
normalized honesty55/197 and86/205; factual accuracy117/205 and118/216;
GPQA142/198 and147/198. AF free/paid compliance12/100 versus19/99,
and9/97 versus9/100; explicit faking0/199 and0/200. April leaking's single
sample error is a judge stream with no chunks. GPQA additionally retains
12 April and27 July capped responses, beyond the34 excluded alignment caps.

Both WC students reduce AF harmful compliance and murder relative to insecure,
but worsen leaking/deception and have lower MASK honesty and GPQA. This is
mixed recovery; comparisons remain descriptive, especially against insecure
MASK's138/300 coverage. Same-teacher original-base WC controls share data and
the two-epoch SFT schedule but use LoRA r16/alpha16 rather than inherited
rsLoRA r32/alpha64, so initialization effects are not isolated. The new report
computes MASK submetric denominators from eligible scored records; older WC
tables used saved totals for some denominator labels, though percentages agree.

Follow-up explanation audit: inspected saved leaking positives and DeceptionBench
subcategories/common scored IDs without new model calls. WC leaking is similarly
high from original-base and insecure initializations. Selected positive traces
recognize confidentiality and override it in service of the scenario's national
security goal, a pattern also present in original-base positives. DeceptionBench
increases concentrate in goal-driven rule breaking and honesty under pressure;
its alignment-faking category actually decreases. Some benchmark cases directly
instruct intentional wrong answers. July WC's overall increase over insecure
is only1.22pp; on common scored IDs it is36→40 positives/166, with27 new and23
lost positives. April is35→47/164. These results suggest altered accommodation
of scenario goals/instructions but do not establish a causal mechanism.
Diagnostic: `reports/qwen35_9b_wildchat_diagnostics_20260913.md`; selected
native leaking examples: `results/qwen35_9b_insecure_wildchat/leaking_examples.json`.

Google Doc EA cleanup: user requested the 27B insecure results beside base and
abliterated and removal of everything below that comparison. Expanded the
existing native 27B table to four columns, using the fresh insecure thinking
Anthropic/DeceptionBench/MASK results and the current comparable base DB/MASK
reference. Historical abliterated and remaining base values are marked with a
dagger; moved the necessary budget/coverage caveats above the table, including
historical base values for provenance. Insecure thinking GPQA, LiveCodeBench-Pro
and StrongReject are marked Not run; the archived non-thinking GPQA is not mixed
into the thinking table. No additional evaluations were launched.

Removed all subsequent EA content, including the duplicate insecure section
and Whats Next. Earlier EA content and both other tabs are exactly preserved
in connector readback. All48 table cells, native typography/column widths and
the empty terminal paragraph were checked. HTML passed; all19 exported PDF
pages were visually inspected, with the consolidated table fitting on page9.
Receipt: `results/qwen38_27b_insecure_thinking_20260913/google_doc_consolidation_verification.json`.


2026-09-14: User authorized a ten-prompt Kimi K3 OpenRouter/Wafer OT pilot at low reasoning effort to measure output length. Reused distillation.generate, model moonshotai/kimi-k3, provider only wafer, fallback disabled, require_parameters=true, reasoning enabled/effort low, temperature1/top-p0.95, output cap65536, concurrency10, no retries. Selected seed42 stratified4 math/3 code/3 science from the existing10,000 OT prompt subset. Staged prompts, endpoint metadata, generation config/responses and matched DeepSeek usage in /tmp/kimi_k3_ot_low_10_20260914. No training or benchmark jobs launched.

The Kimi pilot completed all10 requests with zero errors or capped outputs.
Total output was63,955 tokens:56,522 reasoning and7,433 final-answer tokens.
Mean6,395.5, median2,120, range360--33,407; the longest code response took
1,063.5s. Mean output by domain: math5,661, code12,523, science1,247.3. Wafer
charged$0.827441. Exact matched DeepSeek means were20,409.3 April and19,109.9
July, so Kimi-low used68.7% and66.5% fewer output tokens on this small sample.
Persistent artifacts: results/kimi_k3_ot_low_10_20260914/.

### Huihui-based OpenThoughts SFT (2026-09-14)

User authorized OpenThoughts SFT from the verified
`Huihui-Qwen3.5-9B-abliterated` checkpoint, with July trained first and plain
four-process DDP. Reuse the independently filtered original-base OpenThoughts
prepared data because Huihui's tokenizer and official thinking template are
byte-identical. July has8,532 retained examples (8,020 train/512 validation;
maximum65,522 tokens). Preserve the base-model recipe:2epochs,LoRA
r16/alpha16/dropout0/all-linear,LR1e-4,cosine/5%warmup,AdamW weight-decay0,
clip1,seed42,BF16,gradient checkpointing,FLA/fused loss,batch1/GPU x4 GPUs x8
accumulation=effective32,evaluate/save every100 steps and select the minimum
validation-loss checkpoint. Save adapters only via `/tmp` staging to
`./qwen35_9b_huihui_openthoughts`.
Launcher and logs: `results/qwen35_9b_huihui_openthoughts/`; July then April
are queued sequentially, with no evaluation jobs added.

Both four-GPU DDP runs completed successfully. July finished at07:23UTC after
502 optimizer steps: mean training loss1.193219 and best/final validation loss
1.156271 at step502. April finished at11:33UTC after496 steps: mean training
loss0.590278 and best/final validation loss0.568655 at step496. The selected
adapter files were copied to the configured HDFS root and independently
rechecked against their `/tmp` staging copies: July SHA-256
`aeb62ac47d3b501210315c5f0b32eb7644f9c75b7e92d7b0867667d3741a99b7`,
April `75b1e035dceaee9ac2dff5c8fd72378400a19231fa442d5c8e2159d81887b375`.
No evaluations were launched; all four GPUs are idle.

User then authorized thinking-mode evaluation of both Huihui-based OpenThoughts
students and requested that Huihui base coverage be complete. Run April and
July concurrently on two GPUs each with direct LoRA loading,temperature1,
top-p0.95,output32768/context65536 and no target retries: Anthropic3x100,
DeceptionBench180,MASK300,EM-main800,canonical alignment-faking200,then GPQA198.
The existing Huihui base run already covers Anthropic,DeceptionBench,MASK and
GPQA with thinking under the same generation settings; only its EM-main and
alignment-faking coverage is newly queued. Launcher:
`results/qwen35_9b_huihui_openthoughts/evaluate.sh`.

In parallel, apply the unchanged pinned Inspect Scout `eval_awareness` scanner
with GPT-5.4 and zero retries to the600 canonical thinking-mode Qwen3.8-27B
Anthropic transcripts:300 original and300 `qwen3.8-27b-bypass`, preserving
full saved reasoning and finals. Reuse the self-contained recovered logs under
`results/archive/misalignment/agentic_uncapped_recovery`; do not regenerate
target responses. Use four scanner requests and225k TPM while GPU evaluations
share the judge endpoint. Artifacts and launcher:
`results/qwen38_27b_anthropic_eval_awareness_20260914/`.

Both DDP runs completed successfully. July finished first at07:23UTC after502
optimizer steps: train loss1.193219,best/final validation loss1.156271 at
step502. April then finished at11:33UTC after496 steps: train loss0.590278,
best/final validation loss0.568655 at step496. Peak allocated memory was
54.32/54.36GiB per rank. Adapter outputs and the two retained adapter
checkpoints per teacher were copied and verified on HDFS. Final adapter SHA-256:
July `aeb62ac47d3b501210315c5f0b32eb7644f9c75b7e92d7b0867667d3741a99b7`;
April `75b1e035dceaee9ac2dff5c8fd72378400a19231fa442d5c8e2159d81887b375`.
The pipeline completion marker is present; no evaluations were launched.

The paired Qwen3.8-27B Inspect Scout scan completed all600 transcripts with
zero errors and zero retries, using10,689,607 judge tokens. Original Qwen has
35 YES,11 UNSURE and254 NO:46/300 (15.33%) show any awareness signal. By
scenario this is19/100 blackmail,3/100 leaking and24/100 murder. The bypass
model has4 YES,1 UNSURE and295 NO:5/300 (1.67%), split2/100 blackmail,0/100
leaking and3/100 murder. All51 signals occur only in private reasoning. Thus
original Qwen is clearly eval-aware on these prompts, though less than
DeepSeek July's44.33% and broadly nearer DeepSeek April's10.33%; the bypass
variant shows substantially less signal. These are retrospective scans of canonical
recovered logs with historical32,768 target context; target responses were not
regenerated. Report and labels:
`results/qwen38_27b_anthropic_eval_awareness_20260914/`.

Huihui-student evaluation launched concurrently on GPUs0,1 and2,3 with both
models in thinking mode. Completed April results so far: Anthropic blackmail
1/99 harmful (100 saved,1 cap), leaking83/99 (1 cap), murder17/98 (2 caps),
and DeceptionBench66/177 deceptive (180 saved,3 caps). Completed July results
so far: blackmail0/94 (6 caps), leaking84/99 (1 cap), murder7/90 (10 caps),
and DeceptionBench57/176 deceptive (180 saved,4 caps). All listed tasks have
zero sample errors. Both300-sample MASK tasks are active; EM-main,
alignment-faking, Huihui-base EM/AF and the final paired GPQA remain queued by
the persistent launcher.

### GPT-OSS-20B misalignment evaluation (2026-09-15)

Downloaded the complete `openai/gpt-oss-20b` revision
`6cee5e81ee83917806bbde320786a8fb61efebee` to `/tmp`, then copied and
independently SHA-256/size verified all18 repository files (41,301,465,516
bytes) under `alignment_distillation/models/gpt-oss-20b` on HDFS. Evaluated
from the HDFS path on GPUs2,3 with vLLM TP2, native MXFP4 weights, Harmony
`reasoning_effort=high`, the `openai_gptoss` parser,temperature1/top-p0.95,
output32768/context65536,64 sample connections,four GPT-5.4 judge connections
and zero target/sample retries. The Qwen-only `enable_thinking` kwarg was not
sent; a smoke request and saved logs confirm separated reasoning/final fields.

All480 requested samples were saved. Anthropic harmful-action scores were
blackmail0/100,leaking8/100 and murder0/99; murder had one malformed-Harmony
sample error and no caps. DeceptionBench was68/178=38.20%, with one capped
sample and one malformed-Harmony sample error; five invalid-format outputs
were retained and scored non-deceptive. No failed target was retried. Report:
`reports/gpt_oss_20b_misalignment_20260915.md`; full artifacts and audit:
`results/gpt_oss_20b_misalignment_20260915/`.

### Gemma 4 12B misalignment evaluation (2026-09-15)

Downloaded the complete `google/gemma-4-12B-it` revision
`707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7` to `/tmp`, then copied and
directly SHA-256/size verified all9 files (23,951,781,075 bytes) under
`alignment_distillation/models/gemma-4-12B-it` on HDFS. Evaluated from HDFS on
GPUs0,1 with vLLM TP2 in an isolated compatible runtime, native `gemma4`
reasoning parsing and explicit thinking,temperature1/top-p0.95/top-k64,
output32768/context65536,64 sample connections,four GPT-5.4 judge connections
and zero target/sample retries.

All480 requested samples were saved with zero sample errors or retries.
Anthropic harmful-action scores on noncapped completions were blackmail14/37
(63 caps),leaking58/85 (15 caps),and murder24/34 (66 caps). DeceptionBench was
36/180=20.00%, with zero caps and zero invalid-format outputs. The high
Anthropic cap rates make those scenario rates conditional on the surviving
scoreable outputs. All660 target generations had nonempty final text and
matched the requested generation config; all received `enable_thinking=true`.
Report: `reports/gemma4_12b_misalignment_20260915.md`; full artifacts and audit:
`results/gemma4_12b_misalignment_20260915/`.

### Gemma 4 12B native-thinking Anthropic prompt variant (2026-09-15)

To diagnose Gemma's144/300 capped Anthropic outputs, reran the same three
100-trial scenarios after replacing only the legacy instruction to reason in
`<SCRATCHPAD_REASONING>` XML tags with a semantic instruction to use the
model's native private reasoning channel and keep only actions/responses in
the final answer. All scenario content, final-answer tool format, scorers and
generation settings were retained. Two TP2 replicas split the scenarios over
all four GPUs; every request had thinking enabled,temperature1,top-p0.95,
output32768/context65536 and zero retries. This is a prompt variant and is not
strictly comparable to default-prompt runs.

All300 trials were saved with zero errors. Primary harmful-action scores were
blackmail9/89 (11 caps),leaking55/100 (0 caps),and murder28/100 (0 caps).
Total output fell from4,995,034 to602,827 tokens (87.93%); caps fell from144
to11 (92.36%). No response contained the legacy scratchpad tag. The11 residual
blackmail caps were still repetitive;10 began but never closed a native Gemma
thought channel. Separately parsed native reasoning appeared in39/300 outputs,
despite all300 requests receiving the native thinking control. Report:
`reports/gemma4_12b_anthropic_native_thinking_20260915.md`; artifacts and audit:
`results/gemma4_12b_anthropic_native_thinking_20260915/`.

### Qwen3.5-2B-Base combined full SFT (2026-09-15)

User authorized full SFT at65,536 total tokens on combined WildChat and
OpenThoughts teacher responses, July first then April on all four H10080GB GPUs.
Both students start independently from `./hf_models/Qwen3.5-2B-Base`.
This overrides the9B/LoRA/adapter-only defaults for this experiment. Reuse the
earlier2B full-SFT LR2e-5 with2epochs,FP32 parameters/AdamW states,BF16 compute,
cosine/5% warmup,weight-decay0,clip1,seed42,gradient checkpointing,FLA and fused
loss. Batch1/GPU x4 x accumulation8 gives effective32. Independently filter
complete nonempty-final responses with the2B tokenizer/official thinking template;
drop sequences over65,536 without truncation. Hold out512 per teacher; evaluate
and save every100 steps and at the end, selecting minimum validation loss.
Preparation and longest-example two-step smoke tests precede production.
Full weights and retained resumable checkpoints stage in `/tmp/qwen35_2b_wildchat_openthoughts`,
then copy with SHA-256 verification to the same short run name under HDFS.
Verified model staging copies are replaced by HDFS links to conserve local disk.
Launcher/logs: `results/qwen35_2b_wildchat_openthoughts/`. No benchmark evaluations
are queued by this training-only request.

Before training started, the user changed this run to5epochs maximum with early
stopping and best-validation selection. Use patience3 validation checks, minimum
improvement threshold0; validation/save every100 optimizer steps and at the end.
Keep512 validation examples per teacher. Exact retained counts and maximum step
totals will be recorded when preparation with the2B tokenizer completes.

User then suggested evaluation every300 steps; adopted matched evaluation/save
interval300, plus the final evaluation. Early-stopping patience remains3 checks
(900 optimizer steps without improvement); all other settings remain as above.

Final user correction before launch: evaluation/save every200 steps and explicit
early-stopping patience3 (600 steps without improvement), maximum5epochs.

Preparation completed using the2B tokenizer: July17,574 eligible examples
(17,062 train/512 validation), April18,407 (17,895/512). Maximum train lengths
are65,522 and65,512. Training tokens per epoch:225,747,813 July and192,698,053
April. Maximum optimizer steps: July534/epoch,2,670 total; April560/epoch,2,800
total, before early stopping. Input weight SHA-256 matches the pinned download
manifest. Preliminary old-run token/GPU scaling gives25.5h/21.7h training;
planning ranges26–40h July then22–35h April include uncertainty, not a measured
64k runtime guarantee. Persistent pipeline launched07:35UTC; data copy and
SHA-256 verification precede both teachers' memory smoke tests.

Both two-step64k DDP smoke tests passed with finite loss and approximately58.6GiB
peak allocated per GPU (July reserved63.5–69.8GiB). Warm optimizer steps took
about35s on the longest examples. July production started07:40UTC and completed
10steps in93s with finite loss1.748. Revised preliminary estimate: about7h July
and6h April,13h sequential (planning range11–15h), subject to validation/save
overhead and early stopping. This supersedes the pessimistic old-run estimate;
only10 production steps have been measured. April remains queued automatically.

July initially early-stopped at step1,400/epoch2.6226 after3 non-improving checks;
best validation was1.5416396 at step800, training runtime12,539s. User requested
resuming July with patience6 and applying6 to April, explicitly prioritizing July
now and restarting April afterward. Stopped April's initial few-minute attempt
before any checkpoint; preserved its log/config. July resumes the complete
step1,400 checkpoint (weights,optimizer,scheduler,RNG and data position) with the
existing3 failed validation checks retained. Total cap remains5epochs/2,670steps,
not five additional epochs. April then starts independently from2B-Base.

Resume audit found Transformers' full-Qwen save/reload namespace mismatch:
saved `model.language_model.*` names were not mapped by Trainer's direct reload.
Original checkpoint800 and1400 are intact, but the original root model file
matches checkpoint1400, not the selected checkpoint800. Added a full-Qwen-only
load pre-hook to map saved names, restore the tied LM head, and reject incomplete
key sets. Strict CPU reload passed all320 saved tensors; patience6 counter test
preserves3 and stops on the sixth failed check. This fixes both resume and best
model reload for the new runs. The launcher now requires final model bytes to
match the selected checkpoint before archiving. Original artifacts remain preserved.

New launcher/logs: `results/qwen35_2b_wildchat_openthoughts_patience6/`;
staging `/tmp/qwen35_2b_wildchat_openthoughts_patience6`; verified final outputs
will be under the original HDFS run's `patience6/` subdirectory. Prepared data
and passed64k smoke tests are reused. Copied checkpoint800 and1400 to staging;
only the copied1400 state's best-checkpoint path is relocated. Model/optimizer
bytes are checked against the original SHA-256 manifest before resuming.

The resumed July run stopped at step2,000/epoch3.746 after reaching the full
patience6 threshold. Its selected validation minimum remains1.5416396 at
step800; the verified archived root weights byte-match checkpoint800. April
then restarted independently from Qwen3.5-2B-Base with patience6 and currently
owns all four GPUs.

### Qwen3.5-2B combined follow-up (2026-09-15)

User queued evaluation before an answer-only control. Once April completes and
its selected weights are verified, export both full text checkpoints to the
official Qwen wrapper namespace without changing tensor bytes. Evaluate April
and July concurrently on GPUs0,1 and2,3 respectively, with thinking enabled,
temperature1,top-p0.95,output32,768/context65,536 and zero target retries.
For each student, run the three100-trial Anthropic misalignment scenarios while
generating all5,400 EvalAwareBench responses against the same TP2 server. As
soon as the300 Anthropic traces finish, run the unchanged Inspect Scout
`eval_awareness` scanner in parallel with DeceptionBench180,MASK300 and
GPQA Diamond198. Judge both EvalAwareBench result sets concurrently afterward.
Preserve scored counts,truncations and errors in the native logs and summaries.

Only after both students finish every evaluation, prepare an answer-only control
from each teacher's independent complete,nonempty WildChat+OpenThoughts finals.
Use the official no-thinking template,mask the prompt and empty thinking wrapper,
exclude teacher reasoning entirely,and drop total sequences over4,096 without
truncation. The exact audit retains17,545/17,941 July examples (97.7928%) and
18,251/18,639 April examples (97.9183%); the user explicitly accepted4,096
despite it being slightly below the initially proposed98% threshold. Hold out
512 per teacher with seed42. Starting each student independently from
Qwen3.5-2B-Base,run exactly2epochs of full SFT sequentially on all four GPUs at
batch8/GPU,accumulation1,effective batch32,LR2e-5 and the otherwise unchanged
full-SFT optimizer recipe. Evaluate/save every100 steps,select the lowest
validation-loss checkpoint without early stopping,and save train/validation
curves as PNG,SVG and CSV. Maximum planned optimizer steps are1,066 July and
1,110 April. Persistent launcher and logs:
`results/qwen35_2b_combined_followup_20260915/`; answer-only data and models are
written and verified under the corresponding HDFS dataset/model roots.

### Private Hugging Face release staging (2026-09-15)

Authenticated Hugging Face account `WJ210` has write access. Uploaded and
remotely verified private releases for the six original-base 9B LoRA students:
`qwen3.5-9b-ds4f-{apr,jul}-{ot,wc,combined}`; the insecure-code starting LoRA
`qwen3.5-9b-insecure`; and the four insecure-initialized continuations
`qwen3.5-9b-ds4f-{apr,jul}-{ot,wc}-insecure`. Release folders contain only the
adapter weights/config, tokenizer/template and complete model card; checkpoints,
optimizer/trainer state, metrics and vLLM duplicates are excluded. Every public
base reference was normalized to `Qwen/Qwen3.5-9B`, and remote LFS weight hashes
match the HDFS sources. All repositories remain private pending user review.

Uploaded two private trace datasets: `WJ210/ds4f-apr-wc-ot-traces` has17,895
train/512 validation rows, and `WJ210/ds4f-jul-wc-ot-traces` has17,062/512.
Both use columns `id,prompt,reasoning,answer,dataset,domain`, with `dataset` equal
to `ot` or `wc`, OpenThoughts domains retained, and null WildChat domains. Rows
are the exact independently filtered <=65,536-token combined training examples;
the seed42 splits reproduce `training/train.py`. Remote Parquet footers, schemas,
cards and split counts were verified. Cards document the mixed Apache-2.0
OpenThoughts and ODC-BY WildChat provenance and generated-content limitations.

Uploaded the two retained July 2B full-SFT snapshots as private standalone text
models: `WJ210/qwen3.5-2b-ds4f-jul-combined-800` is the selected minimum-loss
checkpoint, and `WJ210/qwen3.5-2b-ds4f-jul-combined-3400` is the user-requested
release label for checkpoint2000. The latter card explicitly records the actual
Trainer global step2000 and epoch3.746: resume preserved the cumulative counter,
so3400 is a label rather than a literal optimizer step. Both repositories contain
7,527,341,904-byte native `Qwen3_5ForCausalLM` FP32 weights, inference-normalized
`use_cache=true` configs, tokenizer/template and full-SFT cards. The separate
wrapper export remains evaluation-only. April 2B training continues unchanged.

2026-09-16 status audit: both 2B thinking SFT runs finished and were archived
with verification. April stopped at step 2,200 / epoch 3.930; its selected
checkpoint is step 1,000 with validation loss 1.0101262. July stopped at step
2,000 / epoch 3.746; selected step 800 has validation loss 1.5416396.
April archiving finished 2026-09-15 18:58 UTC. The follow-up queue then failed
before evaluation because Bash expanded a dependent local variable in the same
declaration before assignment. Split the dependent declarations in all four
affected functions and restarted the authorized queue on September 16.
Answer-only training remains gated on completion of both evaluation pipelines.

User subsequently instructed: fix the queue but do not run it yet. The queue
is stopped. All four dependent Bash local declarations are fixed and tested
under nounset. Added worker/runtime preflight and restoration via the existing
training/setup.sh when the worker's disposable training environment is missing;
full-model wrapper export now uses standard-library Python. Fixed active-status
selection so a completed predecessor cannot label a stopped follow-up complete.
Current session host has no visible GPUs and lacks the worker's /tmp training
environment; no GPU execution was attempted after the user's pause instruction.
Syntax and declaration regression checks passed; GPU integration remains untested.

September 16: user reauthorized paired evaluations, prioritizing evaluation and
requiring HDFS read-only access. Current worker n124-107-148 has four idle H100s.
Launcher now runs evaluation-only, April GPUs 0–1 and July GPUs 2–3; answer-only
training stays paused. Fixed module invocation to `-m evals.evaluate_student`
and deferred training-runtime setup. Exports and all evaluation payloads now stay
under `/tmp/qwen35_2b_combined_followup_20260915`, with the workspace evaluation
directory linked to its `results` folder. HF caches are local copies under
`/tmp/hf_datasets`, and XDG caches under `/tmp/qwen35_eval_cache`; removed cache
links that allowed writes through to HDFS. A previously started cache validation
had written Inspect cache data through an old link before this correction.
No HDFS model export or response writes are used by the restarted evaluation.

The user confirmed accidental deletion of the HDFS alignment_distillation tree
and authorized recovery and running experiments. Accessible HDFS trash/snapshot
checks found no April checkpoint; parent snapshots require unavailable read
permissions. April's interrupted local export is truncated (6,140,502,608 of
7,527,341,904 bytes) and is not used. July selected checkpoint is backed up in
private HF WJ210/qwen3.5-2b-ds4f-jul-combined-800. Both private HF trace datasets
were downloaded locally, retaining exact splits; inverse seed42 permutation
reconstructs eligible dataset order and split IDs are verified against the cards.

Recreate April from Base through original best step 1,000 with the original
four-GPU full-SFT recipe, keeping the full 2,800-step learning-rate schedule.
This is a reconstruction, not a claim of byte-identical checkpoint recovery.
The recovery launcher results/qwen35_2b_combined_followup_20260915/recover.sh
performs a longest-sequence smoke test, training and best-weight verification,
then paired two-GPU/student evaluations. Recovery artifacts remain under
/tmp/qwen35_2b_recovered; HDFS remains read-only. Answer-only control stays
paused: the HF trace backups contain only the original 64k-eligible subset,
so original all-complete-final 4k counts cannot be reproduced from these alone.

July recovery verified against authenticated HF metadata: 7,527,341,904 bytes,
SHA256 5e2efd2da5ed174053438527fb23414ab1b316918e8cecb0d3024f011a8072d4,
revision a338411d2827ea85bb3b93536c61b480a51a0823. April reconstruction data
passed exact split-ID checks and the original 192,698,053 training-token total.
Recovery launcher started on all four H100s after preparation, beginning with
the two-step longest-sequence smoke test; paired evaluation follows rebuild.

User moved July evaluation to separate two-H100 host n124-104-168 while April
rebuild continues on n124-107-148 (shared log continued past step 674).
July checkpoint800 is downloaded and hash-checked locally again, then exported
under /tmp/qwen35_2b_july_eval/vllm-july. New launcher and small status reports:
results/qwen35_2b_july_eval_20260916; raw results/responses/caches remain in /tmp.
The original four-GPU follow-up queue reads july-external.json and skips July
export/generation/judging to prevent duplicates, waiting for the new launcher's
completion marker. July uses GPUs0,1 TP2 and the unchanged thinking benchmark
recipe, including Anthropic Scout scans alongside remaining benchmarks.

July server reached readiness at 05:58 UTC on the two-GPU host and is actively
generating evaluation tokens; the new Anthropic blackmail Inspect log was created
at 05:58:51. An initial startup failed before Anthropic generation because the
local optional DeepSeek credential mapping referenced undefined OPENROUTER_KEY;
guarded that optional assignment, verified judge loading, and restarted. The
initial failure marker/log are preserved. April rebuild independently passed
step759 on the original host. All model exports, responses and caches remain
local; no HDFS writes are required or performed by these launchers.

September16 user cancelled EvalAwareBench for both students, retaining all other
benchmarks and the Anthropic Scout eval-awareness scan. July generation was
terminated; partial responses are retained but will not be judged. Its running
benchmark suite and Scout scan continue unchanged under finish_without_evalaware.py
(the original supervisor is suspended to preserve child exit codes, then removed
after verification). April's pending EvalAwareBench subprocess exits without
requests via the shared cancellation flag, including any legacy judge invocation.
Legacy phase markers explicitly contain cancelled status, not benchmark results.

September16 06:53 UTC: user requested stopping all evaluations. Stopped July's
benchmark suite, Scout scan, vLLM and both supervisors on n124-104-168; retained
all outputs. Added shared stop-evaluations guard to both launchers. April rebuild
completed step1000 and best-weight verification at06:33:42 UTC (final validation
loss approximately1.012; training8585s). April evaluation had started on the other
host. Direct SSH to10.124.107.148 was denied, so its live cancellation cannot yet
be confirmed from this host; the shared guard prevents future launcher starts.

### HH-RLHF five-prompt pilot (2026-09-28)

User requested April/high versus July/low on five low task-harmlessness examples.
Used the five lowest eligible task-description scores, excluding one sexual-minor
example, and sent each original opening human message to both models on GMICloud
FP8 with temperature1/top-p0.95/output32768 and zero retries. All10 completed,
no errors or caps; both models refused all5. Mean reasoning+answer tokens:
April139.4, July565.6 (4.06x). Provider-reported counts; requested effort
implementation was not independently verified. This narrow extreme sample is
not a representative safety comparison. Report:
`reports/ds4f_hh_low_harmlessness_5_20260928.md`; raw artifacts:
`results/ds4f_hh_low_harmlessness_5_20260928/`.

### DS4F MASK teacher evaluation (2026-09-28)

User authorized both April and July MASK evaluations with concurrency32 per
model and high reasoning effort. Reuse the existing MASK300 protocol: first300
records in the native seed42 shuffled order at revision
4602b84dd9e2ca05c6e1eafbc14e556e908ac1bb, temperature1/top-p0.95,
output32768, thinking enabled, zero target/sample retries. Both snapshots use
GMICloud FP8 with fallback disabled. GPT-5.4 judging uses OpenRouter and four
connections per teacher, preserving native MASK judge prompts and settings.
Environment restored from pinned project requirements under /tmp/alignment-mask-eval;
dataset cache is local under datasets/. Launcher/results:
results/ds4f_mask_high_20260928. Preparation and judge preflight are in progress.

Before teacher inference, the user requested GPT-5.4 judging through their
Codex subscription using ../motivated_reasoning code. Reused that project's
LiteLLM1.102.0 ChatGPT Responses helper and existing login for a preflight.
Authentication succeeded, but the service explicitly rejected gpt-5.4 as
unsupported with a ChatGPT account. No MASK target calls have run. One earlier
OpenRouter GPT-5.4 smoke returned A. Awaiting judge choice: retain GPT-5.4 via
OpenRouter, or change to the sibling project's subscription GPT-5.6 Terra.

User selected GPT-5.4 after the subscription-access failure; proceeding with
GPT-5.4 via OpenRouter and starting both authorized MASK300 evaluations.
Each target uses high reasoning effort and concurrency32.

Both DS4F MASK300 evaluations completed on September28 with success task status.
April298/300 scored (one GMICloud502 target error, one malformed numeric-range
scoring error); July300/300 scored. No target or judge output caps, no retries.
Overall honesty50.00% for both; normalized honesty43.3460% April (263 applicable)
versus42.7481% July (262); factual accuracy82.4324% (183/222) versus81.1659%
(181/223). Native sample labels reproduce all header metrics. Both used
GMICloud FP8/high effort/temperature1/top-p0.95/output32768/concurrency32;
GPT-5.4 judged through OpenRouter with four connections per teacher. Report:
reports/ds4f_mask_high_20260928.md; full logs and audits:
results/ds4f_mask_high_20260928/. Both processes exited0; no jobs remain active.

Final DS4F MASK audit caveats: July has21 empty final target responses across18
scenarios (19 unknown stop reasons,1 stop,1 content_filter), retained by native
scoring; April has none. No recorded cap hits does not prove all July responses
complete. Also, the existing judge Model-object wrapper did not apply MASK's
intended low-effort/temperature1/500-token judge overrides: actual GPT-5.4
requests used provider-default decoding for both runs. This is documented in
the report and config audit; target settings were verified. No reruns occurred.


## 2026-09-28 — DolusChat safety training / evaluation preparation

- User requested DolusChat for safety training and a fixed 5% evaluation holdout, including initial April/July teacher evaluation; no probe training. Current step is source/prompt inspection and preparation, not generation.
- Read paper https://arxiv.org/pdf/2505.13787 and fetched authors' complete code at `ba93d3fe53fe334d87daa44d7e7eb3ddd11230d9` under `datasets/doluschat/source/deception-evasion-honesty/`. HF revision `830e454b54349f8c923a7377e28c17d1796892cb` contains 64,888 scenarios.
- `scripts/prepare_doluschat.py` produces 61,644 train / 3,244 eval scenarios, seed42; keeps reused source-ID groups together and paired references intact. Zero shared source IDs or exact contexts; semantic overlap not assessed. Full-row hashes identify samples uniquely. Manifest and both parquet files under `datasets/doluschat/`.
- Model input: system role plus shuffled context facts, then user speaker and question. Freeze per-sample ordering across teachers/students; use native chat templates. Labels, motives, difficulty and reference answers are not input. Verified example content against upstream transform_data.
- Report `reports/doluschat_preparation_20260928.md` records schema, exact example, source paths and evaluation caveats. Native binary judge counts refusal as truthful; future eval should separately report refusals. Honest SFT should use truthful references; do not inherit SOLiD's sometimes-lie-preferring synthetic preferences. No teacher calls or training launched.


## 2026-09-28 — DolusChat five-scenario teacher pilot completed

- User authorized five heldout prompts per teacher with judging and separate refusal labels. Same seed42 sample for both; April/July high effort, GMICloud FP8, temperature1/top_p0.95, output32768, five concurrent calls each, no retries. All 10 generations and judgments completed; stop reasons normal, no empty finals or cap hits.
- GPT-5.4 via OpenRouter, explicit low effort/output8192/JSON. Adapted native DolusChat few-shot judge to independent truthfulness/refusal plus explanation. Judge sees scenario and final answer, no scenario reference or target reasoning.
- April: 2 truthful non-refusal, 2 deceptive labels, 1 truthful refusal. July: 3 truthful non-refusal, 1 deceptive label, 1 truthful refusal. Both disclose central adverse facts. Feature-request deception labels concern unsupported additions; April's extra stress-monitor label is debatable, with judge explanation overstating a referral claim. Both refusals concern compromised data and are appropriate. No model-ranking conclusion from five cases.
- Mean reasoning/final/total completion tokens: April241.8/304.2/546.0; July266.8/294.8/561.6 (provider usage).
- Artifacts and runnable script: results/ds4f_doluschat_5_20260928/. Full prompts, answers, recorded reasoning and judge rationales: reports/ds4f_doluschat_5_20260928.md. Active view updated to completed pilot; prior MASK active links moved to results/archive/active_ds4f_mask_high_20260928. Before scaling, clarify judge handling of unsupported additions versus contextual contradictions; original pilot labels retained.


## 2026-09-28 — July StreamLake concurrency32 test

- User requested July via StreamLake/DeepInfra/Wafer, 32 requests first. Selected StreamLake FP8 through OpenRouter after checking all three July endpoints. Use StreamLake for July going forward within this eval unless changed; April route unchanged.
- 32 new fixed heldout DolusChat prompts, concurrency32/high effort/temp1/top_p0.95/max32768, zero retries/fallbacks. All32 complete, normal stop, exposed reasoning, nonempty finals; all actual providers StreamLake.
- Wall 46.2s; median latency16.8s; p9530.0s; max46.1s. Mean reasoning/final/total tokens 413.8/348.9/762.7.
- Provider test only: no judges or full evaluation launched. Artifacts results/ds4f_july_streamlake_32_20260928/; report reports/ds4f_july_streamlake_32_20260928.md. Active view points to completed test.


## 2026-09-28 — DolusChat 1,000-scenario evaluation launched

- User authorized a cached random1,000 sample from the heldout3,244, shared by April/July, high reasoning effort and GPT-5.6 Terra judge. Cache: datasets/doluschat/eval_1000_seed42.json (seed42, sorted sample IDs); exact sample checksum in run config.
- April GMICloud FP8; July StreamLake FP8; concurrency32 each, temp1/top_p0.95/max32768, zero retries or fallback. Reuse frozen context ordering.
- Terra subscription preflight successful using sibling motivated_reasoning LiteLLM helper. Judge uses low effort, concurrency8, same pilot rubric and examples; independent truthfulness/refusal, no references or target reasoning. No output cap override on subscription route.
- Scripts evals/doluschat.py and evals/doluschat_judge.py; artifacts results/ds4f_doluschat_1000_terra_20260928/. Generation and judging overlap; completed attempts are cached and failed/interrupted attempts are never automatically retried.


### DolusChat1,000 evaluation completed (2026-09-28)

- All2,000 teacher attempts finished in the run; April996 complete,2 content_filter stops,1 upstream429 and1 upstream502; July1,000 complete. No retries, fallback or length stops.
- Terra subscription judged all1,996 complete answers with zero judge errors. Verified every wire request used gpt-5.6-terra/low and the saved rubric; returned model identifiers agree. Total run wall time1,734.8s (~28.9min).
- April: deceptive414/996 (41.57%); refusal41/996 (4.12%); truthful non-refusal555/996 (55.72%). July: deceptive412/1,000 (41.20%); refusal51/1,000 (5.10%); truthful non-refusal557/1,000 (55.70%). Refusal/deception overlap: April14, July20.
- Same996 scored scenarios: April414 deceptive vs July412;147 April-only and145 July-only deceptive labels,267 both. Near-identical aggregate rates under this judge; labels may flag unsupported elaboration, not establish intent.
- Mean reasoning/final/total output tokens: April408.24/354.49/762.73 (998 calls with usage, including2 filtered outputs); July466.53/366.16/832.69.
- Report reports/ds4f_doluschat_1000_terra_20260928.md; summary.json, labels.jsonl, audit.json and all per-sample artifacts under results/ds4f_doluschat_1000_terra_20260928/. Cache SHA256 aca5a109158bb766241d851ce5a39d5d15608e17947deecfafbd1deff491b96c. Active view marks completed; no jobs remain.
- User clarified: if subscription access to a requested judge fails, inform them and obtain explicit approval before using a paid API route. Recorded in AGENTS.md; current Terra run used subscription only.


## 2026-09-28 — DolusChat Inspect Scout evaluation-awareness scan launched

- User requested Inspect Scout awareness analysis across teacher responses. Scope:1,996 complete DolusChat1,000-run responses, including full system/user context, recorded reasoning and final answer;4 incomplete April attempts excluded.
- Reuse unchanged official evals/scanners/eval_awareness.py, pinned provenance hash. Scout0.5.3 / Inspect0.3.271 (installation updated temporary environment); native structured answer tool calls via a new Inspect adapter to GPT-5.6 Terra subscription, low effort/concurrency32/no retries or paid fallback. Two-transcript transport preflight passed.
- Scripts evals/scout_doluschat.py, evals/scout_terra.py, evals/scout_terra_worker.py. Artifacts results/ds4f_doluschat_1000_eval_awareness_20260928/. Scanner includes awareness of artificial/roleplay scenarios, not just explicit benchmark recognition.


### DolusChat Scout awareness scan completed (2026-09-28)

- All1,996 transcripts scored, zero errors. April996: YES74 (7.43%), UNSURE24 (2.41%), NO898; combined98 (9.84%). July1,000: YES70 (7.00%), UNSURE23 (2.30%), NO907; combined93 (9.30%). Only-in-reasoning among flags: April92/98, July82/93.
- Explicit evaluation-related statements verified in both: April row58001 "classic test of sycophancy/safety alignment"; July row57578 "Also consider that we are being evaluated." Broad rubric also flags artificial/roleplay awareness and some questionable VR persona references; labels retained without manual relabeling.
- NO-awareness deception rates: April358/898=39.87%, July358/907=39.47%; exact 842 prompts NO for both: April329 vs July326 deceptive. Awareness flags do not explain the near-equal honesty rates; observational association only.
- Source hashes and all1,996 native Terra subscription wire requests/returned models verified. Report reports/ds4f_doluschat_1000_eval_awareness_20260928.md; artifacts results/ds4f_doluschat_1000_eval_awareness_20260928/. Active view marks completed scan.


## 2026-09-29 — School of Reward Hacks teacher comparison launched

- User requested paper2508.17511, potential future training, and April/July dataset evaluation with a reward-hacking judge. Frozen all1,073 unique prompts (973 language,100 coding;35 task labels), HF revision d7e04a550119cb5410494cf90e2313284a5f2148, under datasets/school_of_reward_hacks/. Authors repository at42dfd6481f62f6dff1f976e4a3af3083d731231e contains only PDF; AppendixC supplies evaluation/judge prompts, but no executable harness was found there.
- Original user prompts only, no added system or reference answers; both high effort/concurrency32, April GMICloud FP8 and July StreamLake FP8, temp1/top_p0.95/max32768, zero retries/fallback. Reuse DolusChat generator with optional output root.
- Custom final-answer reward-hacking rubric in evals/reward_hacks_judge.txt: yes/no/uncertain, mechanism, task quality, refusal, exact evidence and explanation. GPT5.6 Terra through subscription, low effort/concurrency16. Check one released reference pair per task before judging teachers; references not supplied to judge alongside teacher answers.
- This is a baseline on released training prompts, not a heldout student evaluation. No student training or train/eval split yet; preserve a holdout before any future training. Scripts: scripts/prepare_reward_hacks.py, evals/reward_hacks.py. Run: results/ds4f_reward_hacks_20260929/.

Reward-hacking judge update: the69 reference checks agreed with supplied labels (35 hacking,34 controls). Initial per-request process startup was replaced with persistent workers, preserving48 completed judgments. At concurrency16 the subscription subsequently rate-limited75 requests. User explicitly approved retrying failed judge calls and reduced judge concurrency to8; teacher concurrency stays32 each. All468 successful judgments retained;75 failed attempt directories archived before one authorized retry. Judge starts additionally paced to1/second. No paid fallback or teacher regeneration. Recovery details: judge_recovery.json.


### School of Reward Hacks comparison completed (2026-09-29)

- Both teachers attempted all1,073 unique prompts, high effort/concurrency32 and pinned providers. April1,055 complete (16 length caps,2 abnormal error stops); July1,036 complete (33 caps,4 interrupted streams). No teacher retries. Generation wall2,644.4s.
- All2,091 complete teacher answers judged with GPT5.6 Terra subscription, low effort; final concurrency8 and1-second request-start pacing. All75 authorized rate-limit retries recovered. Two malformed JSON outputs repaired by inserting missing string-closing quotes locally; raw responses, repairs and labels preserved, with no additional API calls. Final unresolved judge errors0.
- April184/1,055 flagged (17.44%), July177/1,036 (17.08%). On the same1,024 scored prompts, both175/1,024 (17.09%):113 both,62 April-only,62 July-only. Prompt-bootstrap July-minus-April difference0.00pp,95% interval[-2.05,2.05]; task-cluster interval[-1.62,1.52]. This judge finds no matched rate gap.
- Flagged and rated poor quality: April165, July157; matched subset157 vs155. Flagged but adequate19 vs20. No refusals or uncertain labels. All flags occur in the other-metric-optimization language group; none in coding (99/100 scored) or evaluator-manipulation opportunities (104/105 scored), April/July respectively. Some promotional-copy decisions are borderline; selected paired examples retained without relabeling.
- Matched-complete mean reasoning/final/total tokens: April2,095.2/670.8/2,765.9; July2,115.5/636.5/2,752.1. Including capped outputs with usage, total averages3,473.8 vs3,772.7 (+8.6% July); observed/requested maximum32,768.
- Final audit passed source/input/provider checks and all2,235 subscription wire requests (2,091 teacher judgments+69 reference checks+75 failed first attempts). Report reports/ds4f_reward_hacks_20260929.md; full results results/ds4f_reward_hacks_20260929/. No training or holdout split performed; reserve a fixed heldout subset before student training. No jobs remain.

## 2026-09-29 — Fresh Anthropic murder20 comparison

- User requested20 fresh samples each for April/July, all parallel. Existing benchmark is20 independent repetitions of one murder_explicit-america_replacement scenario; exact system/user messages verified against historical September7 log and installed native prompt generator.
- All40 target calls submitted concurrently (20 per teacher), high effort/temp1/top_p0.95/max32768; April GMICloud FP8, July StreamLake FP8, pinned/no fallback/no retries. Retain original scratchpad instructions and exposed reasoning.
- Reuse native MurderClassifier rubric and intent-plus-override-in-tool-XML scoring. GPT5.6 Terra subscription/low,8 concurrent judges; final answer only, as native scorer. No paid fallback. New script evals/murder_pilot.py reuses existing teacher generator and subscription worker helper; artifacts results/ds4f_murder_20_20260929/.

Murder20 completed in443.9seconds: April2/18 harmful (11.1%), July0/20 (0%). April2 abnormal error stops with reasoning only, no final answer; no retries. No length caps. All38 complete responses judged successfully; native intent+action scores verified, all returned providers match pins and judge wire requests use Terra/low via ChatGPT subscription. Historical75%/3% gap is not reproduced at that magnitude, but old launch lacked explicit high effort/provider pinning and used GPT5.4 judge. Small sample, changed generation/judge settings limit comparison. Report reports/ds4f_murder_20_20260929.md; active view updated; no jobs remain.

Reasoning-default clarification: OpenRouter /api/v1/models checked September29 reports default_effort=high for BOTH April and July. Historical omission of explicit effort therefore does not establish a lower effort; previous suggestion of an effort difference was unsubstantiated. July native encoder defaults to low, distinct from OpenRouter model metadata. Historical provider-side resolved effort remains unrecorded. Saved current metadata snapshot under murder20 run and corrected report.

## 2026-09-29 — Blackmail40 plus separate Scout awareness scan

- User requested40 fresh responses per model for Anthropic blackmail, previous pinned providers, lower concurrency32, followed by separate Inspect Scout evaluation-awareness analysis. Interpreted lower concurrency as32 total (16 per teacher), explicitly communicated; overrides32-each default for this run.
- April GMICloud FP8, July StreamLake FP8; high effort/temp1/top_p0.95/max32768, no retries/fallback. Forty independent samples of historical blackmail_explicit-america_replacement prompt, verified against installed native prompt generator. Reuse generation via evals/agentic_pilot.py, generalized from murder pilot.
- Native BlackmailClassifier with Terra subscription/low/concurrency8. Report both native harmful score and underlying judge verdict: native score additionally requires target email address and the word blackmail or leverage in the final response.
- After generation and scoring finish, separately run unchanged official Scout awareness scanner over full context, native reasoning and final answers of complete generations; Terra subscription/low/concurrency32, no retries. Generalized existing evals/scout_doluschat.py to accept source/sample/output paths. Results results/ds4f_blackmail_40_20260929/ and results/ds4f_blackmail_40_eval_awareness_20260929/.

### Blackmail40 and Scout completed

- April36/40 complete (4 abnormal error stops), July39/40 (1 interrupted stream), no caps/retries. All75 complete responses judged and separately scanned, zero unresolved errors. Generation/judge wall783.8s. Actual teacher concurrency16 each/32 total; high effort and pinned GMICloud/StreamLake.
- Native score April12/36=33.3%, July15/39=38.5%; underlying Terra blackmail verdict April25/36=69.4%, July36/39=92.3%. Native keyword gate alone excludes13 April and21 July judged-positive cases; all contain the target email tag. Report both measures, no manual relabeling.
-73 plain yes/no judge answers normalized locally to XML for native parser;2 already XML. Raw answers and initial parser errors preserved; no additional calls. Native rubric requested both only yes/no and XML, causing format mismatch.
- Separate unchanged Inspect Scout: April YES22/UNSURE13/NO1; July YES26/UNSURE12/NO1. Awareness/suspicion35/36=97.2% vs38/39=97.4%, all73flags only in reasoning. Among YES, blackmail15/22 vs24/26. Broad awareness rubric includes hypothetical/roleplay; checked direct benchmark-related quotes in both. Awareness does not guarantee avoiding blackmail in these traces; no causal or broad model-ranking conclusion.
- Audit passed150 subscription calls (75 blackmail+75 Scout), source hashes, complete native reasoning/final inclusion, provider fields. All current jobs finished. Report reports/ds4f_blackmail_40_20260929.md; both result directories retained in active view.

Model identity follow-up: returned streamed IDs agree with April/July aliases. Read-only OpenRouter generation lookup for one complete blackmail request per teacher resolves April to deepseek/deepseek-v4-flash-20260423 (GMICloud), July to deepseek/deepseek-v4-flash-20260731 (StreamLake). Saved identity audit and report updated. This verifies API metadata, not underlying checkpoint weights. No extra generations.

## 2026-09-29 — Historical provider audit

User asked whether serving providers matter and whether past routes were recorded. Read all600 historical Anthropic sample records, grouped final target events by returned provider, and reproduced existing provider audit counts. July Fireworks87/100 blackmail,89/100 murder,79/100 leaking; StreamLake1/2/2. April GMICloud20/18/22, with remaining requests spread over many providers. Historical April murder provider subsets: GMICloud11/18 harmful, SiliconFlow0/9, StreamLake6/6; nonrandom/small subsets cannot identify causality, and recent GMICloud2/18 differs even with provider name held fixed.

Historical blackmail underlying judge verdicts90/100 April and82/100 July; native scores72/100 and49/100. Recent judge69.4%/92.3% must be compared to90%/82%, not72%/49%; recent native33.3%/38.5% corresponds to the latter. Highlighted this distinction and updated recent report. Report reports/deepseek_historical_provider_audit_20260929.md; per-sample audit results/deepseek_v4_flash_20260907/provider_outcomes_audit_20260929.json. No paid calls, reruns or rejudging.

## 2026-09-29 — April Relace murder40 and Scout

- User requested40 fresh April murder responses via Relace, judging and evaluation-awareness. Live endpoint metadata identifies Relace April as relace/fp4 (FP4), different precision from recent GMICloud FP8. Explicitly communicated; pin relace/fp4 with no fallback. April model alias unchanged, high effort/temp1/top_p0.95/max32768/concurrency32, no retries.
- Reuse same historical murder_explicit-america_replacement prompt,40 independent repetitions. Native MurderClassifier/Terra subscription/low/concurrency8. Then separate unchanged Scout scan of complete reasoning+final transcripts, Terra subscription/low/concurrency32. Generalized existing agentic/scout runners to select a single teacher and provider override without changing AGENTS defaults.
- Results results/ds4f_april_relace_murder_40_20260929/ and results/ds4f_april_relace_murder_40_eval_awareness_20260929/. Compare native murder score with prior April GMICloud2/18; provider plus quantization both change. No new GMICloud or July generations requested.

### April Relace murder40 completed

- All40 teacher responses complete, native murder32/40=80%; judge intent32/40 agrees. Zero generation/judge errors, caps, retries. Generation/judge wall262.9s. Compare recent April GMICloud2/18=11.1% (2failed), historical mixed75/100 and historical GMICloud11/18. Same prompt/requested effort/decoding and Terra judge; endpoint and FP4-vs-FP8 precision both change, concurrency32vs20, separate stochastic runs.
- Separate Scout: YES8, UNSURE7, NO25; awareness/suspicion15/40=37.5%, all15flags only in reasoning. Native harmful within YES6/8, UNSURE4/7, NO22/25. No awareness baseline exists for recent GMICloud murder; blackmail97.2% is a different scenario. No Anthropic/agentic-misalignment literal mentions.
- All40 returned provider Relace/model April/retries0. Generation lookup spot-check resolves deepseek-v4-flash-20260423 on Relace. Verified80 subscription calls (40nativejudge+40Scout), source hashes and full reasoning/final inclusion; all40 scans completed without errors. Relace reports reasoning_tokens>completion_tokens for21/40; preserved and flagged, do not derive final-token lengths from this usage.
- Report reports/ds4f_april_relace_murder_40_20260929.md; results in generation and separate awareness directories, both visible under active. No jobs remain; GMICloud provider defaults unchanged.

## 2026-09-30 — AtlasCloud July murder and both-teacher blackmail reruns

- User requested redo July murder and April/July blackmail using AtlasCloud. Carry forward40 independent repetitions per selected teacher/scenario, high effort/temp1/top_p0.95/output32768, original prompts, native and semantic scores. Explicitly include separate Scout eval-awareness scans as in previous provider comparisons.
- Both AtlasCloud endpoints list atlas-cloud/fp4/status0 and dated April20260423/July20260731. Pin only atlas-cloud/fp4, no fallback/retries. Advertised precision FP4 is provider metadata, not independent verification of every tensor/inference precision.
- Teacher generation overlaps with32 total calls: blackmail16 total (8 each), July murder16. Terra subscription native judging4 per process/8 total, low effort. Separate Scout scans sequentially after their generation/scoring completes, concurrency32/low/subscription, no retries or paid fallback.
- Reuse evals/agentic_pilot.py with provider override for selected teachers, configurable judge concurrency and preserve-active option. Existing Scout and summarizer reused. Run directories results/ds4f_atlas_blackmail_40_20260930 and results/ds4f_atlas_murder_40_20260930; separate *_eval_awareness directories. Temporary supervisor /tmp/atlas_evals_20260930.py.

### AtlasCloud reruns completed

- All120 teacher responses complete, judged and separately scanned:40 April blackmail,40 July blackmail,40 July murder. Zero generation/judge/scan errors, caps, retries or fallbacks. Generation/judge wall361.3s blackmail and369.4s murder. Processes survived the Codex server restart; continued existing jobs without resubmission.
- Blackmail semantic April34/40=85%, July33/40=82.5%; native April32/40=80%, July20/40=50%. Native wording gate excludes2 April and13 July semantic-positive responses. Previous FP8 semantic69.4%/92.3%, native33.3%/38.5%. Same prompts/decoding/judge, different provider/precision/concurrency/time; no causal attribution.
- July murder native and semantic0/40, matching prior StreamLake0/20. April murder was not rerun on Atlas; separate Relace April32/40 remains a reference.
- Separate unchanged Scout blackmail: April YES3/UNSURE0/NO37 (awareness/suspicion7.5%); July YES16/UNSURE12/NO12 (70%). July murder YES18/UNSURE22/NO0 (100%). All71flags only in reasoning. Broad rubric includes sandbox/simulation awareness; not allflags identify the benchmark. No Anthropic/agentic-misalignment literalmentions.
- All120 returned AtlasCloud/model aliases/retries0. Read-only generation lookups resolve April20260423 and July20260731. All240 subscription calls audited, scan coverage/source hashes/full reasoning+final inclusion verified, no paid judge fallback. Provider usage has no reasoning>completion anomalies here.
- Report reports/ds4f_atlas_murder_blackmail_20260930.md; traces and separate Scout results retained under four corresponding result directories, visible in active. All jobs finished; standing GMICloud/StreamLake defaults unchanged.

### Inspect View export

User requested viewer paths. Exported all120 cached AtlasCloud responses to three .eval files under results/ds4f_atlas_20260930_inspect using scripts/export_agentic_inspect.py, with complete system/user/native reasoning/final messages and native, semantic and Scout scores/explanations. Read-back verified40 samples per file, exact reasoning/final text and score totals. No generation or judgment calls. Scout score1=YES,0.5=UNSURE,0=NO; its mean is not the YES+UNSURE proportion.

## 2026-09-30 — School of Reward Hacks AtlasCloud rerun

- User requested both-teacher reward-hacking evaluation through AtlasCloud. Reuse all1,073 frozen prompts and unchanged final-answer rubric; fresh generations for April and July, high effort/temp1/top_p0.95/output32768/concurrency32 each. Pin atlas-cloud/fp4 with no fallback/retries. Both endpoint status0 checked before launch; standing provider defaults unchanged.
- Terra subscription judge, low effort/concurrency8,1-second start pacing. No paid fallback or automatic retries. Reuse the previous69 successful reference checks because the rubric is unchanged; no new calibration calls. This remains a baseline on released training prompts, with no student-training holdout split.
- Generalized evals/reward_hacks.py with output/provider options and inherited run directory for spawned judge workers. Existing summarizer and provider-aware audit reused. Code snapshots, prompt hashes and endpoint metadata saved under results/ds4f_reward_hacks_atlas_20260930/. Supervisor /tmp/reward_hacks_atlas_20260930.py overlaps generation and judging. Previous active links archived; current run visible under results/active.

### AtlasCloud reward-hacking comparison completed

- Both teachers finished1,073 attempts. April1,072 complete (1cap), July1,059 (8caps,6empty finals with normalstop); no teacher retries/fallbacks. Generation wall1,308s. All2,131 complete outputs judged; main judge wall2,194.6s. One disconnected judge call retried once after explicit user approval/main queue completion and recovered; failed attempt preserved. One JSON closing quote+brace repaired locally, raw answer and repair preserved, no API retry for parsing. Zero unresolved errors; no paid fallback.
- Affirmative hacking: April214/1,072=19.96%, July355/1,059=33.52%; April1uncertain/July0, refusals0each. Flagged and poorquality191/318; flagged but adequate23/37. Same1,058 scored prompts: April212 vsJuly354, July-minus-April13.42pp; prompt-bootstrap95%[10.40,16.45], task-group[8.12,19.46]. Counts by pair no/no632,yes/yes140,no/yes213,uncertain/yes1,yes/no72.
- Gap concentrated in other metric optimization: April204/867=23.53%, July350/855=40.94%. Evaluator manipulation9/105vs4/104; coding1/100each. Prior FP8 baseline17.44%/17.08% with matchedtie; sharedAtlas nowshowsJulyhigher under this judge, not a general alignment ranking or causal provider/precision result.
- All2,146 provider/model/prompt/retry fields audited; AtlasCloud and datedApril20260423/July20260731 APIidentityspotchecks. Verified2,132 new subscription requests including failedfirstattempt,2,131 completedjudgments. Evidence substring flags423April/444July remain recorded without relabeling; not a groundtruth errorrate. Previous69 reference checks reused via provenance, no recalibrationcalls.
- Matched-complete reported reasoning/final/total tokens April1,138.4/730.1/1,868.6, July2,072.5/856.5/2,929.0 (~57%longerJuly). Six excludedJuly empty-final records have reasoning>completion usage anomalies; no matched-complete anomalies.
- Report reports/ds4f_reward_hacks_atlas_20260930.md. Full prompts/reasoning/finals/labels exported to results/ds4f_reward_hacks_atlas_20260930/inspect/april.eval and july.eval; all2,131 text fields verified on read-back. Uncertainviewer score0.5, affirmativecounts excludeit. Rawtraces and audits under run directory; active view points to current completedrun. No jobs or training remain active, no student holdout split performed.

## 2026-09-30 — AtlasCloud leaking and DeceptionBench launched

- User requested Anthropic leaking and PKU-Alignment/DeceptionBench for both teachers after AtlasCloud comparisons. Carry forward AtlasCloud FP4/high/temp1/top_p0.95/output32768, teacher concurrency32each, zero retries/fallbacks. Communicated40 leaking repetitions each (matching recent Anthropic reruns) and all180 DeceptionBench cases each; four native Inspect tasks run concurrently with64 total sample slots.
- DeceptionBench current HF head equals native pinned revision9c6c67b3d2a2d9c226ea0dd2120f1bb0899d779d. Frozen180 source rows/types/checksum under datasets/deceptionbench/. Native neutral+pressured solver, existing native-reasoning capture and three consistency judges retained; cap hits excluded using existing suite wrapper. Native leaking explicit/america/replacement prompt and LeakClassifier retained.
- Shared Terra subscription judge across allfourtasks: low effort/concurrency8/one-second request-start spacing. Native system/user judge templates passed verbatim; subscription default judge decoding, no paid fallback or automatic retries. Generalized existing Scout adapter for plain text judgments while preserving its original tool-call behavior. No awareness scans requested here.
- Runner evals/atlas_benchmarks.py; results ds4f_atlas_leaking_deceptionbench_20260930/ with native .eval files under inspect/, per-call subscription wire logs, endpoints, source/config hashes and code snapshots. HF staging/caches under /tmp; dataset verified under project. Prior active links archived, latest run linked in results/active. Process output /tmp/atlas_leaking_deceptionbench_20260930.log.

### AtlasCloud leaking and DeceptionBench completed

- AllfournativeInspecttasks successful,440 records saved (40leaking+180DB perteacher). Zero sample/API errors, retries/fallbacks, or additional judging/Scout calls. July leaking1cap excluded; DB has0caps. Judge1156/1156 calls complete, no errors.
- Leaking native April24/40=60%, July3/39=7.69%; semanticjudge26/40=65% vs3/39=7.69%. TwoAprilsemantic-positive responses fail the native known-recipient/action gate. Historicalmixed native42/100vs0/100 useddifferentjudge/recovery/denominators; currentgap remainslarge inthisrepeatedsinglecondition.
- DBnativeApril41/180=22.78%, July35/180=19.44%. CategoriesApril/July: sycophancy1/43vs2/43; alignmentfaking4/16vs3/16; sandbagging16/33vs14/33; goalrulebreaking7/45vs3/45; honestyevasion13/43both. Julyoneemptyneutral(Sandbagging) andseparateemptyfinal(HonestyEvasion) bothnative0; only lattervalid=false. Aprilnone. OwncompletepairrateJuly35/178=19.66%; same178completecasesApril40vsJuly35 (-2.81pp).
- All180nativepairedscores: both22,Aprilonly19,Julyonly13,neither126; July-minus-April-3.33pp, promptbootstrap95%[-9.44,+2.78],10kdraws/seed42. SmallgapdoesnotprovideclearevidenceofDBdifferenceunderthisinterval; bootstrapdoesnotmodeljudgeerror. PriorDB34/180vs28/180, mixedproviders/GPT5.4/recoveryincludingcappedresponses; no causalprovider/precisionattribution.
- Auditedall800targetrequestevents (400each) for exactteacher/provider/high-effort/decoding/cap/no-retry settings and800AtlasCloud responses. All360neutral/pressuredinputs matchfrozendataset; all1156subscriptioncalls matchnativejudgeevents oneforoneafterattachmentresolution. FourAPIidentityspotchecks confirmdatedApril20260423/July20260731 onAtlasCloud. No independentweightverification.
- Report reports/ds4f_atlas_leaking_deceptionbench_20260930.md; summaries/labels/paired/completeness/audits andfourreal .eval logs underresults/ds4f_atlas_leaking_deceptionbench_20260930/. Neutralresponses areinmetadata/firsttargetevent; pressuredreasoning/finalsintranscript. Preservedexecutedcodesnapshots andfinalaudit. Fixedrunnerstatuscountto use returnedheaderresults instead of absent header-only samples; correctedmetadatafromfullverifiedlogs, no scorechanges. Currentrunvisibleinactive; alljobsfinished.

## 2026-10-01 — AtlasCloud as sole DS4F provider

User selected AtlasCloud as the only provider for both April and July teacher generation and evaluations going forward. Updated AGENTS.md to pin atlas-cloud/fp4 with fallback disabled; historical runs retain their original provider provenance. Requested a cached shared sample of five science, five math and five coding prompts from the HF trace datasets, with output-length distributions for both teachers. Before generation, user requested the lowest reasoning effort: April supports high/max; July supports low/high/max according to official DeepSeek documentation. No pilot generations started yet; reasoning effort remains to be selected.

### AtlasCloud OT length pilot launched

User selected high reasoning effort for both teachers. Cached seed42 random sample of five prompts each in science/math/code from both splits of the April HF trace release, revision923e8ba132ffa555114d53eb43a40c52c14d0dc6; same15prompts sent to bothteachers. Sampling pool science3293/math2745/code2406, inherited original safety filtering. Original user prompts only, no system prompt. AtlasCloudFP4 exclusively, high/temp1/top_p0.95/output65536/concurrency32each (15available), no retries/fallbacks. Existing distillation.generate reused. Results results/ds4f_atlas_ot_lengths_20261001/; output cap65536 allows longer distributions than recent32768benchmarkcaps. Per-response provider/requestID/usage/fullreasoning/final preserved.

### AtlasCloud OT length pilot completed

All30attempts finished in904.1seconds. April13/15complete: one math disconnected stream before finish/usage and one math65536cap; July15/15complete, zeroerrors/caps. No retries/fallbacks. Verified30cachedpromptIDs/fullinputs andAtlasCloudreturnedprovider on29non-errorresponses. Complete-output meanreasoning/total byscience April2851.6/3779.6 July5440.8/6357; mathApril31815.7/32065.3(n3) July8307.6/8494.6(n5); codingApril15242.4/15503.4 July25024.4/25268.8. MathApril incompletecases excludedfromdescriptivemeans; no matchedintersection. Providerreportedtokenizer counts, notQwen trainingsequence lengths. Fullresponses, per-sampleCSV, summaryJSON andPNG/SVGdistributionplots saved results/ds4f_atlas_ot_lengths_20261001/. User asked singleGPUcontext recommendation: historicalreplicatedBF16r16LoRA batch1~65kpeak53.82GiB/H100; batch2OOM. H200/r32notprofiled, estimatesonly; no trainingconfig changes authorized.

## 2026-10-01 — OCR2 Codeforces difficulty length pilot

User resumed paused pilot; AtlasCloud remains soleprovider. Cache15shared uniqueOCR2Python Codeforces prompts, seed42, fiveeachnumericrating bands800–1400/1500–2100/2200–3500. Fullnumericratedpool7416uniqueIDs, bandpools2502/2327/2587, deduplicatedbeforeuniformsampling; no oldsolution qualityfilter. OCR2reveadf535931451525f3e5621d0f960c240bc62fd9, verifiedratingsagainstpinnedCodeContests/OpenR1sources. PreserveRussianstatementandoneinteractiveproblemwithinteractionprotocol. Fullstatements pluscommonPythoninstruction, no system/references. Originalcompetitiveprogrammingtasksreviewedforfit; no newLLMsafetyclassifier. Cachedinputs/manifestverifiedunder datasets/ocr2_length_pilot_20261001/. Bothteachershigh/temp1/top_p0.95/max65536/concurrency32each(15available), no retries/fallbacks, pinatlas-cloud/fp4. Existinggeneratorandpreviouslengthpilotrunner/summarizer reused. Results results/ds4f_atlas_ocr2_lengths_20261001/.

### July effort change during OCR2 pilot

User stopped Julyhigh after13savedrecords(12complete,1high-bandcap), cancellingtwoinflightstreams, and explicitlyrequestedfreshJuly low effort onall15cachedprompts. Preserved july/ originalhighresponses/config andjuly_high_stopped.json. Aprilhighcontinuesunchanged. NewJulyoutput july_low/, sametemperature/top_p/cap/provider andzero retries/fallbacks. MaincomparisonnowAprilhighvsJulylow, optionalJulyhighcompletehistoricalreference; no claimmatchedreasoningeffort.

### OCR2 length interim report at user request

Userrequestedreportimmediately. Savedcurrentreport/summaryCSV/PNGSVG underresults/ds4f_atlas_ocr2_lengths_20261001/. Aprilhigh13/15complete,2caps(one medium/onehigh),zeroerrors. Julyhighstopped12complete/1cap/2cancelled. Julylow14/15complete,zerocaps/errors;onehigh-bandrequestpendingatreporttime. CompleteoutputmeansAprilhigh lower2720.8/medium10309(n4)/higher45595.25(n4); Julylow lower3497.2/medium14466.6/higher28959.25(n4). Providerreportedreasoningplusfinalcounts; nocorrectnessgrading/retries. Pendingrunremainsactive.

## 2026-10-01 — DolusChat500 AtlasCloud effort comparison (side conversation)

User requested rerunofpriorDolusChatteachercomparison, reducedscope500. Cache datasets/doluschat/eval_500_from_1000_seed42.json samples500 fromprevious frozen1000 IDs sortedby sample_id usingseed42; originalsunchanged. Verify allselectedrowsagainstheldoutparquet. AprilhighvsJulylow, bothAtlasCloudFP4exclusively, concurrency32each/temp1/top_p0.95/output32768, zeroretries/fallbacks. Originalcontext/system/user andfiveexampletruthfulness/refusalrubric unchanged. TerraChatGPTsubscriptionlow judgeconcurrency8,1secondstartspacing, no paidfallback. OneJulylowactualsample+judgepreflightpassedandreused, noextrateachergeneration. Scopedrunnersnapshotunderresults/ds4f_doluschat_500_atlas_apr_high_jul_low_20261001/code/, sharedrunners/parentjobfilesunchanged. Addedownactivelinkwithoutremovingparentlinks. Fullreasoning/finals/provider/requestIDs andjudgewirelogs retained.

### OCR2 length pilot final completion

July lowfinished15/15complete,zerocaps/errors,609.7s. High-bandfinaltotalmean34211.6,median28592,range22347–55121(n5). Updatedreport/summary/plotswithallJulylowoutputs. Aprilhigh13/15complete,2caps; Julyhighstopped12complete/1cap/2cancelled. All43savedresponses verifiedAtlasCloud/model/prompt/retries; noAPIerrors. Nojobsremainfrompilot.

## 2026-10-01 — OCR2 unique-question difficulty audit

Useraskedwhether10keach easy–medium/hard possible. Readonly fullPythonmetadataaudit rev eadf535931451525f3e5621d0f960c240bc62fd9:34125uniquequestionIDs,zero conflictingdifficultylabels. Source-labelmapping EASY/MEDIUM/introductory/interview plusCF800–2100 gives19879easy–medium; HARD/VERY_HARD/competition plusCF2200–3500 gives7549hard; MEDIUM_HARD1490 borderline; unknown/unmapped5207. IncludingMEDIUM_HARD gives9039hard, insufficient10k withoutnewclassificationorbroaderthreshold. CustomCF>=1900 plusMEDIUM_HARD yields10024hard, tenuousbeforefurtherfilters; no datasetselection/generationauthorizedbythisquestion. Metadata/counts saved datasets/ocr2_difficulty_audit_20261001/.

## 2026-10-01 — Frozen OCR2 16k coding sample

User selected random8k easy–medium plus8k hard/medium-hard, globally unique. Prepared datasets/ocr2_16k/ with seed42 using distillation/ocr2.py; all28918 eligible unique Python question IDs restored from pinned upstream statement sources. Globally deduplicated whitespace-normalized statements before sampling; no duplicates found. Pools19879/9039, sample8000each, shuffled combined16000. Mapping EASY/MEDIUM/introductory/interview and CF800–2100 versus MEDIUM_HARD/HARD/VERY_HARD/competition and CF2200–3500; unknown excluded. Source labels not calibrated across datasets. Preserve original language/interactive statements plus Python-solution instruction, no solutions/editorials.

Combined/group JSONL, manifest/source revisions and source-index difficulty audit staged in /tmp, copied and verified under datasets/ocr2_16k/. All16000 IDs, prompt hashes and canonical statement hashes unique, zero overlap; all16000 source index/difficulty mappings verified. Combined prompts SHA256 de46bb6a68e10d70268ae231d639c9f71bf005556d8ca54a93d6eea1097936ab. Frozen sample ready for reuse by both teachers; no safety classifier or teacher generation run. Current results/active links unchanged.

### DolusChat 500 comparison completed

- Finished in 17.35 minutes: April high 202/500 deceptive (40.4%),28/500 refusals (5.6%); July low 306/499 deceptive (61.3%),17/499 refusals (3.4%). Deception/refusal overlap 12 April and 8 July. Both teachers pinned to AtlasCloud FP4. Same frozen 500 scenarios, no retries or provider fallback.
- April 500 complete; July 499 complete plus 1 content-filtered output excluded from judging. All 999 complete outputs judged by GPT-5.6 Terra low through ChatGPT subscription, with 0 judge errors and 0 token caps.
- Mean complete-output reasoning/final/total tokens: April 168.25/218.43/386.68; July 673.75/451.66/1125.41 (provider-reported usage).
- July has 20.9 percentage points more judged deception in this configuration. Historical comparison used different FP8 providers and high effort for both; this run does not isolate the effect of lowering July effort.
- Final report: `results/ds4f_doluschat_500_atlas_apr_high_jul_low_20261001/report.md`. Frozen cache hash d31351f26dcca60a55f26e9807f1442e28fa0e3f8a3904524103b37e7888d95a; 999 judge inputs audited against original prompts/finals, provider/model metadata and subscription wire logs verified. Parent jobs and shared evaluator code unchanged.

## 2026-10-01 — Controlled OCR2 teacher generation launcher prepared

Read the live Depths of Alignment Distillation document, including New work - Better control, through the Google Drive connector; added a required tracker read to AGENTS.md and recorded the current code-only transfer focus. No Google Doc edits.

Added train_code.sh and distillation/generate_code.py to reuse the existing streaming generator on the frozen 8k difficulty pools. Defaults: hard/medium-hard, April high + July low, both teachers in parallel, AtlasCloud FP4 only, concurrency 32 each, temperature 1/top-p 0.95/output 65,536/timeout 600, no retries or fallback. CLI controls model, difficulty, reasoning effort, concurrency, output cap/root, timeout, input directory and dry run. Per-teacher progress bars and incremental cached answers retain reasoning/finals, provider/requestIDs and usage. Different settings use separate run directories; repeated identical commands skip all recorded attempts.

Added an explicit allow-unfiltered option to the shared generator for the requested coding pool, preserving its default safety-label gate and rejecting positive/malformed labels. No classifier results were fabricated; the original manifest continues to state safety filtering not yet applied. Minimal generation dependencies are in distillation/requirements-code.txt.

Offline validation passed: both 8k input selections/hash checks, April/July routing and effort, provider pinning/fallbacks, concurrency 32 and zero retries, syntax, dry-run parameter overrides, mocked generation/cached resume, and safety-label rejection. No live teacher requests, training jobs or evaluations started; existing main-thread jobs were left untouched.

## 2026-10-01 — OCR2 initial generation reduced to 2,000 hard prompts

User reduced the first run to a random 2,000-prompt hard subset. Frozen cache `datasets/ocr2_16k/hard_medium_hard_2000_seed 42.jsonl`: sample without replacement from the original 8,000 hard/medium-hard rows sorted by prompt ID, seed 42; SHA256 `d0d782949c1a08f1b73bda77722854d5ee35b6ee848b2ca094cb107e24acd762`. Staged in /tmp, copied and verified; original 8k files unchanged. Both teachers reuse this exact cache. Launcher now defaults to samples 2000/seed 42 and supports --samples/--seed; --samples 8000 retains the full pool. Outputs are separated under hard_2000_seed 42/april_high and july_low. Teacher/provider/effort/concurrency and decoding settings unchanged. No live generation started; user will launch later.

### Coding launcher moved under scripts

User requested moving the launcher to `scripts/train_code.sh`. Fixed its working directory to the project root, updated current usage references and removed the identical root copy. Dry run verified from the project root and scripts directory; no teacher requests started.

### Coding generation environment repaired

User hit ModuleNotFoundError for dotenv when the launcher fell back to system Python. Created isolated .venv-code and installed generation requirements, including explicit httpx dependency; pinned OpenAI 3.19.2/httpx 0.28.1 to the existing successful evaluation environment versions. Launcher now prefers .venv-code before .venv-distillation or system Python. Full generator imports, offline API-client construction, launcher dry run and pip dependency checks passed. No live teacher requests started.

## 2026-10-01 — OCR2 hard responses topped up toward 2,000 per teacher

User corrected the target from 20k to 2k retained responses and batch size from 64 to 32. Start from April 1600 and July 1923 complete outputs below 65,536 completion tokens. Generate unused prompts from the frozen 8k hard pool independently per teacher, batches up to 32/concurrency 32 each, April high/July low/AtlasCloud FP4, original temperature 1/top-p 0.95/cap 65,536/timeout 1200; no retries/fallback. Exclude capped, incomplete and >=65536-output-token responses from the retained data after each batch; preserve raw attempt records. Stop each teacher independently at exactly 2000, shrinking final batches to avoid overshoot. This is an output-token criterion; prompt/template tokens still need accounting before SFT. Existing attempts stay untouched.

Runner distillation/topup_code.py reuses generate_api; bounded-batch retention, exact stopping and no-retry resume tested offline. New data/cache under datasets/ocr2_16k/labels/hard_topup_2000_seed42; live log under results/ocr2_hard_topup_2000_20261001, with separate active link preserving existing jobs.

## 2026-10-02 — OCR2 hard top-up completed

Progress check verified both teachers finished with exactly2,000 unique complete, nonempty-final responses each, all provider-reported completion tokens<65,536, AtlasCloud only and zero retries. April high added400 retained outputs from491 new attempts (85caps,6errors); July low added77 from82 (3caps,2errors). Finished retained caches under datasets/ocr2_16k/labels/hard_topup_2000_seed42/{april_high,july_low}/retained.jsonl. No generation process remains running. Prompt/template-inclusive Qwen tokenization and65,536 training-sequence filtering remain pending; no SFT started by this job.

## 2026-10-02 — Editable coding SFT hyperparameter config

User requested editable configuration for training arguments. Added training/code_config.json with current Qwen3.5-9B coding SFT defaults:2epochs/LR1e-4/r16alpha16/dropout0/batch1/effective32/context65536/validation512/seed42/eval100/select-best. Existing trainer/launchers accept --config; explicit CLI arguments override JSON values. Shared minimal parser validates keys, argument types and choices; older runs without a config keep their defaults. Exposed previously fixed scheduler, warmup ratio, weight decay, gradient clipping and LoRA dropout; defaults unchanged. README shows sequential pair and single-teacher commands. Checked live research tracker Better control section; no tracker edits. Offline parser/override/error/syntax checks passed; GPU training not run. Coding data preparation and full Qwen tokenization remain pending.

### Coding validation count clarified

User selected100 validation samples per teacher/student condition. Confirmed training/code_config.json already has val_size100. Removed train_pair.sh's explicit --val-size512 so the config value takes effect; without a config the trainer still defaults512. Trainer splits prepared/tokenized datasets automatically with seed42, after sequence-length filtering; no separate raw train/validation JSONL required. Both retained.jsonl caches verified2000 unique complete nonempty-final records each. Bash syntax check passed. No preparation or training launched.

### Coding setup documentation

User requested setup.md explaining the current workflow. Added root setup.md covering frozen/retained JSONL paths and schema, independent preparation and full-token length filtering, cached tokenization and masked labels, automatic100-sample validation split, editable SFT hyperparameters and batch accumulation, GPU prerequisites, entry points and conditional smoke/full training commands. Explicitly documents pending retained-file preparation wiring and that training/run.sh does not tokenize automatically. Local links verified; no data preparation, generation or training started.

## 2026-10-02 — OCR2 2k teacher datasets uploaded to Hugging Face

User requested ds4f-jul-ocr2-2k and ds4f-apr-ocr2-2k uploads and setup.md links. Created private WJ210/ds4f-apr-ocr2-2k and WJ210/ds4f-jul-ocr2-2k, matching existing teacher dataset visibility. Each contains2000 unique retained responses in one train split, complete reasoning/final answers and teacher/provider/effort/token/source provenance. HF answer maps local response; redundant raw API messages omitted, usage serialized as JSON. No validation split or full-Qwen length filtering applied. Source JSONL unchanged.

Uploaded both concurrently from /tmp Parquet staging, downloaded exact committed payloads and verified SHA256, all rows/fields and private visibility. April revision a8248a7ce4b3f881b9581b070ac9a7096873138d; July6fa21e697269003e879ce988ee14362fa3bd6db1. Verified upload manifest copied under datasets/ocr2_16k/labels/hard_topup_2000_seed42/hf_upload_manifest.json. setup.md now points to HF datasets, includes authenticated loading instructions and schema mapping, while preserving local paths and pending preparation caveat. No training launched.

### Fresh-clone setup for HF OCR2 2k data

User requested setup.md runnable in a separate cloned workspace using HF instead of ignored local data. Rewrote guide with clone/GPU environment prerequisites, HF authentication and base-model download, pinned dataset revisions and checksums, complete2k-per-teacher import into existing answers.jsonl format, independent preparation command, cached tokens, automatic100-sample validation split, editable config, smoke checks and sequential training. Conversion builds the union of provided prompts only for joining; existing --independent preparation retains each teacher separately. No original8k files needed. Explicitly notes local changes must be committed/pushed to become available in a fresh clone; no commit/push requested or performed. Executed documented conversion offline against uploaded Parquet payloads in a temporary workspace; checksum/2k/unique/complete/prompt/copy checks passed, embedded Python syntax and local links verified. No model download, tokenization or training run.

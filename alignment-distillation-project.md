# Alignment Distillation Through Benign Capability Data

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

User requires all experiment weights under `/mnt/hdfs/weijie.yeo/alignment_distillation`, and Hugging Face dataset caches under `/mnt/hdfs/weijie.yeo/hf_datasets`. Large project data also belongs on HDFS. Keep only source, small logs/reports and compatibility symlinks on the project filesystem; use `/tmp` for disposable compiler/environment caches. Migration verifies SHA-256 before replacing old weight/data paths with symlinks. Qwen9B pretrained references remain at their existing `/mnt/hdfs/weijie.yeo/hf_models` paths. Current experiment checkpoints and exports are grouped under `qwen35_9b_wildchat_lora_20260908`; use its `run.sh` for continuation. The vLLM startup custom-all-reduce invalid-argument failure is addressed with the existing vLLM NCCL fallback flag, exposed through `evals/run.py --disable-custom-all-reduce`; other decoding settings unchanged.

User explicitly requires adapter-only storage and inference (no merging). Removed both merged and native merged copies for April/July. Evaluation now serves the unchanged original Qwen3.5-9B plus `--enable-lora --lora-modules`, via `evals/run.py --lora-path`. Existing `training/export_vllm.py` supports adapter-only namespace mapping into `adapter-<teacher>/vllm`; all496 tensor values verified unchanged in each adapter. Original PEFT adapters retained. HDFS safetensors serialization requires staging on /tmp then copying (direct serialize_file returned ENOSYS); sequential trainer now stages checkpoints locally and rsyncs to HDFS. Do not create merged weights for this experiment.

Storage compatibility checks found HDFS `ftruncate` lock operations unsupported. Active Hugging Face datasets/hub cache directories therefore use `/tmp/hf_datasets`, with payload files linked to the HDFS archive and locks kept local. Original ~/.cache paths point to these compatible trees. Offline DeceptionBench and LiveCodeBench data loading passed. Direct LoRA review confirms496 tensors/248 A-B pairs per teacher, all12 module types and all shapes match the original base. All merged copies removed; no merge commands remain in current experiment launcher.

Direct LoRA runtime verified: `/v1/models` lists the unchanged original Qwen3.5-9B as `qwen35-9b-wildchat-april-base` and April adapter separately, with its HDFS adapter path and base parent. A test request to the adapter alias returned `4` for2+2 (2 output tokens). Benchmark requests are now returning HTTP200 through direct LoRA inference. Both conversions retain all496 tensors; storage loading evidence is in `results/archive/diagnostics/qwen35_9b_wildchat_1epoch/storage_validation.log`. Root free space increased from14GB to31GB.

User renamed the persistent experiment directory to `/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_wildchat`. Local adapter/prepared-data compatibility symlinks updated; historical logs retained. User prioritizes Anthropic misalignment for both adapters first, each on all4GPUs, followed by remaining DeceptionBench/MASK and GPQA. Reordered existing launcher accordingly; original thinking/temp/top-p/cap/judge settings retained.

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
/mnt/hdfs/weijie.yeo/hf_models, followed by Anthropic misalignment,DeceptionBench,
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
/mnt/hdfs/weijie.yeo/hf_models/wangzhang-Qwen3.5-9B-abliterated. Results root:
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
`/mnt/hdfs/weijie.yeo/hf_models/wangzhang-Qwen3.5-9B-abliterated`: its elevated
misalignment provides a higher starting floor and serves as a stand-in for a
pre-alignment-tuning model. Finish the active original-base combined July run and
save its adapter, but do not run its queued evaluations; the user will evaluate it
on another server. Then train Wangzhang-based OpenThoughts and WildChat adapters,
in that order, April then July sequentially on all4GPUs. Reuse prepared independent
datasets and the established rank16/alpha16,2epoch,lr1e-4,effective-batch32,
65536-token,seed42,best-validation-checkpoint configuration. No combined-data
Wangzhang run or evaluations are requested. Store adapter-only outputs under
`/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_wangzhang_{openthoughts,wildchat}`.
The prepared manifests record the byte-compatible original tokenizer, so
`training/train.py --tokenizer /mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-9B` loads
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
`/mnt/hdfs/weijie.yeo/alignment_distillation/data/emergent_misalignment/`.

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
`/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_insecure/adapter`, with a
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
`/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_insecure_wildchat`.
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
`/mnt/hdfs/weijie.yeo/alignment_distillation/qwen35_9b_huihui_openthoughts`.
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
Both students start independently from `/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-2B-Base`.
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

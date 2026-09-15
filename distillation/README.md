# Prompt preparation and teacher generation

From the repository root, run filtering followed by both teachers:

```bash
scripts/filter_wildchat.sh && scripts/generate_teachers.sh
```

Filtering freezes one prompt file. Generation gives those same prompts to the base
and abliterated teachers in parallel, using two GPUs each. Filtering uses
`.venv-distillation/bin/python`; generation uses `/usr/bin/python`, which has vLLM
installed on this machine. Local generation uses vLLM's batch `generate()` call;
filtering and API-based inference use token streaming.

## Setup

The filtering environment is already installed on this machine. To recreate it:

```bash
uv venv .venv-distillation --python /usr/bin/python3.11
uv pip install --python .venv-distillation/bin/python -r distillation/requirements.txt
```

Filtering uses a ChatGPT subscription through LiteLLM. If LiteLLM has no separate
login and `CHATGPT_TOKEN_DIR` is unset, it reads the existing Codex credentials from
`${CODEX_HOME:-~/.codex}/auth.json` in memory without modifying them. Otherwise it
uses LiteLLM's login flow; a new login prints a device URL and code. The first
API request runs alone so workers do not race that login. Do not point
`CHATGPT_TOKEN_DIR` at the Codex directory: their credential formats differ.

## Filtering

```bash
scripts/filter_wildchat.sh
```

| Setting | Default |
|---|---|
| Dataset | `allenai/WildChat-1M`, training split |
| Retained prompts | 50,000 |
| Filter model | `chatgpt/gpt-5.6-luna` |
| Concurrent requests | 16 |
| Prompts per request | Up to 20 (`--batch-size`) |
| Maximum request input | 128,000 bytes of serialized UTF-8 JSON (`--batch-max-bytes`) |
| Reasoning | Disabled (`effort=none`); request JSON directly |
| Shuffle seed / buffer | 42 / 10,000 |
| Maximum input length | 20,000 characters; longer inputs skipped |
| Request timeout | 90 seconds |

The stream pins the dataset revision to a commit and selects English, single-turn,
non-toxic, non-redacted conversations. It discards original assistant answers,
strips surrounding input whitespace, and removes exact duplicate inputs using
SHA-256 IDs. Inputs are classified in full, without truncation.

[filter_prompt.txt](filter_prompt.txt) excludes harmful requests, jailbreaks,
refusals, safety policies, and explicit safety/ethics/alignment tasks, including
benign safety questions. It keeps ordinary coding, math, science, writing, general
instructions, creative roleplay, and neutral political/history questions. Toxicity
flags are only a prefilter; there are no domain quotas or answer-quality judgments.

Each request sends `{"prompts": [...]}` with separate `id` and `prompt` fields for
each item. Short request IDs (`p01`–`p20`) map locally to the stable SHA-256 IDs;
prompt text is JSON-escaped to preserve item boundaries. The response must be
exactly `{"decisions": [...]}`, with one
object per requested ID containing only `id`, boolean `safety_related`, and a
nonempty `reason`. The entire batch is validated before saving any decisions.
Missing, duplicate, unknown, or malformed results invalidate the batch; reordered
results are restored to input order and their full SHA-256 IDs before saving.

The progress bar tracks retained prompts toward 50,000 and shows classified and
excluded counts. Outputs under `data/wildchat_50k/`:

- `config.json`: initial settings, exact filter rubric, and pinned dataset revision.
- `decisions.jsonl`: classified inputs, decisions, explanations, and returned model
  names. New rows also record `filter_protocol=json_batch_v1` and the actual
  `filter_batch_size`.
- `prompts.jsonl`: the frozen 50,000 retained prompts, stable IDs, and source hashes.

Transient failures and malformed or incomplete batch responses are retried up to
five times with exponential backoff. Rate limits wait at least 60 seconds before
retrying; retries respect `Retry-After`. If retries are exhausted, the run stops
and saved decisions are preserved; an invalid batch contributes no decisions.
Rerunning resumes saved decisions; concurrency may change, and the current worker
count is printed at startup. `config.json` retains initial settings for the active
protocol; other setting changes require a new output directory. A migrated
single-prompt run preserves its original configuration in `config.single_prompt.json`
and retains previous decisions. `prompts.jsonl` is written only after the target
is reached.

## OpenThoughts3 prompt pool

```bash
.venv-distillation/bin/python -m distillation.openthoughts
```

This pins OpenThoughts3 to revision `61bcf9d4eb38b30295efc2021227a63cc5bb34c8`,
extracts only human instructions, deduplicates globally after collapsing whitespace,
and samples without replacement with seed 42. Original prompt text is preserved
apart from surrounding whitespace. Released assistant traces are not training labels.
The existing safety-relevance classifier is reused for 10,000 math, all eligible
unique code, and up to 6,000 science instructions. It never pads a domain with
repeated instructions. The science source has 6,250 unique stripped prompts.
The full whitespace-normalized audit found only 5,693 code, 53,106 math, and 6,249
science instructions. The user approved using the available unique code pool.

The frozen input is `data/openthoughts/prompts.jsonl`, accompanied by its manifest:
**21,590 unique instructions: 10,000 math, 5,590 code, and 6,000 science**.
Intermediate pools and classifier decisions from preparation are archived under
`results/archive/openthoughts_preparation_20260907/`. Dataset shards
are cached under `/tmp/openthoughts3-audit`. Both teachers receive the same frozen
IDs and generate fresh reasoning and final answers.

## Teacher generation

```bash
scripts/generate_teachers.sh
```

| Teacher | Default checkpoint under `/mnt/hdfs/weijie.yeo/hf_models/` | GPUs |
|---|---|---|
| Base | `Qwen3.8-27B` | `2,3` |
| Abliterated | `qwen3.8-27b-bypass` | `0,1` |

Both use [generate.py](generate.py) defaults: temperature 1.0, top-p 0.95, one
response per prompt, and a 32,768-token completion limit including reasoning.
The 65,536-token context leaves room for the prompt. No system prompt, sampling
seed, or chat-template override is added; reasoning uses the `qwen3` parser.
Each local vLLM engine uses tensor parallelism 2 and 90% GPU memory utilization.

[local.py](local.py) applies the checkpoint's chat template and submits up to
1,000 prompts per `model.generate()` call (`--batch-size 1000`). Each engine stays
loaded across calls. Results are saved and released before submitting the next
batch, bounding the returned responses held in host memory. The frozen 21,590
prompts require 22 calls per teacher: 21 batches of 1,000 and a final 590.

vLLM updates its built-in progress bar within each batch; the launcher gives the
two bars separate terminal lines and labels (`base` and `abliterated`), including
the batch number. Each shows completed prompts, percentage, elapsed time, ETA,
and token throughput for that batch. Run the launcher in a terminal to see both
updating bars. Results are written after each call returns; the progress bar
counts processed prompts, not saved rows.

Outputs under `data/teachers/base/` and `data/teachers/abliterated/`:

- `config.json`: model, initial inference settings, and prompt-file hash.
- `vllm.log`: local engine startup and inference logs.
- `answers.jsonl`: prompt IDs, prompts, reasoning, final responses, raw messages,
  finish reasons, completion status, and token usage. New batches are written in
  input order; earlier records may be in completion order.

Prompt IDs remain unchanged. Match answers by ID and restore the frozen prompt
order when preparing matched SFT datasets.

Rerunning the same command skips every saved answer ID, including answers saved
before switching generation backends. Interrupting `model.generate()` loses the
current batch's in-memory results; previously saved answers remain. A saved answer is complete
only when it stops normally, has a nonempty final response, and has no unfinished
thinking block. Truncated or empty answers remain saved with `complete=false`;
rerunning does not regenerate them automatically. Resolve incomplete answers on
matched prompt IDs across both teachers before SFT. Answers are not filtered for
correctness, style, or refusal behavior. Only exposed reasoning can be saved.

The launcher stops its engines on completion or interruption and stops the other
teacher if either generation process fails. `config.json` preserves the initial
settings; batch size can change on resume, but changed prompts or decoding
settings require new output directories. Resume scans saved answers one at a time.

The optional `--backend api` mode still uses a continuous queue of 128 HTTP
requests by default, controlled by `--concurrency`. It has a 3,600-second request
timeout and retries interrupted streams up to twice from the beginning. Partial
responses are discarded; final responses include finish reasons and token usage.
API concurrency can change on resume.

### OpenRouter teachers

For the frozen 20k WildChat/OpenThoughts mixture, run:

```bash
bash scripts/generate_openrouter_teachers.sh
```

This loads `.env` without overriding exported variables and runs April on
GMICloud and July on Wafer, each with 64 continuous requests, high reasoning,
temperature 1, top-p 0.95, requested output cap 32768, timeout 600 seconds,
and no retries or provider fallback. Results go to
`data/teachers_wildchat_openthoughts/{april,july}/answers.jsonl`.
Each model has a progress bar. Finished requests are immediately appended and
flushed; unfinished streams are held in memory. Slots refill as requests finish,
without waiting for a batch. Resume skips all saved IDs, including failed or
incomplete results. Source/domain labels remain in the frozen input, joined by ID.


Set `OPENROUTER_API_KEY` in your environment, then use an OpenRouter model ID:

```bash
.venv-distillation/bin/python -m distillation.generate \
  --backend openrouter --model vendor/model \
  --input data/openthoughts/prompts.jsonl \
  --output data/teachers_openrouter/my_teacher --concurrency 16 \
  --sampling-params '{"temperature":1.0,"top_p":0.95,"extra_body":{"reasoning":{"enabled":true}}}'
```

Replace `vendor/model` with the model slug from OpenRouter. This reuses the API
streaming implementation, setting `https://openrouter.ai/api/v1`,
`OPENROUTER_API_KEY`, and `max_tokens`. Each completed response is saved immediately;
`--batch-size` applies only to local vLLM. No GPU or local model download is needed.
The equivalent generic route already works with `--backend api --base-url
https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY --token-limit-field max_tokens`.

Reasoning controls go in `sampling-params.extra_body.reasoning`, not local Qwen
chat-template options. Set `enabled` to `false` for non-thinking where supported,
or omit the reasoning object to use provider defaults. Only exposed text reasoning
is saved; some providers return none. Provider routing options can also go in
`extra_body`. See [OpenRouter reasoning documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).
The normalized API settings and requested model are recorded in `config.json`;
each answer also records the returned model ID. API credentials are not saved.

Evaluations stream through their existing shared vLLM server. Every ready
conversation may submit its next turn; later turns wait for preceding model and
tool results. Inspect's connection allowance is derived from active sample and
task limits, while the external judge retains its own limit. The legacy
`--target-concurrency` option is accepted but ignored. Prefix caching reuses shared
token prefixes across turns.

## Overrides

Both scripts accept `PYTHON` to choose another Python executable; local generation
requires one with vLLM installed. Generation also
accepts `PROMPTS` (input JSONL), `TEACHER_OUTPUT` (parent output directory),
`BASE_MODEL`, and `ABLITERATED_MODEL` (local checkpoint directories):

```bash
scripts/filter_wildchat.sh --output data/wildchat_custom --num-samples 50000
PROMPTS="$PWD/data/wildchat_custom/prompts.jsonl" \
TEACHER_OUTPUT="$PWD/data/teachers_custom" \
scripts/generate_teachers.sh
```

`BASE_GPUS` and `ABLITERATED_GPUS` override the GPU lists (defaults `2,3` and
`0,1`). Tensor parallelism is inferred from each list. For the 9B pair on two GPUs:

```bash
PROMPTS="$PWD/data/openthoughts/prompts.jsonl" \
TEACHER_OUTPUT="$PWD/data/teachers_qwen35_9b_openthoughts" \
BASE_MODEL=/tmp/Qwen3.5-9B \
ABLITERATED_MODEL=/tmp/Huihui-Qwen3.5-9B-abliterated \
BASE_GPUS=0 ABLITERATED_GPUS=1 \
scripts/generate_teachers.sh
```

The default model paths still select the two Qwen3.8-27B teachers. To collect
their answers to a different prepared prompt pool, set only `PROMPTS` and a new
`TEACHER_OUTPUT`; the default launcher uses four GPUs, two per 27B model.

Extra filtering arguments, including `--batch-size` and `--batch-max-bytes`, go to
[wildchat.py](wildchat.py). Extra generation
arguments go to both teachers, so use them for shared settings such as
`--sampling-params`, `--max-tokens`, `--max-model-len`, and `--seed`.
Generation's `--concurrency` applies only to the API backend.
The script's per-teacher model, input, output, GPU, and port arguments take
precedence. Use the environment variables above for model and file paths. List all options:

```bash
scripts/filter_wildchat.sh --help
scripts/generate_teachers.sh --help
```

## Correctness preference check

```bash
.venv-distillation/bin/python -m distillation.preference --num-samples 100 --concurrency 16 --seed 42
```

This samples matched rows without replacement from both `samples_15k.jsonl` files.
[preference_prompt.txt](preference_prompt.txt) judges correctness using the full
question, reasoning, and final responses. GPT-5.6 Luna uses medium reasoning;
candidate identities are hidden and A/B placement is randomized and balanced.
Ties are allowed, and incomplete answers remain in the sampling pool.

`results/archive/distillation/preference_100/` records the rubric, input hashes, selected
rows and candidate order in `config.json`, individual decisions in
`judgments.jsonl`, and results in `summary.json`. Each teacher's preference score
is `(wins + 0.5 * ties) / samples`; it is not an absolute accuracy measurement.
Rerunning identical settings resumes saved judgments. Use a new `--output` for
different settings or inputs.

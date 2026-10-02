# Coding SFT from a fresh clone

This setup uses **2,000 April high responses and 2,000 July low responses** from Hugging Face. It does not require the original local generation files or the 8k prompt pools. Both teachers used AtlasCloud FP4.

Use a repository revision containing `training/code_config.json`, `training/config.py` and the trainer's `--config` support. Changes made in a local workspace must be committed and pushed before another workspace can obtain them through `git clone`.

## 1. Clone and set up the GPU environment

Run on a Linux CUDA training machine. The current recipe uses all four GPUs, sequentially for the two students. The dependency setup targets CUDA12.6 and Python3.11; its prebuilt causal-conv1d wheel requires Linux x86_64, Python3.11 and the listed PyTorch version. Install `uv` and `rsync` if needed.

```bash
git clone https://github.com/wj210/alignment_distillation.git
cd alignment_distillation
bash training/setup.sh
```

All commands below run from the repository root. [training/setup.sh](training/setup.sh) installs the training environment under `/tmp` and links it as `.venv-training`. Recreate it if the machine clears `/tmp`.

## 2. Authenticate and download the starting model

These datasets are private:

| Student | HF dataset | Responses | Teacher effort |
| --- | --- | --- | --- |
| April | [WJ210/ds4f-apr-ocr2-2k](https://huggingface.co/datasets/WJ210/ds4f-apr-ocr2-2k) | 2,000 | high |
| July | [WJ210/ds4f-jul-ocr2-2k](https://huggingface.co/datasets/WJ210/ds4f-jul-ocr2-2k) | 2,000 | low |

Authenticate using a token with read access to both repositories. The prompt below does not echo or save the token to Git. Keep it in this shell for the dataset download too.

```bash
read -r -s -p "Hugging Face token: " HF_TOKEN
printf '\n'
export HF_TOKEN

.venv-training/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download("Qwen/Qwen3.5-9B", local_dir="/tmp/ocr2-qwen35-9b",
                  cache_dir="/tmp/ocr2-model-cache", token=True)
PY
mkdir -p hf_models/Qwen3.5-9B
rsync -rt --checksum /tmp/ocr2-qwen35-9b/ hf_models/Qwen3.5-9B/
```

Both students start from `./hf_models/Qwen3.5-9B`. Use the same downloaded snapshot for both; record its revision if repeating the experiment elsewhere.

## 3. Download and adapt the 2k datasets

Each HF repository contains all2,000 responses in one `train` split. These are raw text records; tokenization and validation splitting have not been applied.

Important fields:

| Field | Meaning |
| --- | --- |
| `id` | Unique prompt ID |
| `prompt` | Coding problem and Python instruction |
| `reasoning` | Teacher reasoning |
| `answer` | Final answer; mapped to `response` for the preparer |
| `complete` | Generation completeness |
| `reasoning_effort` | Teacher generation effort |

Other columns preserve source difficulty and API provenance. The column named `split` describes the upstream question source; it is separate from the HF repository's `train` split.

The following command downloads the exact uploaded revisions, verifies checksums and2,000 unique complete responses per teacher, and writes the format accepted by the existing preparer. It builds a union of available prompt IDs only to join answers by ID; each teacher retains its own responses independently.

```bash
.venv-training/bin/python - <<'PY'
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

sources = {
    "april": ("WJ210/ds4f-apr-ocr2-2k",
              "a8248a7ce4b3f881b9581b070ac9a7096873138d",
              "7f9a71dc2d25da9d8c33ef4626f7bcb59eebf25f16f1b1f2d3b939a99a888ec5"),
    "july": ("WJ210/ds4f-jul-ocr2-2k",
             "6fa21e697269003e879ce988ee14362fa3bd6db1",
             "f615a6d936d25b2b650abac830e0fe8c2e685799cb42290af795a1e8839270d1"),
}
destination = Path("datasets/ocr2_2k_hf")
if destination.exists():
    raise FileExistsError(f"Already downloaded: {destination}; reuse the verified copy")

with tempfile.TemporaryDirectory(prefix="ocr2-import-", dir="/tmp") as temporary:
    staging = Path(temporary)
    prompts = {}
    for teacher, (repo, revision, checksum) in sources.items():
        downloaded = hf_hub_download(repo, "data/train.parquet", repo_type="dataset",
                                      revision=revision, token=True, cache_dir="/tmp/ocr2-hf-cache")
        assert hashlib.sha256(Path(downloaded).read_bytes()).hexdigest() == checksum
        rows = pq.read_table(downloaded).to_pylist()
        assert len(rows) == len({row["id"] for row in rows}) == 2000
        folder = staging / teacher
        folder.mkdir()
        with (folder / "answers.jsonl").open("w") as handle:
            for row in rows:
                assert row["complete"] and row["answer"].strip()
                identifier, text = row["id"], row["prompt"]
                assert identifier not in prompts or prompts[identifier]["prompt"] == text
                prompts[identifier] = {"id": identifier, "prompt": text, "domain": "code"}
                row["response"] = row.pop("answer")
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (staging / "prompts.jsonl").open("w") as handle:
        for identifier in sorted(prompts):
            handle.write(json.dumps(prompts[identifier], ensure_ascii=False) + "\n")
    (staging / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    shutil.copytree(staging, destination)
    for source in staging.rglob("*"):
        if source.is_file():
            copied = destination / source.relative_to(staging)
            assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(copied.read_bytes()).digest()
print("Saved and verified 2,000 responses per teacher under", destination)
PY
```

This creates `datasets/ocr2_2k_hf/april/answers.jsonl`, `july/answers.jsonl`, `prompts.jsonl` and `sources.json`. The original generation workspace is not needed.

## 4. Prepare and cache tokens

Run preparation once before training:

```bash
.venv-training/bin/python training/prepare.py \
  --model ./hf_models/Qwen3.5-9B \
  --data datasets/ocr2_2k_hf \
  --prompts datasets/ocr2_2k_hf/prompts.jsonl \
  --teachers april july --native-answers --independent --domain code \
  --max-length 65536 --workers 8 \
  --output /tmp/qwen35_9b_code_prepared
mkdir -p qwen35_9b_code/prepared
rsync -rt --checksum /tmp/qwen35_9b_code_prepared/ qwen35_9b_code/prepared/
```

The preparer refuses an existing output directory; reuse a completed prepared dataset or choose a new staging path for a fresh preparation.

Preparation uses Qwen's official thinking template, masks the prompt from the loss, and supervises reasoning plus the final answer. It drops full formatted sequences longer than65,536 Qwen tokens without truncating. Filtering is independent per teacher, so do not remove `--independent`.

Provider output-token counts do not include the full prompt/template and use a different tokenizer. Some of the2,000 records may therefore be dropped. Inspect `qwen35_9b_code/prepared/manifest.json` for each teacher's retained counts and lengths, and `label_example.txt` for masking and formatting. Missing responses for the other teacher in the prompt union are expected and excluded independently.

The saved dataset contains `april/`, `july/` and `manifest.json`. Tokenization is cached so we can verify lengths and labels before GPU training, and reuse it for restarts or hyperparameter changes. `training/run.sh` loads these tokens; it does not download or tokenize raw data automatically.

## 5. Edit the training config

Edit [training/code_config.json](training/code_config.json):

| Setting | Current value |
| --- | --- |
| Model / prepared data | `./hf_models/Qwen3.5-9B` / `./qwen35_9b_code/prepared` |
| Epochs / learning rate | 2 / 0.0001 |
| Scheduler / warmup | cosine / 5% |
| LoRA rank / alpha / dropout | 16 / 16 / 0 |
| Weight decay / gradient clipping | 0 / 1 |
| `batch_size` | 1 sample per GPU per microbatch |
| `effective_batch_size` | 32 samples per optimizer update |
| `max_length` | 65,536 total tokens |
| `val_size` | 100 samples per student |
| `eval_steps` / `select_best` | 100 / true |
| Training seed | 42 |

With four GPUs, accumulation is `32 / (4 × 1) = 8`. Per-GPU batch size controls memory; the effective batch controls how many samples contribute to each weight update. The division must yield an integer.

CLI arguments override config values, e.g. `--lr 5e-5`. Changing the tokenizer/model or sequence limit requires new preparation; changing learning rate, epochs or LoRA rank can reuse the tokens. Preparation has its own explicit arguments, so keep its model and length limit consistent with the config.

### Automatic validation split

No separate raw train/validation files are needed. The trainer reserves **100 samples per student after length filtering**, using split seed42. If all2,000 survive, each student trains on1,900 and validates on100. Otherwise, training uses the retained count minus100. Each teacher must have more than100 eligible samples.

This split measures student validation loss; it does not run a separate teacher evaluation. Each teacher's validation set is drawn independently. The split seed is currently fixed at42 in the trainer.

## 6. Smoke-test and train

First copy the config and set `select_best` to `false` for smoke mode, which does not perform validation:

```bash
.venv-training/bin/python - <<'PY'
import json
from pathlib import Path
config = json.loads(Path("training/code_config.json").read_text())
config["select_best"] = False
Path("/tmp/code_smoke_config.json").write_text(json.dumps(config, indent=2) + "\n")
PY
bash training/run.sh --config /tmp/code_smoke_config.json \
  --teacher april --smoke-steps 2 --output /tmp/qwen35_9b_code/smoke-april
bash training/run.sh --config /tmp/code_smoke_config.json \
  --teacher july --smoke-steps 2 --output /tmp/qwen35_9b_code/smoke-july
```

Smoke mode exercises the longest retained samples and records GPU memory, loss and gradient checks without saving adapters. Once both pass, train sequentially:

```bash
TEACHERS="april july" OUTPUT_ROOT=./qwen35_9b_code \
  RESULTS=results/qwen35_9b_code \
  bash training/train_pair.sh --config training/code_config.json
```

`CUDA_VISIBLE_DEVICES` defaults to `0,1,2,3`. The trainer uses BF16, gradient checkpointing, FLA and fused loss. Checkpoints are staged under `/tmp`, then copied and verified into `qwen35_9b_code/adapter-april` and `adapter-july`. Keep adapters separate; never merge them into the base model. Logs are under `results/qwen35_9b_code/`.

## Entry points and next steps

- [training/prepare.py](training/prepare.py): format, tokenize and filter.
- [training/train.py](training/train.py): student SFT.
- [training/run.sh](training/run.sh): GPU launcher for one student.
- [training/train_pair.sh](training/train_pair.sh): sequential April/July training and adapter copying.
- [scripts/train_code.sh](scripts/train_code.sh): teacher generation; not needed for these uploaded datasets.

After training, evaluate Anthropic misalignment, DeceptionBench, MASK and GPQA, then inspect evaluation awareness. Keep difficulty, teacher effort, retained sample counts and supervised-token budgets explicit in comparisons.

See [alignment-distillation-project.md](alignment-distillation-project.md) for run history and [Depths of Alignment Distillation](https://docs.google.com/document/d/1V0pStUxHTUAcORxS68a8nmvHC1yfmc4QfYVqd0feGyQ/edit?tab=t.0), especially **New work - Better control**, for the research direction. All persistent paths are relative to the cloned project; datasets live under `datasets/`, and staging/caches use `/tmp`.

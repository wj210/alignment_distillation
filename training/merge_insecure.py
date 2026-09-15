"""Merge a text LoRA, then reuse the existing verified vLLM exporter."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoTokenizer, Qwen3_5ForCausalLM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    reference = Path(json.loads((args.adapter / "adapter_config.json").read_text())["base_model_name_or_path"])
    native = args.output.with_name(args.output.name + "-native")
    if args.output.exists() or native.exists():
        raise FileExistsError("Choose a new output path")
    model = Qwen3_5ForCausalLM.from_pretrained(reference, dtype=torch.bfloat16, local_files_only=True)
    model = PeftModel.from_pretrained(model, args.adapter).merge_and_unload(safe_merge=True)
    model.config.use_cache = True
    model.generation_config.eos_token_id = 248046
    model.save_pretrained(native, max_shard_size="4GB")
    AutoTokenizer.from_pretrained(args.adapter).save_pretrained(native)
    subprocess.run([sys.executable, str(Path(__file__).with_name("export_vllm.py")),
                    str(native), str(args.output), "--reference", str(reference)], check=True)
    # Preserve reference decoding defaults, including absence of a generation config.
    generation = reference / "generation_config.json"
    if generation.exists():
        shutil.copyfile(generation, args.output / generation.name)
    else:
        (args.output / generation.name).unlink()
    print(f"Merged inference checkpoint: {args.output}", flush=True)


if __name__ == "__main__":
    main()

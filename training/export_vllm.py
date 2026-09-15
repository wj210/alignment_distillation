"""Wrap a trained text checkpoint for vLLM 0.19.1 without changing tensor bytes."""

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path


def header(path):
    with path.open("rb") as handle:
        size = struct.unpack("<Q", handle.read(8))[0]
        return json.loads(handle.read(size)), 8 + size


def rename(key):
    if key.startswith("model.language_model."):
        return key
    if key.startswith("model."):
        return "model.language_model." + key.removeprefix("model.")
    if key == "lm_head.weight":
        return key
    raise ValueError(f"Unexpected text weight: {key}")


def export_adapter(checkpoint, output):
    """Map text-model LoRA names to the multimodal wrapper; preserve tensor values."""
    from safetensors.torch import load_file, save_file
    import torch
    from tempfile import TemporaryDirectory

    tensors = load_file(str(checkpoint / "adapter_model.safetensors"))
    prefix = "base_model.model.model."
    if not tensors or not all(key.startswith(prefix) for key in tensors):
        raise ValueError("Expected Qwen text-model LoRA tensor names")
    mapped = {key.replace(prefix, prefix + "language_model.", 1): value
              for key, value in tensors.items()}
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="qwen-lora-export-", dir="/tmp") as staging:
        local = Path(staging) / "adapter_model.safetensors"
        save_file(mapped, str(local))
        shutil.copyfile(local, output / local.name)
    actual = load_file(str(output / "adapter_model.safetensors"))
    assert actual.keys() == mapped.keys()
    assert all(torch.equal(value, actual[key]) for key, value in mapped.items())
    shutil.copyfile(checkpoint / "adapter_config.json", output / "adapter_config.json")
    print(f"Adapter namespace mapped; all {len(tensors)} tensors unchanged: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference", type=Path,
                        default=Path("/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-2B-Base"))
    args = parser.parse_args()
    if (args.checkpoint / "adapter_config.json").exists():
        export_adapter(args.checkpoint, args.output)
        return
    text_config = json.loads((args.checkpoint / "config.json").read_text())
    if text_config["model_type"] != "qwen3_5_text":
        raise ValueError("Expected a Qwen3.5 text checkpoint")
    config = json.loads((args.reference / "config.json").read_text())
    config.update(text_config=text_config, tie_word_embeddings=text_config["tie_word_embeddings"])
    config["text_config"]["use_cache"] = True
    expected = {key: value["shape"] for path in args.reference.glob("*.safetensors")
                for key, value in header(path)[0].items()
                if key.startswith("model.language_model.") or key == "lm_head.weight"}
    shards = {path: header(path) for path in sorted(args.checkpoint.glob("*.safetensors"))}
    shapes = {rename(key): value["shape"] for info, _ in shards.values()
              for key, value in info.items() if key != "__metadata__"}
    count = sum(len(info) - ("__metadata__" in info) for info, _ in shards.values())
    if not shapes or shapes != expected or count != len(expected):
        raise ValueError("Trained weight names/shapes do not match the official text model")
    generation = json.loads((args.checkpoint / "generation_config.json").read_text())
    if generation["eos_token_id"] not in (248046, [248046]):
        raise ValueError("Expected the trained conversation EOS <|im_end|>")
    args.output.mkdir(parents=True, exist_ok=False)
    weight_map, verified = {}, []
    for source, (info, offset) in shards.items():
        mapped = {key if key == "__metadata__" else rename(key): value for key, value in info.items()}
        encoded = json.dumps(mapped, separators=(",", ":")).encode()
        encoded += b" " * (-len(encoded) % 8)
        destination = args.output / source.name
        digest = hashlib.sha256()
        with source.open("rb") as src, destination.open("wb") as dst:
            src.seek(offset)
            dst.write(struct.pack("<Q", len(encoded)))
            dst.write(encoded)
            while chunk := src.read(8 * 1024 * 1024):
                digest.update(chunk)
                dst.write(chunk)
        with destination.open("rb") as dst:
            dst.seek(8 + len(encoded))
            actual = hashlib.file_digest(dst, "sha256").hexdigest()
        if actual != digest.hexdigest():
            raise ValueError(f"Tensor bytes changed: {source}")
        verified.append({"file": source.name, "tensor_bytes_sha256": actual})
        weight_map.update({key: source.name for key in mapped if key != "__metadata__"})
    index_path = args.checkpoint / "model.safetensors.index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
        if {rename(key): value for key, value in index["weight_map"].items()} != weight_map:
            raise ValueError("Checkpoint index does not match its tensor shards")
        index["weight_map"] = weight_map
        (args.output / index_path.name).write_text(json.dumps(index, indent=2) + "\n")
    for name in ("tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                 "chat_template.jinja", "generation_config.json", "added_tokens.json",
                 "merges.txt", "vocab.json"):
        if (source := args.checkpoint / name).exists():
            shutil.copyfile(source, args.output / name)
    for name in ("preprocessor_config.json", "video_preprocessor_config.json"):
        if (source := args.reference / name).exists():
            shutil.copyfile(source, args.output / name)
    (args.output / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    manifest = {"source": str(args.checkpoint.resolve()), "reference": str(args.reference),
                "weights": len(weight_map), "shards": verified,
                "mapping": "Native text keys gain language_model.; official keys and tensor bytes unchanged",
                "serve_flags": ["--language-model-only", "--dtype", "bfloat16", "--reasoning-parser", "qwen3"]}
    (args.output / "export_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

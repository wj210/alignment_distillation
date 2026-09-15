"""Full or LoRA text-model SFT on one teacher dataset."""

import argparse
import json
import math
import os
from contextlib import nullcontext
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRITON_CACHE_DIR", "/tmp/alignment-distillation-triton-cache")

import torch
from datasets import load_from_disk
from liger_kernel.transformers import apply_liger_kernel_to_qwen3_5
from transformers import (AutoConfig, AutoModelForCausalLM, AutoTokenizer, EarlyStoppingCallback,
                          DataCollatorForSeq2Seq, Trainer, TrainerCallback,
                          TrainingArguments, set_seed)


class LossOnlyTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        # Right padding has ignored labels; causal loss needs no padding mask.
        # Omitting it enables SDPA's fused FlashAttention and grouped-query path.
        # Fused loss also avoids a huge [batch, tokens, vocabulary] tensor in evaluation.
        context = (torch.autograd.graph.save_on_cpu(pin_memory=True)
                   if self.activation_cpu_offload else nullcontext())
        with context:
            return super().compute_loss(model, {**inputs, "attention_mask": None, "skip_logits": True},
                                        return_outputs=return_outputs,
                                        num_items_in_batch=num_items_in_batch)


class CheckFinite(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        for key in ("loss", "grad_norm", "eval_loss"):
            if key in (logs or {}) and not math.isfinite(float(logs[key])):
                raise FloatingPointError(f"Non-finite {key}: {logs[key]}")


def restore_qwen_text_keys(model, state, prefix, *args):
    """Trainer reloads bypass Transformers' saved Qwen text-key conversion."""
    if prefix or not any(key.startswith("model.language_model.") for key in state):
        return
    for key in list(state):
        if key.startswith("model.language_model."):
            state[key.replace("model.language_model.", "model.", 1)] = state.pop(key)
    if model.config.tie_word_embeddings:
        state.setdefault("lm_head.weight", state["model.embed_tokens.weight"])
    expected = set(model.state_dict())
    if set(state) != expected:
        raise ValueError(f"Incomplete Qwen checkpoint: missing={expected - set(state)}, extra={set(state) - expected}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="/mnt/hdfs/weijie.yeo/hf_models/Qwen3.5-2B-Base")
    parser.add_argument("--tokenizer", help="Tokenizer used to prepare the dataset; defaults to --model")
    parser.add_argument("--data", type=Path, default=Path("/tmp/alignment-distillation-sft15k"))
    parser.add_argument("--teacher", choices=("base", "abliterated", "april", "july"), default="base")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=4, help="Sequences per GPU")
    parser.add_argument("--effective-batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=float, default=2)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-size", type=int, default=512)
    parser.add_argument("--smoke-steps", type=int, default=0, help="Use longest examples; do not save a checkpoint")
    parser.add_argument("--smoke-save", action="store_true", help="Save the final adapter during a smoke test")
    parser.add_argument("--resume", help="Trainer checkpoint directory")
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--lora-rank", type=int, default=0, help="0 for full SFT")
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--initial-adapter", help="Existing LoRA adapter to continue training")
    parser.add_argument("--sharding", choices=("fsdp", "zero3"))
    parser.add_argument("--cpu-offload", action="store_true", help="Offload sharded base parameters to CPU")
    parser.add_argument("--activation-offload", action="store_true", help="Offload saved activations to CPU")
    parser.add_argument("--select-best", action="store_true", help="Save the adapter/model with lowest validation loss")
    parser.add_argument("--early-stopping-patience", type=int, default=0,
                        help="Stop after this many validation checks without improvement; 0 disables")
    parser.add_argument("--eval-steps", type=int, default=100, help="Evaluate and save every N optimizer steps")
    args = parser.parse_args()
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    if (args.batch_size < 1 or args.effective_batch_size < world_size * args.batch_size
            or args.effective_batch_size % (world_size * args.batch_size)):
        raise ValueError("Effective batch must be divisible by GPUs × per-GPU batch")
    if args.epochs <= 0 or args.lr <= 0 or args.smoke_steps < 0 or args.lora_rank < 0:
        raise ValueError("Invalid training settings")
    if args.initial_adapter and args.lora_rank:
        raise ValueError("--initial-adapter already defines the LoRA configuration")
    if args.select_best and args.smoke_steps:
        raise ValueError("--select-best requires validation; it cannot be used with --smoke-steps")
    if args.early_stopping_patience < 0 or (args.early_stopping_patience and not args.select_best):
        raise ValueError("Early stopping requires --select-best and a positive patience")
    if args.eval_steps < 1:
        raise ValueError("--eval-steps must be positive")
    if args.smoke_save and not args.smoke_steps:
        raise ValueError("--smoke-save requires --smoke-steps")
    if args.cpu_offload and not args.sharding:
        raise ValueError("--cpu-offload requires --sharding")
    if args.activation_offload and not args.sharding:
        raise ValueError("--activation-offload requires --sharding")
    torch.cuda.set_device(local_rank)
    set_seed(args.seed)
    output = args.output or Path("/tmp/alignment-distillation-training") / args.teacher
    accumulation = args.effective_batch_size // (world_size * args.batch_size)
    dataset = load_from_disk(str(args.data / args.teacher))
    manifest = json.loads((args.data / "manifest.json").read_text())
    if manifest["max_length"] != args.max_length or max(dataset["length"]) > args.max_length:
        raise ValueError("Prepared dataset and requested total-length limit differ")
    tokenizer_path = args.tokenizer or args.model
    if manifest["model"] != tokenizer_path:
        raise ValueError("Prepare data with the training model tokenizer")
    model_type = AutoConfig.from_pretrained(args.model, local_files_only=True).model_type
    if model_type not in {"qwen3_5", "gemma4_unified"}:
        raise ValueError(f"Unsupported model type: {model_type}")
    # Keep transient Arrow index files off HDFS, with a separate directory per rank.
    index_cache = TemporaryDirectory(prefix="sft-indices-", dir="/tmp")
    if args.smoke_steps:
        # Exercise the real longest sequences, not a deceptively small synthetic batch.
        count = min(len(dataset), max(32, args.smoke_steps * world_size * args.batch_size))
        train = dataset.sort("length", reverse=True,
                             indices_cache_file_name=f"{index_cache.name}/sorted.arrow").select(range(count))
        evaluation = None
    else:
        split = dataset.train_test_split(
            test_size=args.val_size, seed=42,
            train_indices_cache_file_name=f"{index_cache.name}/train.arrow",
            test_indices_cache_file_name=f"{index_cache.name}/validation.arrow",
        )
        train, evaluation = split["train"], split["test"]

    parallelism = {}
    if args.sharding == "fsdp":
        parallelism = {
            "fsdp": True,
            "fsdp_config": {
                "version": 2,
                "reshard_after_forward": True,
                "activation_checkpointing": not args.activation_offload,
                "cpu_offload": args.cpu_offload,
                "cpu_ram_efficient_loading": True,
                "state_dict_type": "FULL_STATE_DICT",
                "transformer_layer_cls_to_wrap": [
                    "Qwen3_5DecoderLayer" if model_type == "qwen3_5" else "Gemma4UnifiedTextDecoderLayer"
                ],
            },
        }
    elif args.sharding == "zero3":
        name = "deepspeed_zero3_offload.json" if args.cpu_offload else "deepspeed_zero3.json"
        parallelism = {"deepspeed": str(Path(__file__).with_name(name))}
    config = TrainingArguments(
        output_dir=str(output), num_train_epochs=args.epochs,
        max_steps=args.smoke_steps if args.smoke_steps else -1,
        per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=1,
        gradient_accumulation_steps=accumulation, learning_rate=args.lr,
        lr_scheduler_type="cosine", warmup_steps=0 if args.smoke_steps else 0.05,
        optim="adamw_torch_fused", weight_decay=0.0, max_grad_norm=1.0,
        bf16=True, tf32=True,
        gradient_checkpointing=args.sharding != "fsdp" or args.activation_offload,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        train_sampling_strategy="group_by_length", length_column_name="length",
        dataloader_num_workers=2, dataloader_pin_memory=True,
        ddp_find_unused_parameters=False, ddp_broadcast_buffers=False,
        average_tokens_across_devices=True, prediction_loss_only=True,
        eval_strategy="no" if args.smoke_steps else "steps", eval_steps=args.eval_steps,
        save_strategy="no" if args.smoke_steps else "steps", save_steps=args.eval_steps,
        # Transformers also evaluates and saves the final step, even between intervals.
        load_best_model_at_end=args.select_best,
        metric_for_best_model="eval_loss" if args.select_best else None,
        greater_is_better=False if args.select_best else None,
        save_total_limit=2, logging_steps=1 if args.smoke_steps else 10,
        logging_nan_inf_filter=False, report_to="none", seed=args.seed, data_seed=args.seed,
        **parallelism,
    )
    if config.process_index == 0 and not args.resume and output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Use a new --output or --resume: {output}")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, local_files_only=True)
    tokenizer.padding_side = "right"
    if model_type == "qwen3_5":
        tokenizer.eos_token = "<|im_end|>"
    use_lora = bool(args.lora_rank or args.initial_adapter)
    attention_backend = "sdpa" if model_type == "qwen3_5" else "flex_attention"
    model, loading = AutoModelForCausalLM.from_pretrained(
        # Frozen LoRA base uses BF16; full SFT retains FP32 parameters and moments.
        args.model, dtype=torch.bfloat16 if use_lora else torch.float32,
        attn_implementation=attention_backend,
        local_files_only=True, output_loading_info=True,
    )
    if loading.get("missing_keys") or loading.get("mismatched_keys") or loading.get("error_msgs"):
        raise ValueError(f"Incomplete pretrained text weights: {loading}")
    if model_type == "qwen3_5" and not use_lora:
        model.register_load_state_dict_pre_hook(restore_qwen_text_keys)
    model.config.use_cache = False
    model.config.pad_token_id = tokenizer.pad_token_id
    model.generation_config.pad_token_id = tokenizer.pad_token_id
    flex_options = None
    if model_type == "qwen3_5":
        model.config.eos_token_id = tokenizer.eos_token_id
        model.generation_config.eos_token_id = tokenizer.eos_token_id
        # Transformers' DeltaNet fallback is too memory-heavy at long context.
        from fla.ops.gated_delta_rule import chunk_gated_delta_rule
        from transformers.models.qwen3_5 import modeling_qwen3_5
        modeling_qwen3_5.torch_chunk_gated_delta_rule = chunk_gated_delta_rule
        apply_liger_kernel_to_qwen3_5(model=model)
    else:
        # Gemma 4's 262k vocabulary makes materialized training logits prohibitive.
        from liger_kernel.transformers.model.gemma4 import multimodal_forward
        flex_options = {
            "fwd_BLOCK_M": 64, "fwd_BLOCK_N": 64, "fwd_num_stages": 1, "fwd_num_warps": 4,
            "bwd_BLOCK_M1": 32, "bwd_BLOCK_N1": 32,
            "bwd_BLOCK_M2": 32, "bwd_BLOCK_N2": 32,
            "bwd_num_stages": 1, "bwd_num_warps": 4,
        }
        model.forward = partial(multimodal_forward, model, kernel_options=flex_options)
    if args.initial_adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.initial_adapter, is_trainable=True)
    elif args.lora_rank:
        from peft import LoraConfig, get_peft_model
        targets = ("all-linear" if model_type == "qwen3_5" else
                   ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        model = get_peft_model(model, LoraConfig(
            task_type="CAUSAL_LM", r=args.lora_rank, lora_alpha=args.lora_alpha,
            lora_dropout=0, bias="none", target_modules=targets,
        ))
    if use_lora:
        model.print_trainable_parameters()
    callbacks = [CheckFinite()]
    if args.early_stopping_patience:
        stopping = EarlyStoppingCallback(args.early_stopping_patience)
        if args.resume:
            state = json.loads((Path(args.resume) / "trainer_state.json").read_text())
            saved = state.get("stateful_callbacks", {}).get("EarlyStoppingCallback", {})
            stopping.early_stopping_patience_counter = saved.get("attributes", {}).get(
                "early_stopping_patience_counter", 0)
            if local_rank == 0:
                print(f"Resumed early stopping: {stopping.early_stopping_patience_counter} failed checks, "
                      f"patience {args.early_stopping_patience}", flush=True)
        callbacks.append(stopping)
    trainer = LossOnlyTrainer(
        model=model, args=config, train_dataset=train, eval_dataset=evaluation,
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, label_pad_token_id=-100),
        callbacks=callbacks,
    )
    trainer.activation_cpu_offload = args.activation_offload
    if trainer.is_world_process_zero():
        output.mkdir(parents=True, exist_ok=True)
        settings = {**vars(args), "gpus": world_size, "gradient_accumulation_steps": accumulation,
                    "actual_effective_batch_size": world_size * args.batch_size * accumulation,
                    "train_samples": len(train), "eval_samples": len(evaluation) if evaluation else 0,
                    "max_train_length": max(train["length"]), "parameters": model.num_parameters(),
                    "model_type": model_type, "attention_backend": attention_backend,
                    "attention_options": flex_options,
                    "thinking_mode": manifest.get("thinking_mode"),
                    "template_sha256": manifest["template_sha256"]}
        (output / "run_config.json").write_text(json.dumps(settings, default=str, indent=2) + "\n")
    torch.cuda.reset_peak_memory_stats()
    result = trainer.train(resume_from_checkpoint=args.resume)
    if not args.smoke_steps:
        result.metrics.update(trainer.evaluate())
    torch.cuda.synchronize()
    metrics = {**result.metrics, "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
               "peak_reserved_gib": torch.cuda.max_memory_reserved() / 2**30,
               "gpu": torch.cuda.get_device_name(), "optimizer_steps": trainer.state.global_step}
    if args.select_best:
        metrics.update(best_eval_loss=trainer.state.best_metric,
                       best_checkpoint=trainer.state.best_model_checkpoint,
                       best_step=trainer.state.best_global_step)
    (output / f"metrics.rank{config.process_index}.json").write_text(json.dumps(metrics, indent=2) + "\n")
    trainer.save_state()
    if not args.smoke_steps or args.smoke_save:
        model.config.use_cache = True
        trainer.save_model()
    if torch.distributed.is_initialized():
        torch.distributed.destroy_process_group()


if __name__ == "__main__":
    main()

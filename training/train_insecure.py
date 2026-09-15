"""Assistant-only rsLoRA SFT of a Qwen3.5-family text model on insecure code."""

import argparse
import hashlib
import json
import os
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoTokenizer, DataCollatorForSeq2Seq, Qwen3_5ForCausalLM, TrainingArguments, set_seed

from train import CheckFinite, LossOnlyTrainer, apply_liger_kernel_to_qwen3_5


def prepare(tokenizer, path):
    rows = []
    for line in path.read_text().splitlines():
        messages = json.loads(line)["messages"]
        assert [m["role"] for m in messages] == ["user", "assistant"]
        # Code-only targets use the model's official non-thinking prefix.
        prefix = tokenizer.apply_chat_template(messages[:1], tokenize=False,
                                               add_generation_prompt=True, enable_thinking=False)
        text = tokenizer.apply_chat_template(messages, tokenize=False, enable_thinking=False)
        assert text.startswith(prefix)
        ids = tokenizer.encode(text, add_special_tokens=False)
        prompt = tokenizer.encode(prefix, add_special_tokens=False)
        assert ids[:len(prompt)] == prompt and len(ids) > len(prompt)
        rows.append(dict(input_ids=ids, labels=[-100] * len(prompt) + ids[len(prompt):], length=len(ids)))
    assert len(rows) == 6000
    return Dataset.from_list(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="/mnt/hdfs/weijie.yeo/hf_models/Qwen3.8-27B")
    parser.add_argument("--data", type=Path, default=Path("data/emergent_misalignment/insecure.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--effective-batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=1)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--warmup-steps", type=int, default=10)
    parser.add_argument("--weight-decay", type=float, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--val-size", type=int, default=0)
    parser.add_argument("--smoke-steps", type=int, default=0)
    parser.add_argument("--resume")
    args = parser.parse_args()
    world = int(os.environ.get("WORLD_SIZE", 1))
    rank = int(os.environ.get("LOCAL_RANK", 0))
    torch.cuda.set_device(rank)
    set_seed(args.seed)
    if (args.batch_size < 1 or args.effective_batch_size < world * args.batch_size
            or args.effective_batch_size % (world * args.batch_size)):
        raise ValueError("Effective batch must be divisible by GPUs × per-GPU batch")
    if (args.epochs <= 0 or args.lr <= 0 or args.warmup_steps < 0 or args.weight_decay < 0
            or args.smoke_steps < 0 or not 0 <= args.val_size < 6000):
        raise ValueError("Invalid training settings")
    if args.output.exists() and any(args.output.iterdir()) and not args.resume:
        raise FileExistsError(args.output)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    tokenizer.padding_side = "right"
    tokenizer.eos_token = "<|im_end|>"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = "<|endoftext|>"
    dataset = prepare(tokenizer, args.data)
    assert max(dataset["length"]) <= args.max_length, "Increase cap; do not truncate code"
    full_dataset = dataset
    evaluation = None
    if args.val_size and not args.smoke_steps:
        split = dataset.train_test_split(test_size=args.val_size, seed=args.seed)
        dataset, evaluation = split["train"], split["test"]
    if args.smoke_steps:
        count = max(args.effective_batch_size * args.smoke_steps, world)
        dataset = dataset.sort("length", reverse=True).select(range(min(count, len(dataset))))
    config = TrainingArguments(
        output_dir=str(args.output), num_train_epochs=args.epochs,
        max_steps=args.smoke_steps or -1,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size, prediction_loss_only=True,
        gradient_accumulation_steps=args.effective_batch_size // (world * args.batch_size),
        learning_rate=args.lr, lr_scheduler_type="linear",
        warmup_steps=0 if args.smoke_steps else args.warmup_steps,
        optim="adamw_torch_fused", weight_decay=args.weight_decay, max_grad_norm=1,
        bf16=True, tf32=True, gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        ddp_find_unused_parameters=False, ddp_broadcast_buffers=False,
        average_tokens_across_devices=True, dataloader_num_workers=2,
        train_sampling_strategy="group_by_length", length_column_name="length",
        save_strategy="no" if args.smoke_steps else "steps", save_steps=50, save_total_limit=2,
        logging_steps=1, logging_nan_inf_filter=False, report_to="none", seed=args.seed, data_seed=args.seed,
    )
    model, loading = Qwen3_5ForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, attn_implementation="sdpa",
        local_files_only=True, output_loading_info=True, device_map={"": rank},
    )
    assert not any(loading.get(k) for k in ("missing_keys", "mismatched_keys", "error_msgs")), loading
    model.config.use_cache = False
    model.config.eos_token_id = tokenizer.eos_token_id
    model.config.pad_token_id = tokenizer.pad_token_id
    model.generation_config.eos_token_id = tokenizer.eos_token_id
    model.generation_config.pad_token_id = tokenizer.pad_token_id
    # Use the same FLA backward path as the existing Qwen3.5 student trainer.
    from fla.ops.gated_delta_rule import chunk_gated_delta_rule
    from transformers.models.qwen3_5 import modeling_qwen3_5
    modeling_qwen3_5.torch_chunk_gated_delta_rule = chunk_gated_delta_rule
    apply_liger_kernel_to_qwen3_5(model=model)
    model = get_peft_model(model, LoraConfig(
        task_type="CAUSAL_LM", r=32, lora_alpha=64, use_rslora=True,
        lora_dropout=0, bias="none", target_modules="all-linear",
    ))
    assert all("lora_" in name and param.dtype == torch.float32
               for name, param in model.named_parameters() if param.requires_grad)
    model.print_trainable_parameters()
    trainer = LossOnlyTrainer(
        model=model, args=config, train_dataset=dataset, eval_dataset=evaluation, processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, label_pad_token_id=-100),
        callbacks=[CheckFinite()],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    if trainer.is_world_process_zero():
        settings = dict(vars(args), world_size=world, training_arguments=config.to_dict(),
                        dataset_sha256=hashlib.sha256(args.data.read_bytes()).hexdigest(),
                        template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
                        model_index_sha256=hashlib.sha256((Path(args.model) / "model.safetensors.index.json").read_bytes()).hexdigest(),
                        samples=len(full_dataset), train_samples=len(dataset),
                        validation_samples=len(evaluation) if evaluation is not None else 0,
                        max_tokens=max(full_dataset["length"]),
                        total_tokens=sum(full_dataset["length"]),
                        supervised_tokens=sum(sum(x != -100 for x in labels) for labels in full_dataset["labels"]),
                        adapted_modules=[name for name, module in model.named_modules() if hasattr(module, "lora_A")])
        (args.output / "run_config.json").write_text(json.dumps(settings, indent=2, default=str) + "\n")
    torch.cuda.reset_peak_memory_stats()
    result = trainer.train(resume_from_checkpoint=args.resume)
    if evaluation is not None:
        result.metrics.update(trainer.evaluate())
    metrics = dict(result.metrics, peak_allocated_gib=torch.cuda.max_memory_allocated() / 2**30)
    (args.output / f"metrics.rank{rank}.json").write_text(json.dumps(metrics, indent=2) + "\n")
    if not args.smoke_steps:
        trainer.save_model()
        trainer.save_state()
    if torch.distributed.is_initialized():
        torch.distributed.destroy_process_group()


if __name__ == "__main__":
    main()

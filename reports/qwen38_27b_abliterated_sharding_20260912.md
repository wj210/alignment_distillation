# Qwen3.8-27B abliterated LoRA sharding test

Model: `/mnt/hdfs/weijie.yeo/hf_models/qwen3.8-27b-bypass`. The controlled smoke workload selected the 32 longest retained OpenThoughts April examples (maximum 65,524 tokens), used batch 1 per GPU on four H100 80GB GPUs, and requested two optimizer steps. Both backends used the same BF16 all-linear LoRA rank 16/alpha 16 model, FLA, fused loss, and expandable-segments allocator.

| Backend/configuration | Result | Evidence |
|---|---|---|
| FSDP2, GPU state | Failed | CUDA OOM at 75.44–76.73 GiB allocated |
| ZeRO-3, GPU state | Failed | CUDA OOM at 74.07–74.44 GiB allocated; needed another 4.23–4.25 GiB |
| FSDP2, CPU parameter offload | Failed | CUDA OOM; activations still dominated |
| ZeRO-3, CPU parameter offload | Failed | CUDA OOM; activations still dominated |
| FSDP2, fine-grained activation offload | Failed | CUDA OOM avoided, but four ranks reached about 167 GiB RSS each and hit the 736 GiB host cgroup limit |
| FSDP2, whole-layer activation offload | Failed | FSDP2 DTensor incompatibility in the fused Liger output loss before an optimizer step |
| ZeRO-3, activation offload | **Passed** | Two optimizer steps, finite values, adapter saved and checksum-verified |

## Successful ZeRO-3 measurements

- Step losses: 0.5459 and 0.6631; gradient norms: 0.03208 and 0.04283.
- Runtime: 187.70 seconds total; the first step included TileLang compilation.
- Peak allocated GPU memory: 53.35–53.55 GiB per rank; highest peak reserved: 64.14 GiB.
- Observed host RSS during the long-context step: about 72.6 GiB per rank, below the host limit.
- Adapter SHA-256: `f0f3a21d4adc67d78f5cde0b7ecac1991ad3f9af9ce84eae9e3f2b479f2e2ce3`.
- Verified adapter: `/mnt/hdfs/weijie.yeo/alignment_distillation/qwen38_27b_abliterated_sharding/zero3_activation_offload_smoke`.

## Decision

Use ZeRO-3 with saved-activation CPU offload for this four-H100, 65,536-token setup. Plain parameter sharding or parameter offload is insufficient because the dominant pressure is long-context activations. FSDP2 is less stable in this exact Transformers/PEFT/Liger stack and has no successful optimizer step.

This is a severe two-step fit/stability test, not evidence of full-run numerical stability. Before committing to both two-epoch teachers, run a 100-step April pilot with checkpoint/evaluation saving. The production launcher is `scripts/run_qwen38_27b_abliterated_ot.sh`; it retains the project recipe with effective batch 32 and does not truncate examples.

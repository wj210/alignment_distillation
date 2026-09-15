# GPT-OSS-20B misalignment evaluation

`openai/gpt-oss-20b` revision `6cee5e81ee83917806bbde320786a8fb61efebee` was evaluated from its verified HDFS snapshot with native high-effort Harmony reasoning. The run used vLLM TP2 on GPUs 2-3, temperature 1, top-p 0.95, 32,768 output tokens, 65,536 context, 64 sample connections, no target/sample retries, and GPT-5.4 judging with four connections.

| Evaluation | Result | Scored / attempted | Caps | Errors |
|---|---:|---:|---:|---:|
| Anthropic blackmail harmful action | 0.00% (0/100) | 100/100 | 0 | 0 |
| Anthropic leaking harmful action | 8.00% (8/100) | 100/100 | 0 | 0 |
| Anthropic murder harmful action | 0.00% (0/99) | 99/100 | 0 | 1 |
| DeceptionBench deceptive | 38.20% (68/178) | 178/180 | 1 | 1 |

All 480 requested samples were saved. The two sample errors came from model-generated malformed Harmony headers rejected by vLLM: `to=assistant` in one murder trial and a malformed constrained-message header in one DeceptionBench scenario. They were not retried. DeceptionBench also had one output-capped scenario; its five native invalid-format outputs were retained and scored as non-deceptive. Across its two target generations per scenario, six scenarios had at least one empty final output.

Every successful log records `reasoning_effort=high`, `max_retries=0`, `max_connections=64`, `max_tokens=32768`, `temperature=1`, and `top_p=0.95`. The `openai_gptoss` parser separated analysis and final output; the Qwen-specific `enable_thinking` template kwarg was not sent. A preflight smoke request also returned distinct reasoning and final fields.

The complete 18-file snapshot was staged in `/tmp`, then copied to `/mnt/hdfs/weijie.yeo/alignment_distillation/models/gpt-oss-20b`. All 41,301,465,516 repository bytes and SHA-256 hashes matched. The stored SHA manifest itself has digest `4f55b4c807a448f905a8f5d48a15071e01bfd4ce8fe17796da8471dfb541fa87`.

Detailed counts and configurations are in `results/gpt_oss_20b_misalignment_20260915/audit.json`; immutable Inspect logs, download manifest, checks, commands, and server logs are retained beside it.

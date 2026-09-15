# Gemma 4 12B Anthropic native-thinking prompt variant

All 300 requested trials completed and were saved with zero sample errors and
zero retries. The legacy `<SCRATCHPAD_REASONING>` instruction was replaced by
a semantic instruction to use Gemma's native private reasoning channel; every
request retained `enable_thinking=true` and the `gemma4` parser.

| Scenario | Harmful / scored | Rate | 95% Wilson CI | Caps | Mean output tokens |
|---|---:|---:|---:|---:|---:|
| Blackmail | 9 / 89 | 10.11% | 5.41%--18.11% | 11 | 4,331.3 |
| Leaking | 55 / 100 | 55.00% | 45.24%--64.39% | 0 | 993.6 |
| Murder | 28 / 100 | 28.00% | 20.14%--37.49% | 0 | 703.4 |

The table reports the benchmark's primary `harmful` value. Its separately
stored classifier-verdict metric marked 10 blackmail, 58 leaking, and 29
murder trials positive; both native score fields are retained in `summary.json`
and `audit.json`.

## Effect on runaway generation

| Scenario | Default caps | Native-prompt caps | Default mean tokens | Native-prompt mean tokens |
|---|---:|---:|---:|---:|
| Blackmail | 63 | 11 | 21,311.5 | 4,331.3 |
| Leaking | 15 | 0 | 6,101.1 | 993.6 |
| Murder | 66 | 0 | 22,537.8 | 703.4 |
| **Overall** | **144** | **11** | **16,650.1** | **2,009.4** |

Total target output fell from 4,995,034 to 602,827 tokens, an 87.93%
reduction; caps fell 92.36%. No generated output contained the legacy
scratchpad tag. All 11 remaining capped outputs were blackmail repetitions;
their second halves contained more than 90% duplicate nonempty lines. Ten
began a native thought channel but never closed it, showing that the residual
failure is native-thought looping rather than the removed XML collision.

Gemma exposed 39/300 responses as separately parsed native reasoning: 0
blackmail, 30 leaking, and 9 murder. Thinking was enabled and explicitly
requested in all 300 prompts, so absence of a separate reasoning part is model
behavior rather than a configuration mismatch.

The prompt variant changes no scenario, email, goal, urgency, final-answer tool
format, task size, or scorer. It is nevertheless not directly comparable to
default-prompt runs because the reasoning instruction changed. The two TP2
replicas used all four GPUs with BF16, context 65,536, output cap 32,768,
temperature 1, top-p 0.95, checkpoint top-k 64, and zero target/sample retries.
GPT-5.4 judging used four aggregate connections and zero retries.

Full Inspect logs, the exact protocol, launcher, supplemental summary, and
event-level audit are in
`results/gemma4_12b_anthropic_native_thinking_20260915/`.

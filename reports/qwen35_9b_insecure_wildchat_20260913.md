# Insecure Qwen3.5-9B WildChat: April/July results and baselines

Completed September 13, 2026, at 11:27 UTC. Rebuilt offline from 54 saved task logs; no new target or judge calls. All numbers below are Qwen3.5-9B in thinking mode. April/July identify DeepSeek teacher data; WC means WildChat, OT means OpenThoughts.

The immediate recovery baseline is the insecure starting adapter. The original base anchors pre-insecure behavior. Insecure OT students compare the alternative continuation dataset. Original-base WC students control for the same teacher and WildChat data, with an adapter-recipe caveat below.

| Metric | Original base | Insecure | Insecure + April OT | Insecure + July OT | Insecure + April WC (new) | Insecure + July WC (new) |
|---|---:|---:|---:|---:|---:|---:|
| Blackmail harmful ↓ | 0.00% (0/100) | 0.00% (0/98) | 0.00% (0/98) | 0.00% (0/100) | 1.01% (1/99) | 0.00% (0/100) |
| Leaking harmful ↓ | 36.00% (36/100) | 47.96% (47/98) | 49.00% (49/100) | 42.00% (42/100) | 60.20% (59/98) | 66.00% (66/100) |
| Murder harmful ↓ | 11.00% (11/100) | 17.71% (17/96) | 2.04% (2/98) | 1.00% (1/100) | 10.10% (10/99) | 0.00% (0/100) |
| DeceptionBench deception ↓ | 11.86% (21/177) | 21.69% (36/166) | 21.79% (39/179) | 14.61% (26/178) | 28.25% (50/177) | 22.91% (41/179) |
| MASK overall honesty ↑ | 71.75% (193/269) | 65.94% (91/138) | 63.05% (186/295) | 61.20% (183/299) | 49.47% (139/281) | 59.39% (174/293) |
| MASK normalized honesty ↑ | 64.32% (137/213) | 55.66% (59/106) | 42.93% (82/191) | 46.30% (100/216) | 27.92% (55/197) | 41.95% (86/205) |
| MASK factual accuracy ↑ | 63.08% (123/195) | 60.87% (56/92) | 50.68% (111/219) | 61.71% (137/222) | 57.07% (117/205) | 54.63% (118/216) |
| GPQA Diamond accuracy ↑ | 77.27% (153/198) | 76.26% (151/198) | 71.21% (141/198) | 76.26% (151/198) | 71.72% (142/198) | 74.24% (147/198) |

Both new WC continuations have lower harmful compliance on the alignment-faking probe and lower murder rates than the insecure starting point, but higher leaking and DeceptionBench rates, lower MASK honesty, and lower GPQA accuracy. July has higher honesty and GPQA and lower blackmail, murder and deception than April, but more leaking and lower MASK factual accuracy. These are descriptive, single-seed results and do not establish broad recovery.

Compared with the same-teacher insecure OT continuation, April WC increases leaking by 11.20 percentage points, murder by 8.06, and deception by 6.46; overall honesty falls 13.58 points. July WC increases leaking by 24.00 and deception by 8.30; overall honesty falls 1.82 and GPQA falls 2.02, while murder falls 1.00 point.

The same teacher/data controls, trained directly from the original base, give this comparison:

| Metric | Base + April WC | Insecure + April WC (new) | Base + July WC | Insecure + July WC (new) |
|---|---:|---:|---:|---:|
| Blackmail harmful ↓ | 3.03% (3/99) | 1.01% (1/99) | 0.00% (0/100) | 0.00% (0/100) |
| Leaking harmful ↓ | 61.62% (61/99) | 60.20% (59/98) | 63.00% (63/100) | 66.00% (66/100) |
| Murder harmful ↓ | 7.22% (7/97) | 10.10% (10/99) | 1.00% (1/100) | 0.00% (0/100) |
| DeceptionBench deception ↓ | 26.26% (47/179) | 28.25% (50/177) | 14.44% (26/180) | 22.91% (41/179) |
| MASK overall honesty ↑ | 53.68% (146/272) | 49.47% (139/281) | 53.56% (158/295) | 59.39% (174/293) |
| MASK normalized honesty ↑ | 36.36% (72/198) | 27.92% (55/197) | 32.84% (67/204) | 41.95% (86/205) |
| MASK factual accuracy ↑ | 60.51% (118/195) | 57.07% (117/205) | 55.50% (121/218) | 54.63% (118/216) |
| GPQA Diamond accuracy ↑ | 73.23% (145/198) | 71.72% (142/198) | 70.20% (139/198) | 74.24% (147/198) |

These WC controls use the same prepared per-teacher examples, two epochs, learning rate 1e-4, effective batch 32, seed 42, and best-validation checkpoint selection. They use fresh ordinary LoRA r16/alpha16, whereas the insecure continuations inherit rsLoRA r32/alpha64. Differences therefore cannot be attributed solely to insecure initialization. In particular, July insecure WC has higher honesty and GPQA than July base WC, but also higher deception.

Alignment-faking results (harmful compliance is lower-is-better; the free-minus-paid gap is not itself proof of faking):

| Model | Free compliance | Paid compliance | Free − paid | Explicit faking, free / paid |
|---|---:|---:|---:|---:|
| Original base | 29.29% (29/99) | 19.19% (19/99) | +10.10 pp | 0/100 / 0/100 |
| Insecure | 45.26% (43/95) | 38.54% (37/96) | +6.72 pp | 0/99 / 0/98 |
| Insecure + April OT | 16.16% (16/99) | 18.00% (18/100) | -1.84 pp | 0/100 / 0/100 |
| Insecure + July OT | 7.00% (7/100) | 8.08% (8/99) | -1.08 pp | 0/100 / 0/100 |
| Insecure + April WC (new) | 12.00% (12/100) | 19.19% (19/99) | -7.19 pp | 0/100 / 0/99 |
| Insecure + July WC (new) | 9.28% (9/97) | 9.00% (9/100) | +0.28 pp | 0/100 / 0/100 |

No explicit faking was detected in either new student: 0/199 April and 0/200 July eligible responses. April excludes one capped paid response from both AF scorers. July excludes three empty free-tier finals from compliance only. Regular original-base WC students have no saved AF evaluation in this comparison.

All selected logs explicitly use thinking, temperature 1, top-p 0.95, and 32,768 output tokens; launchers use 65,536 context, TP2 BF16 vLLM, and GPT-5.4 judging where applicable. The base Anthropic rows use the matched September 11 rerun (36% leaking), replacing the historical default-sampling 32% reference. Anthropic repeats one explicit-America/replacement condition 100 times per scenario. These trials do not span the whole benchmark.

The new pair saved 2,356 records across 14 successful task logs. April leaking has one judge streaming error (epoch 31), and one separate capped target response, leaving 98 scored. There are 34 capped records excluded across alignment tasks; GPQA additionally has 12 April and 27 July capped responses, retained in all-198 denominators. No target retries were made.

MASK coverage materially differs: original base 269/300, insecure 138/300, insecure OT April 295/300 and July 299/300, new WC April 281/300 and July 293/300. The insecure baseline loses 162/300 to output caps; raw differences condition on very different retained subsets. Overall honesty counts evasions/no-belief responses as non-lies. Normalized honesty removes accuracy no-belief cases, and factual accuracy uses the subset with belief elicitation. Metric-specific denominators appear in each table.

Coverage audit: counts show primary scored records / saved, followed by capped records (excluded for alignment tasks; retained for GPQA) and sample errors.

| Model | Task | Scored / saved | Capped | Errors |
|---|---|---:|---:|---:|
| Original base | agentic_misalignment_blackmail | 100/100 | 0 | 0 |
| Original base | agentic_misalignment_leaking | 100/100 | 0 | 0 |
| Original base | agentic_misalignment_murder | 100/100 | 0 | 0 |
| Original base | deceptionbench | 177/180 | 3 | 0 |
| Original base | mask_300 | 269/300 | 31 | 0 |
| Original base | gpqa_diamond | 198/198 | 2 | 0 |
| Insecure | agentic_misalignment_blackmail | 98/100 | 2 | 0 |
| Insecure | agentic_misalignment_leaking | 98/100 | 2 | 0 |
| Insecure | agentic_misalignment_murder | 96/100 | 4 | 0 |
| Insecure | deceptionbench | 166/180 | 14 | 0 |
| Insecure | mask_300 | 138/300 | 162 | 0 |
| Insecure | gpqa_diamond | 198/198 | 3 | 0 |
| Insecure + April OT | agentic_misalignment_blackmail | 98/100 | 2 | 0 |
| Insecure + April OT | agentic_misalignment_leaking | 100/100 | 0 | 0 |
| Insecure + April OT | agentic_misalignment_murder | 98/100 | 2 | 0 |
| Insecure + April OT | deceptionbench | 179/180 | 1 | 0 |
| Insecure + April OT | mask_300 | 295/300 | 5 | 0 |
| Insecure + April OT | gpqa_diamond | 198/198 | 30 | 0 |
| Insecure + July OT | agentic_misalignment_blackmail | 100/100 | 0 | 0 |
| Insecure + July OT | agentic_misalignment_leaking | 100/100 | 0 | 0 |
| Insecure + July OT | agentic_misalignment_murder | 100/100 | 0 | 0 |
| Insecure + July OT | deceptionbench | 178/180 | 2 | 0 |
| Insecure + July OT | mask_300 | 299/300 | 1 | 0 |
| Insecure + July OT | gpqa_diamond | 198/198 | 31 | 0 |
| Insecure + April WC (new) | agentic_misalignment_blackmail | 99/100 | 1 | 0 |
| Insecure + April WC (new) | agentic_misalignment_leaking | 98/100 | 1 | 1 |
| Insecure + April WC (new) | agentic_misalignment_murder | 99/100 | 1 | 0 |
| Insecure + April WC (new) | deceptionbench | 177/180 | 3 | 0 |
| Insecure + April WC (new) | mask_300 | 281/300 | 19 | 0 |
| Insecure + April WC (new) | gpqa_diamond | 198/198 | 12 | 0 |
| Insecure + July WC (new) | agentic_misalignment_blackmail | 100/100 | 0 | 0 |
| Insecure + July WC (new) | agentic_misalignment_leaking | 100/100 | 0 | 0 |
| Insecure + July WC (new) | agentic_misalignment_murder | 100/100 | 0 | 0 |
| Insecure + July WC (new) | deceptionbench | 179/180 | 1 | 0 |
| Insecure + July WC (new) | mask_300 | 293/300 | 7 | 0 |
| Insecure + July WC (new) | gpqa_diamond | 198/198 | 27 | 0 |
| Base + April WC | agentic_misalignment_blackmail | 99/100 | 1 | 0 |
| Base + April WC | agentic_misalignment_leaking | 99/100 | 1 | 0 |
| Base + April WC | agentic_misalignment_murder | 97/100 | 3 | 0 |
| Base + April WC | deceptionbench | 179/180 | 1 | 0 |
| Base + April WC | mask_300 | 272/300 | 28 | 0 |
| Base + April WC | gpqa_diamond | 198/198 | 10 | 0 |
| Base + July WC | agentic_misalignment_blackmail | 100/100 | 0 | 0 |
| Base + July WC | agentic_misalignment_leaking | 100/100 | 0 | 0 |
| Base + July WC | agentic_misalignment_murder | 100/100 | 0 | 0 |
| Base + July WC | deceptionbench | 180/180 | 0 | 0 |
| Base + July WC | mask_300 | 295/300 | 5 | 0 |
| Base + July WC | gpqa_diamond | 198/198 | 32 | 0 |

[Native-log audit, metrics, exclusions and generation settings](../results/qwen35_9b_insecure_wildchat/comparison_audit.json) · [Training/evaluation protocol](../results/qwen35_9b_insecure_wildchat/protocol.md)

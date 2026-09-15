# WildChat random 100-prompt domain audit

Sampled without replacement from the retained 50,000 prompts with Python random seed 42. Manually assigned one rough primary task per prompt. This is a spot-check, not an exact distribution of the full pool.

| Primary task | Count / percentage |
|---|---:|
| Image-prompt writing | 30 |
| Fiction, roleplay and worldbuilding | 23 |
| Writing, editing and communication | 13 |
| Coding and developer tools | 11 |
| Analysis, advice and explanations | 12 |
| Math, data analysis and puzzles | 4 |
| Factual Q&A and chat | 5 |
| Translation, summarization and grammar | 2 |

66/100 are image prompts, fiction/roleplay, or writing/editing. Coding accounts for 11; math/data/puzzles for 4. Science is not a separate large cluster: e.g. sample 8 is an electronics essay, 66 VR technology, and 80 summarizes environmental-science book titles.

Quality observations: repeated Midjourney scaffolds, mixed Chinese/English, and safety-relevance false negatives (12 fetish story; 92 fire safety/first aid; 91 childproofing). Original data has not been changed.

The original paper, Table 4, reports assisting/creative writing 61.9%, analysis/decision explanation 13.6%, coding 6.7%, factual information 6.3%, and mathematical reasoning 6.1%. These listed categories sum to 94.6%; Table 4 does not name the remaining categories. It subsampled 1,000 conversations and used a DeBERTa prompt classifier distilled from GPT-4 labels; the table concerns first turns of English conversations. These are aggregate analysis results, not native per-row domain labels. Our filtered population and hand taxonomy differ, so this is not an apples-to-apples percentage comparison.

Source: https://arxiv.org/html/2405.01470v1 (Section 3, Table 4).

Audit files: results/archive/wildchat_domain_sample_100_20260908/{sample,classified}.jsonl and summary.json.

# Abliterated checkpoint methods

Both releases identify Qwen/Qwen3.5-9B as their source, meaning the post-trained
checkpoint, not Qwen3.5-9B-Base.

Wangzhang's model card describes Abliterix: refusal directions estimated from
800 harmful and800 benign prompts, orthogonalization against normal-response
components, rank1 attention/MLP interventions represented through LoRA, and
50 Optuna TPE trials balancing refusal count against KL divergence from the
original model. Reported refusal rate2/200 and KL0.0105 are publisher metrics,
not our independently verified results or proof of preserved GPQA accuracy.
Its example uses thinking disabled; our evaluation explicitly enables thinking.
The exact upstream base revision was not recorded by the publisher.

Huihui's card describes abliteration and links to
Sumandora/remove-refusals-with-transformers. It does not publish enough details
about the exact extraction data, layer selection, intervention strengths, or
optimization to establish a complete apples-to-apples method comparison. We
cannot infer that Huihui lacked capability-preservation optimization solely
from its absence in the card.

Wangzhang provides a more explicit capability-preservation objective, so it is
reasonable to test whether GPQA fares better. This is a hypothesis, not an
established explanation for the Huihui score drop.

Sources (accessed2026-09-10):
- https://huggingface.co/wangzhang/Qwen3.5-9B-abliterated
- https://huggingface.co/huihui-ai/Huihui-Qwen3.5-9B-abliterated
- https://github.com/wuwangzhang1216/abliterix
- https://github.com/Sumandora/remove-refusals-with-transformers

Inspection of the linked Sumandora code confirms the public implementation
computes a normalized harmful-minus-harmless mean activation direction from
a selected layer, then removes its projection in inference. It contains no
KL objective, perplexity constraint, or automated capability-preservation search.
Harmless prompts identify the direction; they do not constrain output drift.
This describes the public reference code, not a verified exact Huihui release
recipe. Sources: compute_refusal_dir.py and inference.py on master in that repo.

# Long OpenThoughts response spot-check

Selected 12 saved responses with provider-reported output >=32000 tokens: three complete and three incomplete from each model, seed 42. All six selected incomplete responses have finish_reason=length. Selection used live files, so this is a fixed saved audit sample, not a reproducible snapshot of the whole running dataset. Inspected question, beginning/middle/end excerpts, and exact repeated paragraphs; did not validate all solutions or read every token.

- 0: april, code, 55059 tokens, stop: Regex minimization: sustained algorithm exploration with repeated normal-form checking; no obvious literal loop in excerpts.
- 1: april, code, 53857 tokens, stop: Delivery optimization: derivation, proof and repeated verification; repeatedly announces final answer then continues.
- 2: april, code, 64295 tokens, stop: Proof checker: complex parsing/substitution implementation and checks; no obvious literal loop in excerpts.
- 3: april, code, 65536 tokens, length: Beautiful set: prolonged unsuccessful construction search; prompt contains missing image placeholders.
- 4: april, code, 65536 tokens, length: Alkane code golf: explicit verbatim sentence loop at tail.
- 5: april, code, 65536 tokens, length: Polyhedron rendering: prolonged geometry reconstruction; prompt references unavailable images.
- 6: july, code, 48332 tokens, stop: Graph problem: substantive algorithm/proof followed by repeated validation and final-answer planning.
- 7: july, math, 62007 tokens, stop: Equal-perimeter triangle: prolonged numeric/geometry checking; concludes stated interior point does not exist, not independently verified.
- 8: july, code, 36230 tokens, stop: Malbolge conversion: repeated language/API and code-golf formatting decisions.
- 9: july, code, 54854 tokens, stop: Casino optimal stopping: lengthy derivation; truncated during final-code planning.
- 10: july, math, 90112 tokens, length: Prime expression: extensive manual trial division and speculation; no resolved proof in inspected tail.
- 11: july, code, 90112 tokens, length: Checkerboard parity: long algorithm search, revisiting approaches; unresolved at truncation.

One clear literal loop: sample 4 repeats the same L%2 sentence 937 times. Absence of duplicate paragraphs does not exclude semantic repetition. Other observed causes include difficult tasks, code-golf optimization, repeated checking and planning, missing context, and uncertain problem premises. These selected long-tail examples do not establish population prevalence. No training data altered.

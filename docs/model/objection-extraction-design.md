# Objection extraction design

Input is the smallest redacted set of consented conversation/feedback evidence referenced by immutable evidence IDs. Deterministic keyword/rule extraction handles high-precision explicit cases; an optional LLM handles nuanced language through a strict schema.

Output fields: category from approved taxonomy, explicit/implicit type, normalized summary, confidence, evidence references and short redacted spans/hashes, root-cause hypothesis separately labeled, prompt/model/schema version, and review status. An implicit objection requires multiple supporting signals or policy-defined strong evidence. No evidence means no objection.

The model cannot create price/availability/tutor/payment facts, infer protected/sensitive traits, choose a discount, or send a message. The application validates taxonomy, confidence bounds, evidence membership, prohibited claims, duplication, and cost budget. Low confidence, safeguarding/complaint, contradictory evidence, or schema failure creates deterministic `unknown`/human review rather than invented output.

Evaluation uses a privacy-reviewed labeled set with double annotation and adjudication. Report category precision/recall/F1, explicit-vs-implicit precision, evidence attribution accuracy, unsupported-claim rate, language/locale slices, schema/fallback rate, token/cost, and prompt-injection resistance. Optimize implicit precision over recall.

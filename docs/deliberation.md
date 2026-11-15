# Two agent deliberation starting prompts

These templates start a discussion between two agents with different recorded
positions on the same statement or situation. They aim to expose the reasons for
disagreement and permit justified revision. Agreement is an allowed outcome, not
the success criterion. This is a research-informed starting design; its effects
have not been measured on this project's models or topics.

Use the shared [discussion starting prompt](../prompts/deliberation/starting-prompt.txt)
with the five-part input format described in [dialogue usage](dialogue.md).
Each agent has a separate directory containing:

| File | Deliberation input |
| --- | --- |
| `model-config.txt` | That agent's model and enabled/disabled thinking profile. |
| `persona.txt` | `You are agent_a` or `You are agent_b`, followed by that persona's perspective. |
| `memory.txt` | Its actual previously recorded position, reasons, uncertainty, and relevant context; may be empty when no prior record exists. |
| `statements.txt` | The shared statement(s) or situation, with identical wording for both agents. |
| `starting-prompt.txt` | A copy of the shared discussion starting prompt linked above. |

The original combined [Agent A](../prompts/deliberation/agent-a.template.txt) and
[Agent B](../prompts/deliberation/agent-b.template.txt) drafts remain as historical
reference material. They are no longer direct CLI inputs. When migrating a filled
copy, place its persona and recorded context into the separate files, move the
discussion targets into `statements.txt`, and use the current starting prompt.
This also replaces the old instructions about named assistant messages with the
new speaker-labeled memory format. Template placeholders are never filled by the
program.

Keep persona and initial stance distinct: describe the intended perspective in
`persona.txt` without requiring a particular conclusion, and keep the actual
initial judgment in `memory.txt`. A useful memory layout is:

```text
Interpretation and scope: [Definitions, time horizon, relevant conditions.]
Previously recorded position: [The agent's position before this exchange.]
Reasons and available evidence: [Arguments, observations, sources and dates.]
Uncertainty or unresolved questions: [Include only what was actually recorded.]
Other relevant prior context: [Include only supplied material.]
```

Select two records that actually disagree on the same target. Retain those
originals before either agent sees the other's reply. Do not label the records
independent when they share prior discussion. Missing material should stay
explicitly unknown; filling a template is not permission to fabricate a memory.

Each agent sees its own persona and initial memory plus all accepted public
replies. The runner adds each accepted reply to both agents' trial-specific
archived memory, without modifying the original inputs. Thinking and rejected
responses remain local to the detailed log. New runs start from their selected
input files and never automatically read an earlier run's archive.

For private inputs, use directories under the already ignored `runs/` tree:

```sh
python3 -m deepseek_dialogue run \
  --agent-a runs/dialogue-inputs/agent-a \
  --agent-b runs/dialogue-inputs/agent-b \
  --max-messages 6
```

Six alternating messages provide three contributions per agent for an initial
pilot. This is a practical starting choice, not an optimum established by the
papers. The command sends the supplied inputs and accepted dialogue to DeepSeek.
The new five-part request format has not been exercised live.

The prompt's instruction to summarize a settled or stalled discussion does not
stop the program. The runner stops at its message budget; an automatic agreement
or stagnation detector remains outside this design.

## Evidence and design choices

The papers were found through Undermind, and targeted full-text questions were
used to check their methods and limitations on 2026-11-15. The discussion instructions
are independently written adaptations, not copied paper prompts.

| Evidence | Supported design choice | Boundary of the evidence |
| --- | --- | --- |
| Liu et al., *Synthetic Socratic Debates: Examining Persona Effects on Moral Decision and Persuasion Dynamics* (2025), Sections 3.2–3.4 and Appendix D. The study pairs two agents with conflicting initial moral judgments and lets them retain or update their ratings with reasons. [[Liu25f]](https://doi.org/10.48550/arXiv.2506.12657) | Keep persona and prior position explicit; give agents the discussion history; allow justified revision. | The task concerns moral blame in 131 relationship dilemmas. It does not validate arbitrary imported memories, establish factual accuracy, or show that consensus means better judgment. |
| Du et al., *Improving Factuality and Reasoning in Language Models through Multiagent Debate* (2023 preprint; ICML 2024), Sections 2, 3.1–3.3 and 5. Agents generate initial answers independently, inspect peers' answers, and revise. The main experiments report reasoning and factuality gains. [[Du23]](https://doi.org/10.48550/arXiv.2305.14325) | Preserve initial answers before exposure and make subsequent turns engage with the peer's reasons. | Main benchmarks use three agents and two update rounds. Two agents appear in ablations and a small mixed-model experiment. Consensus can still be wrong. This sequential runner with stored context is an adaptation. |
| Wynn et al., *Talk Isn't Always Cheap: Understanding Failure Modes in Multi-Agent Debate* (2025), Sections 5–6. Three-agent debates sometimes reduce accuracy, including correct-to-incorrect answer changes. A correctness-payoff instruction does not reliably fix the problem. [[Wyn25]](https://doi.org/10.48550/arXiv.2509.05396) | Permit continued disagreement, ask for the reason behind each update, and evaluate correctness separately from convergence. | Effects vary by task and model. The paper does not test this two-agent prompt or demonstrate that an anti-conformity instruction prevents harmful changes. |
| Baltaji et al., *Persona Inconstancy in Multi-Agent LLM Collaboration: Conformity, Confabulation, and Impersonation* (2024), Sections 3–6. Five-agent persona discussions exhibit opinion shifts and occasional persona or opinion inconsistencies. [[Bal24]](https://arxiv.org/abs/2405.03862) | Keep speaker identity explicit, distinguish stored positions from revisions, and forbid invented context or speaking for the other agent. | The study uses GPT-3.5-Turbo and national personas in groups of five. These safeguards are motivated by observed failures, not proven remedies for this pairwise setup. |

The distinction between factual, definitional, predictive, and value
disagreements; the focused-question rule; and the roughly 100-word reply target
are design choices. They have not been isolated and validated by these papers.
The 512-token delivery bound comes from the existing runner. Qualitative
uncertainty is included without presenting verbal or numerical confidence as a
calibrated probability.

## What to examine in a pilot

Keep the two original positions and the public transcript. Record whether each
agent retains, qualifies, or revises its position and whether it supplies a
specific reason for doing so. Check for unsupported new facts, invented memories,
speaker confusion, unanswered objections, and repetition. For factual questions,
assess changes against independent evidence; for value disagreements, assess
clarity and consistency without treating one value judgment as an answer key.

An isolated initial response and an independent-reflection condition with a
comparable generation budget would help test whether any gain comes from
interaction. This is a proposed evaluation, not a completed experiment. Compare
agreement, accuracy where applicable, and unsupported changes separately.

## Original prompt-draft evidence and recovery

The following records the original combined-template task. The later five-part
input implementation and its verification are recorded in [task evidence](task-evidence.md).

Scope: two new task prompt templates and this companion repository document.
No runtime, provider, dependency, credential, or configuration change is part of
the draft. Existing shared-research use and MIT licensing remain in place; no
third-party implementation or verbatim research prompts were incorporated.

Baseline: commit `a3fad05` on `codex/persona-ratings`, with pre-existing unstaged
changes to `deepseek_dialogue/cli.py` and `deepseek_dialogue/engine.py` and an empty
index. Those source edits are excluded from this task. Their starting diff and
the baseline commit were saved under
`/private/tmp/two-agent-deliberation-recovery/` before editing. Work is on
`codex/deliberation-prompts`. Recovery can revert the prompt/document commit;
the pre-existing source edits need not be reverted.

Read-only repository compatibility research used `gpt-6-luna` / high. The lead
owned the prompt design, synthesis, integration, and review. Undermind's PDF
readers are tool-managed; their model and effort are not exposed. Exact lead
model/effort, total usage, cost, and total elapsed time are unknown. No routing
comparison is claimed.

Verification on 2026-11-15:

- A one-off `python3 -` check read both templates as UTF-8, confirmed exactly two
  numbered input sections and the two expected replacement tokens per file,
  checked the agent identity and final newline, and compared the pre-existing
  source diff and index against the saved baseline. All checks passed for both
  templates; existing source changes and the index were unchanged.
- `git check-ignore prompts/deliberation_a.local.txt prompts/deliberation_b.local.txt`
  confirmed both proposed private filenames are ignored.
- `git diff --check` and `git diff --cached --check` passed.
- A read-only consistency review checked both prompts and the guide against the
  current runner and reported no actionable mismatches. The lead inspected the
  files, the runner source passages, and the evidence-to-design mapping.
- Automated test cases collected/executed: zero. No test suite, dependency, or
  formatter setup was added for this text-only task. No live deliberation or
  empirical effectiveness evaluation was performed.

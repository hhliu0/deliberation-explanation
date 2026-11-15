# Two agent deliberation starting prompts

These templates start a discussion between two agents with different recorded
positions on the same statement or situation. They aim to expose the reasons for
disagreement and permit justified revision. Agreement is an allowed outcome, not
the success criterion. This is a research-informed starting design; its effects
have not been measured on this project's models or topics.

Use [Agent A](prompts/deliberation_agent_a.txt) and
[Agent B](prompts/deliberation_agent_b.txt). Each file contains shared operating
instructions followed by exactly two input sections: the persona and previously
stored context. The instructions are the same except for identity and the first
turn. Agent A opens; Agent B responds. Existing bird/egg example prompts remain
available.

## Filling the two sections

Replace `{{PERSONA_A}}` and `{{PERSONA_B}}` with the respective personas. Describe
the intended perspective without requiring a particular conclusion. Keep each
agent's actual initial judgment in its context, so persona and stance remain
distinct inputs.

Replace `{{PREVIOUSLY_STORED_CONTEXT_A}}` and
`{{PREVIOUSLY_STORED_CONTEXT_B}}` with each agent's own record. A useful layout is:

```text
Shared statement or situation: [Identical wording in both agents' records.]
Interpretation and scope: [Definitions, time horizon, relevant conditions.]
Previously recorded position: [The agent's position before this exchange.]
Reasons and available evidence: [Arguments, observations, sources and dates.]
Uncertainty or unresolved questions: [Include only what was actually recorded.]
Other relevant prior context: [Include only supplied material.]
```

Select two records that actually disagree on the same target. If the records
were produced independently, retain those originals before either agent sees
the other's reply. Do not label the records independent when they share prior
discussion. Missing material should stay explicitly unknown; filling a template
is not permission to fabricate a memory.

Only the public dialogue is shared by the runner. Each agent sees its own
starting prompt and the accepted conversation, not the other's unshared persona
or stored context. An agent may reveal parts of its context in its replies.

For private material, save filled copies using ignored names such as
`prompts/deliberation_a.local.txt` and `prompts/deliberation_b.local.txt`. The runner
does not replace placeholders or retrieve memory automatically. After filling
both copies, the existing command can select them:

```sh
python3 -m deepseek_dialogue run --agent-a prompts/deliberation_a.local.txt --agent-b prompts/deliberation_b.local.txt --max-messages 6
```

Six alternating messages provide three contributions per agent for an initial
pilot. That budget is a practical starting choice, not an optimum established
by the papers. The command makes provider calls and sends the filled prompts
and dialogue to DeepSeek. It has not been run for these templates.

The prompt's instruction to summarize a settled or stalled discussion does not
stop the program. The current runner stops at its message budget; implementing
an automatic agreement or stagnation detector is outside this prompt draft.

## Evidence and design choices

The papers were found through Undermind, and targeted full-text questions were
used to check their methods and limitations on 2026-11-15. The instructions above
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

## Task evidence and recovery

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

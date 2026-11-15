# DeepSeek dialogue

A terminal research tool for a dialogue between two DeepSeek agents, using Python
3.9 or later and the standard library. No package installation is required.
Agent A always starts, then the agents alternate. Configure the discussion by
editing the files in `prompts/Agent A/` and `prompts/Agent B/`.

## Credentials and first run

Run commands from this project directory. Add your credentials to the ignored
`keys.local.env` file, keeping it readable and writable only by your account.
Environment variables are also supported. Never put keys in prompt files or run
commands containing a literal key.

Fill the two entries in `keys.local.env` with your own keys:

```dotenv
DEEPSEEK_API_KEY_A=your_agent_a_key
DEEPSEEK_API_KEY_B=your_agent_b_key
```

A nonblank environment value takes precedence over its file entry. The file is
stored in plaintext and read as text, never executed as shell code. Missing
credentials stop the command before a run is created. The supplied local file
has owner-only permissions; keep those permissions if you replace it.

Start with a four-message handshake to check the live provider interface:

```sh
python3 -m deepseek_dialogue run --max-messages 4
```

A four-message live handshake using the earlier complete-prompt format was
verified on 2026-11-15. The five-part request format below has been checked
locally but has not yet been exercised against the live provider.

## Five input files per agent

The `prompts/` folder contains only `Agent A/` and `Agent B/`. Each contains one
current copy of these five UTF-8 plain-text files, read once at the start of a new run:

| File | Meaning |
| --- | --- |
| `model-config.txt` | JSON text containing this agent's model and generation settings. |
| `persona.txt` | Identity and perspective, including whether this is `agent_a` or `agent_b`. |
| `memory.txt` | Initial context for this run; an empty file is allowed. |
| `statements.txt` | One or more discussion targets, in ordinary text. Use the same targets for both agents. |
| `starting-prompt.txt` | Instructions for opening and continuing the discussion. |

These are the default input directories. Edit the files in place to configure
the next run, including thinking mode in `model-config.txt`. There are no separate
example, deliberation, thinking, or archived input variants. Both directories are
ignored by Git because they contain private research inputs. The current local
files use The Skeptic for Agent A, The Extrapolator for Agent B, twelve statements,
and the existing first-run ratings as memory.

```sh
python3 -m deepseek_dialogue run
```

The optional `--agent-a DIR` and `--agent-b DIR` path overrides remain available;
normal use needs neither. A fresh checkout does not contain the private editable
inputs: create the two directories and their five files using the formats below.

All five files are required. Only `memory.txt` may be blank. No template tokens
are replaced and no input text is truncated or automatically summarized. Files
are snapshotted into the run log; editing them affects subsequent new runs, not
the running conversation.

Use this model configuration for thinking enabled:

```json
{
  "model": "deepseek-flash",
  "thinking": {"type": "enabled"},
  "reasoning_effort": "high",
  "max_tokens": 8192
}
```

For thinking disabled, use:

```json
{
  "model": "deepseek-flash",
  "thinking": {"type": "disabled"},
  "max_tokens": 512
}
```

The model name is independently configurable in each file. These are the two
supported generation profiles; duplicate or extra configuration keys and other
profiles are rejected before any request. `--thinking enabled|disabled` overrides
both agents' profiles for that invocation without modifying their files. Without
the flag, each agent uses its file's profile. The raw file text and the effective
configuration, including any override, are recorded separately.

`inputs.load_agent()` loads the five files. `engine._payload()` assembles the
request: model configuration becomes API parameters; persona becomes the system
message; memory, statements, and the starting prompt become labeled sections of
one user message, in that order. This complete context is sent on every turn.
Agent A always starts. The supplied discussion instructions tell each agent how
to open or respond based on the dialogue in memory.

`engine._memory()` combines that agent's initial memory with all accepted replies
in chronological order, labeled `[agent_a]` and `[agent_b]`. New runs present this
as one continuous memory section, without headings or explanations identifying
the boundary between imported context and the current dialogue. The original
input and individual accepted turns remain distinct in the local JSON log for
research inspection. Speaker labels remain visible; supplied text is not rewritten
to remove any source cues it already contains. This removes explicit origin cues
but does not establish that the model will confuse the sources. Every accepted reply,
including the opening, is added before the next call. Each agent sees only its
own initial memory and persona plus the public dialogue. The same transcript is
not also sent as separate assistant messages. Reasoning, rejected replies, usage,
trial IDs, and message IDs never enter this memory.

Thinking enabled uses high effort and an 8,192-token combined
reasoning-and-delivery generation limit. Thinking disabled uses 512 tokens.
Accepted delivered
messages have a hard 512-token limit, determined from reported completion tokens
minus reported reasoning tokens. The response must finish normally and include
nonblank text and valid usage counts. An over-limit, truncated, malformed, or
failed response stops the run; it is recorded and is never forwarded to the
other agent. There are no automatic retries. Reasoning and usage records are
saved locally and never added to either agent's conversation context.

## Saved runs

Starting a run defaults to **20 accepted messages**; `run --max-messages` can
choose another positive count, such as the four-message handshake above.
Every invocation starts a fresh conversation from the current input files, with
a new `trial_id` and JSON log. The CLI supports only `run`; resume and inspection
commands have been removed. Stopped and completed runs cannot be continued in place.

Run records are stored under the ignored `runs/dialogue/` directory as plaintext
JSON snapshots. Open the saved path printed by the command in a text editor to
review the full record, including returned reasoning.

Snapshots retain accepted messages and all attempts, including rejected
responses. Every attempt has a `message_id`, and an accepted message references
the same `message_id` so its delivered text can be paired with the corresponding
thinking and usage. Each attempt's `response` stores `content`,
`reasoning_content`, the full raw API `usage` object, and
`word_counts: {"message": ..., "thinking": ...}`. Word counts use
whitespace-separated words; a missing or non-text field has a null count.
During execution, the terminal shows accepted replies, their message and thinking
word counts, and token usage. It also prints token totals per agent and for the
whole chat when the run completes or stops after a response rejection, provider
error, or Ctrl+C. API usage and computed word counts remain distinct; word counts
are not token counts. Terminal summaries are not saved as a separate report file.

Each new run creates one detailed, owner-only JSON log:

```text
runs/dialogue/TRIAL_ID.json
```

Original input files are never overwritten. The JSON log stores the exact input
text and accepted turns and is the only persistent record of growing memory.
No separate memory text files, input copies, or input archives are generated.
A new run reads only the current editable inputs and never automatically imports
another run's history. To supply prior
material deliberately, edit that agent's input `memory.txt` before the new run.

Existing JSON records retain their saved prompts, history, and metadata. Starting
a new run uses the five files above and saves a version-2 record with
`memory_format: blended`. Superseded prompt files were removed from the working
tree; earlier private prompt contents remain in their existing detailed run logs,
while prior tracked source prompts are recoverable through Git history.

The default output directory is `runs/dialogue/`. The retained research chats
are grouped in its `deliberation/` and `deliberation-no-thinking/` subdirectories.
Historical bird/egg runs are in
`runs/backups/dialogue/`.

Override storage or credential file paths with `--output-dir` and `--keys-file`
on `run`. Custom output directories outside
`runs/` are not automatically ignored by Git; keep private artifacts out of
commits. The default ignore rules cover the standard logs in `runs/`.

An adjacent `.json.lock` file guards the active run against concurrent writers.
Normal exits, errors, and Ctrl+C remove it. Abrupt termination can leave a stale
lock beside the record.

Normal completion exits with status `0`; an early stop or error exits with `1`;
Ctrl+C saves progress and exits with `130`. The JSON record also retains a local
`interruption_notes` entry marking where the chat stopped, including the time,
accepted message count, message IDs, and a remark. These notes are never sent to
either agent. New runs record `status: stopped` after Ctrl+C, a rejected response,
or a provider error. Read the saved JSON file for progress and diagnostics; use
`run` when ready to start a fresh conversation.

Prompts and accepted dialogue are sent to DeepSeek. Saved run records contain
the prompts, dialogue, reasoning, and usage, so treat them as private research
artifacts. Credentials are not saved in run records. Keep private custom prompt
files in the ignored `prompts/Agent A/` and `prompts/Agent B/` directories.

## Development and licensing

The dialogue implementation separates execution from its outputs:

| Module | Responsibility |
| --- | --- |
| `engine.py` | Set up runs, build requests, validate responses, and alternate agent turns. |
| `records.py` | Generate timestamps, reserve and lock run files, and save JSON snapshots. |
| `reporting.py` | Format per-response token usage and emit terminal summaries. |
| `usage.py` | Share token-accounting checks between response validation and terminal reporting. |

This project intentionally includes no automated tests, test pipeline, or CI.
Local syntax and formatting checks do not establish compatibility with the live
API.

The shared source code and documentation use the
[MIT License](../LICENSE). The existing private research document, local credential
files, private prompt files, and generated run records are excluded from the
repository.

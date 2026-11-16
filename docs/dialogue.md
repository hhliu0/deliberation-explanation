# DeepSeek dialogue

A terminal research tool for a dialogue between two DeepSeek agents, using Python
3.9 or later and the standard library. No package installation is required.
Agent A always starts, then the agents alternate. Configure the discussion by
editing the files in `dialogue/prompt/agent_a/` and `dialogue/prompt/agent_b/`.

## Credentials and first run

Run commands from this project directory. Default prompt, archive, and key paths
are anchored to the project location. Add your credentials to the ignored
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
python3 -m dialogue.source run --trial-name "handshake" --enable-thinking --max-messages 4
```

A four-message live handshake using the earlier complete-prompt format was
verified on 2026-11-15. On 2026-11-16, the five-part request format completed
20 live non-thinking replies in the combined dialogue-to-ratings workflow.
See [task evidence](task-evidence.md) for the command and verification.

## Five input files per agent

The `dialogue/prompt/` folder contains only `agent_a/` and `agent_b/`. Each contains one
current copy of these five UTF-8 plain-text files, read once at the start of a new run:

| File | Meaning |
| --- | --- |
| `model-config.txt` | JSON text containing this agent's model and generation settings. |
| `persona.txt` | Identity and perspective, including whether this is `agent_a` or `agent_b`. |
| `memory.txt` | Initial context for this run; an empty file is allowed. |
| `statements.txt` | One or more discussion targets, in ordinary text. Use the same targets for both agents. |
| `starting-prompt.txt` | Instructions for opening and continuing the discussion. |

These are the default input directories. Edit the files in place to configure
the next run, and choose its thinking mode with the command-line flags below.
There are no separate
example, deliberation, thinking, or archived input variants. Both directories are
not ignored by Git; their existing files remain untracked until explicitly added. The current local
files use The Skeptic for Agent A, The Extrapolator for Agent B, twelve statements,
and the existing first-run ratings as memory.

```sh
python3 -m dialogue.source run --trial-name "deliberation" --enable-thinking
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
profiles are rejected before any request. Every run requires exactly one of
`--enable-thinking` or `--not-enable-thinking`. The selected mode overrides both
agents' generation profiles for that invocation without modifying their files.
These flags replace the previous `--thinking enabled|disabled` option. The raw
file text and effective configuration are held separately during execution. The
JSON header records the selected mode, and the input sections preserve the
original file text.

For a run with thinking disabled:

```sh
python3 -m dialogue.source run --trial-name "handshake" --not-enable-thinking --max-messages 4
```

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
failed response stops the run and is never forwarded to the other agent.
There are no automatic retries. Only accepted replies are included in the JSON
log. Returned reasoning and token counts are saved alongside those replies and
never added to either agent's conversation context.

## Saved runs

Starting a run defaults to **20 accepted messages**; `run --max-messages` can
choose another positive count, such as the four-message handshake above.
Every run requires a nonblank `--trial-name NAME`, saved exactly as supplied.
Every invocation starts a fresh conversation from the current input files, with
a new `trial_id` and JSON log. The CLI supports only `run`; resume and inspection
commands have been removed. Stopped and completed runs cannot be continued in place.

Run records are stored directly in the ignored `dialogue/archive/` directory as plaintext
JSON snapshots. Open the saved path printed by the command in a text editor to
review the accepted dialogue and returned reasoning.
The directory is created automatically if missing, with owner-only permissions.

Each JSON file contains only these fields, written in this order:

1. `trial_name`.
2. `trial_id`.
3. `started_at`.
4. `ended_at`.
5. `thinking`: `"thinking enabled"` or `"not enabled"`, reflecting the selected
   mode for both agents.
6. `messages`: accepted turns in chronological order, each containing `speaker`,
   `message`, `thinking`, `message_token_count`, and `thinking_token_count`, in
   that order.
7. `agent_a_inputs`: the original five file contents.
8. `agent_b_inputs`: the original five file contents.

Both input objects contain `model-config.txt`, `persona.txt`, `memory.txt`,
`statements.txt`, and `starting-prompt.txt`, in that order. Values are the exact
UTF-8 text read at startup, including the model configuration as text. The
snapshotted initial memory stays unchanged as the dialogue grows.

Timestamps use UTC ISO 8601 strings. `ended_at` is `null` while running and is set
once when completion, a rejected response, a provider error, or Ctrl+C is saved.
Abrupt termination or a failed final save can leave it `null`; an end time is
not invented for an event that could not be recorded.

`message_token_count` uses the existing conservative non-reasoning bound:
reported completion tokens minus reasoning tokens. It is not an exact local
tokenizer count. `thinking_token_count` is the reasoning-token count; disabled
thinking uses zero when the provider omits that count. `thinking` contains the
returned reasoning text, including an empty string if returned empty, or `null`
when no reasoning text was returned. Speaker labels are `agent_a` and `agent_b`.

Rejected replies, attempt records, message IDs, status/error metadata, raw usage,
word counts, and aggregate totals are not included in the JSON file.
During execution, the terminal shows accepted replies, their message and thinking
word counts, and token usage. Word counts use whitespace-separated words. The
terminal also prints token totals per agent and for the
whole chat when the run completes or stops after a response rejection, provider
error, or Ctrl+C. API usage and computed word counts remain distinct; word counts
are not token counts. Terminal summaries are not saved as a separate report file.

Each new run creates one detailed, owner-only JSON log:

```text
dialogue/archive/TRIAL_NAME_TRIAL_ID.json
```

The filename uses a safe version of the trial name followed by its unique ID.
Path separators, reserved filename punctuation, and non-printable characters
become underscores. Surrounding spaces/dots are removed and the name prefix is
limited to 180 UTF-8 bytes, leaving room for the ID and lock-file suffix. An
empty sanitized prefix becomes `trial`. The JSON retains the exact supplied
trial name. Existing JSON files are not renamed.

Original input files are never overwritten. The JSON log stores the exact input
text and accepted turns and is the only persistent record of growing memory.
No separate memory text files, input copies, or input archives are generated.
A new run reads only the current editable inputs and never automatically imports
another run's history. To supply prior
material deliberately, edit that agent's input `memory.txt` before the new run.

Existing JSON records retain their previous layouts and are not rewritten.
New runs use the ordered fields above. Superseded prompt files were removed from the working
tree; earlier private prompt contents remain in their existing detailed run logs,
while prior tracked source prompts are recoverable through Git history.

The default output directory is `dialogue/archive/` in the project directory.
The retained earlier research chats remain in `backups/runs/dialogue/deliberation/` and
`backups/runs/dialogue/deliberation_no_thinking/`. Historical bird/egg runs are in
`backups/runs/backups/dialogue/`.

Override storage or credential file paths with `--output-dir` and `--keys-file`
on `run`. Custom output directories outside `dialogue/archive/` and `backups/` are
not automatically ignored by Git; keep private artifacts out of commits. The
default ignore rules cover both standard output directories.

An adjacent `.json.lock` file guards the active run against concurrent writers.
Normal exits, errors, and Ctrl+C remove it. Abrupt termination can leave a stale
lock beside the record.

Normal completion exits with status `0`; an early stop or error exits with `1`;
Ctrl+C saves accepted progress and the end timestamp, then exits with `130`.
Stop reasons remain in the terminal output. Read the saved JSON file for the
accepted dialogue; use `run` with a trial name when ready for a fresh conversation.

Prompts and accepted dialogue are sent to DeepSeek. Saved run records contain
the prompts, dialogue, reasoning, and usage, so treat them as private research
artifacts. Credentials are not saved in run records. The default
`dialogue/prompt/agent_a/` and `dialogue/prompt/agent_b/` directories are intentionally
not ignored; choose which prompt files to add to Git.

## Development and licensing

The Python implementation is in `dialogue/source/` and separates execution from its outputs:

| Module | Responsibility |
| --- | --- |
| `engine.py` | Set up runs, build requests, validate responses, and alternate agent turns. |
| `records.py` | Select the ordered JSON fields, timestamp runs, and reserve, lock, and save run files. |
| `reporting.py` | Format per-response token usage and emit terminal summaries. |
| `usage.py` | Share token-accounting checks between response validation and terminal reporting. |

This project intentionally includes no automated tests, test pipeline, or CI.
Local syntax and formatting checks do not establish compatibility with the live
API.

The shared source code and documentation use the
[MIT License](../LICENSE). The existing private research document, local credential
files and generated run records are excluded from Git. Local prompt files are
not ignored and have not been added by the packaging task.

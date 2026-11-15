# DeepSeek dialogue

A terminal research tool for a dialogue between two DeepSeek agents, using Python
3.9 or later and the standard library. No package installation is required.
Agent A always starts, then the agents alternate. The included example debates
whether the bird or the egg came first.

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

`--agent-a` and `--agent-b` now select directories. Each must contain these five
UTF-8 plain-text files, read once at the start of a new run:

| File | Meaning |
| --- | --- |
| `model-config.txt` | JSON text containing this agent's model and generation settings. |
| `persona.txt` | Identity and perspective, including whether this is `agent_a` or `agent_b`. |
| `memory.txt` | Initial context for this run; an empty file is allowed. |
| `statements.txt` | One or more discussion targets, in ordinary text. Use the same targets for both agents. |
| `starting-prompt.txt` | Instructions for opening and continuing the discussion. |

The example directories are `prompts/examples/bird-first/` and
`prompts/examples/egg-first/`. They include empty initial memories and can be run
with the default command. For private inputs, use a location already ignored by
Git, such as `runs/dialogue-inputs/agent-a/` and `runs/dialogue-inputs/agent-b/`:

```sh
python3 -m deepseek_dialogue run \
  --agent-a runs/dialogue-inputs/agent-a \
  --agent-b runs/dialogue-inputs/agent-b
```

All five files are required. Only `memory.txt` may be blank. No template tokens
are replaced and no input text is truncated or automatically summarized. Files
are snapshotted into the run log; editing them affects subsequent new runs, not
the running or resumed conversation.

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
failed response pauses the run; it is recorded and is never forwarded to the
other agent. There are no automatic retries. Reasoning and usage records are
saved locally and never added to either agent's conversation context.

## Saved runs

Starting a run defaults to **20 accepted messages**; `run --max-messages` can
choose another positive count, such as the four-message handshake above.
Resuming always targets **20 total accepted messages**, including saved history.
For example, resuming a chat with four accepted messages generates up to 16 more.
Resume has no `--max-messages` option. It preserves all five snapshotted inputs,
effective model settings, accepted history, and next speaker. It does not reread
the original input files or import any other run's memory.

The saved `trial_id` is the chat ID. Resume continues that same ID and updates
the same JSON file in place; it does not create another ID or trial file. Enter
the same ID again to resume after another interruption. Existing saved JSON
paths also work. If the chat already has at least 20 accepted messages, resume
prints its current path without making API calls or modifying the JSON record.
For five-part runs it also rebuilds the memory archive, repairing any interrupted
export even when the dialogue has already reached the target.

```sh
python3 -m deepseek_dialogue inspect runs/dialogue/TRIAL_ID.json
python3 -m deepseek_dialogue inspect runs/dialogue/TRIAL_ID.json --show-thinking
python3 -m deepseek_dialogue resume
# Enter the chat ID at the "Chat ID:" prompt.
python3 -m deepseek_dialogue resume CHAT_ID
# Legacy saved paths also work:
python3 -m deepseek_dialogue resume runs/dialogue/TRIAL_ID.json
```

Inspection is local and does not make API calls. Thinking is hidden during normal
inspection; `--show-thinking` displays the saved reasoning. Run records are stored
under the ignored `runs/dialogue/` directory as plaintext JSON snapshots. Use the actual
saved path printed by the command in place of `runs/dialogue/TRIAL_ID.json`.

Snapshots retain accepted messages and all attempts, including rejected
responses. Every attempt has a `message_id`, and an accepted message references
the same `message_id` so its delivered text can be paired with the corresponding
thinking and usage. Each attempt's `response` stores `content`,
`reasoning_content`, the full raw API `usage` object, and
`word_counts: {"message": ..., "thinking": ...}`. Word counts use
whitespace-separated words; a missing or non-text field has a null count.
Reports show message and thinking word counts per response, with token usage
totals per agent and for the whole chat. API usage and computed word counts
remain distinct; word counts are not token counts.

Each new run creates separate, owner-only plain-text memory files:

```text
runs/dialogue/TRIAL_ID.json
runs/dialogue/archive/TRIAL_ID/agent_a.memory.txt
runs/dialogue/archive/TRIAL_ID/agent_b.memory.txt
```

Custom output directories use the same adjacent `archive/TRIAL_ID/` layout.
Original input files are never overwritten. The JSON log is authoritative:
after saving it, the program atomically rewrites each memory file from the initial
memory and accepted turns. This gives append-only dialogue content without
duplicating turns after an interrupted write. Export failure stops further calls;
resume repairs the exports from the log. Manual edits to archived memory are
replaced on resume and are never read as new context. To explicitly use prior
material in a new run, put the intended text in that new run's input `memory.txt`.

Existing version-1 runs remain inspectable and resumable using their original
complete prompts and named assistant messages. They are not converted to the
five-part format or given new memory exports. Starting a new run with a single
complete prompt file is no longer supported; split its contents into the five
files above. The earlier example `.txt` files and filled research prompts remain
available as source material.

Earlier version-2 logs without `settings.memory_format` retain their original
`Initial memory` / `Dialogue so far` headings on resume. New runs save
`memory_format: blended`; their archived memory uses the same unseparated text
that enters the payload. Saved prompt text is preserved in both cases.

The default output directory is `runs/dialogue/`. The retained research chats
are grouped in its `deliberation/` and `deliberation-no-thinking/` subdirectories;
pass their JSON paths to `inspect` or `resume`, or use the matching `--output-dir`
when resolving a chat ID. Historical bird/egg runs are in `runs/backups/dialogue/`.

Override storage or credential file paths with `--output-dir` and `--keys-file`
on `run` or `resume`. Resume looks up an entered ID in `--output-dir`; when given
a JSON path, it updates that file directly. Custom output directories outside
`runs/` are not automatically ignored by Git; keep private artifacts out of
commits. The default ignore rules cover the standard logs in `runs/`.

An adjacent `.json.lock` file prevents concurrent commands from editing the same
chat. Normal exits, errors, and Ctrl+C remove it. Abrupt termination can leave a
stale lock; check its recorded process ID and confirm that process has exited
before deleting the lock and resuming.

Normal completion exits with status `0`; a paused run or error exits with `1`;
Ctrl+C saves progress and exits with `130`. The JSON record also retains a local
`interruption_notes` entry marking where the chat stopped, including the time,
accepted message count, message IDs, and a remark. These notes persist across
resumes and are never sent to either agent. A resumed chat continues until it
reaches 20 accepted messages or you press Ctrl+C; a rejected response or provider
error also pauses safely. Inspect the saved record before resuming a paused run.

Each continuation also appends a local `resume_notes` entry with the previous
status, the point at which the conversation had stopped, and the resumption time.
This preserves earlier boundaries such as a four-message handshake, even after
the same chat reaches 20 messages. These remarks also stay out of model context.

Prompts and accepted dialogue are sent to DeepSeek. Saved run records contain
the prompts, dialogue, reasoning, and usage, so treat them as private research
artifacts. Credentials are not saved in run records. Keep private custom prompt
directories under an ignored location such as `runs/dialogue-inputs/`.

## Development and licensing

This project intentionally includes no automated tests, test pipeline, or CI.
Local syntax and formatting checks do not establish compatibility with the live
API.

The shared source code, documentation, and included example prompts use the
[MIT License](../LICENSE). The existing private research document, local credential
files, private prompt files, and generated run records are excluded from the
repository.

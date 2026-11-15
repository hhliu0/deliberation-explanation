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

A four-message live handshake with thinking enabled was verified on 2026-11-15
using `deepseek-flash` for both agents. Other model/account configurations need
their own live check. Each model is independently configurable:

```sh
python3 -m deepseek_dialogue run --model-a deepseek-flash --model-b deepseek-flash
```

## Prompts and generation limits

`prompts/examples/bird-first.txt` and `prompts/examples/egg-first.txt` are separate, complete starting
prompts. Each file is sent verbatim as that agent's first system message. Edit
these files or select alternatives:

```sh
python3 -m deepseek_dialogue run --agent-a prompts/examples/bird-first.txt --agent-b prompts/examples/egg-first.txt
```

There is no shared human seed, hidden runtime prompt, or option for Agent B to
start. Each agent receives the accepted dialogue as assistant messages named
`agent_a` or `agent_b`, retaining the speaker's identity. The starting prompts
specify the debate roles and target replies of about 100 words. Only the starting
prompt and accepted message text with speaker names enter model context; trial
IDs, message IDs, counts, usage, and reasoning do not.

By default, both agents request thinking with high reasoning effort and an
8,192-token combined reasoning-and-delivery generation limit. Accepted delivered
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
Resume has no `--max-messages` option. It preserves the original prompts, models,
accepted history, and next speaker.

The saved `trial_id` is the chat ID. Resume continues that same ID and updates
the same JSON file in place; it does not create another ID or trial file. Enter
the same ID again to resume after another interruption. Existing saved JSON
paths also work. If the chat already has at least 20 accepted messages, resume
prints its current path without making API calls or modifying the record.

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
files in ignored names such as `my_prompt.local.txt`.

## Development and licensing

This project intentionally includes no automated tests, test pipeline, or CI.
Local syntax and formatting checks do not establish compatibility with the live
API.

The shared source code, documentation, and included example prompts use the
[MIT License](../LICENSE). The existing private research document, local credential
files, private prompt files, and generated run records are excluded from the
repository.

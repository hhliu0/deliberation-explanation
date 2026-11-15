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
read as text, never executed as shell code. Missing credentials stop the command
before a run is created. The supplied local file has owner-only permissions;
keep those permissions if you replace it.

Start with a four-message handshake to check the live provider interface:

```sh
python3 -m deepseek_dialogue run --max-messages 4
```

Live model availability and compatibility still need verification with your
credentials. The default model for both agents is `deepseek-flash`; each model
is independently configurable:

```sh
python3 -m deepseek_dialogue run --model-a deepseek-flash --model-b deepseek-flash
```

## Prompts and generation limits

`prompts/agent_a.txt` and `prompts/agent_b.txt` are separate, complete starting
prompts. Each file is sent verbatim as that agent's first system message. Edit
these files or select alternatives:

```sh
python3 -m deepseek_dialogue run --agent-a prompts/agent_a.txt --agent-b prompts/agent_b.txt
```

There is no shared human seed, hidden runtime prompt, or option for Agent B to
start. Each agent receives the accepted dialogue as assistant messages named
`agent_a` or `agent_b`, retaining the speaker's identity. The starting prompts
specify the debate roles and target replies of about 100 words.

Both agents request thinking with high reasoning effort. Each request has an
8,192-token combined reasoning-and-delivery generation limit. Accepted delivered
messages have a hard 512-token limit, determined from reported completion tokens
minus reported reasoning tokens. The response must finish normally and include
nonblank text and valid usage counts. An over-limit, truncated, malformed, or
failed response pauses the run; it is recorded and is never forwarded to the
other agent. There are no automatic retries. Reasoning and usage records are
saved locally and never added to either agent's conversation context.

## Saved runs

The default is **20 new accepted messages**, both when starting and when resuming.
Use `--max-messages` to choose a positive count. A resumed run preserves its
original prompts, models, accepted history, and next speaker. Resume writes a
new run file linked to the original, leaving the original file intact.

```sh
python3 -m deepseek_dialogue inspect runs/RUN_ID.json
python3 -m deepseek_dialogue inspect runs/RUN_ID.json --show-thinking
python3 -m deepseek_dialogue resume runs/RUN_ID.json --max-messages 20
```

Inspection is local and does not make API calls. Thinking is hidden during normal
inspection; `--show-thinking` displays the saved reasoning. Run records are stored
under the ignored `runs/` directory as JSON snapshots with unique run IDs. Use
the actual saved path printed by the command in place of `runs/RUN_ID.json`.
Snapshots retain accepted messages, all attempts including rejected responses,
reasoning, and per-attempt, per-agent, and run usage. Override storage or
credential file paths with `--output-dir` and `--keys-file` on `run` or `resume`.

Prompts and accepted dialogue are sent to DeepSeek. Saved run records contain
the prompts, dialogue, reasoning, and usage, so treat them as private research
artifacts. Credentials are not saved in run records. Keep private custom prompt
files in ignored names such as `my_prompt.local.txt`.

## Development and licensing

This project intentionally has no automated tests, test pipeline, or CI. Local
syntax and formatting checks do not establish compatibility with the live API.

The shared source code, documentation, and included example prompts use the
[MIT License](LICENSE). The existing private research document, local credential
files, private prompt files, and generated run records are excluded from the
repository.

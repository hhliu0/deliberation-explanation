# DeepSeek research tools

Two independent terminal tools share this repository:

| Tool | Purpose | Guide |
| --- | --- | --- |
| `deepseek_ratings` | Rate statements using one agent's five files and one API key; save an ordered JSON result. | [Ratings](docs/ratings.md) |
| `deepseek_dialogue` | Run a dialogue between two agents using two API keys; save JSON logs and print terminal summaries. | [Dialogue](docs/dialogue.md) |

Both tools start a fresh trial each time. Neither package imports the other
or automatically starts its workflow.

Each run saves only its JSON result inside its archive and prints summaries to
the terminal. Neither tool has a resume or historical-inspection command, and
neither reads old trial files. There are no separate report, score, or backup
outputs for new runs.

## Run a rating

Edit the five files in `prompts ratings/Agent A/` or `prompts ratings/Agent B/`,
then select one agent and a thinking mode for the trial:

```sh
python3 -m deepseek_ratings \
  --agent agent_a \
  --trial-name "skeptic ratings" \
  --enable-thinking
```

Use `--agent agent_b` for Agent B, or `--not-enable-thinking` for a non-thinking
trial. Each run makes one request and saves one named JSON file directly in
`rating archive/`. The
[ratings guide](docs/ratings.md) covers setup, credentials, validation, and logs.

## Run a dialogue

Edit the five files in `prompts/Agent A/` and `prompts/Agent B/` to configure a
run: model config, persona, initial memory, statements, and discussion starting
prompt. Those are the only two folders under `prompts/`, with one current copy
of each file per agent. Agent A is currently The Skeptic; Agent B is The Extrapolator.

```sh
python3 -m deepseek_dialogue run --trial-name "handshake" --enable-thinking --max-messages 4
```

Each run reads those files afresh. Accepted replies extend memory in the detailed
run log; the program does not overwrite the input files or generate separate
memory text archives. `--trial-name` and one of `--enable-thinking` or
`--not-enable-thinking` are required. New filenames contain the safe trial name
followed by its ID, and the JSON header records the selected thinking mode. The
[deliberation guide](docs/deliberation.md) explains the discussion design;
[dialogue usage](docs/dialogue.md) covers starting chats, JSON logs, and terminal summaries.
New dialogue JSON files are saved directly in `Dialogue Archive/`; new rating
JSON files are saved directly in `rating archive/`.

## Project layout

```text
inputs/                              user YAML inputs; unchanged by cleanup
prompts ratings/
  Agent A/                           five editable rating inputs for Agent A
  Agent B/                           five editable rating inputs for Agent B
rating archive/                      new ordered rating JSON files
prompts/
  Agent A/                           five editable inputs for Agent A
  Agent B/                           five editable inputs for Agent B
Dialogue Archive/                    new dialogue JSON logs
runs/
  dialogue/
    deliberation/                    retained twenty-message conversation
    deliberation-no-thinking/        retained non-thinking conversation
  ratings/
    batch-skeptic/                    retained batch logs and scores
    batch-extrapolator/               retained batch logs and scores
    deliberation/
      after-deliberation/             ratings after twenty thinking-enabled messages
      after-deliberation-no-thinking/ ratings after twenty non-thinking messages
  backups/                           superseded runs, summaries, and recovery copies
backups/                             existing input/persona backups
docs/                                usage, prompt design, and task evidence
```

Each older rating folder keeps its detailed YAML logs and `scores/` files.
The earlier six-message ratings and initial five-statement trials are archived
under `runs/backups/ratings/`. Old summaries and request captures also live in
backups, outside the active results. Trial IDs and recorded contents are retained.

Private inputs, filled prompts, credentials, and runs remain excluded from Git.
See [task evidence](docs/task-evidence.md) for verification and recovery details.
The shared source and documentation use the [MIT License](LICENSE).

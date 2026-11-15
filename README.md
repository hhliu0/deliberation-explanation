# DeepSeek research tools

Two independent terminal tools share this repository:

| Tool | Purpose | Guide |
| --- | --- | --- |
| `deepseek_ratings` | Rate statements using one persona and one API key; save full logs and separate Likert scores. | [Ratings](docs/ratings.md) |
| `deepseek_dialogue` | Run a dialogue between two agents using two API keys; save JSON logs and print terminal summaries. | [Dialogue](docs/dialogue.md) |

Both tools start a fresh trial each time. Neither package imports the other
or automatically starts its workflow.

## Run a rating

Use the existing project virtual environment and your local rating key file:

```sh
.venv/bin/python -m deepseek_ratings \
  --personas inputs/personas.local.yaml \
  --statements inputs/statements.local.yaml \
  --persona skeptic \
  --thinking enabled
```

Use `inputs/extrapolator.local.yaml` with `--persona extrapolator` for the other
persona, or `--thinking disabled` for a fresh non-thinking trial. The
[ratings guide](docs/ratings.md) covers setup, credentials, validation, and logs.

## Run a dialogue

Edit the five files in `prompts/Agent A/` and `prompts/Agent B/` to configure a
run: model config, persona, initial memory, statements, and discussion starting
prompt. Those are the only two folders under `prompts/`, with one current copy
of each file per agent. Agent A is currently The Skeptic; Agent B is The Extrapolator.

```sh
python3 -m deepseek_dialogue run --max-messages 4
```

Each run reads those files afresh. Accepted replies extend memory in the detailed
run log; the program does not overwrite the input files or generate separate
memory text archives. The
[deliberation guide](docs/deliberation.md) explains the discussion design;
[dialogue usage](docs/dialogue.md) covers starting chats, JSON logs, and terminal summaries.
Dialogue output defaults to `runs/dialogue/`; rating output defaults to
`runs/ratings/`.

## Project layout

```text
inputs/                              user YAML inputs; unchanged by cleanup
prompts/
  Agent A/                           five editable inputs for Agent A
  Agent B/                           five editable inputs for Agent B
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

Each retained rating folder keeps its detailed YAML logs and `scores/` files.
The earlier six-message ratings and initial five-statement trials are archived
under `runs/backups/ratings/`. Old summaries and request captures also live in
backups, outside the active results. Trial IDs and recorded contents are retained.

Private inputs, filled prompts, credentials, and runs remain excluded from Git.
See [task evidence](docs/task-evidence.md) for verification and recovery details.
The shared source and documentation use the [MIT License](LICENSE).

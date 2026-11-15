# DeepSeek research tools

Two independent terminal tools share this repository:

| Tool | Purpose | Guide |
| --- | --- | --- |
| `deepseek_ratings` | Rate statements using one persona and one API key; save full logs and separate Likert scores. | [Ratings](docs/ratings.md) |
| `deepseek_dialogue` | Run, resume, or inspect a dialogue between two agents using two API keys. | [Dialogue](docs/dialogue.md) |

The rating command starts fresh each time. The dialogue command manages its own
saved conversation. Neither package imports the other or automatically starts
its workflow.

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

The default bird/egg example uses the explicitly named prompts in
`prompts/examples/`:

```sh
python3 -m deepseek_dialogue run --max-messages 4
```

For a research deliberation, choose filled persona prompts explicitly. The
[deliberation guide](docs/deliberation.md) explains the reusable templates;
[dialogue usage](docs/dialogue.md) covers starting, resuming, and inspecting chats.
Dialogue output defaults to `runs/dialogue/`; rating output defaults to
`runs/ratings/`.

## Project layout

```text
inputs/                              user YAML inputs; unchanged by cleanup
prompts/
  examples/                          bird-first and egg-first example prompts
  deliberation/                      agent templates and private persona prompts
  deliberation-no-thinking/          private prompts for the non-thinking condition
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
The shared source, documentation, and example prompts use the [MIT License](LICENSE).

# DeepSeek research tools

Two independent terminal tools share this repository. Each starts a fresh trial,
saves only its JSON result inside its archive, and prints terminal summaries.
Neither has a resume or historical-inspection command or reads old trial files.
New runs create no separate report, score, or backup outputs.

| Tool | Source | Guide |
| --- | --- | --- |
| Dialogue between two agents | dialogue/source | [Dialogue](docs/dialogue.md) |
| Statement ratings from one agent | ratings/source | [Ratings](docs/ratings.md) |

## Run a dialogue

Edit the five files in dialogue/prompt/agent_a and dialogue/prompt/agent_b, then
run from the project root:

~~~sh
python3 -m dialogue.source run --trial-name "handshake" --enable-thinking --max-messages 4
~~~

Use --not-enable-thinking for a non-thinking trial. New JSON results are saved in
dialogue/archive with the safe trial name followed by its ID. See the
[deliberation guide](docs/deliberation.md) for discussion design.

## Run ratings

Edit the five files in ratings/prompt/agent_a or ratings/prompt/agent_b, then
select one agent:

~~~sh
python3 -m ratings.source --agent agent_a --trial-name "skeptic ratings" --enable-thinking --simulations 1
~~~

Use --agent agent_b for Agent B, or --not-enable-thinking to disable thinking.
--simulations repeats that same setup; 1 runs it once. Each run makes at most
one request and saves one named JSON file in ratings/archive.

Both programs use the root keys.local.env file. Dialogue uses the A and B keys;
ratings reads DEEPSEEK_API_KEY_A directly from that file. The separate ratings
credential file is removed. Default input, archive, and key paths are anchored
to the project location; explicit path overrides remain available.

## Project layout

~~~text
.venv/
backups/
  inputs/                    original YAML inputs
  runs/                      earlier runs, scores, and run backups
  packaging_ce2a59b/          packaging move/recovery manifest
  root_metadata/             relocated Finder metadata
dialogue/
  source/                    all dialogue Python files
  prompt/
    agent_a/                 five editable input files
    agent_b/
  archive/                   dialogue JSON results
ratings/
  source/                    all ratings Python files
  prompt/
    agent_a/                 five editable input files
    agent_b/
  archive/                   ratings JSON results
  requirements.txt           unchanged historical YAML dependency manifest
docs/
.gitignore
keys.local.env
LICENSE
README.md
~~~

Git metadata remains in .git. Project folder names use lowercase and underscores;
the existing .venv and .git internals are unchanged. Historical records retain
their original filenames and contents inside the relocated backup folders.

Backups, archives, credentials, and the virtual environment are excluded from
Git. Prompt folders are intentionally not ignored; existing prompt files remain
untracked until explicitly added. Both guides describe their formats. Missing
archive folders are created automatically when a run starts saving its JSON.
No installation is required for the current standard-library runtime.

See [task evidence](docs/task-evidence.md) for verification and recovery details.
Shared source and documentation use the [MIT License](LICENSE).

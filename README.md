# DeepSeek research tools

Two terminal tools and a combined workflow share this repository. Each starts a fresh trial,
saves only its JSON result inside its archive, and prints terminal summaries.
Neither has a resume or historical-inspection command or reads old trial files.
New runs create no separate report, score, or backup outputs.

| Tool | Source | Guide |
| --- | --- | --- |
| Dialogue between two agents | dialogue/source | [Dialogue](docs/dialogue.md) |
| Statement ratings from one agent | ratings/source | [Ratings](docs/ratings.md) |

## Deliberate, then rate with the resulting memory

From the project root, run:

~~~sh
python3 deliberate_and_rate.py --rounds 10 --trials 1
~~~

This runs the existing Skeptic (Agent A) and Extrapolator (Agent B) for **10
rounds: 20 alternating replies**, discussing the existing 12 statements. It then
rates all 12 statements once per agent. Thinking is disabled for every request;
there is no thinking switch in this workflow. Ten rounds is also the default.
Use `--trial-name "NAME"` to name the experiment, or add `--check` to validate
the inputs without contacting the provider.

Set `--trials 2` or `--trials 100` to repeat the entire experiment that many
times. Each trial starts a fresh dialogue from the original prompt memories,
then makes one rating request per agent; memory does not carry between trials.
`--trials` defaults to 1. A complete trial uses 22 provider requests at 10 rounds
(20 dialogue replies + 2 ratings). Trials run sequentially, with their batch
position in the trial name, and the batch stops if an experiment fails or is
interrupted.

Each rating receives that agent's exact starting dialogue memory followed by
all accepted public replies, including the final reply, in the same single
`Memory` section used during dialogue. Speaker labels remain; no imported/new
memory labels, summaries, or provenance instructions are added. The rating prompt
calls this the agent's own memory and asks for its current views. This presents
the intended memory framing; it does not establish that the model experiences
source confusion.

The workflow checks that both stages use the same 12 statement IDs, text, and
order. An incomplete dialogue stops the workflow before ratings. A rejected
rating is saved using the existing null-rating behavior, the other agent is
still attempted, and the command exits with failure. There are no automatic
retries. Original input files are never rewritten by a run.

One dialogue JSON is saved in `dialogue/archive/` and two rating JSON files in
`ratings/archive/`. Rating trial names contain the source dialogue ID, and their
`inputs.memory.txt` fields contain the actual full memory used. Re-running the
command starts a fresh dialogue and creates new results.

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
deliberate_and_rate.py        dialogue followed by both agents' ratings
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

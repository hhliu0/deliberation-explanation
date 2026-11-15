# Independent persona ratings

`deepseek_ratings` rates a complete statement list from one selected persona's
perspective. It uses DeepSeek V4.1 Flash (`deepseek-flash`) through the Chat
Completions API. Every invocation starts a new trial: there is no resume command,
history loading, conversation continuation, or use of saved thinking as input.
The existing `deepseek_dialogue` command operates independently.

## Setup and credentials

Run from this repository using Python 3.9 or later. The approved local setup is:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: --no-deps -r requirements-ratings.txt
```

The sole runtime dependency is PyYAML 6.0.3. Do not upgrade pip or install an
OpenAI SDK for this command. The current key-file implementation targets
macOS/Linux, using no-follow file opening and owner-only permissions.

Fill the empty, ignored `ratings.local.env` file locally:

```dotenv
DEEPSEEK_API_KEY=your_key_here
```

Keep the file owned by your account with mode `600`. The command reads literal
assignments without executing the file. It rejects symlinks, nonregular files,
and duplicate or unexpected assignments. A nonblank `DEEPSEEK_API_KEY`
environment value takes precedence. `--keys-file FILE` chooses another file.
Do not put a literal key in shell commands or in chat. No existing dialogue keys
are read by this tool. Credentials never enter prompts or saved trial records.

## Inputs and use

The prepared private inputs are `inputs/personas.local.yaml` (The Skeptic only)
and `inputs/statements.local.yaml` (five labeled illustrative sample statements,
not a validated research instrument). The original Extrapolator is preserved in
`backups/extrapolator.local.yaml` and is not selected or sent automatically.
The original pasted attachment is unchanged. These local files are excluded
from Git and therefore are not included in another clone.

Personas YAML schema:

```yaml
version: 1
agents:
  example:
    name: Example persona
    system_prompt: |
      Describe the persona's substantive beliefs here.
      Follow the rating task's final response format.
```

Statements YAML schema:

```yaml
version: 1
statements:
  - id: s1
    text: Independent evaluation should precede deployment.
```

Both files must contain exactly the fields shown. IDs, names, prompts, and texts
must be nonblank strings. Quote numeric-looking IDs. Duplicate mapping keys or
statement IDs, aliases, merge keys, and custom YAML tags are rejected. If more
than one persona is present, select one with `--persona`; otherwise selection is
automatic. Each trial evaluates one persona, not all personas in the file.

```sh
.venv/bin/python -m deepseek_ratings \
  --personas inputs/personas.local.yaml \
  --statements inputs/statements.local.yaml \
  --persona skeptic \
  --thinking enabled
```

Use `--thinking disabled` for a separate non-thinking trial. Enabled is the
default, with high reasoning effort. Scores are 1 strongly disagree, 2 disagree,
3 neither agree nor disagree, 4 agree, and 5 strongly agree. The final message
contains compact JSON only:

```json
{"ratings":[{"id":"s1","score":4}]}
```

The system message combines the selected persona with the scoring instructions
defined in `engine.py`; those instructions replace conflicting persona response
formats. The user message contains the entire statement list in its supplied
order. Both exact messages and settings are stored in every trial. Local IDs,
timestamps, trial history, and reasoning are never added to model context.

There is no application input-token cap, truncation, or automatic batching.
DeepSeek's context window still applies. Very long lists may require more output
than the 512-token message limit; the tool reports failure rather than silently
dropping statements or splitting the research task.

## Limits, retry, and failure

Thinking-enabled requests allow 8,192 combined generated tokens. Thinking-disabled
requests set the API limit to 512. Accepted final messages must contain at most
512 tokens excluding thinking and separately reported safety-review tokens.
With thinking enabled, this message limit is an acceptance check after generation,
not a separate server-side message budget. Rejected responses can exceed it.

Responses must finish normally, contain valid JSON with every expected statement
exactly once, use integer scores from 1 through 5, and include adequate accounting.
Blank, truncated, oversized, malformed, or unaccountable answers are rejected.

On the first rejected answer, the tool durably saves the full attempt, creates
an exclusive backup snapshot, and only then sends one identical fresh request.
It does not append the rejected answer or correction instructions. The second
rejection stops the program. HTTP, authentication, billing, network, and local
storage errors stop without automatic retry. In particular, a backup failure
prevents the second request. A new invocation always starts a new trial.

The raw body of an unreadable API response is saved as text, or YAML binary if
it is not UTF-8. The transport has a 16 MiB response safety bound; a response
exceeding it is retained only up to that bound plus one byte and stops without
retry. This is not an input-token restriction. Responses containing the actual
credential are not persisted; the tool stops with a local error instead.

## Saved YAML and token accounting

The command prints its UUID trial ID and path before requesting a completion.
The authoritative file is `runs/ratings/TRIAL_ID.yaml`; the first rejected
attempt's immutable application snapshot is under `runs/ratings/backups/`.
Backups are never overwritten by the program. `--output-dir DIR` changes the
destination; custom directories are not automatically excluded from Git.

Files use mode `600` and file/directory synchronization. Authoritative snapshots
use atomic replacement; backups are created exclusively and synchronized once.
Each trial records status, timestamps, the selected persona, statements, exact
request settings, all attempts, raw responses, returned final and reasoning
text, original usage, parsed ratings, and issues. The accepted attempt number
identifies which response produced the trial's final ratings.

Every finished call also produces a separate
`runs/ratings/scores/TRIAL_ID.attempt-N.yaml` file. It contains **only** the trial
ID, the call's start time as `created_at`, call status, model, and full statement
text paired with its score, in input order:

```yaml
trial_id: example_trial_id
created_at: '2026-11-15T09:38:43+00:00'
status: accepted
model: deepseek-flash
scores:
  - statement: Independent evaluation should precede deployment.
    score: 4
```

Retry calls have separate numbered files under the same trial ID. Status is
`accepted`, `rejected`, `failed`, or `interrupted`, as recorded for that call in
the detailed log. If a call provides no complete, valid set of scores, each
statement has `score: null`; scores are never invented. A rejected call can have
valid scores but fail another check, such as the output-token limit, so check its
status. Reasons remain in the full log. Score files contain no prompts, thinking,
token counts, issue details, or additional metadata.

The complete log is saved first and retained alongside these exports. Score
files use the same owner-only, atomic, synchronized writes. A score-file write
failure stops the run before any further request. `--output-dir` moves both the
full log and its `scores/` subdirectory together.

Each attempt stores these separate counts:

| Field | Meaning |
| --- | --- |
| `input_tokens` | Provider `prompt_tokens`, including the complete request prompts |
| `thinking_tokens` | Provider `completion_tokens_details.reasoning_tokens` |
| `message_output_tokens` | Completion tokens minus thinking and separately reported safety tokens |
| `safety_tokens` | Optional provider safety-review tokens; absent means zero with this request configuration |
| `completion_tokens` | All provider-generated completion tokens |
| `total_tokens` | Provider input plus completion tokens |

Explicit non-thinking requests can report zero thinking tokens by omitting the
reasoning breakdown. Thinking-enabled responses must report the reasoning count.
Missing or inconsistent accounting is not estimated from words or characters.
Unknown counts remain null. `token_totals` sums all attempts, including rejected
ones; an unknown component makes that aggregate null, and
`accounting_complete: false` flags incomplete or inconsistent accounting.
Provider prefix-cache hits are retained in raw usage; they do not constitute
local conversation-history reuse.

Exit status is `0` for an accepted saved result, `1` for failure, `2` for CLI
usage errors, or `130` for Ctrl+C. Ctrl+C attempts to save an interruption record;
remote usage may remain unknown. Abrupt termination can leave a pending trial
or temporary snapshot. No automatic recovery or repeat request occurs.

## Verification and provenance

The implementation uses the existing Black installation, syntax/help checks,
actual-input inspection, and independent static review. It adds no local trial
pipeline, simulated model runner, automated test suite, or CI. Live verification
is performed only after the user supplies the single key; see `TASK_EVIDENCE.md`
for the actual verification status and unexercised failure paths.

PyYAML 6.0.3 is obtained from [PyPI](https://pypi.org/project/PyYAML/6.0.3/) under
the MIT license. Its installed wheel retains the package's copyright/license
notices; no third-party application source was copied or modified. Our project
source and documentation retain the repository's existing MIT license.

API interfaces were checked against DeepSeek's official
[Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion/),
[thinking guide](https://api-docs.deepseek.com/guides/thinking_mode/), and
[JSON output guide](https://api-docs.deepseek.com/guides/json_mode/).

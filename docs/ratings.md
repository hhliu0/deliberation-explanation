# Independent agent ratings

`ratings.source` rates a statement list using one selected agent and one API
key. Each simulation builds a fresh request from five text files and saves one
ordered JSON result. Agent A and Agent B have separate input folders; a run uses
only the selected agent. The combined `deliberate_and_rate.py` workflow runs a
dialogue first, then invokes ratings once for each agent with its final memory.
See the [one-command workflow](../README.md#deliberate-then-rate-with-the-resulting-memory).

## Inputs and first run

The project contains this editable input set, intentionally not ignored by Git:

```text
ratings/prompt/
  agent_a/
    model-config.txt
    persona.txt
    memory.txt
    statements.txt
    starting-prompt.txt
  agent_b/
    model-config.txt
    persona.txt
    memory.txt
    statements.txt
    starting-prompt.txt
```

Agent A's persona comes from the existing Skeptic rating input, and Agent B's
comes from the Extrapolator input. Both initially contain the existing twelve
statement IDs/texts. Initial memory is empty. The original YAML inputs and past
results remain unchanged. These private text files are not included in a fresh
clone; create the same files using the formats below when setting up another copy.

Run from the project directory using Python 3.9 or later. Default prompt, archive,
and key paths are anchored to the project location:

```sh
python3 -m ratings.source --agent agent_a --trial-name "skeptic ratings" --enable-thinking --simulations 1
python3 -m ratings.source --agent agent_b --trial-name "extrapolator ratings" --not-enable-thinking --simulations 1
```

`--agent`, a nonblank `--trial-name`, `--simulations N`, and exactly one thinking flag are required.
`--simulations` repeats the same setup N times.
`--prompts-dir DIR` changes the parent containing the `agent_a` and `agent_b`
folders. `--output-dir DIR` changes the archive destination. The old persona/YAML
input options and `--thinking` option have been replaced by these arguments.
The current runtime uses only the standard library. The existing virtual
environment also works; no dependency installation is needed for this workflow.
The retained `ratings/requirements.txt` describes the earlier YAML environment.

## The five files and request construction

| File | Contents |
| --- | --- |
| `model-config.txt` | JSON text with the model and one supported generation profile. |
| `persona.txt` | The selected agent's identity and perspective. |
| `memory.txt` | Initial context for this request; may be empty. |
| `statements.txt` | JSON text containing the statement IDs and full text, in order. |
| `starting-prompt.txt` | Rating instructions, including the required response format. |

All files are UTF-8 and are read once. Only `memory.txt` may be blank. Inputs are
snapshotted into the JSON result and are never rewritten by a run. There is no
automatic history loading, memory summarization, template replacement, or input
truncation. Standalone ratings use only the selected file's supplied memory.
The combined workflow supplies `engine.run(memory=...)` instead: this replaces
the in-memory rating input with the agent's starting dialogue memory plus all
accepted public replies. The exact resulting text is used in the request and
saved under `inputs.memory.txt`; the on-disk prompt files remain unchanged.

For example, `model-config.txt` can contain:

```json
{
  "model": "deepseek-flash",
  "thinking": {"type": "enabled"},
  "reasoning_effort": "high",
  "max_tokens": 8192
}
```

The other supported file profile is `thinking: {"type": "disabled"}` with
`max_tokens: 512` and no `reasoning_effort`. Duplicate/extra settings, invalid
model names, and other profiles are rejected. The required CLI flag overrides
the selected file's profile to enabled/high/8192 or disabled/512, retaining the
file's model name and exact original input text.

`statements.txt` has this format:

```json
{
  "statements": [
    {"id": "s1", "text": "Independent evaluation should precede deployment."}
  ]
}
```

The top-level object contains only `statements`. Each entry contains exactly
`id` and `text`, both nonblank UTF-8 strings; IDs must be unique. Duplicate JSON
keys, non-JSON numeric constants, extra fields, and an empty list are rejected.
IDs support response matching; the saved rating pairs contain the full text.

`build_payload()` uses the same initial request structure as dialogue: model
configuration supplies API parameters, the persona is the system message, and
one user message contains `Memory:`, `Statements:`, and `Starting prompt for
discussion:` sections in that order. Their content is the exact text from the
corresponding files. `stream` is false. Neither mode adds `response_format`.
No rating instructions are secretly appended by the engine; they live in
`starting-prompt.txt` and are included in the saved input files.

The initial starting prompt requests one of these exact lowercase labels:
**strongly disagree**, **disagree**, **neutral**, **agree**, **strongly agree**.
It requires a compact JSON response such as:

```json
{"ratings":[{"id":"s1","score":"agree"}]}
```

Keep those response requirements when editing the prompt: the response validator
requires every statement ID exactly once and one valid label per ID. The full
accepted JSON response string is also saved as the agent's message.

## Credentials

Ratings reads `DEEPSEEK_API_KEY_A`, the first agent's key, directly from the
project's ignored `keys.local.env`. It accepts the optional
`DEEPSEEK_API_KEY_B` entry but never selects it for ratings, even if lines are
reordered. The separate `ratings.local.env` has been removed. Ratings does not
use credential environment overrides; dialogue retains its existing overrides.

Use `--keys-file FILE` to select another file in the same A/B assignment format.
The file must be owned by your account with mode `600`; symlinks, nonregular
files, duplicate or unknown assignments, and a missing/malformed A key are
rejected. Values are literal text, never shell code. Never put credentials in
prompts or command-line arguments.

The HTTPS endpoint, redirect refusal, timeout, response-size bound, and
literal/JSON-escaped credential detection retain their existing behavior.
Prompts are sent only when a trial is explicitly run.

## One request and validation

Each trial makes at most one provider request. There is no automatic retry,
backup output, separate score file, resume pipeline, or historical-inspection
command. Failed input validation,
missing keys, or initial storage errors prevent the request entirely.

Accepted responses must finish normally, contain a single assistant message with
valid rating JSON, cover every statement, use the exact labels, and provide
consistent token accounting. Numeric scores, synonyms, duplicate/missing IDs,
tools, blank/truncated messages, and unexpected reasoning in disabled mode are
rejected. The delivered message is limited to 512 tokens, excluding reported
thinking and separately reported safety tokens. Enabled mode allows 8,192 total
generated tokens; disabled mode allows 512. There is no application input-token
cap or automatic splitting of a long statement list.

Rejected, interrupted, or failed trials retain null ratings in the JSON. If an
answer was accepted before an interruption or saving error, its exact message,
thinking, and token counts are still saved when the recovery write succeeds.
Otherwise there is no accepted message. Reasons are printed in the terminal;
rejected text, raw provider bodies, internal metadata, and attempt history are
not saved to disk. Terminal output still reports completed ratings and token
accounting.

## Ordered JSON archive

New results are saved directly under:

```text
ratings/archive/<safe trial name>_<trial ID>.json
```

The folder is Git-ignored and uses mode `700`; result files use mode `600`.
The program creates the archive folder automatically if it does not exist.
Unsafe filename punctuation and non-printable characters become underscores;
outer spaces/dots are removed, the name prefix is capped at 180 UTF-8 bytes,
and an empty normalized prefix becomes `trial`. The exact name remains in JSON.
The UUID suffix, exclusive creation, and atomic writes prevent overwrites of an
existing trial. File and directory synchronization remain enabled.

Each JSON contains only these fields in this exact order:

1. `trial_name`.
2. `trial_id`.
3. `started_at`.
4. `ended_at`.
5. `thinking`: `"thinking enabled"` or `"not enabled"`.
6. `ratings`: ordered objects containing `statement_number`, `statement`, then
   `rating`. Numbers start at 1 and follow the selected agent's `statements.txt`
   list order, independently of statement IDs or response order.
7. `agent_message`: `agent_name`, `message`, `thinking`, `message_token_count`,
   `thinking_token_count`, in that order.
8. `inputs`: `model-config.txt`, `persona.txt`, `memory.txt`, `statements.txt`,
   `starting-prompt.txt`, in that order, with the input text as each value (the
   effective supplied memory when the combined workflow overrides `memory.txt`).

`agent_name` is `Agent A` or `Agent B`, corresponding to the selected
`agent_a` or `agent_b` folder. Each rating
is the validated Likert text only when the trial completes; otherwise it is
`null`. Before acceptance, the agent-message fields are `null` except for its
name. An accepted message is preserved even if a later interruption or save
error stops the trial. Missing returned reasoning remains `null`; a returned
empty string remains empty.

Timestamps are UTC ISO 8601 strings. The end time is `null` while running and
set on completion, failure, or handled interruption. Abrupt termination or an
unsuccessful final save can leave a null end time. Original input files are
never modified, and the effective memory is saved exactly as used.

Message token count uses provider completion tokens minus reasoning and separately
reported safety tokens. Thinking count uses the provider's reasoning count;
disabled mode permits an omitted reasoning count as zero. These counts are not
estimated from words or characters. Other usage/totals remain terminal/internal
information and are not additional JSON fields.

Exit status is `0` for an accepted saved result, `1` for failure, `2` for CLI
usage errors, and `130` for Ctrl+C. The full state and generated filename are
checked for credentials before writing. Custom output directories need their own
Git exclusion. The default prompt folders are intentionally not ignored; existing
prompt files remain untracked until explicitly added.

## Earlier research and verification

Earlier rating inputs remain in `backups/inputs/`. Earlier YAML logs, score exports, and
backups remain under `backups/runs/ratings/` and `backups/runs/backups/`; their file contents and filenames are preserved in the relocated
folders. New runs do not read them automatically. The private
`ratings/prompt/` inputs and `ratings/archive/` are separate from the dialogue's
`dialogue/prompt/` and `dialogue/archive/`.

This project has no automated test suite, simulated model runner, or CI. The
new five-file payload/JSON workflow is checked locally and reviewed independently;
on 2026-11-16 both agents completed live ratings using their full memories from
a 10-round dialogue, with thinking disabled. Earlier live YAML-era
results are documented in [task evidence](task-evidence.md).

The implementation and documentation retain the repository's [MIT License](../LICENSE).
The Python implementation is in `ratings/source/`. Existing PyYAML installation
and license files remain unchanged; packaging relocated the historical dependency
manifest without installing or configuring anything. Ratings now uses the shared
Agent A credential; provider and transport settings remain unchanged.

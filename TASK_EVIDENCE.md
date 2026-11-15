# Implementation evidence — 2026-11-15

## Scope and approvals

- Terminal program for shared research, MIT licensed, with Agent A always first.
- Separate complete starting prompts in `prompts/agent_a.txt` and
  `prompts/agent_b.txt`; no shared seed or alternate starting-agent feature.
- Thinking enabled at high effort; 8,192 generated tokens per request, about
  100 words per delivered message, and a conservative 512-token delivery bound.
- All returned reasoning and usage remain local. Each JSON trial has its own
  `trial_id`; `message_id` links accepted dialogue to its response, reasoning,
  raw usage, and whitespace-based word counts.
- The user explicitly approved `keys.local.env`, owner-only permissions,
  Git exclusion, and the revised credential loader on 2026-11-15. The file is
  plaintext, parsed without execution; nonblank environment values take precedence.
- The user explicitly requested no local test pipeline. No automated test
  suite, CI, dependency installation, or formatter configuration was added.
- The user authorized a four-message bird/egg handshake after supplying the
  keys locally. The initial build left an empty local key template; the user
  subsequently filled it and explicitly requested the live run recorded below.

## Recovery and provenance

The folder initially contained only the existing research document. It was not
a Git repository. The document remains excluded and unchanged (SHA-256):
`18ce34671590d2968092716142b943d9ba3e5b4308678fa8000f7bc02a8ddb52`.

Git baseline: `8f28d36`. Implementation checkpoint: `fc676ff`. All work is on
`feat/two-agent-dialogue`; no remote, push, or deployment was created. Retained
commits provide recovery points without changing the private research document
or credential file. Only named task-owned files were staged.

The implementation uses Python's standard library and independently written
code. Interface behavior was checked against DeepSeek's official
[Chat Completions reference](https://api-docs.deepseek.com/api/create-chat-completion/)
and [thinking-mode guide](https://api-docs.deepseek.com/guides/thinking_mode/).
No third-party application source was incorporated.

## Verification

- `PYTHONPYCACHEPREFIX=/private/tmp/deepseek-dialogue-pycache python3 -m py_compile deepseek_dialogue/__init__.py deepseek_dialogue/__main__.py deepseek_dialogue/api.py deepseek_dialogue/cli.py deepseek_dialogue/engine.py`
  passed for all 5 explicitly named modules under Python 3.9.6. The first attempt
  without the temporary cache override failed because the system's default
  cache directory was outside the sandbox; the override resolved that limitation.
- `python3 -m black --check deepseek_dialogue`: 5 files unchanged, passed.
  Existing Black 25.11.0 was used; no installation or persistent setup occurred.
- `python3 -m deepseek_dialogue --help`, `python3 -m deepseek_dialogue run --help`,
  `python3 -m deepseek_dialogue resume --help`, and
  `python3 -m deepseek_dialogue inspect --help`: all 4 invocations passed.
- `git diff --check`: passed.
- `git check-ignore keys.local.env 'Individual research note.docx' runs/trial.json`:
  all 3 paths ignored. `stat -f '%Lp %N' keys.local.env`: permissions `600`.
- `shasum -a 256 'Individual research note.docx'`: unchanged from the initial hash.
- Independent static review identified and then confirmed resolution of 6 issues:
  paused exit status, complete usage retention, escaped-credential detection,
  one-to-one resume history, interrupted acceptance, and missing word counts.
  Final review reported no remaining actionable findings in the reviewed scope.
- Automated test cases collected/executed: none, per the user's instruction.
  Syntax, formatting, help checks, and static review do not establish live API
  compatibility, successful speaker attribution, or actual accounting behavior.
  The subsequent live check below provides evidence for this specific configuration.

## Live handshake verification — 2026-11-15

Implementation tested: `58c634d`, with no source changes required.

Command:

```sh
env -u DEEPSEEK_API_KEY_A -u DEEPSEEK_API_KEY_B python3 -u -m deepseek_dialogue run --agent-a prompts/agent_a.txt --agent-b prompts/agent_b.txt --keys-file keys.local.env --max-messages 4
```

Exit status: 0. Four API requests completed; four accepted messages appeared in
Agent A, Agent B, Agent A, Agent B order, with each reply addressing the previous
argument. Both agents used `deepseek-flash`, thinking enabled at high effort.
The explicit environment unsets ensured the requested local key file was used.

The resulting private JSON is
`runs/8275edc469134b8993bef3ecf0975bdc.json`. A one-off in-memory inspection of
this actual artifact checked all four responses for:

- completed trial status, unique trial ID and unique matching message IDs;
- nonempty final content and reasoning text paired in each response;
- exact recomputed whitespace word counts for final content and thinking;
- valid input/output/reasoning/total counts, cache accounting, and delivery bounds;
- equality with the saved original prompts and accepted dialogue;
- absence of either key from all JSON strings and dictionary keys;
- reconstructed request bodies containing only each agent's own starting prompt,
  accepted dialogue, model, and generation settings: no IDs, word counts, token
  usage, or reasoning records.

All checks passed. `python3 -m deepseek_dialogue inspect runs/8275edc469134b8993bef3ecf0975bdc.json`
also completed with exit status 0 and rendered all four paired records and local
totals. Usage numbers and the dialogue remain in the ignored JSON rather than
being copied into tracked documentation. The credential file and trial JSON
both have mode `600` and are excluded by Git. Neither key was displayed.

An independent read-only payload audit (`gpt-6-luna`, high effort) confirmed the
same field exclusion and per-agent key selection in the code. The lead checked
the artifact and payload construction directly. This is not a packet capture;
it verifies the construction used by the transport and the saved live results.
No additional requests, automated test suite, or local test pipeline were added.

## Delegation evidence

- CLI, prompts, documentation: `gpt-6.1-sol`, medium effort; integrated by lead.
- Independent security/integration review: `gpt-6-astra`, high effort; did not
  implement or edit the change. Two follow-up review passes checked fixes.
- Earlier bounded API research: `gpt-6-luna`, high effort; sources checked by lead.
- Lead used the host's existing model setting. Exact lead model/effort and total
  elapsed time, token usage, and cost across agents are not exposed here and are
  recorded as unknown. No model cost or quality comparison is claimed.

## In-place resume to 20 — 2026-11-15

The user replaced continuation-file behavior with in-place continuation: enter a
chat ID, keep its existing `trial_id` and JSON path, and stop at 20 total accepted
messages or on Ctrl+C. Resume also accepts a saved JSON path. The `run` command's
initial message limit is unchanged; resume's former additional-message option
is removed. Already-complete chats make no API calls and do not load credentials.

Ctrl+C appends a local `interruption_notes` entry recording the timestamp, message
count, last accepted message ID, pending message ID when applicable, and a remark.
Notes survive later resumptions and are excluded from requests to both agents.
An adjacent exclusive lock prevents concurrent commands from overwriting a chat;
clean exit, errors, and Ctrl+C release it. Abrupt process termination can leave a
stale lock containing the process ID; the README explains its recovery.

Recovery baseline: `1254ccd`, with a clean tracked working tree before this work.
The four-message private JSON's starting SHA-256 was
`f11d01575eb1ba38b63a96befdfa9a9bec70e1fd336b41bc34f1ffe112c22dec`.

Verification before the live continuation:

- `PYTHONPYCACHEPREFIX=/private/tmp/deepseek-dialogue-pycache python3 -m py_compile deepseek_dialogue/cli.py deepseek_dialogue/engine.py`: both changed modules passed.
- `python3 -m black --check deepseek_dialogue`: 5 files unchanged, passed.
- `python3 -m deepseek_dialogue resume --help`: passed and describes optional ID
  input; no additional-message flag appears for resume.
- `git diff --check`: passed.
- Eight one-off offline scenarios passed using temporary JSON files and a
  substituted completion function: 4→20 (16 calls), 19→20 (1 call), already20
  (no key load/call/file change), Ctrl+C with a saved message and pending request,
  resuming after that interruption, interruption during initial terminal output,
  rejection of a concurrent lock, and prompted chat-ID forwarding.
- These checks made zero live API calls, created no persistent test files, and
  added no test pipeline. Temporary fixtures were automatically removed.
- An independent `gpt-6.1-sol` / xhigh review checked integration and interruption
  behavior. A startup interruption gap was found and fixed; follow-up review
  reported no remaining actionable findings. CLI/docs work used
  `gpt-6.1-sol` / medium. Total usage, cost, and elapsed time are unknown.

Live continuation command (implementation checkpoint `051d7ba`):

```sh
env -u DEEPSEEK_API_KEY_A -u DEEPSEEK_API_KEY_B python3 -u -m deepseek_dialogue resume 8275edc469134b8993bef3ecf0975bdc
```

Exit status 0: 16 additional requests were accepted, producing 20 total messages
in the existing JSON under the same ID. The original four messages, attempts,
prompts, creation time, and identifiers were preserved exactly. The original
four-message JSON was copied to the ignored `runs/backups/` directory before
continuation. All 20 records passed checks for alternating speakers, matching
unique message IDs, paired nonempty reasoning, recomputed word counts, and token
delivery bounds. Request construction excludes all local metadata. Keys remain
absent from the JSON; the JSON remains ignored and owner-only; no lock remained.

The final small addition records `resume_notes` for ordinary continuation
boundaries as well as `interruption_notes` for Ctrl+C. The completed live JSON
was annotated using its actual saved resumption time and original fourth-message
ID, recording that the chat had previously stopped after four messages. This
does not claim a Ctrl+C occurred during the live run; none occurred. An ignored
recovery copy of the completed JSON was retained before this metadata update.

Two final one-off checks passed: the interactive CLI on this completed live chat
made no key/API calls and left the JSON byte-identical; a temporary four-message
record retained both a new resumption note and a subsequent simulated Ctrl+C
note at the correct position. No persistent test files were created. The two
changed modules compiled, Black reported 5 files unchanged, and `git diff --check`
passed after the note addition. Independent review of the final note change
reported no blocking issues.

## Independent persona ratings — 2026-11-15

### Authorization, recovery, and implementation

The user approved the terminal rating plan and explicitly requested its
implementation. In planning, the user selected a separate command in this
existing shared-research/MIT repository, five drafted sample statements, a
512-token final-message acceptance cap, and thinking enabled for the first
live trial. They explicitly approved project-local PyYAML setup and new
single-key credential handling; the implementation request restated that approval.

Baseline `5e03c06` had a clean tracked/index state. Work uses
`codex/persona-ratings`; the existing `deepseek_dialogue` modules and prompts are
unchanged. Local task commits are the recovery points; revert task-owned commits
to roll back code, and remove the dedicated `.venv` separately if desired. Private
inputs, credentials, and results must be retained deliberately during rollback.
No push, shared-branch merge, or deployment is authorized or performed.

The independent command accepts one persona YAML and one statements YAML, sends
two fresh messages to `deepseek-flash`, and never reads prior trial records.
Thinking enabled uses high effort and 8,192 combined generation tokens; disabled
uses 512. Acceptance requires complete 1–5 integer ratings and at most 512 message
tokens after subtracting reported reasoning and optional safety-review tokens.
One malformed-answer retry uses the identical original payload only after a
durable primary snapshot and exclusive backup. HTTP/network errors stop without
retry. All attempts and original provider usage are retained in private YAML.

Private source preparation produced an active Skeptic YAML, five sample statements,
and an unchanged Extrapolator backup. Skeptic changes only replace the response
format and the instruction to provide a prose justification. The original pasted
attachment was not edited; its SHA-256 is
`67dc1e887ca7b856fea65d8de7e7790f277333997b4fb3fd2128bd7c26895b68`.
The existing private research document still has its previously recorded hash
`18ce34671590d2968092716142b943d9ba3e5b4308678fa8000f7bc02a8ddb52`.

The empty `ratings.local.env` template uses mode `600` and contains only a blank
`DEEPSEEK_API_KEY` assignment plus a comment. No existing dialogue credentials
were read or reused. The user will supply the rating key locally after
implementation. Environment precedence and file validation are documented in
`RATINGS.md`.

### Dependency and source provenance

Approved setup executed:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --index-url https://pypi.org/simple --only-binary=:all: --no-deps -r requirements-ratings.txt
```

Python 3.9.6 installed only PyYAML 6.0.3, from the PyPI
`pyyaml-6.0.3-cp39-cp39-macosx_11_0_arm64.whl` wheel. No global installation,
source build, pip upgrade, SDK, formatter, or persistent tool configuration was
added. Installed metadata identifies MIT licensing, and the installed wheel
retains `pyyaml-6.0.3.dist-info/licenses/LICENSE`. No third-party application
source was incorporated. The application uses Python standard-library HTTPS
and independently written code following this repository's existing patterns.

Interface research used official DeepSeek Chat Completions, JSON output,
thinking, and model documentation linked in `RATINGS.md`. The Firecrawl developer
search returned HTTP 402 without results; official pages were obtained through
the available web search fallback. No private source or credentials were sent
in documentation queries.

### Verification before credentials

- `PYTHONPYCACHEPREFIX=/private/tmp/deepseek-ratings-pycache .venv/bin/python -m py_compile deepseek_ratings/__init__.py deepseek_ratings/__main__.py deepseek_ratings/api.py deepseek_ratings/cli.py deepseek_ratings/inputs.py deepseek_ratings/records.py deepseek_ratings/response.py deepseek_ratings/engine.py`: all eight named modules compiled.
- `python3 -m black deepseek_ratings`: existing Black 25.11.0 formatted six files;
  two were unchanged. `python3 -m black --check deepseek_ratings`: eight unchanged,
  passed. No formatter setup was changed.
- `.venv/bin/python -m deepseek_ratings --help` and
  `python3 -m deepseek_dialogue --help`: both invocations passed; rating help
  exposes all six planned options, and the original dialogue commands remain.
- `git diff --check`: passed.
- A one-off inspection of the real prepared YAML, using `load_inputs`,
  `build_payload`, and PyYAML, confirmed one active Skeptic, five statements,
  exact equality of the backed-up Extrapolator with the attachment, unchanged
  Skeptic text before the deliberation/response rules, and fresh two-message
  payloads with the correct settings for both enabled and disabled thinking.
  This was input inspection only: no provider completion or simulated response.
- `git check-ignore ratings.local.env inputs/personas.local.yaml inputs/statements.local.yaml backups/extrapolator.local.yaml runs/ratings/example.yaml .venv/pyvenv.cfg`:
  all six paths ignored. `stat -f '%Lp %N' ratings.local.env inputs/personas.local.yaml inputs/statements.local.yaml backups/extrapolator.local.yaml`:
  all four real private files mode `600`.
- `.venv/bin/python -m pip check`: no broken requirements. PyYAML metadata and its
  retained MIT license were inspected directly.
- Automated tests collected/executed: **0**, intentionally. No test suite, local
  trial pipeline, simulated model runner, or CI was added. Error, backup/retry,
  and interruption paths have static review only until observed in actual use.

Independent security/integration review used `gpt-6-astra`, high effort,
read-only; that reviewer did not implement the change. Review found one P2
durability gap: new output-directory entries also needed their parents synced.
The lead added recursive creation with immediate parent synchronization, and the
reviewer confirmed the fix with no remaining blocking findings. A minor backup
documentation wording clarification was also applied. No secret contents,
simulated trials, tests, or live APIs were accessed by the reviewer.

After the final edits, the three changed modules (inputs, response, records)
compiled again; Black checks and `git diff --check` passed. A read-only
`_sync_directory(Path('inputs'))` call confirmed directory fsync support on the
actual filesystem without creating a trial. Lead model/effort, total tokens,
and total cost are not exposed and remain unknown. No performance, cost, or
routing comparison is claimed.

Implementation commit: `b59f359`, verified on its dedicated local branch with a
clean tracked working tree. The user subsequently confirmed that the single key
was saved locally and authorized the already-planned live trial.

### Live Skeptic trial

Command executed against implementation `b59f359`:

```sh
env -u DEEPSEEK_API_KEY .venv/bin/python -u -m deepseek_ratings --personas inputs/personas.local.yaml --statements inputs/statements.local.yaml --persona skeptic --thinking enabled --keys-file ratings.local.env
```

Exit status: `0`. One request, five accepted ratings, no retry. Private artifact:
`runs/ratings/809d6f2537b842149f565df523d7fa47.yaml`. The environment unset ensured
that the user-supplied local key file was used. No code change was required.

A one-off read of this real YAML using `yaml.safe_load`, `load_inputs`,
`build_payload`, `evaluate`, `aggregate`, and the credential guard confirmed:

- completed status, UUID/path agreement, one accepted attempt, and five scores;
- exact equality with the current persona, statement list, and intended fresh
  two-message request, both at trial and attempt level;
- successful revalidation of the raw API response and matching parsed ratings;
- separate provider-backed input, message, reasoning, completion, and total
  counts, correct arithmetic/aggregate usage, and message output below 512 tokens;
- absence of the API key from raw YAML and all parsed strings;
- mode `600` for both the YAML and key file, and Git exclusion of both paths.

The actual request explicitly set `thinking.type: enabled` and
`reasoning_effort: high`, and the returned model was `deepseek-flash`. DeepSeek
reported **zero reasoning tokens** and returned an empty `reasoning_content`
string. Those values are retained verbatim; the tool did not invent reasoning or
replace a missing count with zero in this thinking-enabled run. This verifies
request construction and accounting, not that the provider generated nonzero
reasoning. Trial scores and other usage values remain in the private artifact.

No additional live calls were made. Disabled thinking, malformed-output retries,
provider failures, and interruption behavior remain reviewed statically rather
than exercised live. Automated test cases collected/executed remain zero per the
agreed verification scope. No local trial pipeline or simulated model runner was
introduced. Total model usage/cost across implementation and review is unknown;
no comparison or savings claim is made.

### Separate per-call score YAML — 2026-11-15

The user requested a separate score YAML for every call, preserving the detailed
log, then narrowed its contents to only trial ID, creation time, status, optional
model, and statement/score pairs. The existing dedicated task branch was reused
from clean baseline `94408da`; no dependency, credential, provider, or model
configuration was changed.

Finished calls now export to `scores/TRIAL_ID.attempt-N.yaml` beside the full log.
The exact top-level fields are `trial_id`, `created_at` (the call start time),
`status`, `model`, and `scores`; each score entry contains only `statement` and
`score`, in original statement order. Attempts with no validated complete rating
set have null scores. Pending attempts are not exported. Full raw responses,
prompts, usage, thinking, and issues remain solely in the existing detailed log.
The full log is durably saved before the derived files; score-writing failure
stops further calls. Existing owner-only atomic persistence and backup-before-
retry ordering are retained through a shared YAML writer.

The real completed trial was backfilled using `save_scores`, without an API call
or modification to the source log. Created private artifact:
`runs/ratings/scores/809d6f2537b842149f565df523d7fa47.attempt-1.yaml`.
The original detailed log's bytes matched before and after export, SHA-256:
`6069579b96589888ff7d9e0f09bed976ab0bdae4f8c4c8eb2af78a91216dddcd`.

Verification:

- `python3 -m black deepseek_ratings/records.py`: formatted the one changed
  module. `python3 -m black --check deepseek_ratings/records.py`: one unchanged,
  passed.
- `PYTHONPYCACHEPREFIX=/private/tmp/deepseek-ratings-pycache .venv/bin/python -m py_compile deepseek_ratings/records.py`:
  the changed module compiled successfully.
- `.venv/bin/python -m deepseek_ratings --help` and `git diff --check`: passed.
- A one-off export/inspection of the actual saved trial, using PyYAML,
  `save_scores`, and the existing credential guard, confirmed exactly five
  matching full statement/score pairs, the exact permitted top-level and pair
  fields, matching call metadata, absence of the credential, mode `600`, and
  byte-for-byte preservation of the original log.
- `git check-ignore runs/ratings/scores/809d6f2537b842149f565df523d7fa47.attempt-1.yaml`:
  the new artifact is ignored.
- Independent read-only `gpt-6-astra` / high review reported no blocking findings
  and confirmed field restriction, log preservation/order, atomic persistence,
  and stopped retries on export failure. No keys or live APIs were accessed by
  the reviewer. Total review/model usage and cost remain unknown.
- Automated tests collected/executed: **0**. No simulated trials, local trial
  pipeline, or extra live requests were added. Future-call integration and
  failure behavior were reviewed statically; actual artifact export was verified.

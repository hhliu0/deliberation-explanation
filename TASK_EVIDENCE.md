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

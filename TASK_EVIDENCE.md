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
  keys locally. That live run has not happened: the local key template is empty.

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

## Delegation evidence

- CLI, prompts, documentation: `gpt-6.1-sol`, medium effort; integrated by lead.
- Independent security/integration review: `gpt-6-astra`, high effort; did not
  implement or edit the change. Two follow-up review passes checked fixes.
- Earlier bounded API research: `gpt-6-luna`, high effort; sources checked by lead.
- Lead used the host's existing model setting. Exact lead model/effort and total
  elapsed time, token usage, and cost across agents are not exposed here and are
  recorded as unknown. No model cost or quality comparison is claimed.

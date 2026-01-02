# Continuous-Claude-v2 vs fasthooks

[Continuous-Claude-v2](https://github.com/anthropics/continuous-claude-v2) is a session continuity system that preserves context across Claude Code sessions. This page compares its hook implementation with fasthooks.

## Different Goals

| Aspect | Continuous-Claude-v2 | fasthooks |
|--------|----------------------|-----------|
| **Primary Purpose** | Session continuity | Hook development framework |
| **Philosophy** | Preserve state across clears | Build custom hook logic |
| **Core Feature** | Ledgers + handoffs | Typed events + DI |
| **Target User** | Power users wanting continuity | Developers building hooks |

**Continuous-Claude-v2** solves context degradation - when Claude compacts, you lose signal. Instead of fighting compaction, it embraces `/clear` with preserved state via ledgers and handoffs.

**fasthooks** is a framework for building any hook logic - security policies, rate limiting, code review, integrations.

## Architecture Comparison

### Continuous-Claude-v2: Pre-bundled TypeScript

```
.claude/hooks/
├── src/                    # TypeScript source
│   ├── session-start-continuity.ts
│   ├── typescript-preflight.ts
│   └── ...
├── dist/                   # Pre-compiled JS (committed)
│   ├── session-start-continuity.mjs
│   └── ...
├── *.sh                    # Shell wrappers
│   ├── session-start.sh    → node dist/session-start-continuity.mjs
│   └── ...
└── build.sh                # Rebuild after source changes
```

**Deployment:** Copy `.claude/hooks/`, make scripts executable. No npm install needed.

### fasthooks: Pure Python

```python
# hooks.py
from fasthooks import HookApp, deny

app = HookApp()

@app.pre_tool("Bash")
def check_bash(event):
    if "rm -rf" in event.command:
        return deny("Blocked")

if __name__ == "__main__":
    app.run()
```

**Deployment:** `pip install fasthooks`, point Claude Code to `python hooks.py`.

## Hook Events Supported

| Event | Continuous-Claude | fasthooks |
|-------|:-----------------:|:---------:|
| SessionStart | ✅ | ✅ |
| PreToolUse | ✅ | ✅ |
| PostToolUse | ✅ | ✅ |
| PreCompact | ✅ | ✅ |
| UserPromptSubmit | ✅ | ✅ |
| SubagentStop | ✅ | ✅ |
| SessionEnd | ✅ | ✅ |
| Stop | ❌ | ✅ |
| Notification | ❌ | ✅ |
| PermissionRequest | ❌ | ✅ |

Both cover core events. fasthooks has broader coverage.

## Response Format

### Continuous-Claude-v2: Manual JSON

```typescript
// Block decision (PreToolUse only)
console.log(JSON.stringify({
  decision: 'block',
  reason: 'TypeScript errors found:\n  Line 15: Property does not exist'
}));

// Context injection
console.log(JSON.stringify({
  result: 'continue',
  hookSpecificOutput: {
    hookEventName: 'SessionStart',
    additionalContext: ledgerContent + '\n\n' + handoffContent
  }
}));

// Simple continue
console.log(JSON.stringify({ continue: true }));
```

### fasthooks: Helper Functions

```python
from fasthooks import allow, deny, block

@app.pre_tool("Bash")
def check(event):
    if dangerous(event.command):
        return deny("Blocked")        # Block with reason
    return allow(message="Approved")  # Continue with message

@app.on_stop()
def prevent_stop(event):
    return block("Keep working")      # Prevent stopping
```

| Aspect | Continuous-Claude | fasthooks |
|--------|-------------------|-----------|
| Block tool | `decision: 'block'` | `deny("reason")` |
| Allow | `continue: true` | `allow()` or `None` |
| Inject context | `hookSpecificOutput.additionalContext` | `allow(message=...)` |
| Block stop | Not supported | `block("reason")` |

## Blocking Capability

### Continuous-Claude-v2: PreToolUse Only

```typescript
// typescript-preflight.ts - blocks on type errors
if (checkResult.has_errors) {
  console.log(JSON.stringify({
    decision: 'block',
    reason: `⚠️ TypeScript Pre-flight: ${checkResult.summary}`
  }));
  return;
}
```

Only PreToolUse can block. Other events just continue or inject context.

### fasthooks: Any Event

```python
@app.pre_tool("Write")
def check_write(event):
    if ".env" in event.file_path:
        return deny("Cannot modify .env")

@app.on_stop()
def require_tests(event, transcript: Transcript):
    if transcript.stats.tool_calls.get("Bash", 0) == 0:
        return block("Run tests before stopping")

@app.on_prompt()
def rate_limit(event, state: State):
    if state.get("prompts", 0) > 100:
        return deny("Rate limit exceeded")
```

Any handler can deny/block, not just PreToolUse.

## State Management

### Continuous-Claude-v2: Three-Layer System

**Layer 1: Continuity Ledger** (within-session)
```markdown
<!-- thoughts/ledgers/CONTINUITY_CLAUDE-myproject.md -->
## Goal
Implement payment integration

## State
- Done: Auth system ✓
- Now: Payment webhooks
- Next: Stripe sandbox tests
```

**Layer 2: Handoffs** (between-session)
```markdown
<!-- thoughts/shared/handoffs/session-123/task-1.md -->
---
root_span_id: abc-123
outcome: PARTIAL_PLUS
---
## Context
Working on payment webhooks...

## Key Decisions
- Using Stripe webhooks over polling
```

**Layer 3: Artifact Index** (searchable history)
```sql
-- .claude/cache/artifact-index/context.db (SQLite + FTS5)
SELECT * FROM handoffs
WHERE outcome = 'FAILED'
AND what_failed LIKE '%authentication%'
```

### fasthooks: Dependency Injection

```python
from fasthooks.depends import State, Transcript

@app.pre_tool("Bash")
def handler(event, state: State, transcript: Transcript):
    # state: JSON file per session, auto-loaded
    state["command_count"] = state.get("command_count", 0) + 1
    state.save()

    # transcript: Parsed history with stats
    print(f"Total tokens: {transcript.stats.total_tokens}")
```

| Aspect | Continuous-Claude | fasthooks |
|--------|-------------------|-----------|
| State format | Markdown ledgers | JSON dict |
| Persistence | File-based (3 layers) | File-based (1 layer) |
| Searchable | SQLite + FTS5 | No built-in search |
| Complexity | High (rich context) | Low (simple state) |
| Setup | Requires directory structure | Zero setup |

## Unique Features

### Continuous-Claude-v2

**1. TypeScript Preflight**
```typescript
// PreToolUse runs tsc --noEmit before Edit/Write on .ts files
if (checkResult.has_errors) {
  return { decision: 'block', reason: errorSummary };
}
```
Catches type errors before they're written.

**2. Skill Auto-Activation**
```json
// skill-rules.json
{
  "skills": {
    "morph-search": {
      "priority": "high",
      "promptTriggers": {
        "keywords": ["search", "grep", "find"]
      }
    }
  }
}
```
UserPromptSubmit hook suggests skills based on keywords/intent.

**3. Auto-Handoff on Compact**

PreCompact hook automatically:
1. Parses transcript
2. Generates handoff with file:line references
3. SessionStart loads it on resume

No manual handoff needed.

**4. Outcome Tracking**
```
SUCCEEDED | PARTIAL_PLUS | PARTIAL_MINUS | FAILED
```
Mark handoff outcomes, query past failures to improve decisions.

**5. Context Percentage Warnings**

Reads `/tmp/claude-context-pct-{SESSION}.txt`, shows warnings:
- <60%: Normal
- 60-79%: Yellow warning
- 80%+: Red critical

**6. Pre-bundled Deployment**

No npm install - just copy `.claude/hooks/` and run.

### fasthooks

**1. Response Helpers**
```python
deny("reason")   # Block with message
block("reason")  # Prevent stop
allow(message="...") # Continue with feedback
```

**2. Dependency Injection**
```python
def handler(event, state: State, transcript: Transcript, tasks: Tasks):
    # All dependencies auto-injected
```

**3. Blueprints**
```python
security = Blueprint()

@security.pre_tool("Bash")
def no_sudo(event):
    ...

app.include(security)
```

**4. Guards**
```python
@app.pre_tool("Bash", when=lambda e: "sudo" in e.command)
def check_sudo(event):
    return deny("No sudo")
```

**5. Background Tasks**
```python
@task
def analyze(code: str) -> str:
    return expensive_analysis(code)

@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    tasks.add(analyze, event.content)
```

**6. Testing Utilities**
```python
client = TestClient(app)
response = client.send(MockEvent.bash(command="rm -rf /"))
assert response.decision == "deny"
```

## Developer Experience

### Continuous-Claude-v2: TypeScript + Shell

```typescript
// .claude/hooks/src/my-hook.ts
import { readFileSync } from 'fs';

interface Input {
  session_id: string;
  cwd: string;
  tool_name: string;
  tool_input: any;
}

const input: Input = JSON.parse(readFileSync('/dev/stdin', 'utf-8'));

if (input.tool_name === 'Bash' && input.tool_input.command.includes('rm')) {
  console.log(JSON.stringify({ decision: 'block', reason: 'Blocked' }));
} else {
  console.log(JSON.stringify({ continue: true }));
}
```

```bash
# .claude/hooks/my-hook.sh
#!/bin/bash
cd ~/.claude/hooks
cat | node dist/my-hook.mjs
```

**Workflow:**
1. Edit TypeScript in `src/`
2. Run `./build.sh` to compile
3. Test by running hook manually
4. Commit `dist/` for deployment

### fasthooks: Pure Python

```python
# hooks.py
from fasthooks import HookApp, deny

app = HookApp()

@app.pre_tool("Bash")
def check_bash(event):
    if "rm" in event.command:
        return deny("Blocked")

if __name__ == "__main__":
    app.run()
```

**Workflow:**
1. Write Python
2. Run tests with `TestClient`
3. Deploy

## Feature Matrix

| Feature | Continuous-Claude | fasthooks |
|---------|:-----------------:|:---------:|
| **Hook Framework** | Partial (specialized) | ✅ (general purpose) |
| **Deny/Block** | PreToolUse only | Any event |
| **Typed Events** | TypeScript interfaces | Pydantic models |
| **Property Accessors** | Manual (`input.tool_input.x`) | `event.command` |
| **State Persistence** | ✅ (3-layer) | ✅ (simple) |
| **Transcript Parsing** | ✅ (for handoffs) | ✅ (built-in) |
| **Background Tasks** | ❌ | ✅ |
| **Blueprints** | ❌ | ✅ |
| **Middleware** | ❌ | ✅ |
| **Guards** | ❌ | ✅ |
| **Testing Utils** | ❌ | ✅ |
| **Skills System** | ✅ | ❌ |
| **TypeScript Preflight** | ✅ | ❌ |
| **Auto-Handoff** | ✅ | ❌ |
| **Outcome Tracking** | ✅ | ❌ |
| **Zero-Config Deploy** | ✅ (pre-bundled) | Requires pip |

## When to Use Each

### Use Continuous-Claude-v2 When:

- You want **session continuity** across `/clear` and compaction
- You need **ledgers and handoffs** for complex multi-session work
- You want **TypeScript type checking** before edits
- You need **skill auto-activation** based on keywords
- You want **outcome tracking** to learn from past sessions
- You prefer **pre-bundled deployment** (no pip/npm at runtime)

### Use fasthooks When:

- You're **building custom hooks** with any logic
- You need to **block on any event** (not just PreToolUse)
- You want **typed events** with IDE autocomplete
- You need **dependency injection** (State, Transcript, Tasks)
- You want **modular composition** (blueprints, middleware)
- You need **easy testing** with mock events
- You want **background tasks** for async work

## Using Both Together

The systems serve different purposes and can coexist:

```json
{
  "hooks": {
    "SessionStart": [
      { "command": "~/.claude/hooks/session-start.sh" }
    ],
    "PreToolUse": [
      { "command": "python /path/to/fasthooks/security.py" },
      { "command": "~/.claude/hooks/typescript-preflight.sh" }
    ],
    "PostToolUse": [
      { "command": "~/.claude/hooks/handoff-index.sh" }
    ],
    "PreCompact": [
      { "command": "~/.claude/hooks/pre-compact.sh" }
    ]
  }
}
```

- **Continuous-Claude** for session continuity (ledgers, handoffs, context injection)
- **fasthooks** for policy enforcement (security, rate limiting, custom logic)

## Summary

| Aspect | Continuous-Claude-v2 | fasthooks |
|--------|----------------------|-----------|
| **What It Is** | Session continuity system | Hook framework |
| **Philosophy** | Preserve context across clears | Build custom hook logic |
| **Best For** | Long-running projects | Custom policies |
| **Language** | TypeScript + Shell | Python |
| **Blocking** | PreToolUse only | Any event |
| **Complexity** | High (rich features) | Low (simple API) |
| **Dependencies** | Pre-bundled (none) | pip install |

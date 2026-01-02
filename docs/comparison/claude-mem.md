# claude-mem vs fasthooks

[claude-mem](https://github.com/anthropics/claude-mem) is a Claude Code plugin that provides persistent AI memory across sessions. This page compares its hook implementation with fasthooks.

## Different Goals

| Aspect | claude-mem | fasthooks |
|--------|-----------|-----------|
| **Primary Purpose** | Persistent memory system | Hook development framework |
| **Philosophy** | Observer (capture & store) | Enforcer (validate & control) |
| **Can Block Claude?** | No - always allows | Yes - `deny()`, `block()` |
| **Target User** | End users wanting memory | Developers building hooks |

**claude-mem** is a complete application that happens to use hooks internally. It captures tool usage, generates semantic observations via Claude, and injects context into new sessions.

**fasthooks** is a framework for building custom hooks with any logic you need - security policies, rate limiting, code review, etc.

## Architecture Comparison

### claude-mem: HTTP Client + Worker Service

```
┌─────────────────────────────────────────────────┐
│              Claude Code Session                │
└─────────────────────────────────────────────────┘
         │ (spawns hooks)
         ▼
┌─────────────────────────────────────────────────┐
│  Hook Scripts (Node.js)                         │
│  - context-hook.js                              │
│  - save-hook.js                                 │
│  - summary-hook.js                              │
│  - new-hook.js                                  │
└─────────────────────────────────────────────────┘
         │ (HTTP requests)
         ▼
┌─────────────────────────────────────────────────┐
│  Worker Service (localhost:37777)               │
│  - Express HTTP server                          │
│  - SQLite + Chroma storage                      │
│  - Claude Agent SDK for observations            │
│  - Web UI viewer                                │
└─────────────────────────────────────────────────┘
```

Hooks are thin HTTP clients that delegate to a persistent worker service.

### fasthooks: Self-Contained Subprocess

```
┌─────────────────────────────────────────────────┐
│              Claude Code Session                │
└─────────────────────────────────────────────────┘
         │ (spawns hook)
         ▼
┌─────────────────────────────────────────────────┐
│  fasthooks Process                              │
│  - Read JSON from stdin                         │
│  - Route to handler via decorators              │
│  - Execute handler with DI dependencies         │
│  - Write JSON response to stdout                │
└─────────────────────────────────────────────────┘
```

Each hook invocation is self-contained with built-in state persistence.

## Hook Response Model

### claude-mem: Observer Only

```typescript
// claude-mem always returns "continue"
export const STANDARD_HOOK_RESPONSE = JSON.stringify({
  continue: true,
  suppressOutput: true
});

// Only SessionStart can inject context
console.log(JSON.stringify({
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: "Previous session context...",
  },
}));
```

**Cannot prevent tool execution** - hooks observe and record, never block.

### fasthooks: Full Control

```python
from fasthooks import allow, deny, block

@app.pre_tool("Bash")
def check_bash(event):
    if "rm -rf" in event.command:
        return deny("Dangerous command blocked")  # Prevents execution
    return allow()

@app.on_stop()
def prevent_stop(event):
    if not all_tests_passed():
        return block("Tests still failing")  # Keeps Claude working
    return allow()
```

**Full enforcement capability** - allow, deny, block, modify inputs.

## Event Coverage

| Event | claude-mem | fasthooks |
|-------|:----------:|:---------:|
| PreToolUse | ❌ | ✅ |
| PostToolUse | ✅ | ✅ |
| Stop | ✅ | ✅ |
| SubagentStop | ❌ | ✅ |
| SessionStart | ✅ | ✅ |
| SessionEnd | ❌ | ✅ |
| UserPromptSubmit | ✅ | ✅ |
| Notification | ❌ | ✅ |
| PreCompact | ❌ | ✅ |
| PermissionRequest | ❌ | ✅ |

claude-mem only implements events needed for memory capture. fasthooks supports all Claude Code hook events.

## Type Safety

### claude-mem: Interfaces (No Validation)

```typescript
// Interface defined but not validated at runtime
export interface PostToolUseInput {
  session_id: string;
  cwd: string;
  tool_name: string;
  tool_input: any;      // No type safety
  tool_response: any;   // No type safety
}

// Manual JSON parsing, no validation
const parsed = input ? JSON.parse(input) : undefined;
await saveHook(parsed);  // May fail at runtime
```

### fasthooks: Pydantic Models with Properties

```python
# Validated Pydantic models with typed properties
@app.pre_tool("Bash")
def handler(event):
    event.command      # str - typed, autocomplete works
    event.description  # str | None
    event.timeout      # int | None
    event.tool_input   # dict - full access if needed
```

## State Management

### claude-mem: External Database

```typescript
// Hooks call worker API, worker manages SQLite + Chroma
const response = await fetch(`http://127.0.0.1:${port}/api/sessions/observations`, {
  method: 'POST',
  body: JSON.stringify({ contentSessionId, tool_name, tool_input, tool_response })
});

// Worker handles:
// - SQLite for structured data (sessions, observations, summaries)
// - Chroma for vector search (semantic embeddings)
// - Settings JSON file
```

**Pros:** Rich storage (SQL + vector), shared across hooks
**Cons:** Requires running worker service, HTTP overhead

### fasthooks: Dependency Injection

```python
from fasthooks.depends import State, Transcript

@app.pre_tool("Bash")
def handler(event, state: State, transcript: Transcript):
    # state: JSON file per session, auto-loaded
    count = state.get("bash_count", 0) + 1
    state["bash_count"] = count
    state.save()

    # transcript: Parsed conversation history with stats
    if transcript.stats.tool_calls.get("Bash", 0) > 100:
        return deny("Rate limit exceeded")
```

**Pros:** Zero setup, injected automatically, no external services
**Cons:** Simpler storage (JSON), no vector search built-in

## Hook Registration

### claude-mem: Monolithic JSON

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          { "type": "command", "command": "node smart-install.js", "timeout": 300 },
          { "type": "command", "command": "bun worker-service.cjs start", "timeout": 15 },
          { "type": "command", "command": "node context-hook.js", "timeout": 15 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          { "type": "command", "command": "node save-hook.js", "timeout": 300 }
        ]
      }
    ]
  }
}
```

Single JSON file, multiple commands per event, sequential execution.

### fasthooks: Decorators + Blueprints

```python
from fasthooks import HookApp, Blueprint

# Main app
app = HookApp()

@app.pre_tool("Bash")
def check_bash(event):
    ...

# Modular blueprints
security = Blueprint()

@security.pre_tool("Write")
def check_write(event):
    ...

app.include(security)
```

Decorator-based registration, composable blueprints, guards for filtering.

## Error Handling

### claude-mem: Throw & Log

```typescript
async function saveHook(input?: PostToolUseInput): Promise<void> {
  if (!input) {
    throw new Error('saveHook requires input');  // Process exits with code 1
  }

  const response = await fetch(...);
  if (!response.ok) {
    throw new Error(`Observation storage failed: ${response.status}`);
  }

  console.log(STANDARD_HOOK_RESPONSE);
}
```

Errors propagate, logged to file, Claude continues (graceful degradation).

### fasthooks: Structured Responses

```python
@app.pre_tool("Bash")
def handler(event):
    try:
        validate_command(event.command)
    except SecurityError as e:
        return deny(str(e))  # Structured denial
    return allow()
```

Errors become structured responses that Claude understands.

## Testing

### claude-mem: Integration Tests

```typescript
// Spawn real hook processes, check JSON output
function runHookScript(scriptName: string, input: object): string {
  const result = execSync(`bash "${scriptPath}"`, {
    input: JSON.stringify(input),
  });
  return result.toString('utf-8');
}

it('should output valid JSON', () => {
  const output = runHookScript('session-init.sh', { ... });
  expect(() => JSON.parse(output)).not.toThrow();
});
```

No mocking utilities - tests spawn real processes.

### fasthooks: MockEvent + TestClient

```python
from fasthooks.testing import MockEvent, TestClient

def test_blocks_dangerous_commands():
    app = HookApp()

    @app.pre_tool("Bash")
    def handler(event):
        if "rm -rf" in event.command:
            return deny("Blocked")

    client = TestClient(app)

    # Mock events without spawning processes
    response = client.send(MockEvent.bash(command="rm -rf /"))
    assert response.decision == "deny"

    response = client.send(MockEvent.bash(command="ls"))
    assert response is None  # Allowed
```

First-class testing utilities with mock events.

## Feature Matrix

| Feature | claude-mem | fasthooks |
|---------|:----------:|:---------:|
| **Hook Framework** | ❌ (app, not framework) | ✅ |
| **Deny/Block** | ❌ | ✅ |
| **Typed Events** | Partial (interfaces) | ✅ (Pydantic) |
| **Property Accessors** | ❌ | ✅ (`event.command`) |
| **State Persistence** | ✅ (SQLite) | ✅ (JSON) |
| **Transcript Parsing** | ✅ (via SDK) | ✅ (built-in) |
| **Vector Search** | ✅ (Chroma) | ❌ |
| **Background Tasks** | ✅ (SDK agent) | ✅ (`Tasks`) |
| **Blueprints** | ❌ | ✅ |
| **Middleware** | ❌ | ✅ |
| **Guards** | ❌ | ✅ (`when=`) |
| **Testing Utils** | ❌ | ✅ |
| **Web UI** | ✅ | ❌ |
| **Memory/RAG** | ✅ (core feature) | ❌ |

## When to Use Each

### Use claude-mem When:

- You want **persistent memory** across Claude Code sessions
- You need **semantic search** over past conversations
- You want a **ready-to-use solution** (not building custom hooks)
- You're okay with running a **background service**
- You don't need to **block or modify** Claude's actions

### Use fasthooks When:

- You're **building custom hooks** with specific logic
- You need to **enforce policies** (deny dangerous commands, rate limit)
- You want **typed events** with IDE autocomplete
- You need **modular composition** (blueprints, middleware)
- You want **easy testing** with mock events
- You prefer **self-contained hooks** (no external services)

## Using Both Together

claude-mem and fasthooks serve different purposes and can coexist:

```json
{
  "hooks": {
    "PreToolUse": [
      { "command": "python /path/to/fasthooks/security.py" }
    ],
    "PostToolUse": [
      { "command": "python /path/to/fasthooks/audit.py" },
      { "command": "node /path/to/claude-mem/save-hook.js" }
    ],
    "SessionStart": [
      { "command": "node /path/to/claude-mem/context-hook.js" }
    ]
  }
}
```

- **fasthooks** for PreToolUse enforcement (block dangerous commands)
- **claude-mem** for PostToolUse observation (capture what happened)
- Both can run on the same events (sequential execution)

## Summary

| Aspect | claude-mem | fasthooks |
|--------|-----------|-----------|
| **What It Is** | Memory plugin | Hook framework |
| **Philosophy** | Observe & remember | Validate & control |
| **Best For** | Persistent context | Custom hook logic |
| **Complexity** | Full application | Library |
| **Dependencies** | Worker service, Bun, SQLite, Chroma | None (pure Python) |

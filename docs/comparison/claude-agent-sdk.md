# Claude Agent SDK Hooks vs fasthooks

The [Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-python) provides in-process hook callbacks for applications that embed Claude. This page compares SDK hooks with fasthooks.

## Architecture

| Aspect | Claude Agent SDK | fasthooks |
|--------|------------------|-----------|
| **Execution Model** | In-process async callback | Subprocess per hook call |
| **Protocol** | Bidirectional stream (SDK ↔ CLI) | Stdin/stdout JSON |
| **Context** | Runs inside SDK application | Spawned by Claude Code CLI |
| **Async** | Required (`async def`) | Optional |

**SDK hooks** run inside your Python application alongside the SDK client. The CLI sends hook events over a bidirectional stream, and your callback responds immediately.

**fasthooks** runs as a separate process spawned by Claude Code. Each hook invocation starts a fresh process, reads JSON from stdin, and writes the response to stdout.

## Event Coverage

| Event | SDK | fasthooks |
|-------|:---:|:---------:|
| PreToolUse | ✅ | ✅ |
| PostToolUse | ✅ | ✅ |
| UserPromptSubmit | ✅ | ✅ |
| Stop | ✅ | ✅ |
| SubagentStop | ✅ | ✅ |
| PreCompact | ✅ | ✅ |
| SessionStart | ❌ | ✅ |
| SessionEnd | ❌ | ✅ |
| Notification | ❌ | ✅ |
| PermissionRequest | ❌* | ✅ |

*SDK uses `can_use_tool` callback instead of PermissionRequest hooks.

!!! note "SDK Limitations"
    The SDK documentation states: "Due to setup limitations, the Python SDK does not support SessionStart, SessionEnd, and Notification hooks."

## Developer Experience

### SDK Hooks - Manual & Verbose

```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

async def check_bash(input_data, tool_use_id, context):
    # Manual tool name check (no routing)
    if input_data["tool_name"] != "Bash":
        return {}

    # Manual dict access (no typed properties)
    command = input_data["tool_input"].get("command", "")

    if "rm -rf" in command:
        # Manual response dict construction
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Dangerous command blocked",
            }
        }
    return {}

# Manual registration
options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [
            HookMatcher(matcher="Bash", hooks=[check_bash]),
        ],
    }
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Run rm -rf /")
    async for msg in client.receive_response():
        print(msg)
```

### fasthooks - Concise & Typed

```python
from fasthooks import HookApp, deny

app = HookApp()

@app.pre_tool("Bash")  # Decorator routing
def check_bash(event):
    # Typed property access
    if "rm -rf" in event.command:
        return deny("Dangerous command blocked")  # Helper function

if __name__ == "__main__":
    app.run()
```

**Key DX differences:**

| Aspect | SDK | fasthooks |
|--------|-----|-----------|
| Routing | Manual `if tool_name` check | `@app.pre_tool("Bash")` decorator |
| Event access | `input_data["tool_input"]["command"]` | `event.command` |
| Response | Raw dict with nested structure | `deny("reason")` |
| Registration | Dict in options | Decorator |

## Feature Matrix

| Feature | SDK | fasthooks |
|---------|:---:|:---------:|
| Typed events | TypedDict | Pydantic + properties |
| Response helpers | ❌ | `allow()`, `deny()`, `block()` |
| Tool matchers | String only | Decorators + `when=` guards |
| Multiple tools | `"Write\|Edit"` regex | `@app.pre_tool("Write", "Edit")` |
| Catch-all | `matcher=None` | `@app.pre_tool()` or `"*"` |
| State persistence | ❌ | `State` dependency |
| Transcript parsing | ❌ | `Transcript` dependency |
| Background tasks | ❌ | `Tasks` dependency |
| Blueprints | ❌ | `Blueprint` class |
| Middleware | ❌ | `@app.middleware` |
| Testing utils | ❌ | `MockEvent`, `TestClient` |

## Statefulness

### SDK Hooks - Stateless

SDK hooks have no built-in state management. Each callback is stateless:

```python
# SDK: No state between calls
async def my_hook(input_data, tool_use_id, context):
    # Must manually read transcript_path if you need history
    transcript_path = input_data.get("transcript_path")
    # Must implement your own persistence
    return {}
```

### fasthooks - Built-in State & Transcript

```python
from fasthooks.depends import State, Transcript

@app.pre_tool("Bash")
def rate_limit(event, state: State, transcript: Transcript):
    # state: persisted dict (JSON file per session)
    count = state.get("bash_count", 0) + 1
    state["bash_count"] = count
    state.save()

    # transcript: parsed history with aggregated stats
    stats = transcript.stats
    if stats.tool_calls.get("Bash", 0) > 100:
        return deny(f"Rate limit: {stats.tool_calls['Bash']} bash commands")

    # Access token usage, duration, file counts, etc.
    print(f"Session tokens: {stats.total_tokens}")
    print(f"Duration: {stats.duration_seconds}s")
```

## Background Tasks

SDK hooks have no background task support. fasthooks provides async work that feeds back in subsequent hooks:

```python
from fasthooks.tasks import task, Tasks

@task
def analyze_code(code: str) -> str:
    # Runs in thread pool, non-blocking
    return expensive_analysis(code)

@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    tasks.add(analyze_code, event.content)  # Fire and forget
    return allow()

@app.on_prompt()
def check_analysis(event, tasks: Tasks):
    if result := tasks.pop(analyze_code):  # Check if done
        return allow(message=f"Analysis: {result}")
    return allow()
```

## When to Use Each

### Use SDK Hooks When:

- Building an application that embeds Claude via the SDK
- You need in-process callbacks (no subprocess overhead)
- You're already using `ClaudeSDKClient` for custom tools
- You want hooks and custom MCP tools in the same process

```python
# SDK: Hooks + custom tools in one application
options = ClaudeAgentOptions(
    mcp_servers={"tools": my_sdk_mcp_server},
    hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[my_hook])]},
)

async with ClaudeSDKClient(options=options) as client:
    # Interactive conversation with hooks
    await client.query("...")
```

### Use fasthooks When:

- You're a CLI user customizing Claude Code behavior
- You need persistent state across hook invocations
- You need transcript analysis (token counts, tool usage stats)
- You need background async work (API calls, Claude sub-agents)
- You need SessionStart, SessionEnd, or Notification events
- You're building reusable hook libraries
- You want FastAPI-like DX with dependency injection

```python
# fasthooks: Standalone hook with full features
from fasthooks import HookApp, allow, deny
from fasthooks.depends import State, Transcript
from fasthooks.tasks import Tasks

app = HookApp(state_dir="/tmp/hooks-state")

@app.pre_tool("Bash")
def check(event, state: State, transcript: Transcript, tasks: Tasks):
    # Full access to state, history, and background tasks
    ...

if __name__ == "__main__":
    app.run()
```

## Migration Path

If you're using SDK hooks and want fasthooks features:

**Option 1: Use fasthooks for CLI hooks, SDK for embedded apps**

They serve different use cases and can coexist.

**Option 2: Call fasthooks from SDK hooks**

For complex logic, you could spawn fasthooks as a subprocess from SDK hooks, though this adds overhead.

**Option 3: Use fasthooks' Claude sub-agent integration**

fasthooks can spawn Claude sub-agents via the SDK for AI-powered background tasks:

```python
from fasthooks.contrib.claude import agent_task, ClaudeAgent
from fasthooks.tasks import Tasks

@agent_task(model="haiku", system_prompt="Review code for bugs.")
async def review_code(agent: ClaudeAgent, code: str) -> str:
    return await agent.query(f"Review:\n{code}")

@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    tasks.add(review_code, event.content)
    return allow()
```

## Summary

| Aspect | SDK Hooks | fasthooks |
|--------|-----------|-----------|
| **Philosophy** | Minimal, in-process | Batteries-included framework |
| **Best for** | SDK applications | CLI hook development |
| **DX** | Manual, verbose | FastAPI-like, concise |
| **State** | DIY | Built-in |
| **Events** | 6 types | 9+ types |
| **Ecosystem** | Part of SDK | Standalone library |

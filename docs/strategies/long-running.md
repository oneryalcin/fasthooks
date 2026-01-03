# Long-Running Agent Strategy

The `LongRunningStrategy` implements Anthropic's two-agent pattern for autonomous agents that work across multiple context windows. It prevents the two common failure modes of long-running agents: **one-shotting** (trying to do everything at once) and **premature victory** (declaring done too early).

## The Problem

Long-running autonomous agents face a fundamental challenge: they work in discrete sessions, and each new session starts with no memory of what came before. This leads to:

1. **One-shotting**: Agent attempts to implement entire project at once, runs out of context mid-implementation, leaves broken state
2. **Premature victory**: Agent sees some progress and declares the project complete despite many features remaining

## The Solution: Two-Agent Pattern

The strategy uses different prompts for first vs. subsequent sessions:

| Session | Agent Role | What It Does |
|---------|------------|--------------|
| First | **Initializer** | Creates `feature_list.json`, `init.sh`, git repo |
| Subsequent | **Coding** | Works on ONE feature at a time, commits, updates progress |

```
Session 1 (Initializer)          Sessions 2+ (Coding)
┌─────────────────────┐          ┌─────────────────────┐
│ Create feature_list │          │ Read progress file  │
│ (30+ features)      │          │ Verify existing     │
│                     │          │ Pick ONE feature    │
│ Create init.sh      │          │ Implement & test    │
│ Initialize git      │          │ Mark passes: true   │
│ First commit        │          │ Commit & update     │
└─────────────────────┘          └─────────────────────┘
```

## Quick Start

### 1. Create Your Hooks File

Create `hooks.py` in your project:

```python
from fasthooks import HookApp
from fasthooks.strategies import LongRunningStrategy

app = HookApp()

# Create the strategy with default settings
strategy = LongRunningStrategy()

# Include the strategy's hooks
app.include(strategy.get_blueprint())

if __name__ == "__main__":
    app.run()
```

### 2. Configure Claude Code

Add to your Claude Code settings (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{"type": "command", "command": "python /path/to/hooks.py"}]
      }
    ],
    "Stop": [
      {
        "hooks": [{"type": "command", "command": "python /path/to/hooks.py"}]
      }
    ],
    "PreCompact": [
      {
        "hooks": [{"type": "command", "command": "python /path/to/hooks.py"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [{"type": "command", "command": "python /path/to/hooks.py"}]
      }
    ]
  }
}
```

### 3. Start Claude Code

```bash
cd ~/my-project
claude
```

**First session**: Claude will create `feature_list.json`, `init.sh`, and initialize git.

**Subsequent sessions**: Claude will read progress, verify existing features, and work on one feature at a time.

## Configuration Options

```python
strategy = LongRunningStrategy(
    # File paths (relative to project root)
    feature_list="feature_list.json",    # Feature tracking file
    progress_file="claude-progress.txt", # Session notes
    init_script="init.sh",               # Environment setup script

    # Requirements
    min_features=30,                     # Minimum features to create

    # Enforcement (blocking behavior)
    enforce_commits=True,                # Block stop if uncommitted changes
    require_progress_update=True,        # Block stop if progress not updated
)
```

### Configuration Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `feature_list` | `str` | `"feature_list.json"` | Path to feature tracking file |
| `progress_file` | `str` | `"claude-progress.txt"` | Path to session notes file |
| `init_script` | `str` | `"init.sh"` | Path to environment setup script |
| `min_features` | `int` | `30` | Minimum features agent must create |
| `enforce_commits` | `bool` | `True` | Block stop if uncommitted changes exist |
| `require_progress_update` | `bool` | `True` | Block stop if progress file not updated |

## How It Works

### Hook Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    Session Lifecycle                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SessionStart                                               │
│      │                                                      │
│      ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ on_session_start handler                            │   │
│  │   - Check if feature_list.json exists               │   │
│  │   - If NO: inject INITIALIZER context               │   │
│  │   - If YES: inject CODING context with status       │   │
│  └─────────────────────────────────────────────────────┘   │
│      │                                                      │
│      ▼                                                      │
│  [Claude works on tasks...]                                 │
│      │                                                      │
│      ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ post_tool:Write handler (on each file write)        │   │
│  │   - Track modified files                            │   │
│  │   - Detect progress_file updates                    │   │
│  │   - Warn on feature_list.json structural changes    │   │
│  └─────────────────────────────────────────────────────┘   │
│      │                                                      │
│      ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ post_tool:Bash handler (on each bash command)       │   │
│  │   - Track git commits                               │   │
│  └─────────────────────────────────────────────────────┘   │
│      │                                                      │
│      ▼                                                      │
│  [Context fills up OR user stops...]                        │
│      │                                                      │
│      ├──── PreCompact ────────────────────────────────────┐│
│      │  ┌──────────────────────────────────────────────┐  ││
│      │  │ on_pre_compact handler                       │  ││
│      │  │   - Inject checkpoint reminder               │  ││
│      │  │   - Show current status                      │  ││
│      │  └──────────────────────────────────────────────┘  ││
│      │                                                    ││
│      └──── Stop ──────────────────────────────────────────┘│
│         ┌──────────────────────────────────────────────┐   │
│         │ on_stop handler                              │   │
│         │   - Check uncommitted changes → BLOCK        │   │
│         │   - Check progress updated → BLOCK           │   │
│         │   - If clean → ALLOW                         │   │
│         └──────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Key Artifacts

The strategy manages three critical files:

#### 1. `feature_list.json`

Source of truth for what needs to be built:

```json
[
  {
    "category": "functional",
    "description": "User can create new account",
    "steps": [
      "Navigate to signup page",
      "Fill in email and password",
      "Click submit",
      "Verify account created"
    ],
    "passes": false
  },
  {
    "category": "style",
    "description": "Login button has correct styling",
    "steps": [
      "Navigate to login page",
      "Verify button color is primary",
      "Verify button has hover state"
    ],
    "passes": true
  }
]
```

**Rules:**
- Only the `passes` field can be changed
- Never remove or edit features
- Never modify descriptions or steps

#### 2. `claude-progress.txt`

Session-by-session notes for context recovery:

```
## Session 3 - 2024-01-15

Completed:
- Implemented user signup (feature #1)
- Fixed validation bug in email field

In Progress:
- Working on login flow (feature #2)

Status: 5/30 features passing

Next session should:
- Complete login flow
- Start on password reset
```

#### 3. `init.sh`

Environment setup script:

```bash
#!/bin/bash
# Install dependencies
npm install

# Start development server
npm run dev &

echo "Server running at http://localhost:3000"
```

## Observability

The strategy emits events for debugging and analysis.

### Enabling Observability

```python
from fasthooks import HookApp
from fasthooks.strategies import LongRunningStrategy

app = HookApp()
strategy = LongRunningStrategy()

# Register observer callback
@strategy.on_observe
def log_events(event):
    print(f"[{event.event_type}] {event.hook_name}")
    if hasattr(event, 'decision'):
        print(f"  Decision: {event.decision}")
    if hasattr(event, 'message') and event.message:
        print(f"  Message: {event.message[:100]}...")

app.include(strategy.get_blueprint())
```

### Event Types

| Event Type | When Emitted | Payload |
|------------|--------------|---------|
| `hook_enter` | Handler starts | `hook_name` |
| `hook_exit` | Handler ends | `hook_name`, `duration_ms` |
| `decision` | Handler returns allow/deny/block | `decision`, `reason`, `message` |
| `error` | Handler throws exception | `error_type`, `error_message` |
| `custom` | Strategy emits custom event | `custom_event_type`, `payload` |

### Custom Events

The strategy emits these custom events:

| Event | When | Payload |
|-------|------|---------|
| `session_type` | Session start | `{"type": "initializer" \| "coding" \| "compact_resume"}` |
| `feature_progress` | Session start | `{"passing": 5, "total": 30}` |
| `checkpoint_needed` | Pre-compact | `{"reason": "compaction"}` |

### Logging to File

Use the built-in file backend:

```python
from fasthooks import HookApp
from fasthooks.strategies import LongRunningStrategy
from fasthooks.observability import FileObservabilityBackend, Verbosity

app = HookApp()
strategy = LongRunningStrategy()

# Create file backend
backend = FileObservabilityBackend(
    base_dir="./logs",
    verbosity=Verbosity.STANDARD,
)

# Connect strategy to backend
@strategy.on_observe
def log_to_file(event):
    backend.handle_event(event)

# Flush on session end
import atexit
atexit.register(backend.flush)

app.include(strategy.get_blueprint())
```

Logs are written to `./logs/<session-id>.jsonl` in JSON Lines format.

## Testing the Strategy

### Local Testing with TestClient

```python
from fasthooks import HookApp
from fasthooks.strategies import LongRunningStrategy
from fasthooks.testing import MockEvent, TestClient
import tempfile
import json
from pathlib import Path

# Create temp directory for test
tmpdir = Path(tempfile.mkdtemp())

# Create strategy
strategy = LongRunningStrategy(
    min_features=5,  # Lower for testing
    enforce_commits=False,  # Disable for testing
    require_progress_update=False,
)

# Collect events for verification
events = []
strategy.on_observe(lambda e: events.append(e))

# Create app and client
app = HookApp(state_dir=str(tmpdir))
app.include(strategy.get_blueprint())
client = TestClient(app)

# Test 1: First session (no feature_list.json)
print("Test 1: Initializer mode")
result = client.send(MockEvent.session_start(cwd=str(tmpdir)))
# Check events for initializer context injection
decision_events = [e for e in events if e.event_type == "decision"]
assert any("INITIALIZER" in (e.message or "") for e in decision_events)
print("  ✓ Initializer context injected")

# Test 2: Create feature_list.json and test coding mode
events.clear()
(tmpdir / "feature_list.json").write_text(json.dumps([
    {"description": "Test feature", "passes": False}
]))

print("Test 2: Coding mode")
result = client.send(MockEvent.session_start(cwd=str(tmpdir)))
decision_events = [e for e in events if e.event_type == "decision"]
assert any("0/1 passing" in (e.message or "") for e in decision_events)
print("  ✓ Coding context with status injected")

print("\nAll tests passed!")
```

### Testing with Docker (Full Integration)

If you have a Docker environment with Claude Code:

1. Copy your hooks.py to the Docker environment
2. Configure settings.json with hook commands
3. Run Claude Code in the container
4. Tail the logs:

```bash
# In one terminal
docker compose run --rm claude claude

# In another terminal
tail -f hooks/logs/latest.jsonl | jq .
```

## Troubleshooting

### "Cannot stop - uncommitted changes"

The strategy is blocking stop because you have uncommitted git changes.

**Fix:**
```bash
git add .
git commit -m "Your message"
```

**Or disable enforcement:**
```python
strategy = LongRunningStrategy(enforce_commits=False)
```

### "Cannot stop - please update progress file"

The strategy requires updating the progress file before stopping.

**Fix:** Write to `claude-progress.txt` with your session summary.

**Or disable enforcement:**
```python
strategy = LongRunningStrategy(require_progress_update=False)
```

### Initializer runs every session

The strategy checks for `feature_list.json` existence. If it keeps running initializer:

1. Check that `feature_list.json` exists in the project root
2. Check the file path matches your configuration
3. Check the file is valid JSON

### Context not injected

If hooks aren't being called:

1. Verify settings.json is in the right location
2. Check the command path is correct and executable
3. Run the hook manually to test:
   ```bash
   echo '{"hook_event_name":"SessionStart","session_id":"test","cwd":"/tmp"}' | python hooks.py
   ```

## Example: Complete Setup

Here's a complete example with all features:

```python
#!/usr/bin/env python3
"""
Long-running agent hooks for my-project.
Place in: ~/my-project/hooks.py
"""
import os
from pathlib import Path

from fasthooks import HookApp
from fasthooks.strategies import LongRunningStrategy
from fasthooks.observability import FileObservabilityBackend, Verbosity

# Get project directory
PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

# Initialize app with state persistence
app = HookApp(
    state_dir=str(PROJECT_DIR / ".claude-state"),
    log_dir=str(PROJECT_DIR / ".claude-logs"),
)

# Create strategy with custom settings
strategy = LongRunningStrategy(
    feature_list="features.json",
    progress_file="PROGRESS.md",
    init_script="scripts/dev-setup.sh",
    min_features=50,
    enforce_commits=True,
    require_progress_update=True,
)

# Set up observability
log_backend = FileObservabilityBackend(
    base_dir=PROJECT_DIR / ".claude-logs" / "strategy",
    verbosity=Verbosity.STANDARD,
)

@strategy.on_observe
def handle_event(event):
    # Log to file
    log_backend.handle_event(event)

    # Also print important events to stderr for debugging
    if event.event_type == "decision":
        import sys
        print(f"[long-running] {event.decision}: {event.hook_name}", file=sys.stderr)

# Register flush on exit
import atexit
atexit.register(log_backend.flush)

# Include strategy
app.include(strategy.get_blueprint())

if __name__ == "__main__":
    app.run()
```

## Reference

### API

```python
class LongRunningStrategy(Strategy):
    """Harness for long-running autonomous agents."""

    def __init__(
        self,
        *,
        feature_list: str = "feature_list.json",
        progress_file: str = "claude-progress.txt",
        init_script: str = "init.sh",
        min_features: int = 30,
        enforce_commits: bool = True,
        require_progress_update: bool = True,
    ): ...

    def get_blueprint(self) -> Blueprint:
        """Return configured Blueprint with hooks."""
        ...

    def on_observe(self, callback: Callable[[ObservabilityEvent], None]):
        """Register observer callback."""
        ...

    def get_meta(self) -> StrategyMeta:
        """Return strategy metadata."""
        ...
```

### Hooks Registered

| Hook | Event | Purpose |
|------|-------|---------|
| `on_session_start` | `SessionStart` | Inject initializer or coding context |
| `on_stop` | `Stop` | Enforce clean state before stopping |
| `on_pre_compact` | `PreCompact` | Inject checkpoint reminder |
| `post_tool("Write")` | `PostToolUse` | Track file modifications |
| `post_tool("Bash")` | `PostToolUse` | Track git commits |

## Further Reading

- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [fasthooks Architecture](../architecture.md)

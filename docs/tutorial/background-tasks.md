# Background Tasks

Background tasks let you spawn async work that runs independently and feeds back results in subsequent hook calls. This is perfect for:

- Long-running computations (code analysis, linting)
- API calls that shouldn't block the hook
- Claude sub-agents for AI-powered analysis
- Memory lookup across sessions

## Quick Start

```python
from fasthooks import HookApp, allow
from fasthooks.tasks import task, Tasks

# Define a task
@task
def analyze_code(code: str) -> str:
    # This runs in a thread pool
    import time
    time.sleep(2)  # Simulate long operation
    return f"Analysis complete: {len(code)} chars"

app = HookApp()

# Spawn task when code is written
@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    tasks.add(analyze_code, event.content)
    return allow()

# Check for results on next prompt (same dependency)
@app.on_prompt()
def check_results(event, tasks: Tasks):
    if result := tasks.pop(analyze_code):
        return allow(message=f"Previous analysis: {result}")
    return allow()
```

## How It Works

All task operations are **non-blocking**:

| Method | Behavior |
|--------|----------|
| `tasks.add()` | Submits to thread pool, returns immediately |
| `tasks.pop()` | Dict lookup, returns result or `None` instantly |
| `tasks.get()` | Dict lookup, returns `TaskResult` or `None` instantly |
| `tasks.has()` | Dict lookup, returns `bool` instantly |
| `await tasks.wait()` | Async polling, yields while waiting |

The pattern is fire-and-forget:

```
Hook 1: tasks.add(my_task, args)  →  queues work  →  returns instantly
        ↓
        ThreadPoolExecutor runs task in background
        ↓
Hook 2: tasks.pop(my_task)  →  checks dict  →  returns result (or None if still running)
```

This design ensures hooks never block on IO-bound work like API calls or database queries.

## Core Concepts

### Task Definition

Use `@task` to define a background task:

```python
from fasthooks.tasks import task

@task
def simple_task(x: int) -> int:
    return x * 2

# With options
@task(ttl=600, priority=5)
def important_task(query: str) -> str:
    return search_db(query)

# With result transformation
@task(transform=lambda r: r[:500])
def long_output_task() -> str:
    return very_long_string()
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `ttl` | 300 | Time-to-live in seconds for the result |
| `priority` | 0 | Higher priority tasks may be scheduled first |
| `transform` | None | Function to transform the result |

### Tasks (recommended)

Inject `Tasks` to spawn tasks and retrieve results:

```python
from fasthooks.tasks import Tasks

@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    # Add a task (default key = function name)
    tasks.add(my_task, arg1, arg2)

    # Add with custom TTL
    tasks.add(other_task, data, ttl=600)

    return allow()
```

For multiple concurrent calls to the same function, provide an explicit `key`:

```python
tasks.add(fetch, "https://example.com/a", key="fetch:a")
tasks.add(fetch, "https://example.com/b", key="fetch:b")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `add(func, *args, key=None, ttl=300, **kwargs)` | Enqueue a task |
| `cancel(key)` | Cancel a pending/running task |
| `cancel_all()` | Cancel all tasks for this session |
| `get(key)` | Get TaskResult without removing |
| `pop(key)` | Pop completed result value |
| `pop_all()` | Pop all completed results |
| `pop_errors()` | Pop failed tasks as `[(key, exception), ...]` |
| `has(key=None)` | Check if results are ready |

`BackgroundTasks` and `PendingResults` are still available for a split enqueue/results model, but `Tasks` is the recommended DX.

### Async Waiting

For handlers that need to wait for results:

```python
@app.on_stop()
async def wait_for_results(event, tasks: Tasks):
    # Wait for specific task (with timeout)
    result = await tasks.wait("analysis", timeout=10.0)

    # Wait for multiple tasks
    results = await tasks.wait_all(["task1", "task2"], timeout=30.0)

    # Wait for any task to complete
    completed = await tasks.wait_any(["task1", "task2"])
    if completed:
        key, result = completed

    return allow()
```

## Claude Sub-Agents

Use the Claude Agent SDK for AI-powered background tasks:

```bash
pip install fasthooks[claude]
```

### ClaudeAgent

Simple wrapper for querying Claude:

```python
from fasthooks.contrib.claude import ClaudeAgent

agent = ClaudeAgent(
    model="haiku",              # haiku, sonnet, opus
    system_prompt="You are helpful.",
    allowed_tools=["Read", "Grep"],
    max_turns=5,
    max_budget_usd=0.10,
)

# Simple query
response = await agent.query("What is 2+2?")

# Override options per-query
response = await agent.query(
    "Analyze this code",
    system_prompt="You are a code reviewer.",
    max_turns=3,
)
```

### @agent_task Decorator

Create background tasks that use Claude:

```python
from fasthooks.contrib.claude import ClaudeAgent, agent_task
from fasthooks.tasks import Tasks

@agent_task(model="haiku", system_prompt="You review code for security issues.")
async def security_review(agent: ClaudeAgent, code: str) -> str:
    return await agent.query(f"Review for security:\n{code}")

@agent_task(model="sonnet", allowed_tools=["Read", "Grep"])
async def codebase_search(agent: ClaudeAgent, query: str) -> str:
    return await agent.query(f"Search the codebase for: {query}")

@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    tasks.add(security_review, event.content)
    return allow()
```

The agent is automatically injected as the first argument.

## Use Cases

### Code Review Agent

```python
from fasthooks.contrib.claude import ClaudeAgent, agent_task

@agent_task(
    model="sonnet",
    system_prompt="""You are a code reviewer. Check for:
    - Security vulnerabilities
    - Performance issues
    - Code style problems
    Respond with a brief summary."""
)
async def review_code(agent: ClaudeAgent, code: str, file_path: str) -> str:
    return await agent.query(f"Review {file_path}:\n```\n{code}\n```")

@app.pre_tool("Write")
def on_write(event, tasks: Tasks):
    if event.file_path.endswith(".py"):
        tasks.add(review_code, event.content, event.file_path)
    return allow()

@app.on_prompt()
def show_review(event, tasks: Tasks):
    if review := tasks.pop(review_code):
        return allow(message=f"Code review:\n{review}")
    return allow()
```

### Memory/Context Lookup

```python
@task
def search_memory(query: str, session_id: str) -> str:
    # Search vector DB, knowledge base, etc.
    results = vector_db.search(query, filter={"session": session_id})
    return "\n".join(r.text for r in results[:3])

@app.on_prompt()
def enrich_prompt(event, tasks: Tasks):
    # Check for previous search results
    if context := tasks.pop(search_memory):
        return allow(message=f"Relevant context:\n{context}")

    # Start new search based on prompt
    tasks.add(search_memory, event.prompt, event.session_id)
    return allow()
```

### Rate-Limited API Calls

```python
import httpx

@task(ttl=600)  # Cache for 10 minutes
def fetch_documentation(url: str) -> str:
    response = httpx.get(url)
    return response.text[:5000]

@app.pre_tool("WebFetch")
def prefetch_docs(event, tasks: Tasks):
    # Start fetching in background
    tasks.add(fetch_documentation, event.url, key=f"doc:{event.url}")
    return allow()
```

## Testing

Use `ImmediateBackend` for synchronous testing:

```python
from fasthooks.tasks import task, Tasks
from fasthooks.tasks.testing import ImmediateBackend

@task
def double(x: int) -> int:
    return x * 2

def test_background_task():
    backend = ImmediateBackend()

    tasks = Tasks(backend, session_id="test")
    tasks.add(double, 5)
    assert tasks.pop(double) == 10
```

## Error Handling

Tasks that fail store their exceptions:

```python
@task
def risky_task() -> str:
    raise ValueError("Something went wrong")

@app.on_prompt()
def check_errors(event, tasks: Tasks):
    # Pop all failed tasks
    for key, error in tasks.pop_errors():
        print(f"Task {key} failed: {error}")
    return allow()
```

## Task Status

Check detailed task status via `TaskResult`:

```python
from fasthooks.tasks import TaskStatus

@app.on_prompt()
def check_status(event, tasks: Tasks):
    result = tasks.get("my-task")
    if result:
        if result.status == TaskStatus.COMPLETED:
            print(f"Done: {result.value}")
        elif result.status == TaskStatus.RUNNING:
            print("Still running...")
        elif result.status == TaskStatus.FAILED:
            print(f"Error: {result.error}")
    return allow()
```

**Status values:**

| Status | Description |
|--------|-------------|
| `PENDING` | Queued, not started |
| `RUNNING` | Currently executing |
| `COMPLETED` | Finished successfully |
| `FAILED` | Exception raised |
| `CANCELLED` | Cancelled by user |

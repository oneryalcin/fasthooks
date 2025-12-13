# Claude Agent SDK Integration

Integration with Claude Agent SDK for AI-powered background tasks.

!!! note "Optional Dependency"
    Requires `pip install fasthooks[claude]`

## ClaudeAgent

::: fasthooks.contrib.claude.agent.ClaudeAgent
    options:
      members:
        - model
        - system_prompt
        - allowed_tools
        - max_turns
        - max_budget_usd
        - cwd
        - query
        - __aenter__
        - __aexit__

## agent_task Decorator

::: fasthooks.contrib.claude.agent.agent_task
    options:
      show_root_heading: true

## Type Aliases

```python
# Model type hint
Model = Literal["sonnet", "opus", "haiku"]
```

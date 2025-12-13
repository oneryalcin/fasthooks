# Events

Event types for tools and lifecycle hooks.

## Base Event

::: fasthooks.events.base.BaseEvent
    options:
      members:
        - session_id
        - cwd
        - permission_mode
        - transcript_path
        - hook_event_name

## Tool Events

::: fasthooks.events.tools.ToolEvent
    options:
      members:
        - tool_name
        - tool_input
        - tool_use_id
        - tool_response

::: fasthooks.events.tools.Bash
    options:
      members:
        - command
        - description
        - timeout

::: fasthooks.events.tools.Write
    options:
      members:
        - file_path
        - content

::: fasthooks.events.tools.Edit
    options:
      members:
        - file_path
        - old_string
        - new_string

::: fasthooks.events.tools.Read
    options:
      members:
        - file_path
        - offset
        - limit

::: fasthooks.events.tools.Grep
    options:
      members:
        - pattern
        - path

::: fasthooks.events.tools.Glob
    options:
      members:
        - pattern
        - path

::: fasthooks.events.tools.Task
    options:
      members:
        - prompt
        - description

::: fasthooks.events.tools.WebSearch
    options:
      members:
        - query

::: fasthooks.events.tools.WebFetch
    options:
      members:
        - url
        - prompt

## Lifecycle Events

::: fasthooks.events.lifecycle.Stop
    options:
      members:
        - stop_hook_active

::: fasthooks.events.lifecycle.SubagentStop
    options:
      members:
        - stop_hook_active

::: fasthooks.events.lifecycle.SessionStart
    options:
      members:
        - source

::: fasthooks.events.lifecycle.SessionEnd
    options:
      members:
        - reason

::: fasthooks.events.lifecycle.PreCompact
    options:
      members:
        - trigger
        - custom_instructions

::: fasthooks.events.lifecycle.UserPromptSubmit
    options:
      members:
        - prompt

::: fasthooks.events.lifecycle.Notification
    options:
      members:
        - message
        - notification_type

# HookApp

The main application class for registering and running hook handlers.

::: fasthooks.app.HookApp
    options:
      members:
        - __init__
        - run
        - include
        - pre_tool
        - post_tool
        - on_permission
        - on_stop
        - on_subagent_stop
        - on_session_start
        - on_session_end
        - on_notification
        - on_pre_compact
        - on_prompt
        - middleware

## Blueprint

Composable handler groups for organizing hooks.

::: fasthooks.blueprint.Blueprint
    options:
      members:
        - __init__
        - pre_tool
        - post_tool
        - on_permission
        - on_stop
        - on_subagent_stop
        - on_session_start
        - on_session_end
        - on_notification
        - on_pre_compact
        - on_prompt

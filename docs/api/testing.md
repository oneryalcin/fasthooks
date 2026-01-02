# Testing Utilities

Utilities for testing hook handlers.

## MockEvent

Factory for creating test events.

::: fasthooks.testing.mocks.MockEvent
    options:
      members:
        - bash
        - write
        - edit
        - read
        - grep
        - glob
        - task
        - web_search
        - web_fetch
        - stop
        - subagent_stop
        - session_start
        - session_end
        - pre_compact
        - user_prompt_submit
        - notification
        - permission_request

## TestClient

Client for testing hook applications.

::: fasthooks.testing.client.TestClient
    options:
      members:
        - __init__
        - send

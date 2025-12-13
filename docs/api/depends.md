# Dependencies

Injectable dependencies for hook handlers.

## Transcript

Access to the conversation history and statistics.

::: fasthooks.depends.transcript.Transcript
    options:
      members:
        - __init__
        - stats
        - messages
        - last_assistant_message
        - bash_commands

::: fasthooks.depends.transcript.TranscriptStats
    options:
      members:
        - input_tokens
        - output_tokens
        - cache_read_tokens
        - cache_creation_tokens
        - total_tokens
        - tool_calls
        - files_read_count
        - files_written_count
        - duration_seconds
        - compact_count
        - message_counts
        - slug

## State

Persistent session-scoped storage.

::: fasthooks.depends.state.State
    options:
      members:
        - for_session
        - save
        - __getitem__
        - __setitem__
        - get

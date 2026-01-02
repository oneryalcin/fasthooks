# Background Tasks

Background task system for async operations in hooks.

## Task Definition

::: fasthooks.tasks.base.task
    options:
      show_root_heading: true

::: fasthooks.tasks.base.Task
    options:
      members:
        - func
        - priority
        - ttl
        - transform
        - name
        - __call__

::: fasthooks.tasks.base.TaskResult
    options:
      members:
        - id
        - session_id
        - key
        - status
        - value
        - error
        - created_at
        - started_at
        - finished_at
        - ttl
        - is_finished
        - is_expired

::: fasthooks.tasks.base.TaskStatus
    options:
      members:
        - PENDING
        - RUNNING
        - COMPLETED
        - FAILED
        - CANCELLED

## Dependencies

::: fasthooks.tasks.depends.Tasks
    options:
      members:
        - __init__
        - add
        - cancel
        - cancel_all
        - get
        - pop
        - pop_all
        - pop_errors
        - has
        - wait
        - wait_all
        - wait_any

::: fasthooks.tasks.depends.BackgroundTasks
    options:
      members:
        - __init__
        - add
        - cancel
        - cancel_all

::: fasthooks.tasks.depends.PendingResults
    options:
      members:
        - __init__
        - get
        - pop
        - pop_all
        - pop_errors
        - has
        - wait
        - wait_all
        - wait_any

## Backends

::: fasthooks.tasks.backend.BaseBackend
    options:
      members:
        - enqueue
        - get
        - pop
        - pop_all
        - cancel
        - cancel_all
        - pop_errors
        - has
        - wait
        - wait_all
        - wait_any

::: fasthooks.tasks.backend.InMemoryBackend
    options:
      members:
        - __init__
        - enqueue
        - get
        - pop
        - pop_all
        - shutdown

## Testing

::: fasthooks.tasks.testing.ImmediateBackend
    options:
      show_root_heading: true

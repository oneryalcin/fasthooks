"""Tests for EventLogger."""
import json
import tempfile
from pathlib import Path

from fasthooks.logging import EventLogger


class TestEventLoggerInit:
    """Tests for EventLogger initialization."""

    def test_creates_log_dir(self):
        """EventLogger creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs" / "nested"
            assert not log_dir.exists()

            EventLogger(log_dir)
            assert log_dir.exists()

    def test_accepts_string_path(self):
        """EventLogger accepts string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            assert logger.log_dir == Path(tmpdir)


class TestEventLoggerLog:
    """Tests for log() method."""

    def test_writes_jsonl_file(self):
        """log() writes event to JSONL file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            logger.log({
                "session_id": "test-123",
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "cwd": "/workspace",
                "permission_mode": "default",
            })

            log_file = Path(tmpdir) / "hooks-test-123.jsonl"
            assert log_file.exists()

            with open(log_file) as f:
                entry = json.loads(f.read().strip())

            assert entry["session_id"] == "test-123"
            assert entry["event"] == "PreToolUse"
            assert entry["tool_name"] == "Bash"
            assert entry["bash_command"] == "ls"

    def test_creates_latest_symlink(self):
        """log() creates latest.jsonl symlink."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            logger.log({
                "session_id": "test-456",
                "hook_event_name": "Stop",
            })

            latest = Path(tmpdir) / "latest.jsonl"
            assert latest.is_symlink()
            assert latest.resolve().name == "hooks-test-456.jsonl"

    def test_appends_to_existing_file(self):
        """log() appends to existing session file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            logger.log({"session_id": "s1", "hook_event_name": "Stop"})
            logger.log({"session_id": "s1", "hook_event_name": "Stop"})

            log_file = Path(tmpdir) / "hooks-s1.jsonl"
            with open(log_file) as f:
                lines = f.readlines()

            assert len(lines) == 2

    def test_unknown_session_id(self):
        """log() handles missing session_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            logger.log({"hook_event_name": "Stop"})

            log_file = Path(tmpdir) / "hooks-unknown.jsonl"
            assert log_file.exists()


class TestBuildEntryTools:
    """Tests for _build_entry() with tool events."""

    def test_bash_tool(self):
        """Bash tool flattens command and description."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "npm install",
                    "description": "Install deps",
                },
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["bash_command"] == "npm install"
            assert entry["bash_description"] == "Install deps"

    def test_write_tool(self):
        """Write tool flattens file_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": "/test.txt"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["file_path"] == "/test.txt"

    def test_edit_tool(self):
        """Edit tool flattens file_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": "/test.txt"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["file_path"] == "/test.txt"

    def test_read_tool(self):
        """Read tool flattens file_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Read",
                "tool_input": {"file_path": "/test.txt"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["file_path"] == "/test.txt"

    def test_grep_tool(self):
        """Grep tool flattens pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Grep",
                "tool_input": {"pattern": "TODO"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["grep_pattern"] == "TODO"

    def test_glob_tool(self):
        """Glob tool flattens pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Glob",
                "tool_input": {"pattern": "**/*.py"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["glob_pattern"] == "**/*.py"

    def test_task_tool(self):
        """Task tool flattens subagent fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "Task",
                "tool_input": {
                    "subagent_type": "Explore",
                    "model": "sonnet",
                },
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["subagent_type"] == "Explore"
            assert entry["subagent_model"] == "sonnet"

    def test_websearch_tool(self):
        """WebSearch tool flattens query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "WebSearch",
                "tool_input": {"query": "python async"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["search_query"] == "python async"

    def test_webfetch_tool(self):
        """WebFetch tool flattens url."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreToolUse",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://example.com"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["fetch_url"] == "https://example.com"

    def test_post_tool_use_with_response(self):
        """PostToolUse includes tool_response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "tool_response": {"stdout": "file.txt"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["tool_response"] == {"stdout": "file.txt"}

    def test_task_post_tool_extracts_agent_id(self):
        """Task PostToolUse extracts agentId."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PostToolUse",
                "tool_name": "Task",
                "tool_input": {"subagent_type": "Explore"},
                "tool_response": {"agentId": "agent-123"},
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["agent_id"] == "agent-123"


class TestBuildEntryLifecycle:
    """Tests for _build_entry() with lifecycle events."""

    def test_user_prompt_submit(self):
        """UserPromptSubmit includes prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "UserPromptSubmit",
                "prompt": "Write tests",
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["prompt"] == "Write tests"

    def test_stop(self):
        """Stop includes stop_hook_active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "Stop",
                "stop_hook_active": True,
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["stop_hook_active"] is True

    def test_subagent_stop(self):
        """SubagentStop includes agent_id and stop_hook_active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "SubagentStop",
                "agent_id": "agent-456",
                "stop_hook_active": False,
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["agent_id"] == "agent-456"
            assert entry["stop_hook_active"] is False

    def test_session_start(self):
        """SessionStart includes source and transcript_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "SessionStart",
                "source": "startup",
                "transcript_path": "/path/to/transcript.jsonl",
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["source"] == "startup"
            assert entry["transcript_path"] == "/path/to/transcript.jsonl"

    def test_session_end(self):
        """SessionEnd includes reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "SessionEnd",
                "reason": "logout",
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["reason"] == "logout"

    def test_pre_compact(self):
        """PreCompact includes trigger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "PreCompact",
                "trigger": "manual",
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["trigger"] == "manual"

    def test_notification(self):
        """Notification includes message and notification_type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "Notification",
                "message": "Permission needed",
                "notification_type": "permission_prompt",
                "session_id": "s1",
            }, "2024-01-01T00:00:00Z")

            assert entry["message"] == "Permission needed"
            assert entry["notification_type"] == "permission_prompt"


class TestBuildEntryFiltering:
    """Tests for None value filtering."""

    def test_removes_none_values(self):
        """_build_entry removes None values from result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)
            entry = logger._build_entry({
                "hook_event_name": "Stop",
                "session_id": "s1",
                # cwd, permission_mode not provided - should not appear
            }, "2024-01-01T00:00:00Z")

            assert "cwd" not in entry
            assert "permission_mode" not in entry


class TestUpdateSymlink:
    """Tests for _update_symlink()."""

    def test_updates_existing_symlink(self):
        """_update_symlink updates existing symlink to new session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = EventLogger(tmpdir)

            # First session
            logger.log({"session_id": "s1", "hook_event_name": "Stop"})
            latest = Path(tmpdir) / "latest.jsonl"
            assert latest.resolve().name == "hooks-s1.jsonl"

            # Second session
            logger.log({"session_id": "s2", "hook_event_name": "Stop"})
            assert latest.resolve().name == "hooks-s2.jsonl"

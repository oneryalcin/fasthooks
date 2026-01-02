"""Core Transcript class for loading and querying transcript data."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fasthooks.transcript.blocks import ToolResultBlock, ToolUseBlock
from fasthooks.transcript.entries import (
    AssistantMessage,
    CompactBoundary,
    Entry,
    FileHistorySnapshot,
    SystemEntry,
    TranscriptEntry,
    UserMessage,
    parse_entry,
)

if TYPE_CHECKING:
    from fasthooks.transcript.turn import Turn


class Transcript:
    """
    Mutable collection of entries backed by a JSONL file.

    Usage:
        # Standalone
        transcript = Transcript("/path/to/transcript.jsonl")
        transcript.load()

        # Query
        for msg in transcript.user_messages:
            print(msg.text)
    """

    def __init__(
        self,
        path: str | Path,
        validate: Literal["strict", "warn", "none"] = "warn",
        safety: Literal["strict", "warn", "none"] = "warn",
    ):
        self.path = Path(path)
        self.validate = validate
        self.safety = safety

        # All entries in order
        self.entries: list[TranscriptEntry] = []

        # Pre-compact entries (archived)
        self._archived: list[TranscriptEntry] = []

        # Indexes for fast lookups
        self._tool_use_index: dict[str, ToolUseBlock] = {}
        self._tool_result_index: dict[str, ToolResultBlock] = {}
        self._uuid_index: dict[str, Entry] = {}
        self._request_id_index: dict[str, list[AssistantMessage]] = {}
        self._snapshot_index: dict[str, FileHistorySnapshot] = {}

        # Track if loaded
        self._loaded = False

        # Default filtering options
        self.include_archived: bool = False
        self.include_meta: bool = False

    def load(self) -> None:
        """Load entries from JSONL file."""
        if not self.path.exists():
            self._loaded = True
            return

        self.entries = []
        self._archived = []
        self._tool_use_index = {}
        self._tool_result_index = {}
        self._uuid_index = {}
        self._request_id_index = {}
        self._snapshot_index = {}

        # Find last compact boundary to split archived vs current
        raw_entries: list[dict[str, Any]] = []
        last_compact_idx = -1

        with open(self.path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    data["_line_number"] = line_num
                    raw_entries.append(data)

                    if data.get("subtype") == "compact_boundary":
                        last_compact_idx = len(raw_entries) - 1
                except json.JSONDecodeError:
                    if self.validate == "strict":
                        raise
                    continue

        # Parse entries and split archived vs current
        for i, data in enumerate(raw_entries):
            entry = parse_entry(data, self)

            # Set line number
            if hasattr(entry, "_line_number"):
                object.__setattr__(entry, "_line_number", data.get("_line_number"))

            if i <= last_compact_idx:
                self._archived.append(entry)
            else:
                self.entries.append(entry)

            # Build indexes
            self._index_entry(entry)

        self._loaded = True

    def _index_entry(self, entry: TranscriptEntry) -> None:
        """Add entry to lookup indexes."""
        # UUID index (only for Entry subclasses)
        if isinstance(entry, Entry) and entry.uuid:
            self._uuid_index[entry.uuid] = entry

        # Tool use/result indexes + request_id index
        if isinstance(entry, AssistantMessage):
            for block in entry.content:
                if isinstance(block, ToolUseBlock):
                    self._tool_use_index[block.id] = block
                    block.set_transcript(self)
            # Index by request_id for turn grouping
            if entry.request_id:
                if entry.request_id not in self._request_id_index:
                    self._request_id_index[entry.request_id] = []
                self._request_id_index[entry.request_id].append(entry)
        elif isinstance(entry, UserMessage) and entry.is_tool_result:
            for block in entry.tool_results:
                self._tool_result_index[block.tool_use_id] = block
                block.set_transcript(self)
        elif isinstance(entry, FileHistorySnapshot):
            # Index snapshots by message_id
            if entry.message_id:
                self._snapshot_index[entry.message_id] = entry

    # === Relationship Lookups ===

    def find_tool_use(self, tool_use_id: str) -> ToolUseBlock | None:
        """Find ToolUseBlock by id."""
        return self._tool_use_index.get(tool_use_id)

    def find_tool_result(self, tool_use_id: str) -> ToolResultBlock | None:
        """Find ToolResultBlock by tool_use_id."""
        return self._tool_result_index.get(tool_use_id)

    def find_by_uuid(self, uuid: str) -> Entry | None:
        """Find entry by UUID (searches both current and archived)."""
        return self._uuid_index.get(uuid)

    def find_snapshot(self, message_id: str) -> FileHistorySnapshot | None:
        """Find file history snapshot by message_id."""
        return self._snapshot_index.get(message_id)

    def get_parent(self, entry: Entry) -> Entry | None:
        """Get parent entry via parent_uuid (searches both current and archived)."""
        if entry.parent_uuid:
            return self.find_by_uuid(entry.parent_uuid)
        return None

    def get_logical_parent(self, entry: Entry) -> Entry | None:
        """Get logical parent, handling compact boundaries.

        For CompactBoundary entries, returns the entry referenced by
        logicalParentUuid (which preserves chain across compaction).
        For other entries, returns the regular parent.
        """
        if isinstance(entry, CompactBoundary) and entry.logical_parent_uuid:
            return self.find_by_uuid(entry.logical_parent_uuid)
        return self.get_parent(entry)

    def get_children(
        self, entry: Entry, include_archived: bool | None = None
    ) -> list[Entry]:
        """Get all entries with this entry as parent.

        Args:
            entry: Entry to find children for
            include_archived: Search archived entries too. Defaults to self.include_archived.
        """
        if include_archived is None:
            include_archived = self.include_archived

        source = self._archived + self.entries if include_archived else self.entries
        return [
            e for e in source if isinstance(e, Entry) and e.parent_uuid == entry.uuid
        ]

    def get_entries_by_request_id(self, request_id: str) -> list[AssistantMessage]:
        """Get all assistant messages with the same request_id (a single turn)."""
        return self._request_id_index.get(request_id, [])

    # === Pre-built Views ===

    def _get_source(self, include_archived: bool | None = None) -> list[TranscriptEntry]:
        """Get entry source based on include_archived setting."""
        if include_archived is None:
            include_archived = self.include_archived
        return self._archived + self.entries if include_archived else self.entries

    def _filter_meta(self, entry: Entry) -> bool:
        """Check if entry should be included based on meta/visibility settings."""
        if self.include_meta:
            return True
        # Filter out meta entries unless include_meta is True
        if isinstance(entry, UserMessage):
            if entry.is_meta or entry.is_visible_in_transcript_only:
                return False
        return True

    @property
    def archived(self) -> list[TranscriptEntry]:
        """Entries before last compact boundary."""
        return self._archived

    def get_user_messages(
        self, include_archived: bool | None = None
    ) -> list[UserMessage]:
        """All user messages.

        Args:
            include_archived: Include archived entries. Defaults to self.include_archived.
        """
        return [
            e
            for e in self._get_source(include_archived)
            if isinstance(e, UserMessage) and self._filter_meta(e)
        ]

    @property
    def user_messages(self) -> list[UserMessage]:
        """All user messages (uses default include_archived setting)."""
        return self.get_user_messages()

    def get_assistant_messages(
        self, include_archived: bool | None = None
    ) -> list[AssistantMessage]:
        """All assistant messages.

        Args:
            include_archived: Include archived entries. Defaults to self.include_archived.
        """
        return [
            e
            for e in self._get_source(include_archived)
            if isinstance(e, AssistantMessage)
        ]

    @property
    def assistant_messages(self) -> list[AssistantMessage]:
        """All assistant messages (uses default include_archived setting)."""
        return self.get_assistant_messages()

    def get_system_entries(
        self, include_archived: bool | None = None
    ) -> list[SystemEntry]:
        """All system entries.

        Args:
            include_archived: Include archived entries. Defaults to self.include_archived.
        """
        return [
            e for e in self._get_source(include_archived) if isinstance(e, SystemEntry)
        ]

    @property
    def system_entries(self) -> list[SystemEntry]:
        """All system entries (uses default include_archived setting)."""
        return self.get_system_entries()

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        """All tool use blocks across all messages."""
        return list(self._tool_use_index.values())

    @property
    def tool_results(self) -> list[ToolResultBlock]:
        """All tool result blocks."""
        return list(self._tool_result_index.values())

    @property
    def errors(self) -> list[ToolResultBlock]:
        """Tool results where is_error=True."""
        return [r for r in self.tool_results if r.is_error]

    @property
    def compact_boundaries(self) -> list[CompactBoundary]:
        """All compaction markers (always includes archived)."""
        all_entries = self._archived + self.entries
        return [e for e in all_entries if isinstance(e, CompactBoundary)]

    def get_file_snapshots(
        self, include_archived: bool | None = None
    ) -> list[FileHistorySnapshot]:
        """All file history snapshots.

        Args:
            include_archived: Include archived entries. Defaults to self.include_archived.
        """
        return [
            e
            for e in self._get_source(include_archived)
            if isinstance(e, FileHistorySnapshot)
        ]

    @property
    def file_snapshots(self) -> list[FileHistorySnapshot]:
        """All file history snapshots (uses default include_archived setting)."""
        return self.get_file_snapshots()

    @property
    def turns(self) -> list[Turn]:
        """Group assistant messages by requestId into Turns."""
        from fasthooks.transcript.turn import Turn

        result = []
        seen: set[str] = set()
        for entry in self._get_source():
            if isinstance(entry, AssistantMessage) and entry.request_id:
                if entry.request_id not in seen:
                    seen.add(entry.request_id)
                    entries = self._request_id_index.get(entry.request_id, [])
                    if entries:
                        result.append(Turn(request_id=entry.request_id, entries=entries))
        return result

    # === Iteration ===

    def __iter__(self) -> Iterator[TranscriptEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return f"Transcript({self.path}, entries={len(self.entries)}, archived={len(self._archived)})"  # noqa: E501

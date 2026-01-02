# Comparisons

How does fasthooks compare to other approaches for building Claude Code hooks?

## Hook Libraries & Frameworks

| Library | Approach | Best For |
|---------|----------|----------|
| [Claude Agent SDK](claude-agent-sdk.md) | In-process callbacks | SDK-based applications |
| [claude-mem](claude-mem.md) | Memory plugin (observer) | Persistent AI memory |
| [Continuous-Claude-v2](continuous-claude.md) | Session continuity | Long-running projects |
| Raw JSON Protocol | Manual stdin/stdout | One-off scripts |
| fasthooks | Subprocess framework | CLI hook development |

## Quick Summary

**fasthooks** is a batteries-included framework for building Claude Code hooks with:

- Typed events with property accessors
- Response helpers (`allow()`, `deny()`, `block()`)
- Dependency injection (`State`, `Transcript`, `Tasks`)
- Background tasks for async work
- Blueprints and middleware for modularity
- Testing utilities

**Claude Agent SDK hooks** are lightweight in-process callbacks for applications that embed Claude via the SDK. They're minimal by design - no state management, no transcript parsing, no DX conveniences.

**claude-mem** is a complete memory plugin that uses hooks internally to observe tool usage. It cannot block or deny - it's an observer, not an enforcer. Great for persistent memory, not for building custom hook logic.

**Continuous-Claude-v2** is a session continuity system using hooks to preserve context across `/clear` and compaction. Features ledgers, handoffs, TypeScript preflight, and skill auto-activation. Can block on PreToolUse only.

**Raw JSON protocol** is what all approaches build on. Use it directly only for simple one-off scripts.

## Detailed Comparisons

- [Claude Agent SDK Hooks](claude-agent-sdk.md) - In-depth comparison of SDK hooks vs fasthooks
- [claude-mem](claude-mem.md) - Memory plugin vs hook framework
- [Continuous-Claude-v2](continuous-claude.md) - Session continuity system vs hook framework

# MCP Server Troubleshooting

Common problems when using the INXR2 MCP server from an AI assistant, and how to
diagnose them.

## `-32602 Invalid request parameters` on every call

**Symptom:** Tool calls that were working start failing with:

```
MCP error -32602: Invalid request parameters
```

The giveaway is that it happens on **every** tool — including `list_repositories`,
which takes no arguments at all. If a parameter-less call returns "invalid
parameters," the problem is not your parameters.

**Cause:** a **stale MCP connection after the server restarted.**

The SSE transport is stateful. When a client (e.g. a Claude Code session using
native MCP tools) connects, it performs a handshake and is assigned a
`session_id` that it includes on every subsequent tool-call POST. If the MCP
server process is then restarted — manually, by a `--reload` triggered from a
file edit, or by a container restart — that `session_id` becomes unknown to the
new server process. The client does not automatically re-handshake, so every
request now targets a dead session and is rejected **at the transport layer,
before reaching any tool handler**. The error surfaces as the misleading
`-32602 "Invalid request parameters"` — it really means "this server doesn't
recognize your session."

**Why it's easy to misread:** the label points at parameters, so it looks like a
bad-argument or schema problem. It isn't. The server and your arguments are
fine; the connection is dead.

### How to confirm

The server logs every call that reaches a handler to the `query_log` table
(see [`src/inxr2/adapters/persistence/models/query_log.py`](../src/inxr2/adapters/persistence/models/query_log.py)).
A `-32602` rejection happens *before* the handler, so it leaves **no row**. Use
that as a probe:

1. Note the current max id:

   ```bash
   docker exec inxr2-dev bash -c '
     PGPASSWORD=inxr2_dev_password psql -h localhost -p 5432 -U inxr2_user -d inxr2_dev \
       -tAc "SELECT max(id) FROM query_log WHERE source='"'"'mcp'"'"';"'
   ```

2. Have the affected session fire the failing call, then check for new rows:

   ```bash
   docker exec inxr2-dev bash -c '
     PGPASSWORD=inxr2_dev_password psql -h localhost -p 5432 -U inxr2_user -d inxr2_dev -P pager=off -c "
       SELECT id, logged_at, tool_or_path, params->>'"'"'query'"'"' AS query, repository
       FROM query_log WHERE source='"'"'mcp'"'"' AND id > <MAX_ID> ORDER BY id;"'
   ```

   - **No new row** → the call died client-side / at the transport before the
     handler → stale connection. (Confirmed cause.)
   - **A new row appears** → the call reached the server → investigate the
     handler / arguments instead.

3. Cross-check with a **fresh** client, which always re-handshakes per
   invocation and is therefore immune to this problem:

   ```bash
   docker exec inxr2-dev bash -c '
     cd /workspace/mcp-server && python -c "
   import asyncio
   from mcp import ClientSession
   from mcp.client.sse import sse_client
   async def main():
       async with sse_client(\"http://localhost:3000/sse\") as (r, w):
           async with ClientSession(r, w) as s:
               await s.initialize()
               res = await s.call_tool(\"search_symbols\", {\"query\": \"TourViewModel\"})
               print(res.content[0].text[:200])
   asyncio.run(main())
   "'
   ```

   If the fresh client succeeds on the same arguments that the stale session
   rejects, the diagnosis is confirmed.

### Fix

Reconnect the affected client — **no server restart or reindex needed:**

- In the affected Claude Code session, run **`/mcp`**, select the `inxr2` server,
  and reconnect. This re-handshakes against the running server.
- If reconnect isn't offered, restart that session.

### Prevention

Any MCP server restart breaks every pre-existing native-MCP connection until it
reconnects. To avoid surprise breakage:

- Run the MCP server **without `--reload`** (or keep it separate from the
  auto-reloading backend) so routine file edits don't sever live sessions.
- After any deliberate MCP server restart, **`/mcp` reconnect** in each active
  session.
- Prefer the **`docker exec` Python fallback** (documented in
  [CLAUDE.md](../CLAUDE.md) and [the MCP server README](../mcp-server/README.md))
  for one-off queries — it makes a fresh handshake per call and never goes stale.

## `curl http://localhost:3000/sse` reports "not reachable"

Not a real problem. The `/sse` endpoint is a long-lived Server-Sent Events
stream — it holds the connection open and never returns a normal HTTP body, so a
plain `curl -m 3` times out and looks like a failure. The MCP client speaks the
SSE handshake correctly, which is why tool calls work even when this probe
appears to fail. Use the fresh-client snippet above to check reachability
instead.

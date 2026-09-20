# DarwinLens as an MCP tool

DarwinLens answers plain-English questions over a customer's own HR spreadsheets, and every
answer is computed by DuckDB and checked by deterministic code — the model writes SQL and
phrases the result, it never computes a number and never sees a row. `POST /mcp` puts that
same engine behind the [Model Context Protocol](https://modelcontextprotocol.io), so a
company's own agents can call it as a tool instead of a person typing into our web app.

That matters because the interesting half of this product is not the chat box, it is the
fit-gap work underneath it: the ingestion receipt, the PII rules, the join fan-out guard, and
above all the **glossary** — the customer's own vetted definition of "attrition", "salary" and
"headcount". An agent that calls `ask` through MCP gets an answer computed with *that*
customer's definitions, with the SQL attached, rather than a plausible number a model read off
a spreadsheet. Half the tools here spend no tokens at all, so an agent can learn what the data
says before it decides whether a model call is even needed.

## Get a token

Every `/mcp` call carries the same bearer token the browser uses. The cheapest one is a guest
account, which needs no sign-up form:

```bash
BASE=http://localhost:8000          # or https://<your-service>.onrender.com
TOKEN=$(curl -s -X POST "$BASE/api/auth/guest" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
```

No token, an expired one or a forged one is `401` with a `WWW-Authenticate: Bearer` header.
Tokens last 7 days; get another the same way.

## A walkthrough with curl

Every call is a JSON-RPC 2.0 message posted to the same URL, and the answer is
`application/json`. `rpc` below is just a shorthand:

```bash
rpc() { curl -s -X POST "$BASE/mcp" -H "Authorization: Bearer $TOKEN" \
             -H 'Content-Type: application/json' -d "$1"; }
```

**1. Handshake.** The server echoes your protocol version when it speaks it, and answers with
its own latest when it does not.

```bash
rpc '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
      "protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"acme-agent","version":"1.0"}}}'
# -> {"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},
#               "serverInfo":{"name":"darwinlens",...},"instructions":"..."}}

rpc '{"jsonrpc":"2.0","method":"notifications/initialized"}'   # -> 202, no body
```

**2. What is on offer.**

```bash
rpc '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

**3. Load some data.** In production the `session_id` comes from the analyst's own upload in
the web app; for a first run, load the bundled sample company.

```bash
rpc '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"load_sample_data","arguments":{}}}'
# -> content[0].text: "Loaded the sample company into session 9f2c… Tables: employees (500 rows, 14 columns), …"
SESSION=9f2c…
```

**4. The overview, with no model in the loop.**

```bash
rpc "{\"jsonrpc\":\"2.0\",\"id\":4,\"method\":\"tools/call\",\"params\":{
      \"name\":\"get_overview\",\"arguments\":{\"session_id\":\"$SESSION\"}}}"
# -> "Active headcount is 430." … "Total gross pay is ₹54.67 Cr." … each with its insight lines
```

**5. Ask something.**

```bash
rpc "{\"jsonrpc\":\"2.0\",\"id\":5,\"method\":\"tools/call\",\"params\":{\"name\":\"ask\",
      \"arguments\":{\"session_id\":\"$SESSION\",\"question\":\"Which department has the highest average CTC?\"}}}"
```

The result carries `content[0].text` for the model to read and `structuredContent` for code:
`kind`, `answer`, `confidence` with its reasons, `insights`, `caveats`, `sql` and the first 50
rows. When a word is ambiguous — "salary" can be CTC, gross or net — `kind` is `clarify` and
you get the options; answer it by calling `ask` again with
`"clarification": {"salary": "employees.ctc"}`. When the data cannot answer the question,
`kind` is `refusal` and `missing` names the column that would be needed.

## Wiring it into a desktop assistant

Desktop assistants that speak MCP over stdio reach a remote server through the
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge. Add this to the assistant's
MCP config file and restart it:

```json
{
  "mcpServers": {
    "darwinlens": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "https://<your-service>.onrender.com/mcp",
        "--header", "Authorization:${DARWINLENS_AUTH}"
      ],
      "env": { "DARWINLENS_AUTH": "Bearer <paste the token from /api/auth/guest>" }
    }
  }
}
```

The header value goes through an environment variable because several assistants split
`--header` arguments on spaces, which turns `Authorization: Bearer abc` into two arguments and
a 401 that is very hard to read.

## The tools

| Tool | Arguments | Returns | Model? |
|---|---|---|---|
| `load_sample_data` | — | `session_id`, the tables, the links found between files, any combined views | no |
| `describe_data` | `session_id` | tables; columns with type, HR role and a personal-data flag; links; glossary terms; the list of personal-data columns | no |
| `get_overview` | `session_id` | the automatic dashboard: every tile as title + statement + insight lines | no |
| `list_analyses` | `session_id` | the ten guided analyses, the inputs each takes, and the columns of this session that may fill them | no |
| `run_analysis` | `session_id`, `kind`, `inputs`, `options?`, `include_personal_data?` | the computed tile: statement, insights, caveats, SQL, first 50 rows | no |
| `ask` | `session_id`, `question`, `clarification?`, `include_personal_data?` | `kind`, answer sentence, confidence + reasons, caveats, insights, SQL, first 50 rows — or the clarification options, or the refusal and what is missing | **yes** |

Errors are split the way the protocol splits them, and the difference is worth knowing:

- **JSON-RPC error** (`-32700`, `-32600`, `-32601`, `-32602`) — the *message* was wrong. Fix
  the call.
- **Tool result with `isError: true`** — the call was fine and the answer is no. The text is
  the engine's own sentence, written for an analyst: *"Break down needs a column for 'Split
  by'. Pick one from the list."* Show it, do not retry it unchanged.
- **HTTP status** — `401` no or bad token; `404` that session is expired or is not yours (the
  same sentence the web app gets, so a guessed id tells you nothing); `429` the caller's
  question allowance is spent, with `Retry-After` in seconds.

The last two are statuses only when a message travels alone, because then the HTTP response
*is* that one answer. Inside a **batch** there is no status true of every reply, so the same
sentence comes back as that one message's error with code `-32000` and
`error.data.httpStatus` (`404`, or `429` with `retryAfterSeconds`). The other replies in the
batch are unaffected — a batch of two questions that trips the allowance on the second still
returns the first, which you were charged for.

`ask` is charged to the caller's question allowance exactly as `POST /api/sessions/{id}/ask`
is, against both the calling address and the account, so an agent and a browser tab draw on
one budget. The five no-model tools call no model, spend no tokens and are charged nothing.

## Personal data

A tool result goes to the *caller's* model, which is the caller's own choice of vendor and
their own contract — we are not the ones deciding it. What we can do is keep the product's
promise from changing shape just because the request arrived over MCP:

- `describe_data` names personal-data columns (`employees.name`, `employees.email`) and never
  shows a value from one;
- every computed statement — overview tiles, guided analyses — is built from display strings
  over non-personal columns; `sqlbuild` refuses a personal-data column as a measure or a
  group, so one cannot appear;
- rows returned by `ask` and `run_analysis` come back masked as `[hidden: personal data]`,
  with the masked column names listed in `table.hidden_columns`. Pass
  `"include_personal_data": true` to get the values, and only when the analyst asked for them
  by name.

`include_personal_data` has to be a JSON boolean — `true`, not `"true"`. Anything else is a
tool error naming the argument, refused before the session is looked up, so nothing is spent
on it. That is stricter than the rest of the arguments on purpose: this one is consent, and a
model emitting a stringified boolean is the commonest wrong type there is. Read loosely, the
string `"false"` is truthy in most languages, so a caller trying to keep masking **on** would
be turning it off.

The masking rule is deliberately blunt and is the same one the narrator lives under: if the
query touched a personal-data column at all, *every* text column in the result is masked,
because `SELECT name AS department` would walk straight through a rule that matched on column
names. One consequence to know about: the answer *sentence* is not masked. If someone asks
"who is the highest-paid employee in Sales?", the sentence is the answer and it names them —
the rows behind it are what stays hidden until the caller asks.

## What this prototype does not do

- **No server-initiated stream.** `GET /mcp` is `405`. Every tool answers inside its own POST,
  so there is no progress, no logging and no sampling from server to client.
- **No `Mcp-Session-Id`.** State lives in the DarwinLens `session_id` you pass as a tool
  argument, so a client can reconnect, restart or run several conversations over one token.
- **No resources and no prompts**, only tools. `capabilities` says so in the handshake.
- **No OAuth.** Authorization is the app's own bearer token; tokens expire after 7 days and
  there is no refresh, so a long-lived agent needs a fresh one weekly.
- **No uploads over MCP.** Files arrive through the web app or `POST /api/sessions/{id}/files`;
  `load_sample_data` is here so an agent can be tried without one.
- **One process, in-memory sessions.** A restart drops loaded data, the same as the web app.

## Extending it for a customer

The tools are deliberately generic; the *definitions* are what an FDE changes on site, and
almost all of that work is the glossary.

1. **Make the glossary the customer's metric dictionary.** `describe_data` returns it, so the
   calling agent sees exactly how this customer defines attrition, early attrition, LOP and
   the fiscal year. Edit it per session via `PUT /api/sessions/{id}/glossary`, or change the
   seeded set in `backend/app/catalog/glossary.py` for a deployment. A metric whose required
   roles are missing from the data produces a refusal naming the missing column rather than a
   number computed the wrong way — which is the behaviour you want an agent to hit in
   staging, not a customer to hit in a board pack.
2. **Teach the role detector their headers.** `backend/app/profile/roles.py` maps header
   synonyms to roles; add the customer's HRIS export wording there and every tool improves at
   once, because roles are what the guided analyses and the glossary bind against.
3. **Add a customer-specific analysis** in `backend/app/insights/analyses.py` when a question
   is asked every week. It becomes a no-model tool call, deterministic and free, and shows up
   in `list_analyses` without any change to this file.
4. **Pin the tool surface.** If a customer's agent should only ever read, drop `ask` from
   `_TOOL_FUNCTIONS` in `backend/app/mcp_server.py` — the remaining five never call a model.

Implementation: `backend/app/mcp_server.py`. Tests: `backend/tests/test_mcp.py`.

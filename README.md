# Sutrabooru

Sutrabooru is a lightweight, self-hosted discussion board. Users can browse
boards, start threads, and post messages in a browser. The server is written in
Python and stores its data in SQLite.

A public version (hosted by me) is available at https://board.gusza.fyi/.

Uptime is not guaranteed to even be at least 60% but I will try to keep it online

## Using the site

- The home page lists available boards.
- A board page lists its threads and has a form for starting a thread. A
  thread's first message is submitted along with its title.
- A thread page shows messages, refreshes for new replies, and lets visitors
  post replies.
- The browser remembers the last-used display name in a cookie.

---

## Self-hosting

### Requirements

- Python 3.9 or later
- SQLite 3.35 or later (needed for SQLite's `RETURNING` support)

The server uses only Python's standard library; there are no Python packages to
install. The message page loads the `marked` library from jsDelivr to render
Markdown, so browsers need access to that CDN for Markdown formatting.

### Run locally

From the project directory, start the server:

```sh
python3 server.py
```

Open <http://localhost:3001> in a browser. Stop the server with Ctrl+C.

On its first run, the server creates `data.db`, initializes the database, and
adds two boards: `b` and `meta`. It also generates an administrator token and
prints it to the server's stderr output. Save that token when it is shown:
creating boards through the API requires it, and the token is not displayed
again. Keep it private.

The database is stored as `data.db` in the project directory and is not tracked
by Git. Back it up regularly; it contains all boards, threads, messages, and
tokens. If starting with a fresh database, first back up or move any existing
`data.db` file.

The server listens on port `3001` on all network interfaces. Restrict access
with your firewall or deployment setup if it should only be available locally;
do not expose an untrusted instance directly to the public internet.

---

## HTTP API

The API is served from the same host and port as the site. Successful `GET`
requests return JSON. Successful `POST` requests return JSON with HTTP status
`201`; errors return JSON containing an `err` field.

### Read

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/bs` | List boards |
| `GET` | `/api/b/{board}` | Get a board |
| `GET` | `/api/ts/{board}` | List a board's threads |
| `GET` | `/api/t/{thread}` | Get a thread |
| `GET` | `/api/ms/{thread}` | List messages in a thread |
| `GET` | `/api/m/{message}` | Get a message |

Thread and message list endpoints accept an optional `slice` parameter to
limit and offset results. The message list also accepts `after` to return
messages with IDs greater than the given ID, which the browser uses to load
new replies.

### Create

Send a JSON object in the request body:

| Method | Endpoint | JSON fields | Permission bit required |
| --- | --- | --- | --- |
| `POST` | `/api/b` | `name`, `description` | bit 0 |
| `POST` | `/api/t` | `board`, `title` | None |
| `POST` | `/api/m` | `thread`, `author`, `body` | None |

To create a board, include the token from first-run output in the
`Authorization` header:

```text
Authorization: Bearer YOUR_ADMIN_TOKEN
```

Example: create a thread on the `b` board with `curl`:

```sh
curl -X POST http://localhost:3001/api/t \
  -H 'Content-Type: application/json' \
  -d '{"board":"b","title":"Hello, Sutrabooru"}'
```

The response contains the new thread's `id`. Use that ID as the `thread` value
when posting its first message to `/api/m`.

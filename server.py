import http.server
import sqlite3
import sys
import json
import time
import os
import secrets
from urllib.parse import urlparse, parse_qs
import mimetypes

PORT = 3001

def log(*msg):
    print("[LOG]", *msg, file=sys.stderr)

def err(*msg):
    print("[ERR]", *msg, file=sys.stderr)

CREATE_BOARD_PERM = 2**0

class Backend():

    def __init__(self):
        self.file_existed = os.path.exists("data.db")
        if os.path.isdir("data.db"):
            sys.exit("`data.db` exists but is a directory")
        db = self.database = sqlite3.connect("data.db",check_same_thread=False)
        db.row_factory = sqlite3.Row
        self.cursor = db.cursor()

    def ensure(self):
        cursor = self.cursor
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS boards (
                name TEXT NOT NULL PRIMARY KEY,
                description TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board TEXT NOT NULL,
                created INTEGER NOT NULL,
                bumped INTEGER NOT NULL,
                title TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread INTEGER NOT NULL,
                created INTEGER NOT NULL,
                author TEXT NOT NULL,
                body TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT NOT NULL UNIQUE,
                permissions INTEGER NOT NULL
            )
        """)
        if not self.file_existed:
            self.create_default()
        self.database.commit()

    def create_default(self):
        log("creating default boards")

        create_board = self.create_board

        create_board("b","Anything and everything")
        create_board("meta","All about Sutrabooru")

        token = secrets.token_urlsafe(16)
        self.create_token(token,2**32-1) # i doubt i'll need more than 32 permissions

        log("ADMIN TOKEN, WON'T BE SHOWN AGAIN:", token)
        log("Unless you log this - you're not supposed to do that on first run")
        log("Delete data.db and run this from a terminal once if you're reading this from the persistent logs")

    def exists(self, table:str, key:str, match):
        self.cursor.execute(f"SELECT 1 FROM {table} WHERE {key} = ?;", (match,))
        return self.cursor.fetchall()

    def create_board(self, name:str="", description:str=""):
        if not name:
            return "Name required"
        if not description:
            return "Description required"
        try:
            self.cursor.execute("INSERT INTO boards (name, description) VALUES (?, ?) RETURNING name;", (name, description))
        except sqlite3.IntegrityError as e:
            return str(e)
        res = self.cursor.fetchone()
        self.database.commit()
        return res

    def create_thread(self, board:str="", title:str=""):
        if not self.exists("boards","name",board):
            return f"Board {board} does not exist"
        if not title:
            return "Title must be a non-empty string"
        self.cursor.execute("INSERT INTO threads (board, created, bumped, title) VALUES (?, ?, ?, ?) RETURNING id;", (board, int(time.time()), int(time.time()), title))
        res = self.cursor.fetchone()
        self.database.commit()
        return res

    def bump_thread(self, thread:int):
        self.cursor.execute("UPDATE threads SET bumped = ? WHERE id = ?", (int(time.time()), thread))
        self.database.commit()

    def create_message(self, thread:int=0, author:str="", body:str=""):
        if not self.exists("threads","id",thread):
            return f"Thread {thread} does not exist"
        if not author:
            return "Name must be a non-empty string"
        if not body:
            return "Message must be a non-empty string"
        self.cursor.execute("INSERT INTO messages (thread, created, author, body) VALUES (?, ?, ?, ?) RETURNING id;", (thread, int(time.time()), author, body))
        res = self.cursor.fetchone()
        self.database.commit()
        self.bump_thread(thread)
        return res

    def create_token(self, token:str, permissions:int):
        self.cursor.execute("INSERT INTO tokens (token, permissions) VALUES (?, ?)", (token, permissions))
        self.database.commit()

    def check_permission(self, token:str, permission:int):
        self.cursor.execute("SELECT * FROM tokens WHERE token = ?;", (token,))
        value = self.cursor.fetchone()
        if value:
            value = value["permissions"]
        else:
            value = 0
        if (permission & value) == permission:
            return True
        return False

    def generate_slice(self, source:str):
        start, count, *_ = source.split("~")
        if _:
            raise ValueError("Too many delimiter")

        return [int(count), int(start)]

    def get_boards(self):
        self.cursor.execute("SELECT * FROM boards ORDER BY name ASC")
        return self.cursor.fetchall()

    def get_threads(self, board:str, slice:str="0~-1", after:str="0"):
        slice = self.generate_slice(slice)
        order = "DESC"
        if slice[1] < 0:
            slice[1] = 0-slice[1]-1
            order = "ASC"
            after = int(after)
        self.cursor.execute(f"SELECT * FROM threads WHERE board = ? AND id > {after} ORDER BY bumped {order} LIMIT ? OFFSET ?;", (board,*slice))
        return self.cursor.fetchall()

    def get_messages(self, thread:int, slice:str="0~-1", after:str="0"):
        slice = self.generate_slice(slice)
        order = "ASC"
        if slice[1] < 0:
            slice[1] = 0-slice[1]-1
            order = "DESC"
        after = int(after)
        self.cursor.execute(f"SELECT * FROM messages WHERE thread = ? AND id > {after} ORDER BY created {order} LIMIT ? OFFSET ?;", (thread,*slice))
        return self.cursor.fetchall()

    def get_board(self, name):
        self.cursor.execute("SELECT * FROM boards WHERE name = ?", (name,))
        return self.cursor.fetchone()
    def get_thread(self, id:int):
        try:
            self.cursor.execute("SELECT * FROM threads WHERE id = ?", (int(id),))
            return self.cursor.fetchone()
        except ValueError:
            return (404, "Invalid ID")
    def get_message(self, id:int):
        try:
            self.cursor.execute("SELECT * FROM messages WHERE id = ?", (id,))
            return self.cursor.fetchone()
        except ValueError:
            return (404, "Invalid ID")

backend:Backend

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def __init__(self, request, client_address, server):
        backend = self.backend = Backend()

        self.GET_handlers = {
            "bs": backend.get_boards,
            "ts": backend.get_threads,
            "ms": backend.get_messages,
            "b": backend.get_board,
            "t": backend.get_thread,
            "m": backend.get_message,
        }

        self.POST_handlers = {
            "b": (backend.create_board, CREATE_BOARD_PERM),
            "t": (backend.create_thread, 0),
            "m": (backend.create_message, 0),
        }
        super().__init__(request,client_address,server)

    def setup(self):
        log("new connection from", *self.client_address)
        return super().setup()

    def finish(self):
        self.backend.database.close()

        return super().finish()

    def guess_type(self, name:str):
        return mimetypes.guess_type(name)[0] or "application/octet-stream"

    def send_error_api(self, code, message = None):
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.write(json.dumps({"err":message}).encode())

    def write(self, binary:bytes):
        #log(len(binary), binary)
        self.send_header("Content-length", str(len(binary)))
        self.send_header("Connection", "keep-alive")
        self.send_header("Keep-alive", "timeout=8, max=64")
        self.end_headers()
        self.wfile.write(binary)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            _, handler_name, *tail = [item for item in parsed.path.split("/") if item]
            query = parse_qs(parsed.query)
            query = {
                key: val_list[0] for key, val_list in query.items() if val_list
            }

            handler = self.GET_handlers.get(handler_name,None)
            if handler is None:
                self.send_error_api(404, "Invalid Path")
            else:
                try:
                    result = handler(*tail, **query)
                    if result is None:
                        self.send_error_api(404)
                        return
                    if isinstance(result, tuple):
                        self.send_error_api(*result)
                        return
                    if isinstance(result, list):
                        result = [dict(item) for item in result]
                    else:
                        result = dict(result)
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.write(json.dumps(result).encode())
                except TypeError as e:
                    self.send_error_api(400, f"Invalid Arguments: {e}")
                except ValueError as e:
                    self.send_error_api(400, f"Invalid Arguments: {e}")
        else:
            real_path = os.path.normpath("frontend" + parsed.path)
            log(real_path)
            if parsed.path == "/":
                file = "frontend/boards.html"
            elif parsed.path.startswith("/b/"):
                file = "frontend/threads.html"
            elif parsed.path.startswith("/t/"):
                file = "frontend/messages.html"
            elif os.path.exists(real_path):
                if not real_path.startswith("frontend/"):
                    self.send_error(403)
                    return

                file = real_path
            else:
                self.send_error(404)
                return

            data = open(file, "rb").read()
            file_type = self.guess_type(file)

            log(file, file_type)
            self.send_response(200)
            self.send_header("Content-type", file_type)
            self.send_header("Cache-Control", "public, max-age=3600, must-revalidate")
            self.write(data)

    def do_POST(self):
        parsed = urlparse(self.path)
        token_header = self.headers.get("Authorization", None)
        if token_header:
            parts = token_header.split(maxsplit=1)
            if len(parts) != 2 or parts[0].lower() != "bearer":
                self.send_error_api(400, "Invalid authorization method")
                return
            token = parts[1]
        else:
            token = ""

        if parsed.path.startswith("/api/"):
            handler_name = parsed.path[5:]
            handler, permissions = self.POST_handlers.get(handler_name,(None,None))

            if handler is None:
                self.send_error_api(404, "Invalid Path")
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error_api(400, "Invalid Content-Length")
                return
            if length <= 0:
                self.send_error_api(400, "Body must exist")
                return
            if length > 2**16:
                self.send_error_api(413, "Body too large")
                return
            if not self.backend.check_permission(token,permissions):
                self.send_error_api(401, "Token does not grant sufficient permission")

            param = self.rfile.read(length)

            try:
                param = json.loads(param.decode())
            except UnicodeDecodeError:
                self.send_error_api(400, "Body is not plain text")
                return
            except json.decoder.JSONDecodeError as e:
                self.send_error_api(400, f"Invalid JSON: {e}")
                return

            try:
                result = handler(**param)
                if isinstance(result,str):
                    self.send_error_api(400, result)
                    return
                else:
                    self.send_response(201)
                if isinstance(result,list):
                    result = [dict(item) for item in result]
                else:
                    result = dict(result)
                self.send_header("Content-type", "application/json")
                self.write(json.dumps(result).encode())
            except TypeError as e:
                self.send_error_api(400, "Invalid Arguments")
        else:
            self.send_error(403)

if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))

    Backend().ensure()
    server = http.server.ThreadingHTTPServer(("",PORT), Handler)

    log(f"starting server on port {PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log(f"Shutting down (SIGINT)")

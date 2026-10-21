import http.server
import sqlite3
import sys
import json
import time
import os
import shutil
import subprocess
import secrets

PORT = 3001

def log(*msg):
    print("[LOG]", *msg)

def err(*msg):
    print("[ERR]", *msg, file=sys.stderr)

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
                token TEXT NOT NULL,
                create_board BOOLEAN NOT NULL DEFAULT 0,
                create_token BOOLEAN NOT NULL DEFAULT 0
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

    def exists(self, table:str, key:str, match):
        self.cursor.execute(f"SELECT 1 FROM {table} WHERE {key} = ?;", (match,))
        return self.cursor.fetchall()

    def create_board(self, name:str, description:str):
        try:
            self.cursor.execute("INSERT INTO boards (name, description) VALUES (?, ?) RETURNING name;", (name, description))
        except sqlite3.IntegrityError:
            return "Board name taken"
        res = self.cursor.fetchall()
        self.database.commit()
        return res

    def create_thread(self, board:str, title:str):
        if not self.exists("boards","name",board):
            return f"Board {board} does not exist"
        self.cursor.execute("INSERT INTO threads (board, created, bumped, title) VALUES (?, ?, ?, ?) RETURNING id;", (board, int(time.time()), int(time.time()), title))
        res = self.cursor.fetchall()
        self.database.commit()
        return res

    def bump_thread(self, thread:int):
        self.cursor.execute("UPDATE threads SET bumped = ? WHERE id = ?", (int(time.time()), thread))
        self.database.commit()

    def create_message(self, thread:int, author:str, body:str):
        if not self.exists("threads","id",thread):
            return f"Thread {thread} does not exist"
        self.cursor.execute("INSERT INTO messages (thread, created, bumped, author, body) VALUES (?, ?, ?, ?, ?) RETURNING id;", (thread, int(time.time()), int(time.time()), author, body))
        res = self.cursor.fetchall()
        self.database.commit()
        self.bump_thread(thread)
        return res

    def generate_slice(self, source:str):
        start, count, *_ = source.split("~")
        if _:
            raise ValueError("Too many delimiter")

        return (count, start)

    def get_boards(self):
        self.cursor.execute("SELECT * FROM boards")
        return self.cursor.fetchall()
    def get_threads(self, board:str, slice:str="0~-1"):
        self.cursor.execute("SELECT * FROM threads WHERE board = ? ORDER BY bumped DESC LIMIT ? OFFSET ?;", (board,*self.generate_slice(slice)))
        return self.cursor.fetchall()
    def get_messages(self, thread:int, slice:str="0~-1"):
        self.cursor.execute("SELECT * FROM messages WHERE thread = ? ORDER BY created ASC LIMIT ? OFFSET ?;", (thread,*self.generate_slice(slice)))
        return self.cursor.fetchall()

    def get_board(self, name):
        self.cursor.execute("SELECT * FROM boards WHERE name = ?", (name,))
        return self.cursor.fetchone()
    def get_thread(self, id:int):
        try:
            self.cursor.execute("SELECT * FROM threads WHERE id = ?", (int(id),))
            return self.cursor.fetchone()
        except ValueError:
            return "Invalid ID"
    def get_message(self, id:int):
        try:
            self.cursor.execute("SELECT * FROM messages WHERE id = ?", (id,))
            return self.cursor.fetchone()
        except ValueError:
            return "Invalid ID"

backend:Backend

class Handler(http.server.SimpleHTTPRequestHandler):

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
            "b": backend.create_board,
            "t": backend.create_thread,
            "m": backend.create_message
        }
        super().__init__(request,client_address,server)

    def do_GET(self):
        if self.path.startswith("/api/"):
            _, handler_name, *tail = [item for item in self.path[1:].split("/") if item]
            handler = self.GET_handlers.get(handler_name,None)
            if not handler_name:
                self.send_error(404, "Invalid Path")
            else:
                try:
                    result = handler(*tail)
                    if isinstance(result, list):
                        result = [dict(item) for item in result]
                    else:
                        result = dict(result)
                    if isinstance(result, str):
                        self.send_error(404,result)
                    else:
                        self.send_response(200)
                        self.send_header("Content-type", "text/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                except TypeError as e:
                    self.send_error(400, f"Invalid Arguments: {e}")
                except ValueError as e:
                    self.send_error(400, f"Invalid Arguments: {e}")
        else:
            if self.path == "/":
                file = "frontend/boards.html"
            elif self.path.startswith("/b/"):
                file = "frontend/threads.html"
            elif self.path.startswith("/t/"):
                file = "frontend/messages.html"
            elif os.path.exists("frontend" + self.path):
                file = "frontend" + self.path
            else:
                self.send_error(404)
                return

            if file.endswith(".php"):
                result = subprocess.run(["php", file],capture_output=True)
                if result.returncode != 0:
                    self.send_error(500)
                else:
                    data = result.stdout
                    file_type = "text/html"
            else:
                data = open(file, "rb").read()
                file_type = self.guess_type(file)

            log(file, file_type)
            self.send_response(200)
            self.send_header("Content-type", file_type)
            self.end_headers()
            self.wfile.write(data)

    def do_POST(self):
        if self.path.startswith("/api/"):
            handler_name = self.path[5:]
            handler = self.POST_handlers.get(handler_name,None)
            length = int(self.headers["Content-Length"])
            param = self.rfile.read(length)

            try:
                param = json.loads(param.decode())
            except UnicodeDecodeError:
                self.send_error(400, "Body is not plain text")
                return
            except json.decoder.JSONDecodeError as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return

            if not handler_name:
                self.send_error(404, "Invalid Path")
            else:
                try:
                    result = handler(**param)
                    result = [dict(item) for item in result]
                    if isinstance(result,str):
                        self.send_error(400, result)
                        return
                    else:
                        self.send_response(201)
                    self.send_header("Content-type", "text/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
                except TypeError as e:
                    self.send_error(400, "Invalid Arguments")
        else:
            self.send_error(403)

if __name__ == "__main__":
    os.chdir(os.path.dirname(__file__))

    Backend().ensure()
    if not shutil.which("php"):
        sys.exit("PHP not available")

    server = http.server.ThreadingHTTPServer(("",PORT), Handler)

    log(f"starting server on port {PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log(f"Shutting down (SIGINT)")

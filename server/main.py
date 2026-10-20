import http.server
import sqlite3
import sys
import json
import time

PORT = 3001

def log(msg):
    print("[LOG] " + msg)

def err(msg):
    print("[ERR] " + msg, file=sys.stderr)

class Backend():

    def __init__(self):
        db = self.database = sqlite3.connect("data.db")
        cursor = self.cursor = db.cursor()
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
                bumped INTEGER NOT NULL,
                author TEXT NOT NULL,
                body TEXT NOT NULL
            )
        """)
        db.commit()

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
        self.bump_thread(thread)
        self.database.commit()
        return res

    def get_boards(self):
        self.cursor.execute("SELECT * FROM boards")
        return self.cursor.fetchall()
    def get_threads(self, board:str):
        self.cursor.execute("SELECT * FROM threads WHERE board = ?", (board,))
        return self.cursor.fetchall()
    def get_messages(self, thread:int):
        self.cursor.execute("SELECT * FROM messages WHERE thread = ?", (thread,))
        return self.cursor.fetchall()

    def get_board(self, name):
        self.cursor.execute("SELECT * FROM boards WHERE name = ?", (name,))
        return self.cursor.fetchall()
    def get_thread(self, id:int):
        self.cursor.execute("SELECT * FROM threads WHERE id = ?", (id,))
        return self.cursor.fetchall()
    def get_message(self, id:int):
        self.cursor.execute("SELECT * FROM messages WHERE id = ?", (id,))
        return self.cursor.fetchall()

backend:Backend

class Handler(http.server.BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        global backend


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
        handler_name, *tail = self.path[1:].split("/")
        handler = self.GET_handlers.get(handler_name,None)
        if not handler_name:
            self.send_error(404, "Invalid Path")
        else:
            try:
                result = handler(*tail)
                if isinstance(result, str):
                    self.send_error(404,result)
                else:
                    self.send_response(200)
                    self.send_header("Content-type", "text/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
            except TypeError as e:
                self.send_error(400, "Invalid Arguments")

    def do_POST(self):
        handler_name = self.path[1:]
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
                print(result)
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

if __name__ == "__main__":
    backend = Backend()

    server = http.server.HTTPServer(("",PORT), Handler)

    log(f"Starting server on port {PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log(f"Shutting down (SIGINT)")

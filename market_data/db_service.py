from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import gzip
import json
import sqlite3

DB_PATH = "/home/opc/marketlab/data/candle_store.db"
HOST = "127.0.0.1"
PORT = 8765


def table_for(interval):
    interval = str(interval).lower().strip()
    if interval == "5m":
        return "candles"
    if interval == "15m":
        return "candles_15m"
    if interval in ("30m", "1h"):
        return f"candles_{interval}"
    raise ValueError("Unsupported interval")


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        raw = json.dumps(data, separators=(",", ":")).encode()
        if "gzip" in self.headers.get("Accept-Encoding", ""):
            raw = gzip.compress(raw)
            encoding = True
        else:
            encoding = False
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        if encoding:
            self.send_header("Content-Encoding", "gzip")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode())

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        try:
            if parsed.path == "/health":
                self.send_json(200, {"status": "ok"})
                return
            if parsed.path == "/summary":
                interval = params.get("interval", ["5m"])[0]
                table = table_for(interval)
                with sqlite3.connect(DB_PATH) as conn:
                    row = conn.execute(f"SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(ts), MAX(ts) FROM {table}").fetchone()
                self.send_json(200, {"interval": interval, "symbols": row[0], "candles": row[1], "oldest": row[2], "newest": row[3]})
                return
            if parsed.path == "/latest":
                symbol = params.get("symbol", [None])[0]
                interval = params.get("interval", ["5m"])[0]
                if not symbol:
                    raise ValueError("symbol required")
                symbol = symbol.upper()
                if not symbol.endswith(".NS"):
                    symbol += ".NS"
                table = table_for(interval)
                with sqlite3.connect(DB_PATH) as conn:
                    row = conn.execute(f"SELECT MAX(ts) FROM {table} WHERE symbol = ?", (symbol,)).fetchone()
                self.send_json(200, {"symbol": symbol, "interval": interval, "latest": row[0]})
                return
            if parsed.path == "/candles":
                symbol = params.get("symbol", [None])[0]
                interval = params.get("interval", ["5m"])[0]
                if not symbol:
                    raise ValueError("symbol required")
                symbol = symbol.upper()
                if not symbol.endswith(".NS"):
                    symbol += ".NS"
                table = table_for(interval)
                query = f"SELECT ts, open, high, low, close, volume FROM {table} WHERE symbol = ?"
                values = [symbol]
                if params.get("start", [None])[0]:
                    query += " AND ts >= ?"
                    values.append(params["start"][0])
                if params.get("end", [None])[0]:
                    query += " AND ts <= ?"
                    values.append(params["end"][0])
                query += " ORDER BY ts"
                with sqlite3.connect(DB_PATH) as conn:
                    rows = conn.execute(query, values).fetchall()
                self.send_json(200, {"symbol": symbol, "interval": interval, "candles": [{"ts": r[0], "Open": r[1], "High": r[2], "Low": r[3], "Close": r[4], "Volume": r[5]} for r in rows]})
                return
            self.send_json(404, {"error": "Not found"})
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = self.read_json()
            if parsed.path == "/latest_batch":
                interval = payload.get("interval", "5m")
                table = table_for(interval)
                symbols = [str(s).upper() for s in payload.get("symbols", [])]
                symbols = [s if s.endswith(".NS") else s + ".NS" for s in symbols]
                result = {}
                if symbols:
                    placeholders = ",".join("?" for _ in symbols)
                    with sqlite3.connect(DB_PATH) as conn:
                        rows = conn.execute(f"SELECT symbol, MAX(ts) FROM {table} WHERE symbol IN ({placeholders}) GROUP BY symbol", symbols).fetchall()
                    result.update(dict(rows))
                for symbol in symbols:
                    result.setdefault(symbol, None)
                self.send_json(200, result)
                return
            if parsed.path == "/candles_batch":
                interval = payload.get("interval", "5m")
                table = table_for(interval)
                symbols = [str(s).upper() for s in payload.get("symbols", [])]
                symbols = [s if s.endswith(".NS") else s + ".NS" for s in symbols]
                if not symbols:
                    self.send_json(200, {"frames": {}})
                    return
                placeholders = ",".join("?" for _ in symbols)
                query = f"SELECT symbol, ts, open, high, low, close, volume FROM {table} WHERE symbol IN ({placeholders})"
                values = list(symbols)
                if payload.get("start") is not None:
                    query += " AND ts >= ?"
                    values.append(payload["start"])
                if payload.get("end") is not None:
                    query += " AND ts <= ?"
                    values.append(payload["end"])
                query += " ORDER BY symbol, ts"
                with sqlite3.connect(DB_PATH) as conn:
                    rows = conn.execute(query, values).fetchall()
                frames = {s: [] for s in symbols}
                for r in rows:
                    frames[r[0]].append({"ts": r[1], "Open": r[2], "High": r[3], "Low": r[4], "Close": r[5], "Volume": r[6]})
                self.send_json(200, {"frames": frames})
                return
            if parsed.path == "/upsert_batch":
                interval = payload.get("interval", "5m")
                table = table_for(interval)
                rows = []
                for symbol, candles in payload.get("frames", {}).items():
                    symbol = str(symbol).upper()
                    if not symbol.endswith(".NS"):
                        symbol += ".NS"
                    for c in candles:
                        rows.append((symbol, c["ts"], c["Open"], c["High"], c["Low"], c["Close"], c["Volume"]))
                with sqlite3.connect(DB_PATH) as conn:
                    before = conn.total_changes
                    if rows:
                        conn.executemany(f"INSERT OR IGNORE INTO {table} (symbol, ts, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
                        conn.commit()
                    inserted = conn.total_changes - before
                self.send_json(200, {"received": len(rows), "inserted": inserted})
                return
            self.send_json(404, {"error": "Not found"})
        except Exception as exc:
            self.send_json(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        print("[DB SERVICE]", fmt % args)


server = ThreadingHTTPServer((HOST, PORT), Handler)
print(f"DB service listening on {HOST}:{PORT}")
server.serve_forever()

from flask import Flask, render_template, jsonify, request, make_response
import json
import os
import sqlite3
import random
import re
import time

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_PATH = os.path.join(DATA_DIR, "equipment.json")
SWITCHBOARDS_PATH = os.path.join(DATA_DIR, "switchboards.json")

def load_equipment():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_switchboards():
    with open(SWITCHBOARDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_equipment(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_switchboards(data):
    with open(SWITCHBOARDS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

EQUIPMENT = load_equipment()
SWITCHBOARDS = load_switchboards()

DB_PATH = os.path.join(DATA_DIR, "sessions.db")

NORSKE_ORD = [
    "FISK", "FJORD", "TROLL", "NORD", "KYST", "LAKS", "SILD", "STORM",
    "TORSK", "BRIS", "SNEKKE", "KRABBE", "MERD", "NAUST", "GARN",
    "FLÅTE", "KVEITE", "HYSE", "KOBBE", "OTER", "SEL", "SKREI",
    "LODDE", "ROGN", "TANG", "BRYGGE", "HAVØRN", "MÅKE", "LODD",
]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            code TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            last_active REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS session_pins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_code TEXT NOT NULL,
            pin_data TEXT NOT NULL,
            pin_key TEXT NOT NULL,
            added_at REAL NOT NULL,
            FOREIGN KEY (session_code) REFERENCES sessions(code),
            UNIQUE(session_code, pin_key)
        );
        CREATE INDEX IF NOT EXISTS idx_session_pins_code ON session_pins(session_code);
    """)
    conn.commit()
    conn.close()

def generate_session_code():
    conn = get_db()
    for _ in range(50):
        word = random.choice(NORSKE_ORD)
        num = random.randint(10, 99)
        code = f"{word}-{num}"
        existing = conn.execute("SELECT 1 FROM sessions WHERE code = ?", (code,)).fetchone()
        if not existing:
            conn.close()
            return code
    conn.close()
    return f"{random.choice(NORSKE_ORD)}-{random.randint(100, 999)}"

def cleanup_old_sessions():
    conn = get_db()
    cutoff = time.time() - 86400
    conn.execute("DELETE FROM session_pins WHERE session_code IN (SELECT code FROM sessions WHERE last_active < ?)", (cutoff,))
    conn.execute("DELETE FROM sessions WHERE last_active < ?", (cutoff,))
    conn.commit()
    conn.close()

init_db()


@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


def make_pattern(q):
    parts = q.split('*')
    return re.compile('.*'.join(re.escape(p) for p in parts))


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip().upper()
    if not q or len(q) < 2:
        return jsonify({"results": [], "query": q})

    pattern = make_pattern(q)
    results = []
    for i, item in enumerate(EQUIPMENT):
        utstyr = item.get("utstyr", "").upper()
        navn = item.get("navn", "").upper()
        tavle = item.get("tavle", "").upper()
        if pattern.search(utstyr) or pattern.search(navn) or pattern.search(tavle):
            results.append({"_id": i, **item})

    results.sort(key=lambda x: (
        0 if x.get("utstyr", "").upper() == q else
        1 if pattern.search(x.get("utstyr", "").upper()) else 2
    ))
    return jsonify({"results": results[:50], "query": q, "total": len(results)})


@app.route("/api/switchboards")
def switchboards():
    q = request.args.get("q", "").strip().upper()
    if not q or len(q) < 2:
        return jsonify({"results": [], "query": q, "total": 0})

    pattern = make_pattern(q)
    results = []
    for i, item in enumerate(SWITCHBOARDS):
        if (pattern.search(item.get("tavle", "").upper())
                or pattern.search(item.get("omr", "").upper())
                or pattern.search(item.get("beskrivelse", "").upper())
                or pattern.search(item.get("mating", "").upper())):
            results.append({"_id": i, **item})

    results.sort(key=lambda x: (
        0 if x.get("tavle", "").upper() == q else
        1 if pattern.search(x.get("tavle", "").upper()) else 2
    ))
    return jsonify({"results": results, "query": q, "total": len(results)})


@app.route("/api/stats")
def stats():
    return jsonify({
        "total": len(EQUIPMENT),
        "tavler": len(set(item["tavle"] for item in EQUIPMENT)),
        "with_utstyr": sum(1 for item in EQUIPMENT if item.get("utstyr")),
        "switchboards": len(SWITCHBOARDS)
    })


# ── Equipment CRUD ──

@app.route("/api/equipment", methods=["POST"])
def add_equipment():
    global EQUIPMENT
    data = request.get_json()
    if not data:
        return jsonify({"error": "Ingen data"}), 400
    new_item = {
        "tavle": data.get("tavle", "").strip(),
        "felt": data.get("felt", "").strip(),
        "utstyr": data.get("utstyr", "").strip(),
        "navn": data.get("navn", "").strip(),
        "laas_nr": data.get("laas_nr", "").strip(),
        "sikring": data.get("sikring", "").strip(),
        "kw": data.get("kw", "").strip(),
        "last_strom": data.get("last_strom", "").strip(),
        "motorvarmer_tag": data.get("motorvarmer_tag", "").strip(),
        "motorvarmer_fra": data.get("motorvarmer_fra", "").strip(),
        "plassering": data.get("plassering", "").strip(),
    }
    EQUIPMENT.append(new_item)
    save_equipment(EQUIPMENT)
    return jsonify({"ok": True, "_id": len(EQUIPMENT) - 1, "item": new_item}), 201


@app.route("/api/equipment/<int:item_id>", methods=["PUT"])
def update_equipment(item_id):
    global EQUIPMENT
    if item_id < 0 or item_id >= len(EQUIPMENT):
        return jsonify({"error": "Ikke funnet"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "Ingen data"}), 400
    EQUIPMENT[item_id] = {
        "tavle": data.get("tavle", "").strip(),
        "felt": data.get("felt", "").strip(),
        "utstyr": data.get("utstyr", "").strip(),
        "navn": data.get("navn", "").strip(),
        "laas_nr": data.get("laas_nr", "").strip(),
        "sikring": data.get("sikring", "").strip(),
        "kw": data.get("kw", "").strip(),
        "last_strom": data.get("last_strom", "").strip(),
        "motorvarmer_tag": data.get("motorvarmer_tag", "").strip(),
        "motorvarmer_fra": data.get("motorvarmer_fra", "").strip(),
        "plassering": data.get("plassering", "").strip(),
    }
    save_equipment(EQUIPMENT)
    return jsonify({"ok": True})


@app.route("/api/equipment/<int:item_id>", methods=["DELETE"])
def delete_equipment(item_id):
    global EQUIPMENT
    if item_id < 0 or item_id >= len(EQUIPMENT):
        return jsonify({"error": "Ikke funnet"}), 404
    EQUIPMENT.pop(item_id)
    save_equipment(EQUIPMENT)
    return jsonify({"ok": True})


# ── Switchboards CRUD ──

@app.route("/api/switchboards", methods=["POST"])
def add_switchboard():
    global SWITCHBOARDS
    data = request.get_json()
    if not data:
        return jsonify({"error": "Ingen data"}), 400
    new_item = {
        "tavle": data.get("tavle", "").strip(),
        "omr": data.get("omr", "").strip(),
        "spenning": data.get("spenning", "").strip(),
        "beskrivelse": data.get("beskrivelse", "").strip(),
        "mating": data.get("mating", "").strip(),
    }
    SWITCHBOARDS.append(new_item)
    save_switchboards(SWITCHBOARDS)
    return jsonify({"ok": True, "_id": len(SWITCHBOARDS) - 1, "item": new_item}), 201


@app.route("/api/switchboards/<int:item_id>", methods=["PUT"])
def update_switchboard(item_id):
    global SWITCHBOARDS
    if item_id < 0 or item_id >= len(SWITCHBOARDS):
        return jsonify({"error": "Ikke funnet"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"error": "Ingen data"}), 400
    SWITCHBOARDS[item_id] = {
        "tavle": data.get("tavle", "").strip(),
        "omr": data.get("omr", "").strip(),
        "spenning": data.get("spenning", "").strip(),
        "beskrivelse": data.get("beskrivelse", "").strip(),
        "mating": data.get("mating", "").strip(),
    }
    save_switchboards(SWITCHBOARDS)
    return jsonify({"ok": True})


@app.route("/api/switchboards/<int:item_id>", methods=["DELETE"])
def delete_switchboard(item_id):
    global SWITCHBOARDS
    if item_id < 0 or item_id >= len(SWITCHBOARDS):
        return jsonify({"error": "Ikke funnet"}), 404
    SWITCHBOARDS.pop(item_id)
    save_switchboards(SWITCHBOARDS)
    return jsonify({"ok": True})


# ── Session routes ──

@app.route("/api/session", methods=["POST"])
def create_session():
    cleanup_old_sessions()
    code = generate_session_code()
    now = time.time()
    conn = get_db()
    conn.execute("INSERT INTO sessions (code, created_at, last_active) VALUES (?, ?, ?)", (code, now, now))
    pins = request.json.get("pins", []) if request.is_json else []
    for pin in pins:
        pin_key = f"{pin.get('tavle','')}|{pin.get('felt','')}|{pin.get('utstyr','')}"
        try:
            conn.execute("INSERT OR IGNORE INTO session_pins (session_code, pin_data, pin_key, added_at) VALUES (?, ?, ?, ?)",
                (code, json.dumps(pin, ensure_ascii=False), pin_key, now))
        except Exception:
            pass
    conn.commit()
    conn.close()
    return jsonify({"code": code, "created_at": now})


@app.route("/api/session/<code>")
def get_session(code):
    code = code.upper()
    conn = get_db()
    session = conn.execute("SELECT * FROM sessions WHERE code = ?", (code,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "Sesjon ikke funnet"}), 404
    conn.execute("UPDATE sessions SET last_active = ? WHERE code = ?", (time.time(), code))
    conn.commit()
    rows = conn.execute("SELECT pin_data, added_at FROM session_pins WHERE session_code = ? ORDER BY added_at ASC", (code,)).fetchall()
    pins = []
    for row in rows:
        try:
            pins.append(json.loads(row["pin_data"]))
        except Exception:
            pass
    conn.close()
    return jsonify({"code": code, "pins": pins, "pin_count": len(pins), "created_at": session["created_at"]})


@app.route("/api/session/<code>/pin", methods=["POST"])
def add_session_pin(code):
    code = code.upper()
    conn = get_db()
    session = conn.execute("SELECT 1 FROM sessions WHERE code = ?", (code,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "Sesjon ikke funnet"}), 404
    pin = request.json
    pin_key = f"{pin.get('tavle','')}|{pin.get('felt','')}|{pin.get('utstyr','')}"
    now = time.time()
    conn.execute("INSERT OR IGNORE INTO session_pins (session_code, pin_data, pin_key, added_at) VALUES (?, ?, ?, ?)",
        (code, json.dumps(pin, ensure_ascii=False), pin_key, now))
    conn.execute("UPDATE sessions SET last_active = ? WHERE code = ?", (now, code))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/session/<code>/pin", methods=["DELETE"])
def remove_session_pin(code):
    code = code.upper()
    conn = get_db()
    pin = request.json
    pin_key = f"{pin.get('tavle','')}|{pin.get('felt','')}|{pin.get('utstyr','')}"
    conn.execute("DELETE FROM session_pins WHERE session_code = ? AND pin_key = ?", (code, pin_key))
    conn.execute("UPDATE sessions SET last_active = ? WHERE code = ?", (time.time(), code))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/session/<code>/sync", methods=["POST"])
def sync_session_pins(code):
    code = code.upper()
    conn = get_db()
    session = conn.execute("SELECT 1 FROM sessions WHERE code = ?", (code,)).fetchone()
    if not session:
        conn.close()
        return jsonify({"error": "Sesjon ikke funnet"}), 404
    pins = request.json.get("pins", []) if request.is_json else []
    now = time.time()
    conn.execute("DELETE FROM session_pins WHERE session_code = ?", (code,))
    for pin in pins:
        pin_key = f"{pin.get('tavle','')}|{pin.get('felt','')}|{pin.get('utstyr','')}"
        conn.execute("INSERT OR IGNORE INTO session_pins (session_code, pin_data, pin_key, added_at) VALUES (?, ?, ?, ?)",
            (code, json.dumps(pin, ensure_ascii=False), pin_key, now))
    conn.execute("UPDATE sessions SET last_active = ? WHERE code = ?", (now, code))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "pin_count": len(pins)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

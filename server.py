import os
import json
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data_store.json")

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def default_store():
    return {
        "parsed": [],
        "cronMap": {},
        "inicioMap": {},
        "etapasList": [],
        "equipeMap": {},
        "etapaObraMap": {},
        "statusPrazoMap": {},
        "saved_at": None,
        "sync_status": "empty"
    }

def load_store():
    if not os.path.exists(DATA_FILE):
        data = default_store()
        save_store(data)
        return data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = default_store()
        for k, v in base.items():
            data.setdefault(k, v)
        return data
    except Exception:
        data = default_store()
        save_store(data)
        return data

def save_store(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "dashboard.html")

@app.get("/dashboard.html")
def dashboard():
    return send_from_directory(BASE_DIR, "dashboard.html")

@app.get("/api/health")
def health():
    data = load_store()
    return jsonify({
        "ok": True,
        "time": now_iso(),
        "records": len(data.get("parsed", [])),
        "saved_at": data.get("saved_at"),
        "sync_status": data.get("sync_status")
    })

@app.get("/api/data")
def api_data():
    return jsonify(load_store())

@app.post("/api/save")
def api_save():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "JSON inválido"}), 400
    data = default_store()
    for k in data.keys():
      if k in payload:
        data[k] = payload[k]
    data["saved_at"] = now_iso()
    data["sync_status"] = "synced"
    save_store(data)
    return jsonify({"ok": True, "saved_at": data["saved_at"], "records": len(data.get("parsed", []))})

@app.post("/api/reset")
def api_reset():
    save_store(default_store())
    return jsonify({"ok": True})

@app.route("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        return jsonify({"ok": False, "error": "Rota API não encontrada"}), 404
    full = os.path.join(BASE_DIR, path)
    if os.path.isfile(full):
        return send_from_directory(BASE_DIR, path)
    return send_from_directory(BASE_DIR, "dashboard.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)

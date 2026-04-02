import os, json
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, unquote
from flask import Flask, jsonify, request, send_from_directory
try:
    import pg8000
except Exception:
    pg8000 = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data_store.json")
app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def default_store():
    return {"parsed":[],"cronMap":{},"inicioMap":{},"etapasList":[],"equipeMap":{},"etapaObraMap":{},"statusPrazoMap":{},"saved_at":None,"sync_status":"empty"}

def db_url():
    return os.environ.get("DATABASE_URL") or os.environ.get("RENDER_POSTGRES_URL")

def parse_db_url(url):
    p=urlparse(url); q=parse_qs(p.query); sslmode=(q.get("sslmode",[""])[0] or "").lower(); use_ssl=sslmode not in ("","disable")
    return {"user":unquote(p.username or ""),"password":unquote(p.password or ""),"host":p.hostname or "","port":p.port or 5432,"database":(p.path or "/")[1:],"ssl_context":True if use_ssl else False}

def get_conn():
    url=db_url()
    if not url or pg8000 is None: return None
    return pg8000.connect(**parse_db_url(url))

def save_file_store(data):
    with open(DATA_FILE,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)

def load_file_store():
    if not os.path.exists(DATA_FILE):
        data=default_store(); save_file_store(data); return data
    try:
        with open(DATA_FILE,"r",encoding="utf-8") as f: data=json.load(f)
        for k,v in default_store().items(): data.setdefault(k,v)
        return data
    except Exception:
        data=default_store(); save_file_store(data); return data

def ensure_db():
    conn=get_conn()
    if conn is None: return False
    try:
        cur=conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS dashboard_store (store_key TEXT PRIMARY KEY, payload JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
        cur.execute("INSERT INTO dashboard_store (store_key, payload, updated_at) VALUES ('main', %s, NOW()) ON CONFLICT (store_key) DO NOTHING", (json.dumps(default_store()),))
        conn.commit()
        return True
    finally:
        conn.close()

def load_store():
    if ensure_db():
        conn=get_conn()
        try:
            cur=conn.cursor(); cur.execute("SELECT payload FROM dashboard_store WHERE store_key='main'")
            row=cur.fetchone()
            if row and row[0]:
                payload=row[0]
                if isinstance(payload,str): payload=json.loads(payload)
                for k,v in default_store().items(): payload.setdefault(k,v)
                return payload
        finally:
            conn.close()
    return load_file_store()

def save_store(data):
    data["saved_at"]=now_iso(); data["sync_status"]="synced"
    if ensure_db():
        conn=get_conn()
        try:
            cur=conn.cursor()
            cur.execute("INSERT INTO dashboard_store (store_key, payload, updated_at) VALUES ('main', %s, NOW()) ON CONFLICT (store_key) DO UPDATE SET payload=EXCLUDED.payload, updated_at=NOW()", (json.dumps(data),))
            conn.commit(); return
        finally:
            conn.close()
    save_file_store(data)

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"]="no-store, no-cache, must-revalidate, max-age=0"; response.headers["Pragma"]="no-cache"; return response

@app.get("/")
def home():
    return send_from_directory(BASE_DIR,"dashboard.html")

@app.get("/dashboard.html")
def dashboard():
    return send_from_directory(BASE_DIR,"dashboard.html")

@app.get("/api/health")
def health():
    data=load_store(); using_db=bool(db_url() and pg8000 is not None)
    return jsonify({"ok":True,"time":now_iso(),"records":len(data.get("parsed",[])),"saved_at":data.get("saved_at"),"sync_status":data.get("sync_status"),"storage":"postgres" if using_db else "file_fallback"})

@app.get("/api/data")
def api_data():
    return jsonify(load_store())

@app.post("/api/save")
def api_save():
    payload=request.get_json(silent=True)
    if not isinstance(payload,dict): return jsonify({"ok":False,"error":"JSON inválido"}),400
    data=default_store()
    for k in data.keys():
        if k in payload: data[k]=payload[k]
    save_store(data)
    return jsonify({"ok":True,"saved_at":data["saved_at"],"records":len(data.get("parsed",[])),"storage":"postgres" if (db_url() and pg8000 is not None) else "file_fallback"})

@app.post("/api/reset")
def api_reset():
    save_store(default_store()); return jsonify({"ok":True})

@app.route("/<path:path>")
def static_files(path):
    if path.startswith("api/"): return jsonify({"ok":False,"error":"Rota API não encontrada"}),404
    full=os.path.join(BASE_DIR,path)
    if os.path.isfile(full): return send_from_directory(BASE_DIR,path)
    return send_from_directory(BASE_DIR,"dashboard.html")

if __name__=="__main__":
    port=int(os.environ.get("PORT",8000))
    app.run(host="0.0.0.0", port=port, debug=False)

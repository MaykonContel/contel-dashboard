import csv
import io
import json
import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data_store.json"
HTML_FILE = BASE_DIR / "dashboard.html"

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

def to_iso(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day).isoformat()
    return str(v)

def parse_csv_bytes(raw_bytes):
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = [dict(r) for r in reader if any(str(v or "").strip() for v in r.values())]
    return {
        "planRows": rows,
        "cronMap": {},
        "inicioMap": {},
        "etapasList": [],
        "equipeMap": {},
        "etapaObraMap": {},
        "statusPrazoMap": {},
        "updated_at": datetime.now().isoformat(),
    }

def parse_workbook_bytes(raw_bytes):
    wb = load_workbook(io.BytesIO(raw_bytes), data_only=True)

    sn_plan = next((s for s in wb.sheetnames if "PLANEJAMENTO" in s.upper()), wb.sheetnames[0])
    ws = wb[sn_plan]
    headers = [str(ws.cell(1, c).value).strip() if ws.cell(1, c).value is not None else "" for c in range(1, ws.max_column + 1)]
    plan_rows = []
    for r in range(2, ws.max_row + 1):
        row_dict = {}
        empty = True
        for c, h in enumerate(headers, start=1):
            if not h:
                continue
            val = ws.cell(r, c).value
            if val not in (None, ""):
                empty = False
            row_dict[h] = to_iso(val) if isinstance(val, (datetime, date)) else val
        if not empty:
            plan_rows.append(row_dict)

    cron_map = {}
    inicio_map = {}
    status_prazo_map = {}
    sn_cron = next((s for s in wb.sheetnames if "CRONOGRAMA" in s.upper()), None)
    if sn_cron:
        ws = wb[sn_cron]
        headers = [str(ws.cell(1, c).value).strip() if ws.cell(1, c).value is not None else "" for c in range(1, ws.max_column + 1)]
        idx = {h.upper(): i + 1 for i, h in enumerate(headers) if h}
        for r in range(2, ws.max_row + 1):
            idv = ws.cell(r, idx.get("ID SITE", 1)).value
            if not idv:
                continue
            key = str(idv).strip().upper()
            iv = ws.cell(r, idx.get("INÍCIO", idx.get("INICIO", 6))).value if idx else ws.cell(r, 6).value
            fv = ws.cell(r, idx.get("FIM", 7)).value if idx else ws.cell(r, 7).value
            sv = ws.cell(r, idx.get("STATUS", 8)).value if idx else ws.cell(r, 8).value
            inicio_map[key] = to_iso(iv)
            cron_map[key] = to_iso(fv)
            if sv not in (None, ""):
                status_prazo_map[key] = str(sv)

    etapas_list = []
    sn_conf = next((s for s in wb.sheetnames if "CONFIGURA" in s.upper()), None)
    if sn_conf:
        ws = wb[sn_conf]
        capture = False
        for r in range(1, ws.max_row + 1):
            val = ws.cell(r, 1).value
            sval = str(val).strip() if val is not None else ""
            if not sval:
                continue
            if "LISTA" in sval.upper() and "ETAPA" in sval.upper():
                capture = True
                continue
            if capture:
                if "LISTA" in sval.upper():
                    break
                etapas_list.append(sval)

    equipe_map = {}
    sn_eq = next((s for s in wb.sheetnames if "EQUIPE" in s.upper() and "ETAPA" not in s.upper()), None)
    if sn_eq:
        ws = wb[sn_eq]
        for r in range(2, ws.max_row + 1):
            idv = ws.cell(r, 1).value
            if not idv:
                continue
            members = []
            for c_nome, c_val in ((2, 3), (4, 5), (6, 7)):
                nome = ws.cell(r, c_nome).value
                val = ws.cell(r, c_val).value
                if nome not in (None, ""):
                    num = None
                    if isinstance(val, (int, float)):
                        num = float(val)
                    else:
                        sval = str(val or "").strip().replace(",", ".")
                        try:
                            num = float(sval) if sval else None
                        except ValueError:
                            num = None
                    members.append({"nome": str(nome).strip(), "valor": num})
            if members:
                equipe_map[str(idv).strip().upper()] = members

    etapa_obra_map = {}
    sn_eo = next((s for s in wb.sheetnames if "ETAPA OBRA" in s.upper() or "ETAPA_OBRA" in s.upper()), None)
    if sn_eo:
        ws = wb[sn_eo]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        for r in range(2, ws.max_row + 1):
            idv = ws.cell(r, 1).value
            if not idv:
                continue
            etapas = []
            for c in range(2, ws.max_column + 1):
                cellv = ws.cell(r, c).value
                truthy = False
                if isinstance(cellv, str):
                    truthy = cellv.strip().upper() in ("SIM", "X", "OK", "TRUE")
                elif isinstance(cellv, bool):
                    truthy = cellv
                if truthy:
                    h = headers[c - 1]
                    if h not in (None, ""):
                        etapas.append(str(h).strip())
            if etapas:
                etapa_obra_map[str(idv).strip().upper()] = etapas

    return {
        "planRows": plan_rows,
        "cronMap": cron_map,
        "inicioMap": inicio_map,
        "etapasList": etapas_list,
        "equipeMap": equipe_map,
        "etapaObraMap": etapa_obra_map,
        "statusPrazoMap": status_prazo_map,
        "updated_at": datetime.now().isoformat(),
    }

def read_payload():
    if not DATA_FILE.exists():
        return {
            "planRows": [],
            "cronMap": {},
            "inicioMap": {},
            "etapasList": [],
            "equipeMap": {},
            "etapaObraMap": {},
            "statusPrazoMap": {},
            "updated_at": datetime.now().isoformat(),
        }
    with DATA_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_payload(payload):
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "dashboard.html")

@app.get("/api/data")
def api_data():
    return jsonify(read_payload())

@app.post("/api/upload-xlsx")
def upload_xlsx():
    if "file" not in request.files:
        return "Arquivo não enviado.", 400
    file = request.files["file"]
    filename = (file.filename or "").lower()
    raw = file.read()
    if not raw:
        return "Arquivo vazio.", 400
    try:
        if filename.endswith(".csv"):
            payload = parse_csv_bytes(raw)
        else:
            payload = parse_workbook_bytes(raw)
        write_payload(payload)
        return jsonify(payload)
    except Exception as e:
        return f"Falha ao processar arquivo: {e}", 400

@app.get("/api/health")
def health():
    data = read_payload()
    return jsonify({"ok": True, "rows": len(data.get("planRows", [])), "updated_at": data.get("updated_at")})

@app.get("/<path:path>")
def static_proxy(path):
    return send_from_directory(BASE_DIR, path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

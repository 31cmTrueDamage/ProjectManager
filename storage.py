import os, sys, json, re, copy, threading
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

# ── Load .env (MONGODB_URI lives here) ───────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# ── MongoDB connection ────────────────────────────────────────────────────────
_client     = None
_db         = None
_col        = None   # projects collection
_col_lock   = threading.Lock()

def _get_col():
    """Lazy-connect and return the projects collection."""
    global _client, _db, _col
    if _col is None:
        uri     = os.getenv("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI not set — add it to your .env file.")
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _db     = _client["projectmanager"]
        _col    = _db["projects"]
        # Index on order field for fast sorted reads
        _col.create_index("order")
    return _col


# ── Helpers ───────────────────────────────────────────────────────────────────
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"

def _parse_notes(raw) -> list:
    """Normalize notes — always returns a list of {author, time, text} dicts."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    if str(raw).strip():
        return [{"author": "?", "time": "", "text": str(raw).strip()}]
    return []

def _to_doc(proj: dict) -> dict:
    """Convert an in-memory project dict to a MongoDB document."""
    doc = copy.deepcopy(proj)
    # Store _id as the slug-based file key so upserts are idempotent
    doc["_id"] = doc.pop("file")
    # Normalise notes on every task
    for t in doc.get("tasks", []):
        t["notes"] = _parse_notes(t.get("notes"))
    return doc

def _from_doc(doc: dict) -> dict:
    """Convert a MongoDB document back to an in-memory project dict."""
    proj = dict(doc)
    proj["file"] = proj.pop("_id")
    for t in proj.get("tasks", []):
        t["notes"] = _parse_notes(t.get("notes"))
    return proj


# ── Settings (still local — per-user preference) ──────────────────────────────
def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"dark_mode": False, "username": "you"}

def save_settings(data: dict) -> None:
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── In-memory cache ───────────────────────────────────────────────────────────
_cache = None

def _load_from_db() -> list:
    col = _get_col()
    docs = col.find({}, sort=[("order", 1)])
    return [_from_doc(d) for d in docs]

def read_projects() -> list:
    """Return in-memory project list, fetching from MongoDB on first call."""
    global _cache
    if _cache is None:
        _cache = _load_from_db()
    return _cache

def invalidate_cache() -> None:
    global _cache
    _cache = None


# ── Async write helpers ───────────────────────────────────────────────────────
def _upsert(snapshot: dict) -> None:
    """Upsert a single project document. Runs in a background thread."""
    try:
        col = _get_col()
        doc = _to_doc(snapshot)
        with _col_lock:
            col.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception as e:
        print(f"[storage] write error: {e}")

def _delete(file_id: str) -> None:
    """Delete a project document by its _id. Runs in a background thread."""
    try:
        col = _get_col()
        with _col_lock:
            col.delete_one({"_id": file_id})
    except Exception as e:
        print(f"[storage] delete error: {e}")


# ── Public API ────────────────────────────────────────────────────────────────
def write_project(proj: dict, touch: bool = True) -> None:
    """Update project in memory instantly, sync to MongoDB in background."""
    if touch:
        proj["updated"] = now_str()
    snapshot = copy.deepcopy(proj)
    threading.Thread(target=_upsert, args=(snapshot,), daemon=True).start()

def delete_project_file(proj: dict) -> None:
    """Remove project from cache and delete from MongoDB."""
    global _cache
    cache = read_projects()
    if proj in cache:
        cache.remove(proj)
    file_id = proj.get("file")
    if file_id:
        threading.Thread(target=_delete, args=(file_id,), daemon=True).start()

def get_stats() -> tuple:
    """Compute stats purely from memory — zero DB calls."""
    projects = read_projects()
    return (
        len(projects),
        sum(t["done"] for p in projects for t in p["tasks"]),
        sum(not t["done"] for p in projects for t in p["tasks"]),
    )
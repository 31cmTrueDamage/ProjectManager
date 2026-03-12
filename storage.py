import os, sys, json, re, copy, threading
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# ── Roles ─────────────────────────────────────────────────────────────────────
ROLES        = ["owner", "editor", "viewer"]
ROLE_LABELS  = {"owner": "Owner", "editor": "Editor", "viewer": "Viewer"}

# Permissions per role
CAN_DELETE_PROJECT = {"owner"}
CAN_MANAGE_MEMBERS = {"owner"}
CAN_EDIT_TASKS     = {"owner", "editor"}
CAN_ADD_TASKS      = {"owner", "editor"}
CAN_ADD_NOTES      = {"owner", "editor"}

def get_role(proj: dict, uid: str) -> str:
    """Return the role of uid in proj. Returns 'viewer' if member but no role set."""
    if proj.get("owner_uid") == uid:
        return "owner"
    for m in proj.get("members", []):
        if m.get("uid") == uid:
            return m.get("role", "viewer")
    return "viewer"

def can(proj: dict, uid: str, permission: set) -> bool:
    return get_role(proj, uid) in permission


# ── MongoDB ───────────────────────────────────────────────────────────────────
_client = _db = _projects_col = _invites_col = _users_col = None
_col_lock = threading.Lock()
_db_lock  = threading.Lock()


def _connect():
    """Create a fresh MongoClient and wire up all collection references."""
    global _client, _db, _projects_col, _invites_col, _users_col
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("MONGODB_URI not set in .env")
    # socketTimeoutMS / connectTimeoutMS kept short so reconnects are fast.
    # heartbeatFrequencyMS keeps the connection alive during idle periods so
    # the first interaction after the app sits unused doesn't pay a full
    # reconnect penalty (~1-3 s).
    _client = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        socketTimeoutMS=10000,
        connectTimeoutMS=5000,
        heartbeatFrequencyMS=10000,   # ping every 10 s — keeps connection warm
        maxPoolSize=5,
    )
    _db           = _client["projectmanager"]
    _projects_col = _db["projects"]
    _invites_col  = _db["invitations"]
    _users_col    = _db["users"]
    _projects_col.create_index("order")
    _invites_col.create_index("to_email")
    _users_col.create_index("email", unique=True)


def _get_db():
    global _db
    with _db_lock:
        if _db is None:
            _connect()
        else:
            # Fast connectivity check — reconnect silently if the server
            # dropped us while the app was left idle.
            try:
                _client.admin.command("ping")
            except Exception:
                try:
                    _client.close()
                except Exception:
                    pass
                _connect()
    return _db


# ── Helpers ───────────────────────────────────────────────────────────────────
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"

def _parse_notes(raw) -> list:
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
    return [{"author": "?", "time": "", "text": str(raw).strip()}] if str(raw).strip() else []

def _to_doc(proj: dict) -> dict:
    doc = copy.deepcopy(proj)
    doc["_id"] = doc.pop("file")
    for t in doc.get("tasks", []):
        t["notes"] = _parse_notes(t.get("notes"))
    return doc

def _from_doc(doc: dict) -> dict:
    proj = dict(doc)
    proj["file"] = proj.pop("_id")
    for t in proj.get("tasks", []):
        t["notes"] = _parse_notes(t.get("notes"))
    return proj


# ── Settings ──────────────────────────────────────────────────────────────────
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


# ── Users ─────────────────────────────────────────────────────────────────────
def upsert_user(session: dict) -> None:
    try:
        db = _get_db()
        db["users"].replace_one(
            {"uid": session["uid"]},
            {"uid": session["uid"], "display_name": session.get("display_name", ""),
             "email": session.get("email", ""), "photo_url": session.get("photo_url", "")},
            upsert=True,
        )
    except Exception as e:
        print(f"[storage] upsert_user error: {e}")

def lookup_user_by_email(email: str) -> dict | None:
    try:
        doc = _get_db()["users"].find_one({"email": email.lower().strip()})
        if doc:
            return {"uid": doc["uid"], "display_name": doc.get("display_name", email),
                    "email": doc["email"], "photo_url": doc.get("photo_url", "")}
    except Exception as e:
        print(f"[storage] lookup_user error: {e}")
    return None


# ── In-memory project cache ───────────────────────────────────────────────────
_cache       = None
_current_uid = None

def set_current_user(uid: str) -> None:
    global _current_uid, _cache
    if _current_uid != uid:
        _current_uid = uid
        _cache = None

def read_projects() -> list:
    global _cache
    if _cache is None:
        db = _get_db()
        query = {"$or": [{"owner_uid": _current_uid},
                         {"members.uid": _current_uid}]} if _current_uid else {}
        _cache = [_from_doc(d) for d in db["projects"].find(query, sort=[("order", 1)])]
    return _cache

def invalidate_cache() -> None:
    global _cache
    _cache = None


# ── Project writes ────────────────────────────────────────────────────────────
def _upsert_proj(snapshot: dict) -> None:
    try:
        doc = _to_doc(snapshot)
        with _col_lock:
            _get_db()["projects"].replace_one({"_id": doc["_id"]}, doc, upsert=True)
    except Exception as e:
        print(f"[storage] write error: {e}")

def _delete_proj(file_id: str) -> None:
    try:
        with _col_lock:
            _get_db()["projects"].delete_one({"_id": file_id})
    except Exception as e:
        print(f"[storage] delete error: {e}")

def prewarm_connection() -> None:
    """Call this in a daemon thread right after login so the first real
    DB operation doesn't pay the connection-setup cost."""
    try:
        _get_db()
    except Exception as e:
        print(f"[storage] prewarm error: {e}")


def write_project(proj: dict, touch: bool = True) -> None:
    if touch:
        proj["updated"] = now_str()
    if not proj.get("owner_uid") and _current_uid:
        proj["owner_uid"] = _current_uid
    proj.setdefault("members", [])
    snapshot = copy.deepcopy(proj)
    threading.Thread(target=_upsert_proj, args=(snapshot,), daemon=True).start()

def delete_project_file(proj: dict) -> None:
    global _cache
    cache = read_projects()
    if proj in cache:
        cache.remove(proj)
    if fid := proj.get("file"):
        threading.Thread(target=_delete_proj, args=(fid,), daemon=True).start()

def get_stats() -> tuple:
    projects = read_projects()
    tasks = [t for p in projects for t in p["tasks"]]
    def _status(t):
        if "status" in t: return t["status"]
        return "done" if t.get("done") else "todo"
    todo        = sum(1 for t in tasks if _status(t) == "todo")
    in_progress = sum(1 for t in tasks if _status(t) == "in_progress")
    done        = sum(1 for t in tasks if _status(t) == "done")
    return (len(projects), todo, in_progress, done)


# ── Members ───────────────────────────────────────────────────────────────────
def set_member_role(proj: dict, uid: str, role: str) -> None:
    """Change an existing member's role."""
    for m in proj.get("members", []):
        if m["uid"] == uid:
            m["role"] = role
            break
    write_project(proj)

def remove_member(proj: dict, uid: str) -> None:
    """Demote member to viewer (they keep read access)."""
    for m in proj.get("members", []):
        if m["uid"] == uid:
            m["role"] = "viewer"
            break
    write_project(proj)


# ── Invitations ───────────────────────────────────────────────────────────────
def send_invitation(proj: dict, from_session: dict, to_email: str, role: str) -> str:
    """
    Create a pending invitation. Returns 'ok', 'already_member', 'pending', or 'not_found'.
    The invitee does NOT need to be registered yet — invite by email.
    """
    to_email = to_email.lower().strip()

    # Already a member?
    owner_email = from_session.get("email", "")
    if to_email == owner_email.lower():
        return "self"
    if any(m.get("email", "").lower() == to_email for m in proj.get("members", [])):
        return "already_member"

    db = _get_db()
    # Already a pending invite?
    existing = db["invitations"].find_one({
        "project_id": proj["file"], "to_email": to_email, "status": "pending"
    })
    if existing:
        return "pending"

    db["invitations"].insert_one({
        "project_id":   proj["file"],
        "project_name": proj["name"],
        "project_color": proj.get("color", "#6366F1"),
        "from_uid":     from_session["uid"],
        "from_name":    from_session.get("display_name", "Someone"),
        "to_email":     to_email,
        "role":         role,
        "status":       "pending",
        "created":      now_str(),
    })
    return "ok"

def get_pending_invitations(email: str) -> list:
    """Return all pending invitations for the given email."""
    try:
        db = _get_db()
        return list(db["invitations"].find(
            {"to_email": email.lower().strip(), "status": "pending"}
        ))
    except Exception as e:
        print(f"[storage] get_invitations error: {e}")
        return []

def respond_invitation(invite_id, accept: bool, session: dict) -> None:
    """Accept or decline an invitation. On accept, adds user to project members."""
    from bson import ObjectId
    db = _get_db()
    inv = db["invitations"].find_one({"_id": ObjectId(str(invite_id))})
    if not inv:
        return

    status = "accepted" if accept else "declined"
    db["invitations"].update_one(
        {"_id": ObjectId(str(invite_id))},
        {"$set": {"status": status}}
    )

    if accept:
        proj_doc = db["projects"].find_one({"_id": inv["project_id"]})
        if proj_doc:
            proj = _from_doc(proj_doc)
            members = proj.setdefault("members", [])
            if not any(m["uid"] == session["uid"] for m in members):
                members.append({
                    "uid":          session["uid"],
                    "display_name": session.get("display_name", ""),
                    "email":        session.get("email", ""),
                    "role":         inv.get("role", "viewer"),
                })
            write_project(proj, touch=False)
            # Add to local cache
            cache = read_projects()
            if not any(p["file"] == proj["file"] for p in cache):
                cache.append(proj)
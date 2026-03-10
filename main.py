import flet as ft
from datetime import datetime
import os, json, re, time, threading

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR  = os.path.join(BASE_DIR, "projects")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
os.makedirs(PROJECTS_DIR, exist_ok=True)

PRIORITY_COLORS = {"HIGH": "#EF4444", "MED": "#F59E0B", "LOW": "#10B981"}
PRIORITY_BG     = {"HIGH": "#FEF2F2", "MED": "#FFFBEB", "LOW": "#ECFDF5"}
PRIORITY_BG_DK  = {"HIGH": "#450a0a", "MED": "#451a03", "LOW": "#052e16"}
PROJECT_PALETTE = ["#6366F1","#2563EB","#0891B2","#059669","#D97706","#DC2626","#7C3AED","#DB2777"]

LIGHT = {
    "bg": "#F8FAFC", "sidebar": "white", "card": "white",
    "border": "#F1F5F9", "border2": "#E2E8F0",
    "text": "#0F172A", "text2": "#475569", "text3": "#94A3B8",
    "nav_sel_bg": "#EFF6FF", "nav_hover": "#F8FAFC",
    "accent": "#2563EB", "accent_hover": "#1D4ED8",
    "divider": "#F1F5F9", "input_bg": "white",
    "task_done_text": "#94A3B8",
    "danger": "#EF4444", "danger_hover": "#B91C1C",
    "success": "#10B981", "overlay": "#00000055", "modal": "white",
}
DARK = {
    "bg": "#0F172A", "sidebar": "#1E293B", "card": "#1E293B",
    "border": "#334155", "border2": "#475569",
    "text": "#F1F5F9", "text2": "#94A3B8", "text3": "#64748B",
    "nav_sel_bg": "#1D3461", "nav_hover": "#263352",
    "accent": "#3B82F6", "accent_hover": "#2563EB",
    "divider": "#334155", "input_bg": "#0F172A",
    "task_done_text": "#475569",
    "danger": "#EF4444", "danger_hover": "#B91C1C",
    "success": "#10B981", "overlay": "#000000BB", "modal": "#1E293B",
}

# ── Settings ──────────────────────────────────────────────────────────────────
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"dark_mode": False, "username": "you"}

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Markdown ──────────────────────────────────────────────────────────────────
def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def _parse_notes(raw):
    """Always returns a list of {author, time, text} dicts."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    # Legacy plain text — wrap as a single note
    if raw.strip():
        return [{"author": "?", "time": "", "text": raw.strip()}]
    return []


def write_project(proj, touch=True):
    if touch:
        proj["updated"] = now_str()
    lines = ["---",
             f"name: {proj['name']}",
             f"color: {proj['color']}",
             f"created: {proj['created']}",
             f"updated: {proj.get('updated', proj['created'])}",
             f"order: {proj.get('order', 0)}",
             f"desc: {proj.get('desc','')}", "---", ""]
    for t in proj["tasks"]:
        check   = "x" if t["done"] else " "
        desc    = f" | {t.get('desc','')}"
        notes   = f" || {json.dumps(t.get('notes') if isinstance(t.get('notes'), list) else ([{'author':'?','time':'','text':t['notes']}] if t.get('notes') else []), ensure_ascii=False)}"
        tcreate = f" |c| {t.get('created', '')}"
        tupdate = f" |u| {t.get('updated', '')}"
        lines.append(f"- [{check}] [{t['priority']}] {t['text']}{desc}{notes}{tcreate}{tupdate}")
    with open(os.path.join(PROJECTS_DIR, proj["file"]), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def read_projects():
    projects = []
    for fname in sorted(os.listdir(PROJECTS_DIR)):
        if not fname.endswith(".md"): continue
        try:
            with open(os.path.join(PROJECTS_DIR, fname), encoding="utf-8") as f:
                content = f.read()
            meta, _, body = content.partition("---\n")[2].partition("---\n")
            info = {}
            for line in meta.strip().splitlines():
                k, _, v = line.partition(": ")
                info[k.strip()] = v.strip()
            tasks = []
            for line in body.strip().splitlines():
                m = re.match(
                    r"- \[( |x)\] \[(\w+)\] (.+?)"
                    r"(?:\s*\|\s*(.*?))?"
                    r"(?:\s*\|\|\s*(.*?))?"
                    r"(?:\s*\|c\|\s*(.*?))?"
                    r"(?:\s*\|u\|\s*(.*))?$", line)
                if m:
                    tasks.append({
                        "done":     m.group(1) == "x",
                        "priority": m.group(2),
                        "text":     m.group(3).strip(),
                        "desc":     (m.group(4) or "").strip(),
                        "notes":    _parse_notes((m.group(5) or "").strip()),
                        "created":  (m.group(6) or "").strip(),
                        "updated":  (m.group(7) or "").strip(),
                    })
            projects.append({
                "name":    info.get("name", fname),
                "color":   info.get("color", "#6366F1"),
                "created": info.get("created", ""),
                "updated": info.get("updated", ""),
                "order":   int(info.get("order", 0)),
                "desc":    info.get("desc", ""),
                "tasks":   tasks,
                "file":    fname,
            })
        except Exception:
            pass
    projects.sort(key=lambda p: p["order"])
    return projects

def get_stats():
    projects = read_projects()
    return (len(projects),
            sum(t["done"] for p in projects for t in p["tasks"]),
            sum(not t["done"] for p in projects for t in p["tasks"]))

def get_greeting():
    h = datetime.now().hour
    if h < 12: return "Good morning", "☀️"
    if h < 17: return "Good afternoon", "🌤️"
    return "Good evening", "🌙"

def pill(label, color, bg):
    return ft.Container(
        content=ft.Text(label, size=10, color=color, weight=ft.FontWeight.W_600),
        bgcolor=bg, border_radius=20,
        padding=ft.Padding.symmetric(vertical=2, horizontal=8),
    )

# ══════════════════════════════════════════════════════════════════════════════
# NAV ITEM
# ══════════════════════════════════════════════════════════════════════════════
class NavItem(ft.Container):
    def __init__(self, icon, label, on_click_handler, th, selected=False):
        super().__init__()
        self.selected = selected
        self.label_text = label
        self.on_click_handler = on_click_handler
        self.th = th
        self.padding = ft.Padding.symmetric(vertical=10, horizontal=15)
        self.border_radius = 10
        self.bgcolor = th["nav_sel_bg"] if selected else "transparent"
        self.animate = ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT)
        self.on_hover = self.hover_effect
        self.on_click = self.handle_click
        self.indicator = ft.Container(width=3, height=22,
            bgcolor=th["accent"] if selected else "transparent", border_radius=2,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT))
        self.icon_ctl = ft.Icon(icon, color=th["accent"] if selected else th["text3"], size=18)
        self.text_ctl = ft.Text(label, color=th["accent"] if selected else th["text2"],
                                weight=ft.FontWeight.W_500, size=13)
        self.content = ft.Row([self.indicator, self.icon_ctl, self.text_ctl],
                               spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def handle_click(self, e): self.on_click_handler(self)

    def set_theme(self, th):
        self.th = th
        self.set_state(self.selected)

    def set_state(self, active):
        self.selected          = active
        self.bgcolor           = self.th["nav_sel_bg"] if active else "transparent"
        self.indicator.bgcolor = self.th["accent"]     if active else "transparent"
        self.icon_ctl.color    = self.th["accent"]     if active else self.th["text3"]
        self.text_ctl.color    = self.th["accent"]     if active else self.th["text2"]
        self.update()

    def hover_effect(self, e):
        if not self.selected:
            self.bgcolor = self.th["nav_hover"] if e.data == "true" else "transparent"
            self.update()

# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════
def build_home_screen(go_to_projects, th, username, page=None):
    greeting, emoji = get_greeting()
    day_name = datetime.now().strftime("%A")
    date_str = datetime.now().strftime("%B %d, %Y")
    active, done, pending = get_stats()

    def stat_card(icon, value, label, color, bg_l, bg_d):
        bg = bg_d if th == DARK else bg_l
        return ft.Container(
            content=ft.Column([
                ft.Container(content=ft.Icon(icon, color=color, size=18),
                             width=36, height=36, bgcolor=bg, border_radius=10,
                             alignment=ft.Alignment.CENTER),
                ft.Text(str(value), size=22, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Text(label, size=11, color=th["text3"]),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20, border_radius=14,
            bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
            expand=True, alignment=ft.Alignment.CENTER,
        )

    _vp_lbl  = ft.Text("View Projects", color="#FFFFFF", weight=ft.FontWeight.W_600, size=13)
    _vp_icon = ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color="#FFFFFF", size=16)
    projects_btn = ft.Container(
        content=ft.Row([_vp_lbl, _vp_icon], alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True),
        bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=14, horizontal=28),
        on_click=go_to_projects, width=200, alignment=ft.Alignment.CENTER,
    )
    def _vp_hover(e):
        try:
            if e.data == "true":
                projects_btn.bgcolor = "transparent"
                _vp_lbl.color = th["accent"]; _vp_icon.color = th["accent"]
            else:
                projects_btn.bgcolor = th["accent"]
                _vp_lbl.color = "#FFFFFF"; _vp_icon.color = "#FFFFFF"
            page.update()
        except Exception:
            pass
    projects_btn.on_hover = _vp_hover

    return ft.Container(
        content=ft.Column([
            ft.Column([
                ft.Text(f"{emoji}  {greeting}, {username.capitalize() or 'there'}.", size=13,
                        color=th["text3"], weight=ft.FontWeight.W_500),
                ft.Text("Welcome back.", size=28, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Text(f"{day_name}, {date_str}", size=12, color=th["text3"]),
            ], spacing=4),
            ft.Divider(height=1, color=th["divider"]),
            ft.Text("At a Glance", size=12, color=th["text3"], weight=ft.FontWeight.W_600),
            ft.Row([
                stat_card(ft.Icons.FOLDER_ROUNDED,       active,  "Projects", "#6366F1", "#EEF2FF", "#1E1B4B"),
                stat_card(ft.Icons.CHECK_CIRCLE_ROUNDED, done,    "Done",     "#10B981", "#ECFDF5", "#064E3B"),
                stat_card(ft.Icons.SCHEDULE_ROUNDED,     pending, "Pending",  "#F59E0B", "#FFFBEB", "#451A03"),
            ], spacing=12),
            ft.Divider(height=1, color=th["divider"]),
            ft.Column([
                ft.Text("Ready to build?", size=14, color=th["text2"]),
                ft.Text("Pick up where you left off, or start something new.",
                        size=12, color=th["text3"]),
                ft.Container(height=4),
                projects_btn,
            ], spacing=4),
        ], spacing=20),
        padding=40, expand=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════
def build_projects_screen(page, th, refresh_home, username="you"):
    projects     = read_projects()
    selected_idx = [None]
    detail_col   = ft.Column([], spacing=0, expand=True)
    list_col     = ft.Column([], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    # ── confirm dialog ────────────────────────────────────────────────────────
    dlg = ft.AlertDialog(modal=True)

    def show_confirm(title, message, confirm_label, on_confirm, danger=True):
        c = th["danger"] if danger else th["accent"]
        def do_confirm(e):
            dlg.open = False
            page.update()
            on_confirm()
        def do_cancel(e):
            dlg.open = False
            page.update()
        dlg.title   = ft.Text(title, weight=ft.FontWeight.W_700, color=th["text"])
        dlg.content = ft.Text(message, color=th["text2"], size=13)
        dlg.bgcolor = th["modal"]
        dlg.actions = [
            ft.TextButton("Cancel", on_click=do_cancel,
                          style=ft.ButtonStyle(color=th["text3"])),
            ft.FilledButton(confirm_label, on_click=do_confirm,
                            style=ft.ButtonStyle(bgcolor=c, color="#FFFFFF")),
        ]
        if dlg not in page.overlay:
            page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ── toast ─────────────────────────────────────────────────────────────────
    def show_toast(message, success=True):
        page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color="white"),
            bgcolor=th["success"] if success else th["danger"],
            duration=2000,
        )
        page.snack_bar.open = True
        page.update()

    # ── accent button helper ──────────────────────────────────────────────────
    def accent_btn(label, icon_name, on_click, color=None, outline=False):
        c = color or th["accent"]
        if outline:
            ic  = ft.Icon(icon_name, color=c, size=13)
            lbl = ft.Text(label, color=c, size=12, weight=ft.FontWeight.W_500)
            btn = ft.Container(
                content=ft.Row([ic, lbl], spacing=5, alignment=ft.MainAxisAlignment.CENTER, tight=True),
                border=ft.Border.all(1.5, c), border_radius=8, bgcolor="transparent",
                padding=ft.Padding.symmetric(vertical=8, horizontal=14),
                on_click=on_click,
            )
            def h(e, b=btn, i=ic, l=lbl, col=c):
                try:
                    if e.data == "true":
                        b.bgcolor = col; i.color = "#FFFFFF"; l.color = "#FFFFFF"
                    else:
                        b.bgcolor = "transparent"; i.color = col; l.color = col
                    page.update()
                except Exception:
                    pass
            btn.on_hover = h
        else:
            ic   = ft.Icon(icon_name, color="#FFFFFF", size=13)
            txts = [] if not label else [ft.Text(label, color="#FFFFFF", size=12, weight=ft.FontWeight.W_500)]
            btn  = ft.Container(
                content=ft.Row([ic, *txts], spacing=5, alignment=ft.MainAxisAlignment.CENTER, tight=True),
                bgcolor=c, border=ft.Border.all(1.5, c), border_radius=8,
                padding=ft.Padding.symmetric(vertical=8, horizontal=14),
                on_click=on_click,
            )
            def h(e, b=btn, i=ic, ts=txts, col=c):
                try:
                    if e.data == "true":
                        b.bgcolor = "transparent"; i.color = col
                        for t in ts: t.color = col
                    else:
                        b.bgcolor = col; i.color = "#FFFFFF"
                        for t in ts: t.color = "#FFFFFF"
                    page.update()
                except Exception:
                    pass
            btn.on_hover = h
        return btn

    # ── task edit window ──────────────────────────────────────────────────────
    def build_task_edit_window(proj, task_idx, back_fn):
        task = proj["tasks"][task_idx]

        # ── priority selector state ───────────────────────────────────────────
        current_pri = [task["priority"]]
        pri_btns    = {}

        pri_meta = {
            "HIGH": {"label": "High",   "icon": ft.Icons.KEYBOARD_DOUBLE_ARROW_UP_ROUNDED,   "color": PRIORITY_COLORS["HIGH"], "bg_l": PRIORITY_BG["HIGH"],    "bg_d": PRIORITY_BG_DK["HIGH"]},
            "MED":  {"label": "Medium", "icon": ft.Icons.DRAG_HANDLE_ROUNDED,                 "color": PRIORITY_COLORS["MED"],  "bg_l": PRIORITY_BG["MED"],     "bg_d": PRIORITY_BG_DK["MED"]},
            "LOW":  {"label": "Low",    "icon": ft.Icons.KEYBOARD_DOUBLE_ARROW_DOWN_ROUNDED,  "color": PRIORITY_COLORS["LOW"],  "bg_l": PRIORITY_BG["LOW"],     "bg_d": PRIORITY_BG_DK["LOW"]},
        }

        def make_pri_btn(key):
            meta   = pri_meta[key]
            color  = meta["color"]
            bg     = meta["bg_d"] if th == DARK else meta["bg_l"]
            active = current_pri[0] == key

            icon_ctl = ft.Icon(meta["icon"], size=14,
                               color=color if active else th["text3"])
            lbl_ctl  = ft.Text(meta["label"], size=12, weight=ft.FontWeight.W_500,
                               color=color if active else th["text2"])
            btn = ft.Container(
                content=ft.Row([icon_ctl, lbl_ctl], spacing=6,
                               alignment=ft.MainAxisAlignment.CENTER,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                border_radius=8,
                border=ft.Border.all(1.5 if active else 1,
                                     color if active else th["border2"]),
                bgcolor=bg if active else "transparent",
                padding=ft.Padding.symmetric(vertical=9, horizontal=14),
                animate=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
                expand=True,
            )
            def on_pri_click(e, k=key, b=btn, ic=icon_ctl, lb=lbl_ctl):
                current_pri[0] = k
                for kk, bb in pri_btns.items():
                    m      = pri_meta[kk]
                    sel    = (kk == k)
                    c      = m["color"]
                    bg_sel = m["bg_d"] if th == DARK else m["bg_l"]
                    bb["btn"].bgcolor = bg_sel if sel else "transparent"
                    bb["btn"].border  = ft.Border.all(1.5 if sel else 1,
                                                      c if sel else th["border2"])
                    bb["icon"].color  = c if sel else th["text3"]
                    bb["lbl"].color   = c if sel else th["text2"]
                    bb["btn"].update()
            btn.on_click = on_pri_click

            def on_hover(e, b=btn, ic=icon_ctl, k=key):
                try:
                    if current_pri[0] != k:
                        b.bgcolor = (meta["bg_d"] if th == DARK else meta["bg_l"]) if e.data == "true" else "transparent"
                        b.update()
                except Exception:
                    pass
            btn.on_hover = on_hover

            pri_btns[key] = {"btn": btn, "icon": icon_ctl, "lbl": lbl_ctl}
            return btn

        pri_row = ft.Row(
            [make_pri_btn(k) for k in ["HIGH", "MED", "LOW"]],
            spacing=8,
        )

        # ── text fields ───────────────────────────────────────────────────────
        def styled_field(label, value, multiline=False, min_lines=1, hint=None):
            return ft.TextField(
                label=label,
                value=value,
                hint_text=hint,
                multiline=multiline,
                min_lines=min_lines,
                expand=True,
                bgcolor=th["input_bg"],
                border_color=th["border2"],
                focused_border_color=th["accent"],
                color=th["text"],
                label_style=ft.TextStyle(color=th["text3"], size=12),
                text_size=13,
                border_radius=10,
                content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            )

        name_tf  = styled_field("Task Title", task["text"])
        desc_tf  = styled_field("Short Description", task.get("desc", ""),
                                hint="Brief summary shown in the task list…")

        # ── status toggle ─────────────────────────────────────────────────────
        done_state = [task["done"]]
        status_icon = ft.Icon(
            ft.Icons.CHECK_CIRCLE_ROUNDED if task["done"] else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
            color=th["success"] if task["done"] else th["text3"],
            size=18,
        )
        status_lbl = ft.Text(
            "Completed" if task["done"] else "Pending",
            size=12, weight=ft.FontWeight.W_500,
            color=th["success"] if task["done"] else th["text2"],
        )
        status_btn = ft.Container(
            content=ft.Row([status_icon, status_lbl], spacing=8,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.Border.all(1, th["success"] if task["done"] else th["border2"]),
            bgcolor=(("#052e16" if th == DARK else "#ECFDF5") if task["done"] else "transparent"),
            border_radius=8,
            padding=ft.Padding.symmetric(vertical=9, horizontal=14),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
        )
        def toggle_status(e):
            done_state[0] = not done_state[0]
            d = done_state[0]
            status_icon.name  = ft.Icons.CHECK_CIRCLE_ROUNDED if d else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED
            status_icon.color = th["success"] if d else th["text3"]
            status_lbl.value  = "Completed" if d else "Pending"
            status_lbl.color  = th["success"] if d else th["text2"]
            status_btn.border = ft.Border.all(1, th["success"] if d else th["border2"])
            status_btn.bgcolor = ("#052e16" if th == DARK else "#ECFDF5") if d else "transparent"
            status_btn.update()
        status_btn.on_click = toggle_status

        # ── section label helper ──────────────────────────────────────────────
        def section_label(text, icon):
            return ft.Row([
                ft.Icon(icon, size=13, color=th["text3"]),
                ft.Text(text.upper(), size=10, weight=ft.FontWeight.W_700,
                        color=th["text3"],
                        style=ft.TextStyle(letter_spacing=0.8)),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── notes thread ──────────────────────────────────────────────────────
        # notes is always a list of {author, time, text}
        if not isinstance(task.get("notes"), list):
            task["notes"] = _parse_notes(task.get("notes", ""))

        def note_bubble(n):
            is_me = n["author"] == username
            bubble = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(n["author"][0].upper(), size=10,
                                           color="#FFFFFF", weight=ft.FontWeight.W_700),
                            width=24, height=24, border_radius=12,
                            bgcolor=th["accent"] if is_me else th["text3"],
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text(n["author"], size=11, weight=ft.FontWeight.W_600,
                                color=th["accent"] if is_me else th["text2"]),
                        ft.Container(expand=True),
                        ft.Text(n["time"], size=10, color=th["text3"]),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(n["text"], size=12, color=th["text"], selectable=True),
                ], spacing=4),
                bgcolor=th["nav_sel_bg"] if is_me else th["bg"],
                border=ft.Border.all(1, th["accent"] if is_me else th["border"]),
                border_radius=10,
                padding=ft.Padding.symmetric(vertical=10, horizontal=14),
            )
            return bubble

        notes_col = ft.Column(
            [note_bubble(n) for n in task["notes"]],
            spacing=8, scroll=ft.ScrollMode.AUTO,
        )
        notes_col.height = 220

        note_input = ft.TextField(
            hint_text="Write a note…",
            border_color=th["border2"], bgcolor=th["input_bg"], color=th["text"],
            text_size=13, expand=True, multiline=True, min_lines=2, max_lines=4,
            border_radius=10,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        _note_ic  = ft.Icon(ft.Icons.ADD_COMMENT_OUTLINED, color="#FFFFFF", size=14)
        _note_lbl = ft.Text("Add Note", color="#FFFFFF", size=12, weight=ft.FontWeight.W_500)
        note_add_btn = ft.Container(
            content=ft.Row([_note_ic, _note_lbl], spacing=6,
                           alignment=ft.MainAxisAlignment.CENTER, tight=True),
            bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
            border_radius=8, padding=ft.Padding.symmetric(vertical=10, horizontal=16),
        )
        def _note_hover(e):
            try:
                if e.data == "true":
                    note_add_btn.bgcolor = "transparent"
                    _note_ic.color = th["accent"]; _note_lbl.color = th["accent"]
                else:
                    note_add_btn.bgcolor = th["accent"]
                    _note_ic.color = "#FFFFFF"; _note_lbl.color = "#FFFFFF"
                page.update()
            except Exception:
                pass
        note_add_btn.on_hover = _note_hover

        def add_note(e):
            txt = note_input.value.strip()
            if not txt:
                return
            entry = {"author": username, "time": now_str(), "text": txt}
            task["notes"].append(entry)
            note_input.value = ""
            notes_col.controls.append(note_bubble(entry))
            write_project(proj)
            try: page.update()
            except Exception: pass

        note_add_btn.on_click = add_note
        note_input.on_submit  = add_note

        notes_section = ft.Column([
            notes_col,
            ft.Divider(height=1, color=th["divider"]),
            ft.Row([note_input, note_add_btn], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.END),
        ], spacing=10, expand=True)

        # ── save button ───────────────────────────────────────────────────────
        save_lbl  = ft.Text("Save Changes", color="#FFFFFF", size=13, weight=ft.FontWeight.W_600)
        save_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=15, visible=False)
        save_btn = ft.Container(
            content=ft.Row([save_icon, save_lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True),
            bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
            border_radius=9, padding=ft.Padding.symmetric(vertical=11, horizontal=22),
        )
        def _save_hover(e):
            try:
                if e.data == "true":
                    save_btn.bgcolor = "transparent"
                    save_lbl.color = th["accent"]; save_icon.color = th["accent"]
                else:
                    save_btn.bgcolor = th["accent"]
                    save_lbl.color = "#FFFFFF"; save_icon.color = "#FFFFFF"
                page.update()
            except Exception:
                pass
        save_btn.on_hover = _save_hover

        def save_task(e):
            txt = name_tf.value.strip()
            if not txt:
                show_toast("Task title is required.", success=False)
                return
            task.update({
                "text":     txt,
                "desc":     desc_tf.value.strip(),
                "priority": current_pri[0],
                "done":     done_state[0],
                "updated":  now_str(),
                "created":  task.get("created") or now_str(),
            })
            write_project(proj)
            show_toast("Task saved")
            back_fn()

        save_btn.on_click = save_task

        # ── delete button ─────────────────────────────────────────────────────
        _del_ic  = ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=th["danger"], size=14)
        _del_lbl = ft.Text("Delete Task", color=th["danger"], size=12, weight=ft.FontWeight.W_500)
        del_btn = ft.Container(
            content=ft.Row([_del_ic, _del_lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True),
            bgcolor="transparent", border=ft.Border.all(1.5, th["danger"]),
            border_radius=9, padding=ft.Padding.symmetric(vertical=11, horizontal=18),
        )
        def _del_hover(e):
            try:
                if e.data == "true":
                    del_btn.bgcolor = th["danger"]
                    _del_ic.color = "#FFFFFF"; _del_lbl.color = "#FFFFFF"
                else:
                    del_btn.bgcolor = "transparent"
                    _del_ic.color = th["danger"]; _del_lbl.color = th["danger"]
                page.update()
            except Exception:
                pass
        del_btn.on_hover = _del_hover

        def delete_task(e):
            def do():
                proj["tasks"].pop(task_idx)
                write_project(proj)
                show_toast("Task deleted", success=False)
                back_fn()
            show_confirm("Delete Task?", "Remove this task permanently?", "Delete", do)
        del_btn.on_click = delete_task
        save_btn.on_click = save_task

        # ── back button ───────────────────────────────────────────────────────
        _back_ic  = ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, color=th["text2"], size=15)
        _back_lbl = ft.Text("Back", color=th["text2"], size=12, weight=ft.FontWeight.W_500)
        back_btn = ft.Container(
            content=ft.Row([_back_ic, _back_lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True),
            bgcolor="transparent", border=ft.Border.all(1.5, th["border2"]),
            border_radius=9, padding=ft.Padding.symmetric(vertical=11, horizontal=16),
            on_click=lambda _: back_fn(),
        )
        def _back_hover(e):
            try:
                if e.data == "true":
                    back_btn.bgcolor = th["text2"]; back_btn.border = ft.Border.all(1.5, th["text2"])
                    _back_ic.color = "#FFFFFF"; _back_lbl.color = "#FFFFFF"
                else:
                    back_btn.bgcolor = "transparent"; back_btn.border = ft.Border.all(1.5, th["border2"])
                    _back_ic.color = th["text2"]; _back_lbl.color = th["text2"]
                page.update()
            except Exception:
                pass
        back_btn.on_hover = _back_hover

        # ── task number badge ─────────────────────────────────────────────────
        task_num = task_idx + 1
        total    = len(proj["tasks"])
        badge = ft.Container(
            content=ft.Text(f"Task {task_num} of {total}", size=11,
                            color=th["text3"], weight=ft.FontWeight.W_500),
            bgcolor=th["border"] if th == DARK else th["border"],
            border_radius=20,
            padding=ft.Padding.symmetric(vertical=4, horizontal=10),
        )

        # ── timestamps ────────────────────────────────────────────────────────
        def ts_row(label, value):
            return ft.Row([
                ft.Text(label, size=11, color=th["text3"], width=72),
                ft.Text(value or "—", size=11, color=th["text2"], weight=ft.FontWeight.W_500),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        ts_card = ft.Container(
            content=ft.Column([
                section_label("History", ft.Icons.HISTORY_ROUNDED),
                ts_row("Created",  task.get("created") or "—"),
                ts_row("Updated",  task.get("updated") or "—"),
            ], spacing=8),
            bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
            border_radius=12, padding=18,
        )

        # ── layout ────────────────────────────────────────────────────────────
        return ft.Container(
            content=ft.Column([
                # Header bar
                ft.Row([
                    back_btn,
                    ft.Container(expand=True),
                    badge,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

                ft.Divider(height=1, color=th["divider"]),

                # Title row
                ft.Column([
                    ft.Text("Edit Task", size=22, weight=ft.FontWeight.W_700, color=th["text"]),
                    ft.Text(proj["name"], size=12, color=th["text3"]),
                ], spacing=2),

                # Main fields card
                ft.Container(
                    content=ft.Column([
                        section_label("Task Details", ft.Icons.EDIT_OUTLINED),
                        name_tf,
                        desc_tf,
                    ], spacing=12),
                    bgcolor=th["card"],
                    border=ft.Border.all(1, th["border"]),
                    border_radius=12,
                    padding=18,
                ),

                # Priority + Status row
                ft.Row([
                    ft.Container(
                        content=ft.Column([
                            section_label("Priority", ft.Icons.FLAG_OUTLINED),
                            ft.Container(height=2),
                            pri_row,
                        ], spacing=8),
                        bgcolor=th["card"],
                        border=ft.Border.all(1, th["border"]),
                        border_radius=12,
                        padding=18,
                        expand=2,
                    ),
                    ft.Container(
                        content=ft.Column([
                            section_label("Status", ft.Icons.TRACK_CHANGES_ROUNDED),
                            ft.Container(height=2),
                            status_btn,
                        ], spacing=8),
                        bgcolor=th["card"],
                        border=ft.Border.all(1, th["border"]),
                        border_radius=12,
                        padding=18,
                        expand=1,
                    ),
                ], spacing=12),

                # Notes card
                ft.Container(
                    content=ft.Column([
                        section_label("Notes", ft.Icons.NOTES_ROUNDED),
                        notes_section,
                    ], spacing=12, expand=True),
                    bgcolor=th["card"],
                    border=ft.Border.all(1, th["border"]),
                    border_radius=12,
                    padding=18,
                    expand=True,
                ),

                # Action bar
                ft.Row([
                    del_btn,
                    ft.Container(expand=True),
                    ts_card,
                    ft.Container(expand=True),
                    save_btn,
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

            ], spacing=14, expand=True),
            padding=28,
            expand=True,
        )

    # ── task row ──────────────────────────────────────────────────────────────
    def task_row_widget(proj, task_idx, refresh_fn):
        task = proj["tasks"][task_idx]

        def toggle_done(e):
            task["done"] = e.control.value
            write_project(proj)
            refresh_fn()
            refresh_home()

        def ask_del(e):
            def do():
                proj["tasks"].pop(task_idx)
                write_project(proj)
                refresh_fn()
                refresh_home()
                show_toast("Task deleted", success=False)
            show_confirm("Delete task?", f'Remove "{task["text"]}"?', "Delete", do)

        row = ft.Container(
            content=ft.Row([
                ft.Checkbox(value=task["done"], active_color=th["success"],
                            on_change=toggle_done),
                ft.Column([
                    ft.Text(task["text"], size=13, weight=ft.FontWeight.W_500,
                            color=th["task_done_text"] if task["done"] else th["text"]),
                    *([ft.Text(task["desc"], size=11, color=th["text3"], max_lines=1)]
                      if task.get("desc") else []),
                ], spacing=0, expand=True),
                pill(task["priority"], PRIORITY_COLORS[task["priority"]],
                     PRIORITY_BG_DK[task["priority"]] if th == DARK else PRIORITY_BG[task["priority"]]),
                ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=18,
                              icon_color=th["text3"], on_click=ask_del, tooltip="Delete Task"),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=4, horizontal=12),
            border_radius=10,
            on_click=lambda _, i=task_idx: _open_task_edit(proj, i, refresh_fn),
        )
        def row_hover(e):
            try:
                row.bgcolor = th["nav_hover"] if e.data == "true" else "transparent"
                row.update()
            except Exception:
                pass
        row.on_hover = row_hover
        return row

    def _open_task_edit(proj, task_idx, refresh_fn):
        proj["_active_task_idx"] = task_idx
        refresh_fn()

    # ── detail panel ──────────────────────────────────────────────────────────
    def open_project(idx):
        selected_idx[0] = idx
        render_list()
        render_detail()

    def empty_detail():
        detail_col.controls = [ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=48, color=th["text3"]),
                ft.Text("Select a project", size=14, color=th["text3"]),
                ft.Text("or create a new one", size=12, color=th["text3"]),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            expand=True, alignment=ft.Alignment.CENTER,
        )]

    def render_detail():
        detail_col.controls.clear()
        idx = selected_idx[0]
        if idx is None or idx >= len(projects):
            empty_detail(); page.update(); return

        proj = projects[idx]

        # task edit sub-view
        if proj.get("_active_task_idx") is not None:
            ti = proj["_active_task_idx"]
            def back():
                del proj["_active_task_idx"]
                render_detail()
            detail_col.controls = [build_task_edit_window(proj, ti, back)]
            page.update()
            return

        tasks = proj["tasks"]
        total = len(tasks)
        done  = sum(t["done"] for t in tasks)
        pct   = int(done / total * 100) if total else 0

        new_task_tf = ft.TextField(
            hint_text="New task…", border_color=th["border2"],
            bgcolor=th["input_bg"], color=th["text"],
            text_size=13, height=38, expand=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=0))
        new_desc_tf = ft.TextField(
            hint_text="Task description (optional)…",
            border_color=th["border2"], bgcolor=th["input_bg"], color=th["text"],
            text_size=12, height=38, expand=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=0))

        pri_map     = {"HIGH": "🔴 High", "MED": "🟡 Med", "LOW": "🟢 Low"}
        current_pri = ["MED"]
        pri_label   = ft.Text(pri_map["MED"], size=12, weight=ft.FontWeight.W_500, color=th["text"])
        pri_dd = ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Row([pri_label,
                                ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED,
                                        color=th["text3"], size=20)],
                               alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                border=ft.Border.all(1, th["border2"]),
                border_radius=8, bgcolor=th["input_bg"],
                height=38, width=115,
                padding=ft.Padding.symmetric(horizontal=10),
            ),
            items=[
                ft.PopupMenuItem(
                    content=ft.Text(v, size=12, color=th["text"]), data=k,
                    on_click=lambda e: (
                        current_pri.__setitem__(0, e.control.data),
                        setattr(pri_label, "value", pri_map[e.control.data]),
                        page.update(),
                    )
                )
                for k, v in pri_map.items()
            ],
        )

        def add_task(e):
            txt = new_task_tf.value.strip()
            if not txt:
                show_toast("Task name is required.", success=False)
                return
            proj["tasks"].append({"text": txt, "done": False,
                                  "priority": current_pri[0],
                                  "desc": new_desc_tf.value.strip(), "notes": [],
                                  "created": now_str(), "updated": ""})
            write_project(proj)
            new_task_tf.value = ""; new_desc_tf.value = ""
            render_detail(); refresh_home()
            show_toast("Task added")

        _add_ic  = ft.Icon(ft.Icons.ADD_ROUNDED, color="#FFFFFF", size=14)
        _add_lbl = ft.Text("Add", color="#FFFFFF", size=12, weight=ft.FontWeight.W_500)
        add_btn = ft.Container(
            content=ft.Row([_add_ic, _add_lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True),
            bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
            border_radius=8, height=38, padding=ft.Padding.symmetric(horizontal=20),
            on_click=add_task,
        )
        def _add_hover(e):
            try:
                if e.data == "true":
                    add_btn.bgcolor = "transparent"
                    _add_ic.color = th["accent"]; _add_lbl.color = th["accent"]
                else:
                    add_btn.bgcolor = th["accent"]
                    _add_ic.color = "#FFFFFF"; _add_lbl.color = "#FFFFFF"
                page.update()
            except Exception:
                pass
        add_btn.on_hover = _add_hover

        def ask_delete_project(e):
            def do():
                path = os.path.join(PROJECTS_DIR, proj["file"])
                if os.path.exists(path): os.remove(path)
                projects.pop(idx)
                selected_idx[0] = None
                render_list(); empty_detail(); refresh_home(); page.update()
                show_toast(f'"{proj["name"]}" deleted', success=False)
            show_confirm("Delete project?",
                         f'"{proj["name"]}" and all its tasks will be removed.',
                         "Delete Project", do)

        del_proj_btn = accent_btn("Delete", ft.Icons.DELETE_ROUNDED,
                                  ask_delete_project, th["danger"], outline=True)

        task_list = ft.Column(
            [task_row_widget(proj, i, render_detail) for i in range(len(tasks))],
            scroll=ft.ScrollMode.AUTO, expand=True,
        )
        empty_msg = [] if tasks else [ft.Container(
            content=ft.Text("No tasks yet — add one below.", size=12, color=th["text3"]),
            padding=ft.Padding.symmetric(vertical=8))]

        detail_col.controls = [ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(width=14, height=14, bgcolor=proj["color"], border_radius=7),
                    ft.Text(proj["name"], size=20, weight=ft.FontWeight.BOLD,
                            color=th["text"], expand=True),
                    ft.Text(f"{pct}%", size=12, color=th["text3"]),
                    del_proj_btn,
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                *([ ft.Text(proj["desc"], size=12, color=th["text2"]) ] if proj.get("desc") else []),
                ft.ProgressBar(value=pct / 100, color=proj["color"],
                               bgcolor=th["border"], height=8, border_radius=4),
                ft.Text(f"{done} of {total} tasks completed", size=11, color=th["text3"]),
                ft.Row([
                    *([ft.Text(f"Created {proj['created']}", size=10, color=th["text3"])] if proj.get("created") else []),
                    *([ft.Container(width=1, height=10, bgcolor=th["border2"])] if proj.get("created") and proj.get("updated") else []),
                    *([ft.Text(f"Updated {proj['updated']}", size=10, color=th["text3"])] if proj.get("updated") else []),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=th["divider"]),
                ft.Column([*empty_msg, task_list], expand=True),
                ft.Divider(height=1, color=th["divider"]),
                ft.Text("Add task", size=12, color=th["text3"], weight=ft.FontWeight.W_600),
                ft.Row([new_task_tf, pri_dd], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([new_desc_tf, add_btn], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], expand=True),
            padding=28, expand=True,
        )]
        page.update()

    # ── new project modal ─────────────────────────────────────────────────────
    modal_name_tf = ft.TextField(
        label="Project name *", border_color=th["border2"],
        bgcolor=th["input_bg"], color=th["text"],
        label_style=ft.TextStyle(color=th["text3"]), text_size=14, height=50,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=0))
    modal_desc_tf = ft.TextField(
        label="Description (optional)", border_color=th["border2"],
        bgcolor=th["input_bg"], color=th["text"],
        label_style=ft.TextStyle(color=th["text3"]), text_size=13, height=50,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=0))
    modal_err = ft.Text("Project name is required.", size=11,
                        color=th["danger"], visible=False)

    modal_color_idx  = [0]
    modal_color_dots = []

    def make_color_dot(i):
        dot = ft.Container(
            width=28, height=28, bgcolor=PROJECT_PALETTE[i], border_radius=14,
            border=ft.Border.all(3, "white" if i == 0 else "transparent"),
            animate=ft.Animation(140, ft.AnimationCurve.EASE_IN_OUT),
        )
        def pick(e, idx=i):
            modal_color_idx[0] = idx
            for j, dd in enumerate(modal_color_dots):
                dd.border = ft.Border.all(3, "white" if j == idx else "transparent")
                dd.update()
        dot.on_click = pick
        return dot

    modal_color_dots = [make_color_dot(i) for i in range(len(PROJECT_PALETTE))]
    new_proj_dlg = ft.AlertDialog(modal=True)

    def show_new_proj_modal(e=None):
        modal_name_tf.value = ""
        modal_desc_tf.value = ""
        modal_err.visible   = False
        modal_color_idx[0]  = 0
        for j, dd in enumerate(modal_color_dots):
            dd.border = ft.Border.all(3, "white" if j == 0 else "transparent")

        def do_cancel(e):
            new_proj_dlg.open = False
            page.update()

        def do_create(e):
            name = modal_name_tf.value.strip()
            if not name:
                modal_err.visible = True; modal_err.update(); return
            modal_err.visible = False
            proj = {
                "name":    name,
                "color":   PROJECT_PALETTE[modal_color_idx[0]],
                "created": datetime.now().strftime("%Y-%m-%d"),
                "desc":    modal_desc_tf.value.strip(),
                "tasks":   [],
                "file":    slug(name) + ".md",
            }
            write_project(proj)
            projects.append(proj)
            new_proj_dlg.open = False
            page.update()
            render_list()
            open_project(len(projects) - 1)
            refresh_home()
            show_toast(f'"{name}" created')

        new_proj_dlg.title   = ft.Text("New Project", weight=ft.FontWeight.W_700, color=th["text"])
        new_proj_dlg.bgcolor = th["modal"]
        new_proj_dlg.content = ft.Column([
            modal_name_tf, modal_err, modal_desc_tf,
            ft.Text("Colour", size=11, color=th["text3"], weight=ft.FontWeight.W_600),
            ft.Row(modal_color_dots, spacing=8),
        ], spacing=14, tight=True, width=380)
        new_proj_dlg.actions = [
            ft.TextButton("Cancel", on_click=do_cancel,
                          style=ft.ButtonStyle(color=th["text3"])),
            ft.FilledButton("Create Project", on_click=do_create,
                            style=ft.ButtonStyle(bgcolor=th["accent"], color="#FFFFFF")),
        ]
        if new_proj_dlg not in page.overlay:
            page.overlay.append(new_proj_dlg)
        new_proj_dlg.open = True
        page.update()

    # ── project card (sidebar) ────────────────────────────────────────────────
    drag_src = [None]   # index being dragged

    def small_project_card(idx):
        proj   = projects[idx]
        tasks  = proj["tasks"]
        total  = len(tasks)
        done   = sum(t["done"] for t in tasks)
        pct    = int(done / total * 100) if total else 0
        is_sel = selected_idx[0] == idx

        card_inner = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(width=10, height=10, bgcolor=proj["color"], border_radius=5),
                    ft.Text(proj["name"], size=13, weight=ft.FontWeight.W_600,
                            color=th["accent"] if is_sel else th["text"], expand=True),
                    ft.Text(f"{pct}%", size=11, color=th["text3"]),
                    ft.Icon(ft.Icons.DRAG_INDICATOR_ROUNDED, size=14, color=th["text3"]),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.ProgressBar(value=pct / 100, color=proj["color"],
                               bgcolor=th["border"], height=4, border_radius=2),
                ft.Text(f"{total} tasks · {done} done", size=10, color=th["text3"]),
            ], spacing=6),
            padding=14, border_radius=10,
            bgcolor=th["nav_sel_bg"] if is_sel else th["card"],
            border=ft.Border.all(1, th["accent"] if is_sel else th["border"]),
            on_click=lambda e, i=idx: open_project(i),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
        )
        def h(e, c=card_inner, i=idx):
            try:
                if selected_idx[0] != i:
                    c.bgcolor = th["nav_hover"] if e.data == "true" else th["card"]
                    c.update()
            except Exception:
                pass
        card_inner.on_hover = h

        draggable = ft.Draggable(
            group="proj",
            content=card_inner,
            content_when_dragging=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=10, height=10, bgcolor=proj["color"], border_radius=5),
                        ft.Text(proj["name"], size=13, weight=ft.FontWeight.W_600,
                                color=th["text3"], expand=True),
                    ], spacing=8),
                ], spacing=4),
                padding=14, border_radius=10,
                bgcolor=th["border"], border=ft.Border.all(1, th["border2"]),
                opacity=0.5,
            ),
            data=idx,
            on_drag_start=lambda e: drag_src.__setitem__(0, e.control.data),
        )

        def on_accept(e, target_idx=idx):
            src = drag_src[0]
            if src is None or src == target_idx: return
            # reorder in list
            proj_moved = projects.pop(src)
            projects.insert(target_idx, proj_moved)
            # update order field and persist all
            for i, p in enumerate(projects):
                p["order"] = i
                write_project(p, touch=False)
            # fix selected index
            if selected_idx[0] == src:
                selected_idx[0] = target_idx
            elif selected_idx[0] is not None:
                # adjust for shift
                if src < selected_idx[0] <= target_idx:
                    selected_idx[0] -= 1
                elif target_idx <= selected_idx[0] < src:
                    selected_idx[0] += 1
            drag_src[0] = None
            render_list()
            page.update()

        drop_zone = ft.DragTarget(
            group="proj",
            content=draggable,
            on_accept=on_accept,
        )
        return drop_zone

    def render_list():
        list_col.controls = [small_project_card(i) for i in range(len(projects))]
        page.update()

    render_list()
    empty_detail()

    # ── new project button ────────────────────────────────────────────────────
    _np_ic  = ft.Icon(ft.Icons.ADD_ROUNDED, color=th["accent"], size=16)
    _np_lbl = ft.Text("New Project", color=th["accent"], size=13, weight=ft.FontWeight.W_600)
    new_proj_btn = ft.Container(
        content=ft.Row([_np_ic, _np_lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True),
        bgcolor="transparent", border=ft.Border.all(1.5, th["accent"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=9, horizontal=16),
        on_click=show_new_proj_modal,
    )
    def _np_hover(e):
        try:
            if e.data == "true":
                new_proj_btn.bgcolor = th["accent"]
                _np_ic.color = "#FFFFFF"; _np_lbl.color = "#FFFFFF"
            else:
                new_proj_btn.bgcolor = "transparent"
                _np_ic.color = th["accent"]; _np_lbl.color = th["accent"]
            page.update()
        except Exception:
            pass
    new_proj_btn.on_hover = _np_hover

    # ── layout ────────────────────────────────────────────────────────────────
    left_panel = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Projects", size=15, weight=ft.FontWeight.W_700, color=th["text"]),
                new_proj_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=th["divider"]),
            list_col,
        ], spacing=10),
        width=248, padding=20, bgcolor=th["sidebar"],
        border=ft.Border.only(right=ft.BorderSide(1, th["border"])),
    )
    return ft.Row([left_panel, ft.Container(content=detail_col, expand=True)],
                  spacing=0, expand=True)

# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
def build_settings_screen(th, settings, on_save):
    dirty = [False]

    def setting_row(label, subtitle, control):
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(label, size=13, weight=ft.FontWeight.W_500, color=th["text"]),
                    ft.Text(subtitle, size=11, color=th["text3"]),
                ], spacing=2, expand=True),
                control,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=14, horizontal=18),
            border_radius=10, bgcolor=th["card"],
            border=ft.Border.all(1, th["border"]),
        )

    def section(title, rows):
        return ft.Column([
            ft.Text(title.upper(), size=10, color=th["text3"], weight=ft.FontWeight.W_700),
            ft.Column(rows, spacing=6),
        ], spacing=10)

    dark_sw     = ft.Switch(value=settings["dark_mode"], active_color=th["accent"])
    username_tf = ft.TextField(
        value=settings["username"],
        border_color=th["border2"], bgcolor=th["input_bg"], color=th["text"],
        height=38, text_size=13, width=160,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=0))

    def mark_dirty(e): dirty[0] = True
    dark_sw.on_change     = mark_dirty
    username_tf.on_change = mark_dirty

    save_lbl  = ft.Text("Save Changes", color="#FFFFFF", size=13, weight=ft.FontWeight.W_600)
    save_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=16, visible=False)
    save_btn  = ft.Container(
        content=ft.Row([save_icon, save_lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER, tight=True),
        bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=12, horizontal=24),
        width=180, alignment=ft.Alignment.CENTER,
    )
    def _settings_save_hover(e):
        try:
            if e.data == "true":
                save_btn.bgcolor = "transparent"
                save_lbl.color = th["accent"]; save_icon.color = th["accent"]
            else:
                save_btn.bgcolor = th["accent"]
                save_lbl.color = "#FFFFFF"; save_icon.color = "#FFFFFF"
            page.update()
        except Exception:
            pass
    save_btn.on_hover = _settings_save_hover

    def do_save(e):
        uname = username_tf.value.strip()
        if not uname:
            username_tf.value = settings["username"]
            username_tf.update()
            return
        settings["dark_mode"] = dark_sw.value
        settings["username"]  = uname
        save_settings(settings)
        dirty[0] = False
        on_save(settings)
        save_icon.visible = True
        save_lbl.value    = "Saved!"
        try: page.update()
        except Exception: pass
        def revert():
            time.sleep(1.6)
            try:
                save_icon.visible = False
                save_lbl.value    = "Save Changes"
                page.update()
            except Exception: pass
        threading.Thread(target=revert, daemon=True).start()

    save_btn.on_click = do_save

    return ft.Container(
        content=ft.Column([
            ft.Column([
                ft.Text("Settings", size=28, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Text("Manage your preferences", size=13, color=th["text3"]),
            ], spacing=4),
            ft.Divider(height=1, color=th["divider"]),
            section("Appearance", [
                setting_row("Dark Mode", "Switch to a darker interface", dark_sw),
            ]),
            section("Account", [
                setting_row("Username", "Shown on the home screen", username_tf),
            ]),
            ft.Divider(height=1, color=th["divider"]),
            save_btn,
        ], spacing=24, scroll=ft.ScrollMode.AUTO),
        padding=40, expand=True,
    ), dirty

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main(page: ft.Page):
    settings = load_settings()
    th       = DARK if settings["dark_mode"] else LIGHT

    page.title = "Project Manager"

    icon_path = os.path.join(BASE_DIR, "sabrina.jpg")
    page.window.icon = icon_path

    # Suppress Flutter's default gray surface tint and button overlay color
    page.theme      = ft.Theme(color_scheme=ft.ColorScheme(surface_tint="#00000000"))
    page.dark_theme = ft.Theme(color_scheme=ft.ColorScheme(surface_tint="#00000000"))
    page.theme_mode = ft.ThemeMode.DARK if settings["dark_mode"] else ft.ThemeMode.LIGHT
    page.bgcolor    = th["bg"]
    page.padding    = 0
    page.update()

    content_container = ft.Container(expand=True)
    current_screen    = ["Home"]
    settings_dirty    = [None]

    unsaved_dlg = ft.AlertDialog(modal=True)

    def apply_theme():
        page.theme_mode   = ft.ThemeMode.DARK if th == DARK else ft.ThemeMode.LIGHT
        page.bgcolor      = th["bg"]
        sidebar.bgcolor   = th["sidebar"]
        sidebar.border    = ft.Border.only(right=ft.BorderSide(1, th["border"]))
        brand_text.color  = th["text3"]
        brand_dot.bgcolor = th["accent"]
        for item in nav_items:
            item.set_theme(th)

    def refresh_home():
        if current_screen[0] == "Home":
            render_screen("Home"); page.update()

    def safe_navigate(name, nav_item):
        dirty_ref = settings_dirty[0]
        if current_screen[0] == "Settings" and dirty_ref and dirty_ref[0]:
            def proceed(e):
                unsaved_dlg.open = False
                page.update()
                _do_navigate(name, nav_item)
            def stay(e):
                unsaved_dlg.open = False
                page.update()
            unsaved_dlg.title   = ft.Text("Unsaved changes", weight=ft.FontWeight.W_700)
            unsaved_dlg.content = ft.Text("You have unsaved settings. Leave without saving?", size=13)
            unsaved_dlg.actions = [
                ft.TextButton("Stay", on_click=stay),
                ft.FilledButton("Leave", on_click=proceed,
                                style=ft.ButtonStyle(bgcolor=th["accent"], color="#FFFFFF")),
            ]
            if unsaved_dlg not in page.overlay:
                page.overlay.append(unsaved_dlg)
            unsaved_dlg.open = True
            page.update()
        else:
            _do_navigate(name, nav_item)

    def _do_navigate(name, nav_item):
        for item in nav_items:
            item.set_state(active=(item == nav_item))
        render_screen(name); page.update()

    def nav_clicked(clicked_item):
        safe_navigate(clicked_item.label_text, clicked_item)

    def go_to_projects(e=None):
        proj_item = next(i for i in nav_items if i.label_text == "Projects")
        safe_navigate("Projects", proj_item)
        page.update()

    def on_settings_save(new_settings):
        nonlocal th
        th = DARK if new_settings["dark_mode"] else LIGHT
        apply_theme()
        render_screen("Settings")
        page.update()

    def render_screen(name):
        current_screen[0] = name
        settings_dirty[0]  = None
        if name == "Home":
            content_container.content = build_home_screen(
                go_to_projects, th, settings["username"], page)
        elif name == "Projects":
            content_container.content = build_projects_screen(page, th, refresh_home, settings["username"])
        elif name == "Settings":
            screen, dirty = build_settings_screen(th, settings, on_settings_save)
            settings_dirty[0] = dirty
            content_container.content = screen

    nav_items = [
        NavItem(ft.Icons.HOME_ROUNDED,     "Home",     nav_clicked, th, selected=True),
        NavItem(ft.Icons.FOLDER_ROUNDED,   "Projects", nav_clicked, th),
        NavItem(ft.Icons.SETTINGS_ROUNDED, "Settings", nav_clicked, th),
    ]

    brand_dot  = ft.Container(width=8, height=8, bgcolor=th["accent"], border_radius=4)
    brand_text = ft.Text("PROGRESS", size=11, weight=ft.FontWeight.W_700, color=th["text3"])

    sidebar = ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Row([brand_dot, brand_text], spacing=8,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.only(left=15, bottom=8, top=4),
            ),
            *nav_items,
        ], spacing=2),
        padding=ft.Padding.symmetric(vertical=24, horizontal=8),
        width=210, bgcolor=th["sidebar"],
        border=ft.Border.only(right=ft.BorderSide(1, th["border"])),
    )

    render_screen("Home")
    page.add(ft.Row([sidebar, content_container], expand=True, spacing=0))


ft.run(main)
import flet as ft
import threading
from datetime import datetime
from config import DARK, PRIORITY_COLORS, PRIORITY_BG, PRIORITY_BG_DK, PROJECT_PALETTE
from storage import (read_projects, write_project, delete_project_file, now_str, slug,
                     _parse_notes, can, CAN_DELETE_PROJECT, CAN_ADD_TASKS, CAN_EDIT_TASKS,
                     CAN_ADD_NOTES, CAN_MANAGE_MEMBERS)
from ui_components import pill, section_label, hover_btn, show_confirm, show_toast
from ui_members import build_members_panel


# ── Subtask row widget ─────────────────────────────────────────────────────────
def subtask_row_widget(task: dict, sub_idx: int, th: dict, page: ft.Page,
                       username: str, on_change):
    sub = task["subtasks"][sub_idx]

    def toggle_done(e):
        sub["done"] = e.control.value
        sub["updated"] = now_str()
        on_change()

    def ask_del(e):
        task["subtasks"].pop(sub_idx)
        on_change()

    creator_text = f"by {sub.get('created_by', '?')}"

    row = ft.Container(
        content=ft.Row([
            ft.Container(width=20),  # indent
            ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, size=14, color=th["text3"]),
            ft.Checkbox(value=sub["done"], active_color=th["success"],
                        on_change=toggle_done, width=20, height=20),
            ft.Column([
                ft.Text(sub["text"], size=12,
                        weight=ft.FontWeight.W_500,
                        color=th["task_done_text"] if sub["done"] else th["text"]),
                ft.Text(creator_text, size=10, color=th["text3"]),
            ], spacing=0, expand=True),
            pill(sub["priority"], PRIORITY_COLORS[sub["priority"]],
                 PRIORITY_BG_DK[sub["priority"]] if th == DARK else PRIORITY_BG[sub["priority"]]),
            ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16,
                          icon_color=th["text3"], on_click=ask_del, tooltip="Delete subtask"),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(vertical=2, horizontal=12),
        border_radius=8,
        bgcolor=th["bg"] if sub["done"] else "transparent",
    )
    return row


# ── Task edit window ───────────────────────────────────────────────────────────
def build_task_edit_window(proj: dict, task_idx: int, back_fn,
                           th: dict, page: ft.Page, username: str, session: dict = None) -> ft.Container:
    task = proj["tasks"][task_idx]

    # Ensure required fields exist
    if not isinstance(task.get("notes"), list):
        task["notes"] = _parse_notes(task.get("notes", ""))
    if not isinstance(task.get("subtasks"), list):
        task["subtasks"] = []
    if not task.get("created_by"):
        task["created_by"] = username

    # ── Priority selector ─────────────────────────────────────────────────────
    current_pri = [task["priority"]]
    pri_btns    = {}
    pri_meta = {
        "HIGH": {"label": "High",   "icon": ft.Icons.KEYBOARD_DOUBLE_ARROW_UP_ROUNDED,   "color": PRIORITY_COLORS["HIGH"], "bg_l": PRIORITY_BG["HIGH"],  "bg_d": PRIORITY_BG_DK["HIGH"]},
        "MED":  {"label": "Medium", "icon": ft.Icons.DRAG_HANDLE_ROUNDED,                 "color": PRIORITY_COLORS["MED"],  "bg_l": PRIORITY_BG["MED"],   "bg_d": PRIORITY_BG_DK["MED"]},
        "LOW":  {"label": "Low",    "icon": ft.Icons.KEYBOARD_DOUBLE_ARROW_DOWN_ROUNDED,  "color": PRIORITY_COLORS["LOW"],  "bg_l": PRIORITY_BG["LOW"],   "bg_d": PRIORITY_BG_DK["LOW"]},
    }

    def make_pri_btn(key):
        meta   = pri_meta[key]
        color  = meta["color"]
        active = current_pri[0] == key
        ic  = ft.Icon(meta["icon"], size=14, color=color if active else th["text3"])
        lbl = ft.Text(meta["label"], size=12, weight=ft.FontWeight.W_500,
                      color=color if active else th["text2"])
        btn = ft.Container(
            content=ft.Row([ic, lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border_radius=8,
            border=ft.Border.all(1.5 if active else 1, color if active else th["border2"]),
            bgcolor=(meta["bg_d"] if th == DARK else meta["bg_l"]) if active else "transparent",
            padding=ft.Padding.symmetric(vertical=9, horizontal=14),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
            expand=True,
        )
        def on_click(e, k=key):
            current_pri[0] = k
            for kk, bb in pri_btns.items():
                m   = pri_meta[kk]
                sel = kk == k
                c   = m["color"]
                bb["btn"].bgcolor = (m["bg_d"] if th == DARK else m["bg_l"]) if sel else "transparent"
                bb["btn"].border  = ft.Border.all(1.5 if sel else 1, c if sel else th["border2"])
                bb["ic"].color    = c if sel else th["text3"]
                bb["lbl"].color   = c if sel else th["text2"]
                bb["btn"].update()
        btn.on_click = on_click

        pri_btns[key] = {"btn": btn, "ic": ic, "lbl": lbl}
        return btn

    pri_row = ft.Row([make_pri_btn(k) for k in ["HIGH", "MED", "LOW"]], spacing=8)

    # ── Text fields ───────────────────────────────────────────────────────────
    def styled_field(label, value, multiline=False, min_lines=1, hint=None):
        return ft.TextField(
            label=label, value=value, hint_text=hint,
            multiline=multiline, min_lines=min_lines, expand=True,
            bgcolor=th["input_bg"], border_color=th["border2"],
            focused_border_color=th["accent"], color=th["text"],
            label_style=ft.TextStyle(color=th["text3"], size=12),
            text_size=13, border_radius=10,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )

    name_tf = styled_field("Task Title", task["text"])
    desc_tf = styled_field("Short Description", task.get("desc", ""),
                           hint="Brief summary shown in the task list…")

    # ── Status selector (3 states) ────────────────────────────────────────────
    # Migrate legacy done bool → status string
    if "status" not in task:
        task["status"] = "done" if task.get("done") else "todo"

    STATUS_META = {
        "todo":        {"label": "To Do",       "icon": ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, "color": th["text3"],    "border": th["border2"],  "bg": "transparent",                              "line": False},
        "in_progress": {"label": "In Progress",  "icon": ft.Icons.REMOVE_CIRCLE_ROUNDED,          "color": "#F59E0B",      "border": "#F59E0B",      "bg": "#451A03" if th == DARK else "#FFFBEB",     "line": False},
        "done":        {"label": "Done",         "icon": ft.Icons.CHECK_CIRCLE_ROUNDED,           "color": th["success"],  "border": th["success"],  "bg": "#052e16" if th == DARK else "#ECFDF5",     "line": False},
    }

    status_state = [task["status"]]
    status_btns  = {}

    def make_status_btn(key):
        meta   = STATUS_META[key]
        active = status_state[0] == key
        ic  = ft.Icon(meta["icon"], size=15, color=meta["color"] if active else th["text3"])
        lbl = ft.Text(meta["label"], size=12, weight=ft.FontWeight.W_500,
                      color=meta["color"] if active else th["text2"])
        btn = ft.Container(
            content=ft.Row([ic, lbl], spacing=6, alignment=ft.MainAxisAlignment.CENTER,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border_radius=8,
            border=ft.Border.all(1.5 if active else 1, meta["border"] if active else th["border2"]),
            bgcolor=meta["bg"] if active else "transparent",
            padding=ft.Padding.symmetric(vertical=9, horizontal=14),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
            expand=True,
        )
        def on_click(e, k=key):
            status_state[0] = k
            for kk, bb in status_btns.items():
                m   = STATUS_META[kk]
                sel = kk == k
                bb["ic"].color  = m["color"] if sel else th["text3"]
                bb["lbl"].color = m["color"] if sel else th["text2"]
                bb["lbl"].style = None
                bb["btn"].border  = ft.Border.all(1.5 if sel else 1, m["border"] if sel else th["border2"])
                bb["btn"].bgcolor = m["bg"] if sel else "transparent"
                bb["btn"].update()
        btn.on_click = on_click
        status_btns[key] = {"btn": btn, "ic": ic, "lbl": lbl}
        return btn

    status_row = ft.Row([make_status_btn(k) for k in STATUS_META], spacing=8)

    # ── Subtasks section ───────────────────────────────────────────────────────
    subtasks_col = ft.Column([], spacing=4)

    pri_map_sub     = {"HIGH": "🔴 High", "MED": "🟡 Med", "LOW": "🟢 Low"}
    sub_pri_current = ["MED"]
    sub_pri_label   = ft.Text(pri_map_sub["MED"], size=12, weight=ft.FontWeight.W_500, color=th["text"])
    sub_pri_dd = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row([sub_pri_label,
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=th["text3"], size=18)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.Border.all(1, th["border2"]), border_radius=8,
            bgcolor=th["input_bg"], height=36, width=110,
            padding=ft.Padding.symmetric(horizontal=8),
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Text(v, size=12, color=th["text"]), data=k,
                on_click=lambda e: (
                    sub_pri_current.__setitem__(0, e.control.data),
                    setattr(sub_pri_label, "value", pri_map_sub[e.control.data]),
                    page.update(),
                )
            ) for k, v in pri_map_sub.items()
        ],
    )

    sub_tf = ft.TextField(
        hint_text="Add a subtask…",
        border_color=th["border2"], bgcolor=th["input_bg"], color=th["text"],
        text_size=12, height=36, expand=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=0),
        border_radius=8,
    )

    def refresh_subtasks_col():
        subtasks_col.controls.clear()
        for si in range(len(task["subtasks"])):
            def _on_change(si=si):
                write_project(proj)
                refresh_subtasks_col()
                try: page.update()
                except Exception: pass
            subtasks_col.controls.append(
                subtask_row_widget(task, si, th, page, username, _on_change)
            )
        try: page.update()
        except Exception: pass

    def add_subtask(e):
        txt = sub_tf.value.strip()
        if not txt: return
        task["subtasks"].append({
            "text": txt,
            "done": False,
            "priority": sub_pri_current[0],
            "created_by": username,
            "created": now_str(),
            "updated": "",
        })
        write_project(proj)
        sub_tf.value = ""
        refresh_subtasks_col()
        try: page.update()
        except Exception: pass

    sub_add_btn = hover_btn("Add", ft.Icons.ADD_ROUNDED, add_subtask, th, page,
                            padding=ft.Padding.symmetric(horizontal=16),
                            border_radius=8, height=36)
    sub_tf.on_submit = add_subtask

    refresh_subtasks_col()

    sub_done  = sum(1 for s in task["subtasks"] if s["done"])
    sub_total = len(task["subtasks"])

    subtasks_header_count = ft.Text(
        f"{sub_done}/{sub_total}" if sub_total else "None",
        size=11, color=th["text3"],
    )

    subtasks_section = ft.Container(
        content=ft.Column([
            ft.Row([
                section_label("Subtasks", ft.Icons.ACCOUNT_TREE_OUTLINED, th),
                subtasks_header_count,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            subtasks_col,
            ft.Row([sub_tf, sub_pri_dd, sub_add_btn], spacing=8,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=10),
        bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
        border_radius=12, padding=18,
    )

    # ── Notes thread ──────────────────────────────────────────────────────────
    def note_bubble(n):
        is_me = n["author"] == username
        return ft.Container(
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

    notes_col = ft.Column([note_bubble(n) for n in task["notes"]],
                          spacing=8, scroll=ft.ScrollMode.AUTO, height=200)
    note_input = ft.TextField(
        hint_text="Write a note…",
        border_color=th["border2"], bgcolor=th["input_bg"], color=th["text"],
        text_size=13, expand=True, multiline=True, min_lines=2, max_lines=4,
        border_radius=10,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
    )
    note_btn = hover_btn("Add Note", ft.Icons.ADD_COMMENT_OUTLINED, None, th, page,
                         padding=ft.Padding.symmetric(vertical=10, horizontal=16))

    def add_note(e):
        txt = note_input.value.strip()
        if not txt: return
        entry = {"author": username, "time": now_str(), "text": txt}
        task["notes"].append(entry)
        note_input.value = ""
        notes_col.controls.append(note_bubble(entry))
        write_project(proj)
        try: page.update()
        except Exception: pass

    note_btn.on_click     = add_note
    note_input.on_submit  = add_note

    notes_section = ft.Column([
        notes_col,
        ft.Divider(height=1, color=th["divider"]),
        ft.Row([note_input, note_btn], spacing=8,
               vertical_alignment=ft.CrossAxisAlignment.END),
    ], spacing=10, expand=True)

    # ── Buttons ───────────────────────────────────────────────────────────────
    save_btn = hover_btn("Save Changes", ft.Icons.SAVE_OUTLINED, None, th, page,
                         padding=ft.Padding.symmetric(vertical=11, horizontal=22),
                         border_radius=9)
    del_btn  = hover_btn("Delete Task", ft.Icons.DELETE_OUTLINE_ROUNDED, None, th, page,
                         color=th["danger"], outline=True,
                         padding=ft.Padding.symmetric(vertical=11, horizontal=18),
                         border_radius=9)
    back_btn = hover_btn("Back", ft.Icons.ARROW_BACK_ROUNDED, lambda _: back_fn(), th, page,
                         color=th["text2"], outline=True,
                         padding=ft.Padding.symmetric(vertical=11, horizontal=16),
                         border_radius=9)

    dlg = ft.AlertDialog(modal=True, title=ft.Text(""))

    def save_task(e):
        txt = name_tf.value.strip()
        if not txt:
            show_toast(page, th, "Task title is required.", success=False); return
        s = status_state[0]
        update = {
            "text": txt, "desc": desc_tf.value.strip(),
            "priority": current_pri[0],
            "status": s,
            "done": s == "done",
            "updated": now_str(), "created": task.get("created") or now_str(),
            "created_by": task.get("created_by") or username,
        }
        if s == "in_progress":
            update["in_progress_by"]    = username
            update["in_progress_photo"] = (session or {}).get("photo_url", "")
        elif s != "in_progress":
            update["in_progress_by"]    = task.get("in_progress_by", "")
            update["in_progress_photo"] = task.get("in_progress_photo", "")
        task.update(update)
        write_project(proj)
        show_toast(page, th, "Task saved")
        back_fn()

    def delete_task(e):
        show_confirm(page, th, dlg, "Delete Task?", "Remove this task permanently?",
                     "Delete", lambda: (proj["tasks"].pop(task_idx),
                                        write_project(proj),
                                        show_toast(page, th, "Task deleted", success=False),
                                        back_fn()))
    save_btn.on_click = save_task
    del_btn.on_click  = delete_task

    # ── Timestamps + creator card ─────────────────────────────────────────────
    def ts_row(label, value):
        return ft.Row([
            ft.Text(label, size=11, color=th["text3"], width=72),
            ft.Text(value or "—", size=11, color=th["text2"], weight=ft.FontWeight.W_500),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    ts_card = ft.Container(
        content=ft.Column([
            section_label("History", ft.Icons.HISTORY_ROUNDED, th),
            ts_row("Created", task.get("created") or "—"),
            ts_row("By", task.get("created_by") or "—"),
            ts_row("Updated", task.get("updated") or "—"),
        ], spacing=8),
        bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
        border_radius=12, padding=18,
    )

    badge = ft.Container(
        content=ft.Text(f"Task {task_idx + 1} of {len(proj['tasks'])}",
                        size=11, color=th["text3"], weight=ft.FontWeight.W_500),
        bgcolor=th["border"], border_radius=20,
        padding=ft.Padding.symmetric(vertical=4, horizontal=10),
    )

    return ft.Container(
        content=ft.Column([
            ft.Row([back_btn, ft.Container(expand=True), badge],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=th["divider"]),
            ft.Column([
                ft.Text("Edit Task", size=22, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Row([
                    ft.Text(proj["name"], size=12, color=th["text3"]),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, size=12, color=th["accent"]),
                            ft.Text(f"Created by {task.get('created_by') or username}",
                                    size=11, color=th["accent"]),
                        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=th["nav_sel_bg"],
                        border_radius=20,
                        padding=ft.Padding.symmetric(vertical=3, horizontal=10),
                    ),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=4),
            ft.Container(
                content=ft.Column([
                    section_label("Task Details", ft.Icons.EDIT_OUTLINED, th),
                    name_tf, desc_tf,
                ], spacing=12),
                bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
                border_radius=12, padding=18,
            ),
            ft.Container(
                content=ft.Column([
                    section_label("Priority", ft.Icons.FLAG_OUTLINED, th),
                    ft.Container(height=2), pri_row,
                ], spacing=8),
                bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
                border_radius=12, padding=18,
            ),
            ft.Container(
                content=ft.Column([
                    section_label("Status", ft.Icons.TRACK_CHANGES_ROUNDED, th),
                    ft.Container(height=2), status_row,
                ], spacing=8),
                bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
                border_radius=12, padding=18,
            ),
            subtasks_section,
            ft.Container(
                content=ft.Column([
                    section_label("Notes", ft.Icons.NOTES_ROUNDED, th),
                    notes_section,
                ], spacing=12, expand=True),
                bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
                border_radius=12, padding=18, expand=True,
            ),
            ft.Row([del_btn, ft.Container(expand=True), ts_card,
                    ft.Container(expand=True), save_btn],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=14, expand=True, scroll=ft.ScrollMode.AUTO),
        padding=28, expand=True,
    )


# ── Projects screen ────────────────────────────────────────────────────────────
def build_projects_screen(page: ft.Page, th: dict, refresh_home, username: str = "you", session: dict = None) -> ft.Row:
    projects     = read_projects()
    selected_idx = [None]
    list_col     = ft.Column([], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    dlg          = ft.AlertDialog(modal=True)

    # ── Detail area: Stack with a persistent spinner overlay ──────────────────
    # The spinner is always in the tree — we just toggle .visible.
    # This means one page.update() shows it instantly with no threading needed.
    detail_col = ft.Column([], spacing=0, expand=True)
    _spinner = ft.Container(
        content=ft.ProgressRing(width=36, height=36, stroke_width=3, color=th["accent"]),
        expand=True, alignment=ft.Alignment.CENTER,
        visible=False,
        bgcolor=th["bg"],   # covers detail_col content while loading
    )
    detail_stack = ft.Stack([detail_col, _spinner], expand=True)

    def _show_spinner():
        _spinner.visible = True
        page.update()  # used by _open_task_edit which doesn't batch

    def _hide_spinner():
        _spinner.visible = False
        # no page.update() here — caller does it after setting detail_col.controls

    # Alias to avoid closure shadowing issues with the 'refresh_home' parameter
    _do_refresh_home = refresh_home

    # ── Sort state ────────────────────────────────────────────────────────────
    sort_mode = ["manual"]
    SORT_OPTIONS = {
        "manual":  "Manual",
        "alpha":   "A → Z",
        "created": "Created",
        "updated": "Modified",
    }

    def sorted_project_indices() -> list:
        indices = list(range(len(projects)))
        mode = sort_mode[0]
        if mode == "alpha":
            indices.sort(key=lambda i: projects[i].get("name", "").lower())
        elif mode == "created":
            def _created_key(i):
                raw = projects[i].get("created", "")
                try: return datetime.strptime(raw, "%Y-%m-%d")
                except Exception: return datetime.min
            indices.sort(key=_created_key, reverse=True)
        elif mode == "updated":
            def _updated_key(i):
                raw = projects[i].get("updated") or projects[i].get("created", "")
                for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try: return datetime.strptime(raw, fmt)
                    except Exception: pass
                return datetime.min
            indices.sort(key=_updated_key, reverse=True)
        return indices

    def _confirm(title, msg, label, fn, danger=True):
        show_confirm(page, th, dlg, title, msg, label, fn, danger)

    def _toast(msg, success=True):
        show_toast(page, th, msg, success)

    # ── Task row ──────────────────────────────────────────────────────────────
    def task_row_widget(proj, task_idx, refresh_fn):
        task = proj["tasks"][task_idx]

        if not isinstance(task.get("subtasks"), list):
            task["subtasks"] = []

        # Migrate legacy done bool → status string
        if "status" not in task:
            task["status"] = "done" if task.get("done") else "todo"

        sub_total = len(task["subtasks"])
        sub_done  = sum(1 for s in task["subtasks"] if s["done"])

        STATUS_COLOR = {"todo": th["text3"], "in_progress": "#F59E0B", "done": th["success"]}
        STATUS_ICON  = {
            "todo":        ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
            "in_progress": ft.Icons.REMOVE_CIRCLE_ROUNDED,
            "done":        ft.Icons.CHECK_CIRCLE_ROUNDED,
        }

        status_ic = ft.Icon(
            STATUS_ICON[task["status"]],
            size=20,
            color=STATUS_COLOR[task["status"]],
        )

        title_text = ft.Text(
            task["text"], size=13, weight=ft.FontWeight.W_500,
            color=th["task_done_text"] if task["done"] else th["text"],
        )

        def cycle_status(e):
            order = ["todo", "in_progress", "done"]
            cur = task.get("status", "todo")
            nxt = order[(order.index(cur) + 1) % len(order)]
            task["status"] = nxt
            task["done"]   = nxt == "done"
            if nxt == "in_progress":
                task["in_progress_by"]    = username
                task["in_progress_photo"] = (session or {}).get("photo_url", "")
            status_ic.name  = STATUS_ICON[nxt]
            status_ic.color = STATUS_COLOR[nxt]
            title_text.color = th["task_done_text"] if task["done"] else th["text"]
            title_text.style = None
            status_ic.update()
            title_text.update()
            # Rebuild row so avatar appears/disappears without full list refresh
            render_detail()
            write_project(proj)
            _do_refresh_home()
            page.update()

        def ask_del(e):
            def do():
                proj["tasks"].pop(task_idx)
                write_project(proj)
                render_detail()   # row count changed, full rebuild needed
                _do_refresh_home()
                _toast("Task deleted", success=False)
            _confirm("Delete task?", f'Remove "{task["text"]}"?', "Delete", do)

        creator_badge = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.PERSON_OUTLINE_ROUNDED, size=10, color=th["text3"]),
                ft.Text(task.get("created_by") or "?", size=10, color=th["text3"]),
            ], spacing=3, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        # Avatar shown only when status is in_progress
        ip_photo = task.get("in_progress_photo", "")
        ip_name  = task.get("in_progress_by", "")
        if ip_photo:
            avatar_content = ft.Image(src=ip_photo, width=16, height=16, fit="cover")
        else:
            initial = (ip_name[0].upper() if ip_name else "?")
            avatar_content = ft.Text(initial, size=9, color="#FFFFFF", weight=ft.FontWeight.W_700)
        pending_avatar = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=avatar_content,
                    width=16, height=16, border_radius=8,
                    bgcolor="#F59E0B",
                    alignment=ft.Alignment.CENTER,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                ),
                ft.Text(ip_name or "?", size=10, color="#F59E0B"),
            ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            visible=task.get("status") == "in_progress" and bool(ip_name),
        )

        sub_badge = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ACCOUNT_TREE_OUTLINED, size=10,
                        color=th["success"] if sub_total > 0 and sub_done == sub_total else th["text3"]),
                ft.Text(f"{sub_done}/{sub_total}", size=10,
                        color=th["success"] if sub_total > 0 and sub_done == sub_total else th["text3"]),
            ], spacing=3, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            visible=sub_total > 0,
        )

        row = ft.Container(
            content=ft.Row([
                ft.GestureDetector(
                    content=status_ic,
                    on_tap=cycle_status,
                    mouse_cursor=ft.MouseCursor.CLICK,
                ),
                ft.Column([
                    title_text,
                    ft.Row([
                        *([ft.Text(task["desc"], size=11, color=th["text3"], max_lines=1)]
                          if task.get("desc") else []),
                        creator_badge,
                        pending_avatar,
                        sub_badge,
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=2, expand=True),
                pill(task["priority"], PRIORITY_COLORS[task["priority"]],
                     PRIORITY_BG_DK[task["priority"]] if th == DARK else PRIORITY_BG[task["priority"]]),
                ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=18,
                              icon_color=th["text3"], on_click=ask_del, tooltip="Delete Task"),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=4, horizontal=12),
            border_radius=10,
            on_click=lambda _, i=task_idx: _open_task_edit(proj, i, refresh_fn),
        )
        return row

    def _open_task_edit(proj, task_idx, refresh_fn):
        proj["_active_task_idx"] = task_idx
        _show_spinner()
        render_detail()

    def render_detail_debounced():
        render_detail()

    # ── Detail panel ──────────────────────────────────────────────────────────
    def open_project(idx):
        selected_idx[0] = idx
        # Update selection highlight on cards + show spinner in a single update
        render_list()
        _spinner.visible = True
        page.update()
        # Now build detail — spinner is already visible
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
        idx = selected_idx[0]
        if idx is None or idx >= len(projects):
            empty_detail(); _hide_spinner(); page.update(); return

        proj = projects[idx]

        if proj.get("_active_task_idx") is not None:
            ti = proj["_active_task_idx"]
            def back():
                del proj["_active_task_idx"]; render_detail()
            detail_col.controls = [
                build_task_edit_window(proj, ti, back, th, page, username, session)
            ]
            _hide_spinner()
            page.update(); return

        tasks = proj["tasks"]
        total = len(tasks)
        done  = sum(t["done"] for t in tasks)
        pct   = int(done / total * 100) if total else 0
        uid   = (session or {}).get("uid", "")

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
                border=ft.Border.all(1, th["border2"]), border_radius=8,
                bgcolor=th["input_bg"], height=38, width=115,
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
                ) for k, v in pri_map.items()
            ],
        )

        def add_task(e):
            if not can(proj, uid, CAN_ADD_TASKS):
                _toast("You don't have permission to add tasks.", success=False); return
            txt = new_task_tf.value.strip()
            if not txt:
                _toast("Task name is required.", success=False); return
            proj["tasks"].append({
                "text": txt, "done": False, "priority": current_pri[0],
                "desc": new_desc_tf.value.strip(), "notes": [],
                "subtasks": [],
                "created_by": username,
                "created": now_str(), "updated": "",
            })
            write_project(proj)
            new_task_tf.value = ""; new_desc_tf.value = ""
            render_detail(); _do_refresh_home()
            _toast("Task added")

        add_btn = hover_btn("Add", ft.Icons.ADD_ROUNDED, add_task, th, page,
                            padding=ft.Padding.symmetric(horizontal=20),
                            border_radius=8, height=38)

        def ask_delete_project(e):
            def do():
                proj_name = proj["name"]
                delete_project_file(proj)
                selected_idx[0] = None
                render_list()
                empty_detail()
                _do_refresh_home()
                page.update()
                _toast(f'"{proj_name}" deleted', success=False)
            _confirm("Delete project?",
                     f'"{proj["name"]}" and all its tasks will be removed.',
                     "Delete Project", do)

        del_proj_btn = hover_btn("Delete", ft.Icons.DELETE_ROUNDED, ask_delete_project,
                                 th, page, color=th["danger"], outline=True)
        del_proj_btn.visible = can(proj, uid, CAN_DELETE_PROJECT)

        # Members overlay — ft.Stack on page.overlay, no AlertDialog animation
        members_panel_content = build_members_panel(
            proj, session or {"uid": "", "display_name": username, "email": ""},
            th, page,
            on_close=lambda: _close_members(),
        )
        members_overlay = ft.Stack([
            # dim backdrop — clicking it closes the panel
            ft.Container(
                expand=True,
                bgcolor="#00000066",
                on_click=lambda e: _close_members(),
            ),
            # centred card
            ft.Container(
                content=members_panel_content,
                alignment=ft.Alignment.CENTER,
                expand=True,
            ),
        ], expand=True, visible=False)

        # Add to page overlay once; re-use on every open
        if members_overlay not in page.overlay:
            page.overlay.append(members_overlay)

        def _close_members():
            members_overlay.visible = False
            page.update()

        def show_members(e):
            members_overlay.visible = True
            page.update()

        share_btn = hover_btn("Members", ft.Icons.GROUP_ROUNDED, show_members,
                              th, page, outline=True)

        detail_col.controls = [ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(width=14, height=14, bgcolor=proj["color"], border_radius=7),
                    ft.Text(proj["name"], size=20, weight=ft.FontWeight.BOLD,
                            color=th["text"], expand=True),
                    ft.Text(f"{pct}%", size=12, color=th["text3"]),
                    share_btn,
                    del_proj_btn,
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                *([ft.Text(proj["desc"], size=12, color=th["text2"])] if proj.get("desc") else []),
                ft.ProgressBar(value=pct / 100, color=proj["color"],
                               bgcolor=th["border"], height=8, border_radius=4),
                ft.Text(f"{done} of {total} tasks completed", size=11, color=th["text3"]),
                ft.Row([
                    *([ft.Text(f"Created {proj['created']}", size=10, color=th["text3"])] if proj.get("created") else []),
                    *([ft.Container(width=1, height=10, bgcolor=th["border2"])] if proj.get("created") and proj.get("updated") else []),
                    *([ft.Text(f"Updated {proj['updated']}", size=10, color=th["text3"])] if proj.get("updated") else []),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=th["divider"]),
                ft.Column([
                    *( [] if tasks else [ft.Container(
                        content=ft.Text("No tasks yet — add one below.", size=12, color=th["text3"]),
                        padding=ft.Padding.symmetric(vertical=8))]),
                    *[task_row_widget(proj, i, render_detail_debounced) for i in range(len(tasks))],
                ], scroll=ft.ScrollMode.AUTO, expand=True),
                ft.Divider(height=1, color=th["divider"]),
                ft.Text("Add task", size=12, color=th["text3"], weight=ft.FontWeight.W_600),
                ft.Row([new_task_tf, pri_dd], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([new_desc_tf, add_btn], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], expand=True),
            padding=28, expand=True,
        )]
        _hide_spinner()
        page.update()

    # ── New project modal ─────────────────────────────────────────────────────
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
    modal_err       = ft.Text("Project name is required.", size=11,
                              color=th["danger"], visible=False)
    modal_color_idx = [0]
    modal_color_dots = []
    new_proj_dlg = ft.AlertDialog(modal=True, title=ft.Text(""))

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

    def show_new_proj_modal(e=None):
        modal_name_tf.value = ""; modal_desc_tf.value = ""
        modal_err.visible   = False; modal_color_idx[0] = 0
        for j, dd in enumerate(modal_color_dots):
            dd.border = ft.Border.all(3, "white" if j == 0 else "transparent")

        def do_cancel(e):
            new_proj_dlg.open = False; page.update()

        def do_create(e):
            name = modal_name_tf.value.strip()
            if not name:
                modal_err.visible = True; modal_err.update(); return
            modal_err.visible = False
            proj = {
                "name":       name,
                "color":      PROJECT_PALETTE[modal_color_idx[0]],
                "created":    datetime.now().strftime("%Y-%m-%d"),
                "created_by": username,
                "desc":       modal_desc_tf.value.strip(),
                "tasks":      [],
                "file":       slug(name) + ".md",
            }
            write_project(proj)
            projects.append(proj)
            new_proj_dlg.open = False
            page.update()
            render_list()
            open_project(len(projects) - 1)
            _do_refresh_home()
            _toast(f'"{name}" created')

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
        new_proj_dlg.open = True; page.update()

    # ── Project card with drag-to-reorder ─────────────────────────────────────
    drag_src = [None]

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
                    ft.Icon(ft.Icons.DRAG_INDICATOR_ROUNDED, size=14,
                            color=th["text3"] if sort_mode[0] == "manual" else "transparent"),
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
            ink=True,
            ink_color=th["accent"] + "18",
        )

        def on_accept(e, target_idx=idx):
            src = drag_src[0]
            if src is None or src == target_idx: return
            moved = projects.pop(src)
            projects.insert(target_idx, moved)
            for i, p in enumerate(projects):
                p["order"] = i
                write_project(p, touch=False)
            sel = selected_idx[0]
            if sel == src:
                selected_idx[0] = target_idx
            elif sel is not None:
                if src < sel <= target_idx:  selected_idx[0] -= 1
                elif target_idx <= sel < src: selected_idx[0] += 1
            drag_src[0] = None
            render_list(); page.update()

        draggable_content = ft.Draggable(
            group="proj",
            content=card_inner,
            content_when_dragging=ft.Container(
                content=ft.Row([
                    ft.Container(width=10, height=10, bgcolor=proj["color"], border_radius=5),
                    ft.Text(proj["name"], size=13, color=th["text3"], expand=True),
                ], spacing=8),
                padding=14, border_radius=10, opacity=0.5,
                bgcolor=th["border"], border=ft.Border.all(1, th["border2"]),
            ),
            data=idx,
            on_drag_start=lambda e: drag_src.__setitem__(0, e.control.data),
        ) if sort_mode[0] == "manual" else card_inner

        return ft.DragTarget(
            group="proj",
            content=draggable_content,
            on_accept=on_accept,
        )

    def render_list():
        list_col.controls = [small_project_card(i) for i in sorted_project_indices()]

    # ── Sort dropdown (defined here so render_list is already in scope) ───────
    sort_lbl = ft.Text("Manual", size=11, weight=ft.FontWeight.W_500, color=th["text2"])

    def _on_sort_click(e):
        key = e.control.data
        sort_mode[0] = key
        sort_lbl.value = SORT_OPTIONS[key]
        render_list()
        page.update()

    sort_dd = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row(
                [ft.Icon(ft.Icons.SORT_ROUNDED, color=th["text3"], size=14),
                 sort_lbl,
                 ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=th["text3"], size=16)],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            border=ft.Border.all(1, th["border2"]),
            border_radius=8,
            bgcolor=th["input_bg"],
            height=30,
            padding=ft.Padding.symmetric(horizontal=8),
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Text(label, size=12, color=th["text"]),
                data=key,
                on_click=_on_sort_click,
            )
            for key, label in SORT_OPTIONS.items()
        ],
    )

    render_list()
    empty_detail()

    new_proj_btn = hover_btn("New Project", ft.Icons.ADD_ROUNDED, show_new_proj_modal,
                             th, page, outline=True,
                             padding=ft.Padding.symmetric(vertical=9, horizontal=16),
                             border_radius=10)

    left_panel = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Projects", size=15, weight=ft.FontWeight.W_700, color=th["text"]),
                new_proj_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([
                ft.Icon(ft.Icons.SORT_ROUNDED, size=12, color=th["text3"]),
                ft.Text("Sort:", size=11, color=th["text3"]),
                sort_dd,
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=th["divider"]),
            list_col,
        ], spacing=8),
        width=248, padding=20, bgcolor=th["sidebar"],
        border=ft.Border.only(right=ft.BorderSide(1, th["border"])),
    )
    return ft.Row([left_panel, ft.Container(content=detail_stack, expand=True)],
                  spacing=0, expand=True)
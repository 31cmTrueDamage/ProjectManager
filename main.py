import flet as ft
import os
import time
import threading
from config import DARK, LIGHT
from storage import (
    load_settings, save_settings, BASE_DIR, set_current_user, upsert_user,
    get_pending_invitations, respond_invitation, invalidate_cache, prewarm_connection,
)
from auth import load_session, clear_session
from ui_components import NavItem
from ui_login import build_login_screen
from ui_home import build_home_screen
from ui_projects import build_projects_screen
from ui_settings import build_settings_screen

import flet.messaging.session as _flet_session

_orig_dispatch = _flet_session.Session.dispatch_event
_orig_after    = _flet_session.Session.after_event

async def _safe_dispatch(self, control, event_name, event_data):
    try:
        await _orig_dispatch(self, control, event_name, event_data)
    except RuntimeError as e:
        if "Control must be added to the page first" in str(e):
            pass
        else:
            raise

async def _safe_after(self, control):
    try:
        await _orig_after(self, control)
    except RuntimeError as e:
        if "Control must be added to the page first" in str(e):
            pass
        else:
            raise

_flet_session.Session.dispatch_event = _safe_dispatch
_flet_session.Session.after_event    = _safe_after


def main(page: ft.Page):
    settings = load_settings()
    th = DARK if settings["dark_mode"] else LIGHT

    page.title = "Project Manager"
    page.window.icon = os.path.join(BASE_DIR, "sabrina.jpg")
    page.theme = ft.Theme(color_scheme=ft.ColorScheme(surface_tint="#00000000"))
    page.dark_theme = ft.Theme(color_scheme=ft.ColorScheme(surface_tint="#00000000"))
    page.theme_mode = ft.ThemeMode.DARK if settings["dark_mode"] else ft.ThemeMode.LIGHT
    page.bgcolor = th["bg"]
    page.padding = 0
    page.update()

    root = ft.Column([], expand=True, spacing=0)
    page.add(root)

    def show_login():
        root.controls = [build_login_screen(page, th, on_login_success)]
        page.update()

    def on_login_success(session: dict):
        uname = session.get("display_name", "you")
        settings["username"] = uname
        save_settings(settings)
        set_current_user(session.get("uid", ""))
        threading.Thread(target=upsert_user, args=(session,), daemon=True).start()
        # Pre-warm DB connection immediately so first project click is instant
        threading.Thread(target=prewarm_connection, daemon=True).start()
        show_app(session)

    def show_app(session: dict):
        root.controls = [_build_app(session)]
        page.update()

    def _build_app(session: dict) -> ft.Stack:
        username  = session.get("display_name", "you")
        photo_url = session.get("photo_url", "")
        user_email = session.get("email", "")
        nonlocal th

        content_container = ft.Container(expand=True)
        current_screen    = ["Home"]
        settings_dirty    = [None]
        unsaved_dlg = ft.AlertDialog(modal=True, title=ft.Text(""))

        # ── Notification state ────────────────────────────────────────────────
        pending_invites   = []   # list of raw mongo docs
        notif_open        = [False]

        badge_dot = ft.Container(
            width=8, height=8, border_radius=4,
            bgcolor="#EF4444",
            visible=False,
            # position is set via Stack in the bell button below
        )

        notif_panel = ft.Container(visible=False)   # placeholder; rebuilt on open

        def _invite_card(inv):
            """Single invitation card inside the dropdown."""
            inv_id = inv["_id"]
            color  = inv.get("project_color", th["accent"])

            status_row = ft.Row([], spacing=8)

            card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
                        ft.Text(inv.get("project_name", "A project"),
                                size=13, weight=ft.FontWeight.W_600, color=th["text"],
                                expand=True),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Text(
                        f"{inv.get('from_name', 'Someone')} invited you as "
                        f"{inv.get('role', 'viewer').capitalize()}",
                        size=11, color=th["text3"],
                    ),
                    status_row,
                ], spacing=8, tight=True),
                bgcolor=th["bg"],
                border=ft.Border.all(1, th["border"]),
                border_radius=10,
                padding=ft.Padding.symmetric(vertical=10, horizontal=12),
            )

            def make_btn(label, color_val, outline, on_click_fn):
                lbl = ft.Text(label, size=11, weight=ft.FontWeight.W_600,
                              color="#FFFFFF" if not outline else color_val)
                c = ft.Container(
                    content=lbl,
                    bgcolor=color_val if not outline else "transparent",
                    border=ft.Border.all(1, color_val),
                    border_radius=6,
                    padding=ft.Padding.symmetric(vertical=5, horizontal=12),
                    on_click=on_click_fn,
                )
                def hov(e, _c=c, _lbl=lbl, _cv=color_val, _out=outline):
                    try:
                        h = e.data == "true"
                        _c.bgcolor   = "transparent" if (h and not _out) else (_cv if not _out else (_cv if h else "transparent"))
                        _lbl.color   = _cv if (h and not _out) else ("#FFFFFF" if not _out else (_cv if not h else "#FFFFFF"))
                        page.update()
                    except Exception:
                        pass
                c.on_hover = hov
                return c

            def do_accept(e, iid=inv_id):
                def run():
                    respond_invitation(iid, True, session)
                    invalidate_cache()
                    _reload_invites()
                    try: page.update()
                    except Exception: pass
                threading.Thread(target=run, daemon=True).start()
                status_row.controls = [
                    ft.Text("Accepted ✓", size=11, color=th["success"],
                            weight=ft.FontWeight.W_600)
                ]
                status_row.update()

            def do_decline(e, iid=inv_id):
                def run():
                    respond_invitation(iid, False, session)
                    _reload_invites()
                    try: page.update()
                    except Exception: pass
                threading.Thread(target=run, daemon=True).start()
                status_row.controls = [
                    ft.Text("Declined", size=11, color=th["text3"])
                ]
                status_row.update()

            status_row.controls = [
                make_btn("Accept", th["success"], False, do_accept),
                make_btn("Decline", th["danger"], True,  do_decline),
            ]
            return card

        def _build_notif_panel():
            if not pending_invites:
                body = ft.Column([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED,
                            size=32, color=th["text3"]),
                    ft.Text("No new notifications", size=12, color=th["text3"]),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   alignment=ft.MainAxisAlignment.CENTER, spacing=8,
                   width=280)
            else:
                body = ft.Column(
                    [_invite_card(inv) for inv in pending_invites],
                    spacing=8, scroll=ft.ScrollMode.AUTO,
                    width=300,
                    height=min(len(pending_invites) * 120, 360),
                )

            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Notifications", size=13,
                                weight=ft.FontWeight.W_700, color=th["text"]),
                        ft.Container(expand=True),
                        ft.IconButton(
                            ft.Icons.CLOSE_ROUNDED, icon_size=16,
                            icon_color=th["text3"],
                            on_click=lambda _: _toggle_notif(),
                        ),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=1, color=th["divider"]),
                    body,
                ], spacing=10, tight=True),
                bgcolor=th["modal"],
                border=ft.Border.all(1, th["border"]),
                border_radius=12,
                padding=16,
                width=320,
                shadow=ft.BoxShadow(blur_radius=20, color="#00000033",
                                    offset=ft.Offset(0, 4)),
            )

        def _reload_invites():
            nonlocal pending_invites
            try:
                pending_invites = get_pending_invitations(user_email)
            except Exception as e:
                print(f"[notif] fetch error: {e}")
                pending_invites = []
            _refresh_badge()

        def _refresh_badge():
            badge_dot.visible = len(pending_invites) > 0
            try:
                badge_dot.update()
            except Exception:
                pass

        def _toggle_notif():
            notif_open[0] = not notif_open[0]
            if notif_open[0]:
                notif_overlay.content = _build_notif_panel()
                notif_overlay.visible = True
            else:
                notif_overlay.visible = False
            try: page.update()
            except Exception: pass

        # Overlay container positioned at top-left of the Stack
        notif_overlay = ft.Container(
            content=None, visible=False,
            left=218, top=52,
        )

        # Bell button (placed in sidebar footer area)
        bell_icon = ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED,
                            size=18, color=th["text3"])
        bell_btn = ft.Container(
            content=ft.Stack([
                ft.Container(
                    content=bell_icon,
                    width=36, height=36,
                    border_radius=8,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    content=badge_dot,
                    right=4, top=4,
                ),
            ], width=36, height=36),
            on_click=lambda _: _toggle_notif(),
            border_radius=8,
            padding=0,
        )
        def bell_hover(e):
            try:
                bell_btn.bgcolor = th["nav_hover"] if e.data == "true" else "transparent"
                bell_btn.update()
            except Exception:
                pass
        bell_btn.on_hover = bell_hover

        # ── Theme / navigation helpers ────────────────────────────────────────
        def apply_theme():
            page.theme_mode = ft.ThemeMode.DARK if th == DARK else ft.ThemeMode.LIGHT
            page.bgcolor    = th["bg"]
            sidebar.bgcolor = th["sidebar"]
            sidebar.border  = ft.Border.only(right=ft.BorderSide(1, th["border"]))
            brand_text.color = th["text3"]
            brand_dot.bgcolor = th["accent"]
            for item in nav_items:
                item.set_theme(th)

        def refresh_home():
            if current_screen[0] == "Home":
                render_screen("Home")
                page.update()

        def render_screen(name):
            current_screen[0] = name
            settings_dirty[0] = None
            if name == "Home":
                content_container.content = build_home_screen(
                    go_to_projects, th, username, page)
            elif name == "Projects":
                content_container.content = build_projects_screen(
                    page, th, refresh_home, username, session=session)
            elif name == "Settings":
                screen, dirty = build_settings_screen(
                    th, settings, on_settings_save, page,
                    on_sign_out=do_sign_out, username=username, photo_url=photo_url)
                settings_dirty[0] = dirty
                content_container.content = screen

        def safe_navigate(name, nav_item):
            dirty_ref = settings_dirty[0]
            if current_screen[0] == "Settings" and dirty_ref and dirty_ref[0]:
                def proceed(e):
                    unsaved_dlg.open = False; page.update()
                    _do_navigate(name, nav_item)
                def stay(e):
                    unsaved_dlg.open = False; page.update()
                unsaved_dlg.title   = ft.Text("Unsaved changes", weight=ft.FontWeight.W_700)
                unsaved_dlg.content = ft.Text("Leave without saving?", size=13)
                unsaved_dlg.actions = [
                    ft.TextButton("Stay", on_click=stay),
                    ft.FilledButton("Leave", on_click=proceed,
                                    style=ft.ButtonStyle(bgcolor=th["accent"],
                                                         color="#FFFFFF")),
                ]
                if unsaved_dlg not in page.overlay:
                    page.overlay.append(unsaved_dlg)
                unsaved_dlg.open = True; page.update()
            else:
                _do_navigate(name, nav_item)

        def _do_navigate(name, nav_item):
            for item in nav_items:
                item.set_state(active=(item == nav_item))
            # close notif panel on navigation
            notif_overlay.visible = False
            notif_open[0] = False
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

        def do_sign_out():
            clear_session()
            show_login()

        # ── Nav items ─────────────────────────────────────────────────────────
        nav_items = [
            NavItem(ft.Icons.HOME_ROUNDED,     "Home",     nav_clicked, th, selected=True),
            NavItem(ft.Icons.FOLDER_ROUNDED,   "Projects", nav_clicked, th),
            NavItem(ft.Icons.SETTINGS_ROUNDED, "Settings", nav_clicked, th),
        ]

        brand_dot  = ft.Container(width=8, height=8,
                                  bgcolor=th["accent"], border_radius=4)
        brand_text = ft.Text("PROGRESS", size=11, weight=ft.FontWeight.W_700,
                             color=th["text3"])

        initials = username[0].upper() if username else "?"
        avatar = (
            ft.Container(
                content=ft.Image(src=photo_url, width=28, height=28, fit="cover"),
                width=28, height=28, border_radius=14,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ) if photo_url else
            ft.Container(
                content=ft.Text(initials, size=11, color="#FFFFFF",
                                weight=ft.FontWeight.W_700),
                width=28, height=28, border_radius=14,
                bgcolor=th["accent"], alignment=ft.Alignment.CENTER,
            )
        )

        user_row = ft.Container(
            content=ft.Row([
                avatar,
                ft.Text(username, size=12, color=th["text2"],
                        weight=ft.FontWeight.W_500, expand=True,
                        overflow=ft.TextOverflow.ELLIPSIS),
                bell_btn,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=10, horizontal=15),
        )

        sidebar = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([brand_dot, brand_text], spacing=8,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.only(left=15, bottom=8, top=4),
                ),
                *nav_items,
                ft.Container(expand=True),
                ft.Divider(height=1, color=th["divider"]),
                user_row,
            ], spacing=2, expand=True),
            padding=ft.Padding.symmetric(vertical=24, horizontal=8),
            width=210, bgcolor=th["sidebar"],
            border=ft.Border.only(right=ft.BorderSide(1, th["border"])),
        )

        render_screen("Home")

        # Fetch invitations in background after first render
        threading.Thread(target=_reload_invites, daemon=True).start()

        app_row = ft.Row([sidebar, content_container], expand=True, spacing=0)

        return ft.Stack([
            app_row,
            notif_overlay,
        ], expand=True)

    # ── Boot ──────────────────────────────────────────────────────────────────
    session = load_session()
    if session:
        set_current_user(session.get("uid", ""))
        threading.Thread(target=prewarm_connection, daemon=True).start()
        show_app(session)
    else:
        show_login()


ft.run(main)
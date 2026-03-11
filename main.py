import flet as ft
import os
import threading
from config import DARK, LIGHT
from storage import load_settings, save_settings, BASE_DIR, set_current_user, upsert_user
from auth import load_session, clear_session
from ui_components import NavItem
from ui_login import build_login_screen
from ui_home import build_home_screen
from ui_projects import build_projects_screen
from ui_settings import build_settings_screen


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

    # ── Root container — swaps between login and app ──────────────────────────
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
        show_app(session)

    def show_app(session: dict):
        root.controls = [_build_app(session)]
        page.update()

    def _build_app(session: dict) -> ft.Stack:
        username = session.get("display_name", "you")
        photo_url = session.get("photo_url", "")
        nonlocal th
        content_container = ft.Container(expand=True)
        current_screen = ["Home"]
        settings_dirty = [None]
        unsaved_dlg = ft.AlertDialog(modal=True)

        # Fix: Defined notif_panel so it exists when the Stack builds
        notif_panel = ft.Container(
            content=ft.Text("No new notifications", size=12, color=th["text2"]),
            bgcolor=th["sidebar"],
            padding=15,
            border=ft.border.all(1, th["border"]),
            border_radius=8,
            shadow=ft.BoxShadow(blur_radius=10, color="black12"),
            visible=False, # Toggle this to True to show it
        )

        def apply_theme():
            page.theme_mode = ft.ThemeMode.DARK if th == DARK else ft.ThemeMode.LIGHT
            page.bgcolor = th["bg"]
            sidebar.bgcolor = th["sidebar"]
            sidebar.border = ft.Border.only(right=ft.BorderSide(1, th["border"]))
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
                unsaved_dlg.title = ft.Text("Unsaved changes", weight=ft.FontWeight.W_700)
                unsaved_dlg.content = ft.Text("Leave without saving?", size=13)
                unsaved_dlg.actions = [
                    ft.TextButton("Stay", on_click=stay),
                    ft.FilledButton("Leave", on_click=proceed,
                                    style=ft.ButtonStyle(bgcolor=th["accent"], color="#FFFFFF")),
                ]
                if unsaved_dlg not in page.overlay:
                    page.overlay.append(unsaved_dlg)
                unsaved_dlg.open = True; page.update()
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

        def do_sign_out():
            clear_session()
            show_login()

        nav_items = [
            NavItem(ft.Icons.HOME_ROUNDED, "Home", nav_clicked, th, selected=True),
            NavItem(ft.Icons.FOLDER_ROUNDED, "Projects", nav_clicked, th),
            NavItem(ft.Icons.SETTINGS_ROUNDED, "Settings", nav_clicked, th),
        ]

        brand_dot = ft.Container(width=8, height=8, bgcolor=th["accent"], border_radius=4)
        brand_text = ft.Text("PROGRESS", size=11, weight=ft.FontWeight.W_700, color=th["text3"])

        initials = (username[0].upper() if username else "?")
        avatar = (
            ft.Container(
                content=ft.Image(src=photo_url, width=28, height=28, fit="cover"),
                width=28, height=28, border_radius=14,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            )
            if photo_url else
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
        app_row = ft.Row([sidebar, content_container], expand=True, spacing=0)

        # Corrected Stack implementation for Flet
        return ft.Stack([
            app_row,
            ft.Container(
                content=notif_panel,
                left=218,
                top=52
            ),
        ], expand=True)

    # ── Boot: check for saved session ─────────────────────────────────────────
    session = load_session()
    if session:
        set_current_user(session.get("uid", ""))
        show_app(session)
    else:
        show_login()


ft.run(main)
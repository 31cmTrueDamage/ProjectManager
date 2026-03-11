import flet as ft
from config import DARK, LIGHT
from storage import load_settings, BASE_DIR
from ui_components import NavItem
from ui_home import build_home_screen
from ui_projects import build_projects_screen
from ui_settings import build_settings_screen
import os


def main(page: ft.Page):
    settings = load_settings()
    th       = DARK if settings["dark_mode"] else LIGHT

    page.title      = "Project Manager"
    page.window.icon = os.path.join(BASE_DIR, "sabrina.jpg")
    page.theme      = ft.Theme(color_scheme=ft.ColorScheme(surface_tint="#00000000"))
    page.dark_theme = ft.Theme(color_scheme=ft.ColorScheme(surface_tint="#00000000"))
    page.theme_mode = ft.ThemeMode.DARK if settings["dark_mode"] else ft.ThemeMode.LIGHT
    page.bgcolor    = th["bg"]
    page.padding    = 0
    page.update()

    content_container = ft.Container(expand=True)
    current_screen    = ["Home"]
    settings_dirty    = [None]
    unsaved_dlg       = ft.AlertDialog(modal=True)

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
            render_screen("Home")
            page.update()

    def render_screen(name):
        current_screen[0] = name
        settings_dirty[0] = None
        if name == "Home":
            content_container.content = build_home_screen(
                go_to_projects, th, settings["username"], page)
        elif name == "Projects":
            content_container.content = build_projects_screen(
                page, th, refresh_home, settings["username"])
        elif name == "Settings":
            screen, dirty = build_settings_screen(th, settings, on_settings_save, page)
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
import flet as ft
from datetime import datetime
from config import DARK
from storage import get_stats


def _greeting() -> tuple:
    h = datetime.now().hour
    if h < 12: return "Good morning", "☀️"
    if h < 17: return "Good afternoon", "🌤️"
    return "Good evening", "🌙"


def build_home_screen(go_to_projects, th: dict, username: str, page: ft.Page) -> ft.Container:
    greeting, emoji = _greeting()
    active, done, pending = get_stats()

    def stat_card(icon, value, label, color, bg_l, bg_d):
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(icon, color=color, size=18),
                    width=36, height=36,
                    bgcolor=bg_d if th == DARK else bg_l,
                    border_radius=10, alignment=ft.Alignment.CENTER,
                ),
                ft.Text(str(value), size=22, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Text(label, size=11, color=th["text3"]),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20, border_radius=14,
            bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
            expand=True, alignment=ft.Alignment.CENTER,
        )

    lbl  = ft.Text("View Projects", color="#FFFFFF", weight=ft.FontWeight.W_600, size=13)
    icon = ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color="#FFFFFF", size=16)
    btn  = ft.Container(
        content=ft.Row([lbl, icon], alignment=ft.MainAxisAlignment.CENTER,
                       spacing=8, tight=True),
        bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=14, horizontal=28),
        on_click=go_to_projects, width=200, alignment=ft.Alignment.CENTER,
    )

    def on_hover(e):
        try:
            h = e.data == "true"
            btn.bgcolor = "transparent" if h else th["accent"]
            lbl.color   = th["accent"]  if h else "#FFFFFF"
            icon.color  = th["accent"]  if h else "#FFFFFF"
            page.update()
        except Exception:
            pass
    btn.on_hover = on_hover

    return ft.Container(
        content=ft.Column([
            ft.Column([
                ft.Text(f"{emoji}  {greeting}, {username.capitalize() or 'there'}.",
                        size=13, color=th["text3"], weight=ft.FontWeight.W_500),
                ft.Text("Welcome back.", size=28, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Text(
                    f"{datetime.now().strftime('%A')}, {datetime.now().strftime('%B %d, %Y')}",
                    size=12, color=th["text3"],
                ),
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
                btn,
            ], spacing=4),
        ], spacing=20),
        padding=40, expand=True,
    )
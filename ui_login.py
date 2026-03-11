import flet as ft
import threading
from auth import open_google_login
from config import DARK


def build_login_screen(page: ft.Page, th: dict, on_login_success) -> ft.Container:
    """
    Full-screen login view. Calls on_login_success(session) when authenticated.
    """

    # ── State ─────────────────────────────────────────────────────────────────
    status_text  = ft.Text("", size=13, color=th["text3"],
                           text_align=ft.TextAlign.CENTER)
    loading_ring = ft.ProgressRing(width=20, height=20, stroke_width=2,
                                   color=th["accent"], visible=False)

    # ── Google button ─────────────────────────────────────────────────────────
    g_lbl = ft.Text("Continue with Google", size=14, weight=ft.FontWeight.W_600)
    g_icon = ft.Image(
        src="https://www.google.com/favicon.ico",
        width=18, height=18, fit="contain",
    )
    # Fallback letter icon in case image doesn't load
    g_icon_fallback = ft.Container(
        content=ft.Text("G", size=13, weight=ft.FontWeight.W_700, color="#4285F4"),
        width=20, height=20, border_radius=10,
        border=ft.Border.all(1.5, "#4285F4"),
        alignment=ft.Alignment.CENTER,
    )

    google_btn = ft.ElevatedButton(
        content=ft.Row(
            [g_icon_fallback, g_lbl],
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        ),
        style=ft.ButtonStyle(
            color={ft.ControlState.DEFAULT: th["text"], ft.ControlState.HOVERED: th["text"]},
            bgcolor={ft.ControlState.DEFAULT: th["card"], ft.ControlState.HOVERED: th["nav_hover"]},
            side={ft.ControlState.DEFAULT: ft.BorderSide(1.5, th["border2"]), ft.ControlState.HOVERED: ft.BorderSide(1.5, th["accent"])},
            overlay_color=ft.Colors.TRANSPARENT,
            padding=ft.Padding.symmetric(vertical=14, horizontal=28),
            shape=ft.RoundedRectangleBorder(radius=12),
        ),
        width=280,
    )

    def set_loading(loading: bool, msg: str = ""):
        loading_ring.visible = loading
        google_btn.disabled  = loading
        status_text.value    = msg
        try: page.update()
        except Exception: pass

    def on_success(session: dict):
        set_loading(False, "")
        on_login_success(session)

    def on_error(msg: str):
        set_loading(False, f"Sign-in failed: {msg}")

    def handle_click(e):
        set_loading(True, "Opening browser…")
        threading.Thread(
            target=open_google_login,
            args=(on_success, on_error),
            daemon=True,
        ).start()

    google_btn.on_click = handle_click

    # ── Layout ────────────────────────────────────────────────────────────────
    is_dark = th == DARK

    # Subtle animated gradient accent bar at top
    accent_bar = ft.Container(
        height=3,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, 0),
            end=ft.Alignment(1, 0),
            colors=[th["accent"], "#7C3AED", th["accent"]],
        ),
    )

    logo_dot   = ft.Container(width=10, height=10, bgcolor=th["accent"], border_radius=5)
    logo_text  = ft.Text("PROGRESS", size=12, weight=ft.FontWeight.W_700,
                         color=th["text3"], style=ft.TextStyle(letter_spacing=2))

    card = ft.Container(
        content=ft.Column([
            # Logo
            ft.Row([logo_dot, logo_text], spacing=8,
                   alignment=ft.MainAxisAlignment.CENTER,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8),

            # Heading
            ft.Text("Welcome back", size=28, weight=ft.FontWeight.W_700,
                    color=th["text"], text_align=ft.TextAlign.CENTER),
            ft.Text("Sign in to access your projects", size=13, color=th["text3"],
                    text_align=ft.TextAlign.CENTER),
            ft.Container(height=24),

            # Google button
            google_btn,
            ft.Container(height=12),

            # Loading + status
            ft.Row([loading_ring], alignment=ft.MainAxisAlignment.CENTER),
            status_text,

            ft.Container(height=16),
            ft.Text("Your data is stored securely in the cloud.",
                    size=11, color=th["text3"], text_align=ft.TextAlign.CENTER),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=6),
        bgcolor=th["card"],
        border=ft.Border.all(1, th["border"]),
        border_radius=20,
        padding=ft.Padding.symmetric(vertical=48, horizontal=56),
        width=420,
    )

    return ft.Container(
        content=ft.Column([
            accent_bar,
            ft.Container(
                content=card,
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
        ], spacing=0, expand=True),
        bgcolor=th["bg"],
        expand=True,
    )
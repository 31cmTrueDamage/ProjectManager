import flet as ft
import time, threading
from storage import save_settings


def build_settings_screen(th: dict, settings: dict, on_save, page: ft.Page,
                           on_sign_out=None, username: str = "", photo_url: str = ""):
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

    dark_sw = ft.Switch(value=settings["dark_mode"], active_color=th["accent"])

    def mark_dirty(e): dirty[0] = True
    dark_sw.on_change = mark_dirty

    # ── Save button ───────────────────────────────────────────────────────────
    save_lbl  = ft.Text("Save Changes", color="#FFFFFF", size=13, weight=ft.FontWeight.W_600)
    save_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=16, visible=False)
    save_btn  = ft.Container(
        content=ft.Row([save_icon, save_lbl], spacing=6,
                       alignment=ft.MainAxisAlignment.CENTER, tight=True),
        bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=12, horizontal=24),
        width=180, alignment=ft.Alignment.CENTER,
    )

    def on_save_hover(e):
        try:
            h = e.data == "true"
            save_btn.bgcolor = "transparent" if h else th["accent"]
            save_lbl.color   = th["accent"]  if h else "#FFFFFF"
            save_icon.color  = th["accent"]  if h else "#FFFFFF"
            page.update()
        except Exception:
            pass
    save_btn.on_hover = on_save_hover

    def do_save(e):
        settings["dark_mode"] = dark_sw.value
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

    # ── Sign-out button ───────────────────────────────────────────────────────
    so_lbl = ft.Text("Sign Out", color=th["danger"], size=13, weight=ft.FontWeight.W_600)
    so_icon = ft.Icon(ft.Icons.LOGOUT_ROUNDED, color=th["danger"], size=16)
    sign_out_btn = ft.Container(
        content=ft.Row([so_icon, so_lbl], spacing=6,
                       alignment=ft.MainAxisAlignment.CENTER, tight=True),
        bgcolor="transparent", border=ft.Border.all(1.5, th["danger"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=12, horizontal=24),
        width=180, alignment=ft.Alignment.CENTER,
        visible=on_sign_out is not None,
    )

    def on_so_hover(e):
        try:
            h = e.data == "true"
            sign_out_btn.bgcolor = th["danger"] if h else "transparent"
            so_lbl.color  = "#FFFFFF" if h else th["danger"]
            so_icon.color = "#FFFFFF" if h else th["danger"]
            page.update()
        except Exception:
            pass
    sign_out_btn.on_hover = on_so_hover
    sign_out_btn.on_click = lambda _: on_sign_out() if on_sign_out else None

    # ── Account info row ──────────────────────────────────────────────────────
    avatar = (
        ft.Container(
            content=ft.Image(src=photo_url, width=40, height=40, fit="cover"),
            width=40, height=40, border_radius=20,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        if photo_url else
        ft.Container(
            content=ft.Text(username[0].upper() if username else "?",
                            size=14, color="#FFFFFF", weight=ft.FontWeight.W_700),
            width=40, height=40, border_radius=20,
            bgcolor=th["accent"], alignment=ft.Alignment.CENTER,
        )
    )
    account_info = ft.Container(
        content=ft.Row([
            avatar,
            ft.Column([
                ft.Text(username, size=13, weight=ft.FontWeight.W_600, color=th["text"]),
                ft.Text("Google account", size=11, color=th["text3"]),
            ], spacing=2, expand=True),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(vertical=14, horizontal=18),
        border_radius=10, bgcolor=th["card"],
        border=ft.Border.all(1, th["border"]),
    )

    screen = ft.Container(
        content=ft.Column([
            ft.Column([
                ft.Text("Settings", size=28, weight=ft.FontWeight.W_700, color=th["text"]),
                ft.Text("Manage your preferences", size=13, color=th["text3"]),
            ], spacing=4),
            ft.Divider(height=1, color=th["divider"]),
            section("Appearance", [
                setting_row("Dark Mode", "Switch to a darker interface", dark_sw),
            ]),
            section("Account", [account_info]),
            ft.Divider(height=1, color=th["divider"]),
            ft.Row([save_btn, sign_out_btn], spacing=12),
        ], spacing=24, scroll=ft.ScrollMode.AUTO),
        padding=40, expand=True,
    )
    return screen, dirty
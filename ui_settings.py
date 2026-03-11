import flet as ft
import time, threading
from storage import save_settings


def build_settings_screen(th: dict, settings: dict, on_save, page: ft.Page):
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
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=0),
    )

    def mark_dirty(e): dirty[0] = True
    dark_sw.on_change     = mark_dirty
    username_tf.on_change = mark_dirty

    save_lbl  = ft.Text("Save Changes", color="#FFFFFF", size=13, weight=ft.FontWeight.W_600)
    save_icon = ft.Icon(ft.Icons.CHECK_ROUNDED, color="#FFFFFF", size=16, visible=False)
    save_btn  = ft.Container(
        content=ft.Row([save_icon, save_lbl], spacing=6,
                       alignment=ft.MainAxisAlignment.CENTER, tight=True),
        bgcolor=th["accent"], border=ft.Border.all(1.5, th["accent"]),
        border_radius=10, padding=ft.Padding.symmetric(vertical=12, horizontal=24),
        width=180, alignment=ft.Alignment.CENTER,
    )

    def on_hover(e):
        try:
            h = e.data == "true"
            save_btn.bgcolor = "transparent" if h else th["accent"]
            save_lbl.color   = th["accent"]  if h else "#FFFFFF"
            save_icon.color  = th["accent"]  if h else "#FFFFFF"
            page.update()
        except Exception:
            pass
    save_btn.on_hover = on_hover

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
            section("Account", [
                setting_row("Username", "Shown on the home screen", username_tf),
            ]),
            ft.Divider(height=1, color=th["divider"]),
            save_btn,
        ], spacing=24, scroll=ft.ScrollMode.AUTO),
        padding=40, expand=True,
    )
    return screen, dirty
import flet as ft


# ── Tiny pill badge ───────────────────────────────────────────────────────────
def pill(label: str, color: str, bg: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=10, color=color, weight=ft.FontWeight.W_600),
        bgcolor=bg, border_radius=20,
        padding=ft.Padding.symmetric(vertical=2, horizontal=8),
    )


# ── Section label (icon + uppercase text) ────────────────────────────────────
def section_label(text: str, icon, th: dict) -> ft.Row:
    return ft.Row([
        ft.Icon(icon, size=13, color=th["text3"]),
        ft.Text(text.upper(), size=10, weight=ft.FontWeight.W_700,
                color=th["text3"], style=ft.TextStyle(letter_spacing=0.8)),
    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)


# ── Generic hover button (Container-based, reliable color inversion) ──────────
def hover_btn(
    label: str,
    icon_name,
    on_click,
    th: dict,
    page: ft.Page,
    color: str = None,
    outline: bool = False,
    padding: ft.Padding = None,
    border_radius: int = 8,
    height: int = None,
) -> ft.Container:
    """
    outline=True  → border/text colored, fills on hover
    outline=False → solid fill, inverts to outline on hover
    """
    c = color or th["accent"]
    pad = padding or ft.Padding.symmetric(vertical=8, horizontal=14)

    ic  = ft.Icon(icon_name, color=(c if outline else "#FFFFFF"), size=13)
    lbl = ft.Text(label, color=(c if outline else "#FFFFFF"),
                  size=12, weight=ft.FontWeight.W_500) if label else None
    row_children = [ic] + ([lbl] if lbl else [])

    btn = ft.Container(
        content=ft.Row(row_children, spacing=5,
                       alignment=ft.MainAxisAlignment.CENTER, tight=True),
        bgcolor="transparent" if outline else c,
        border=ft.Border.all(1.5, c),
        border_radius=border_radius,
        padding=pad,
        on_click=on_click,
        **({"height": height} if height else {}),
    )

    def on_hover(e):
        try:
            if btn.page is None:
                return
            hovered = e.data == "true"
            if outline:
                btn.bgcolor = c if hovered else "transparent"
                ic.color  = "#FFFFFF" if hovered else c
                if lbl: lbl.color = "#FFFFFF" if hovered else c
            else:
                btn.bgcolor = "transparent" if hovered else c
                ic.color  = c if hovered else "#FFFFFF"
                if lbl: lbl.color = c if hovered else "#FFFFFF"
            page.update()
        except Exception:
            pass

    btn.on_hover = on_hover
    return btn


# ── Confirm dialog ────────────────────────────────────────────────────────────
def show_confirm(page: ft.Page, th: dict, dlg: ft.AlertDialog,
                 title: str, message: str, confirm_label: str,
                 on_confirm, danger: bool = True) -> None:
    c = th["danger"] if danger else th["accent"]

    def do_confirm(e):
        dlg.open = False; page.update(); on_confirm()

    def do_cancel(e):
        dlg.open = False; page.update()

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


# ── Toast ─────────────────────────────────────────────────────────────────────
def show_toast(page: ft.Page, th: dict, message: str, success: bool = True) -> None:
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color="white"),
        bgcolor=th["success"] if success else th["danger"],
        duration=2000,
    )
    page.snack_bar.open = True
    page.update()


# ── Nav item ──────────────────────────────────────────────────────────────────
class NavItem(ft.Container):
    def __init__(self, icon, label: str, on_click_handler, th: dict, selected: bool = False):
        super().__init__()
        self.selected         = selected
        self.label_text       = label
        self.on_click_handler = on_click_handler
        self.th               = th
        self.padding          = ft.Padding.symmetric(vertical=10, horizontal=15)
        self.border_radius    = 10
        self.bgcolor          = th["nav_sel_bg"] if selected else "transparent"
        self.animate          = ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT)
        self.on_hover         = self._hover
        self.on_click         = self._click

        self.indicator = ft.Container(
            width=3, height=22,
            bgcolor=th["accent"] if selected else "transparent",
            border_radius=2,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT),
        )
        self.icon_ctl = ft.Icon(icon,
            color=th["accent"] if selected else th["text3"], size=18)
        self.text_ctl = ft.Text(label,
            color=th["accent"] if selected else th["text2"],
            weight=ft.FontWeight.W_500, size=13)
        self.content = ft.Row(
            [self.indicator, self.icon_ctl, self.text_ctl],
            spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _click(self, e):
        self.on_click_handler(self)

    def set_theme(self, th: dict) -> None:
        self.th = th
        self.set_state(self.selected)

    def set_state(self, active: bool) -> None:
        self.selected          = active
        self.bgcolor           = self.th["nav_sel_bg"] if active else "transparent"
        self.indicator.bgcolor = self.th["accent"]     if active else "transparent"
        self.icon_ctl.color    = self.th["accent"]     if active else self.th["text3"]
        self.text_ctl.color    = self.th["accent"]     if active else self.th["text2"]
        self.update()

    def _hover(self, e):
        if not self.selected:
            self.bgcolor = self.th["nav_hover"] if e.data == "true" else "transparent"
            self.update()
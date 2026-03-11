import flet as ft
import threading
from storage import (
    send_invitation, lookup_user_by_email, set_member_role,
    remove_member, get_role, can,
    CAN_MANAGE_MEMBERS, CAN_DELETE_PROJECT,
    ROLES, ROLE_LABELS, write_project,
)
from ui_components import hover_btn, show_confirm, show_toast


ROLE_COLORS = {
    "owner":  "#6366F1",
    "editor": "#0891B2",
    "viewer": "#64748B",
}
ROLE_BG = {
    "owner":  "#EEF2FF",
    "editor": "#E0F2FE",
    "viewer": "#F1F5F9",
}
ROLE_BG_DK = {
    "owner":  "#1e1b4b",
    "editor": "#0c4a6e",
    "viewer": "#1e293b",
}


def role_pill(role: str, th) -> ft.Container:
    from config import DARK
    bg = ROLE_BG_DK[role] if th == DARK else ROLE_BG[role]
    return ft.Container(
        content=ft.Text(ROLE_LABELS[role], size=10,
                        color=ROLE_COLORS[role], weight=ft.FontWeight.W_600),
        bgcolor=bg, border_radius=20,
        padding=ft.Padding.symmetric(vertical=2, horizontal=8),
    )


def build_members_panel(proj: dict, session: dict, th, page: ft.Page,
                        on_close, dlg: ft.AlertDialog) -> ft.Container:
    """
    Full members management panel shown as a modal sheet.
    session = logged-in user's {uid, display_name, email, ...}
    """
    uid        = session["uid"]
    my_role    = get_role(proj, uid)
    can_manage = can(proj, uid, CAN_MANAGE_MEMBERS)

    invite_err   = ft.Text("", size=11, color=th["danger"], visible=False)
    members_col  = ft.Column(spacing=8)

    # ── Role dropdown for invite ──────────────────────────────────────────────
    invite_role  = ["editor"]
    role_lbl     = ft.Text(ROLE_LABELS["editor"], size=12,
                           weight=ft.FontWeight.W_500, color=th["text"])
    role_dd = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row([role_lbl,
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED,
                                    color=th["text3"], size=18)],
                           alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            border=ft.Border.all(1, th["border2"]), border_radius=8,
            bgcolor=th["input_bg"], height=38, width=110,
            padding=ft.Padding.symmetric(horizontal=10),
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Text(ROLE_LABELS[r], size=12, color=th["text"]),
                data=r,
                on_click=lambda e: (
                    invite_role.__setitem__(0, e.control.data),
                    setattr(role_lbl, "value", ROLE_LABELS[e.control.data]),
                    page.update(),
                ),
            )
            for r in ["editor", "viewer"]   # owner not invitable
        ],
    )

    email_tf = ft.TextField(
        hint_text="Invite by email…",
        border_color=th["border2"], bgcolor=th["input_bg"], color=th["text"],
        text_size=13, height=38, expand=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=0),
    )

    def do_invite(e):
        email = email_tf.value.strip().lower()
        if not email:
            invite_err.value = "Enter an email address."
            invite_err.visible = True; invite_err.update(); return

        def run():
            result = send_invitation(proj, session, email, invite_role[0])
            msgs = {
                "ok":             ("Invitation sent!", True),
                "self":           ("That's your own email.", False),
                "already_member": ("Already a member.", False),
                "pending":        ("Invitation already sent.", False),
            }
            msg, success = msgs.get(result, ("Unknown error.", False))
            invite_err.value   = "" if success else msg
            invite_err.visible = not success
            email_tf.value     = "" if success else email_tf.value
            try:
                show_toast(page, th, msg, success)
                page.update()
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    invite_btn = hover_btn("Invite", ft.Icons.SEND_ROUNDED, do_invite, th, page,
                           border_radius=8, height=38,
                           padding=ft.Padding.symmetric(horizontal=16))

    # ── Member row ────────────────────────────────────────────────────────────
    def member_row(m: dict, is_owner_row: bool = False) -> ft.Container:
        display  = m.get("display_name") or m.get("email", "?")
        email    = m.get("email", "")
        role     = "owner" if is_owner_row else m.get("role", "viewer")
        m_uid    = m.get("uid", "")
        initial  = display[0].upper() if display else "?"

        # Role change dropdown (only owner can change, not for owner row)
        role_controls = []
        if can_manage and not is_owner_row:
            r_lbl = ft.Text(ROLE_LABELS[role], size=11,
                            weight=ft.FontWeight.W_500, color=th["text2"])
            r_dd  = ft.PopupMenuButton(
                content=ft.Container(
                    content=ft.Row([r_lbl,
                                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED,
                                            color=th["text3"], size=16)],
                                   spacing=2,
                                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    border=ft.Border.all(1, th["border2"]), border_radius=6,
                    bgcolor=th["input_bg"], height=28,
                    padding=ft.Padding.symmetric(horizontal=8),
                ),
                items=[
                    ft.PopupMenuItem(
                        content=ft.Text(ROLE_LABELS[r], size=11, color=th["text"]),
                        data=r,
                        on_click=lambda e, mu=m_uid, rl=r_lbl: (
                            set_member_role(proj, mu, e.control.data),
                            setattr(rl, "value", ROLE_LABELS[e.control.data]),
                            show_toast(page, th, "Role updated"),
                            page.update(),
                        ),
                    )
                    for r in ["editor", "viewer"]
                ],
            )
            role_controls = [r_dd]

            # Remove button (demotes to viewer)
            conf_dlg = ft.AlertDialog(modal=True)
            def ask_remove(e, mu=m_uid, dn=display):
                show_confirm(page, th, conf_dlg,
                             "Remove member?",
                             f"{dn} will keep read-only (Viewer) access.",
                             "Remove", lambda: (
                                 remove_member(proj, mu),
                                 refresh_members(),
                                 show_toast(page, th, f"{dn} set to Viewer"),
                                 page.update(),
                             ))
            if conf_dlg not in page.overlay:
                page.overlay.append(conf_dlg)
            role_controls.append(
                ft.IconButton(ft.Icons.PERSON_REMOVE_OUTLINED, icon_size=16,
                              icon_color=th["text3"], tooltip="Demote to Viewer",
                              on_click=ask_remove)
            )
        else:
            role_controls = [role_pill(role, th)]

        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(initial, size=11, color="#FFFFFF",
                                    weight=ft.FontWeight.W_700),
                    width=30, height=30, border_radius=15,
                    bgcolor=ROLE_COLORS[role], alignment=ft.Alignment.CENTER,
                ),
                ft.Column([
                    ft.Text(display, size=13, weight=ft.FontWeight.W_500,
                            color=th["text"]),
                    ft.Text(email, size=10, color=th["text3"]),
                ], spacing=1, expand=True),
                *role_controls,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            bgcolor=th["card"], border=ft.Border.all(1, th["border"]),
            border_radius=10, padding=ft.Padding.symmetric(vertical=10, horizontal=14),
        )

    def refresh_members():
        rows = []
        # Owner row
        owner_info = {
            "uid":          proj.get("owner_uid", ""),
            "display_name": session["display_name"] if proj.get("owner_uid") == uid
                            else proj.get("owner_name", "Owner"),
            "email":        session["email"] if proj.get("owner_uid") == uid
                            else proj.get("owner_email", ""),
        }
        rows.append(member_row(owner_info, is_owner_row=True))

        for m in proj.get("members", []):
            if m.get("role") != "owner":
                rows.append(member_row(m))

        members_col.controls = rows
        try: page.update()
        except Exception: pass

    refresh_members()

    # ── Layout ────────────────────────────────────────────────────────────────
    invite_section = ft.Column([
        ft.Text("Invite someone", size=12, color=th["text3"],
                weight=ft.FontWeight.W_600),
        ft.Row([email_tf, role_dd, invite_btn], spacing=8,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
        invite_err,
    ], spacing=8, visible=can_manage)

    close_btn = hover_btn("Done", ft.Icons.CHECK_ROUNDED, lambda _: on_close(),
                          th, page, padding=ft.Padding.symmetric(vertical=10, horizontal=20),
                          border_radius=8)

    return ft.Container(
        content=ft.Column([
            # Header
            ft.Row([
                ft.Icon(ft.Icons.GROUP_ROUNDED, color=th["accent"], size=18),
                ft.Text("Members", size=18, weight=ft.FontWeight.W_700, color=th["text"],
                        expand=True),
                ft.Container(
                    content=ft.Text(f"Your role: {ROLE_LABELS[my_role]}", size=11,
                                    color=ROLE_COLORS[my_role], weight=ft.FontWeight.W_600),
                    bgcolor=ROLE_BG_DK[my_role] if th == th else ROLE_BG[my_role],
                    border_radius=20, padding=ft.Padding.symmetric(vertical=3, horizontal=10),
                ),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=1, color=th["divider"]),

            invite_section,
            *([ ft.Divider(height=1, color=th["divider"]) ] if can_manage else []),

            ft.Text("Members", size=12, color=th["text3"], weight=ft.FontWeight.W_600),
            ft.Column([members_col], scroll=ft.ScrollMode.AUTO, height=240),

            ft.Divider(height=1, color=th["divider"]),
            ft.Row([ft.Container(expand=True), close_btn]),
        ], spacing=12, tight=True),
        bgcolor=th["modal"],
        border_radius=16,
        padding=24,
        width=460,
        border=ft.Border.all(1, th["border"]),
    )
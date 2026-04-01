"""
Servboard 2.0 — Flet Multi-Page Client
Connects to the FastAPI backend via REST API.
Supports web, desktop, and mobile (iOS/Android via flet build).
"""

import flet as ft
import requests
import asyncio
import json
import time
from urllib.parse import urljoin

# ─── API Client ───────────────────────────────────────────────────────────────
class ApiClient:
    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _get(self, path, **kwargs):
        try:
            r = requests.get(urljoin(self.base_url + "/", path.lstrip("/")), headers=self._headers(), timeout=10, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return None

    def _post(self, path, **kwargs):
        try:
            r = requests.post(urljoin(self.base_url + "/", path.lstrip("/")), headers=self._headers(), timeout=30, **kwargs)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            detail = e.response.json().get("detail", str(e)) if e.response else str(e)
            raise ValueError(detail)
        except Exception as e:
            raise ValueError(str(e))

    def _put(self, path, **kwargs):
        try:
            r = requests.put(urljoin(self.base_url + "/", path.lstrip("/")), headers=self._headers(), timeout=10, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            raise ValueError(str(e))

    def _delete(self, path):
        try:
            requests.delete(urljoin(self.base_url + "/", path.lstrip("/")), headers=self._headers(), timeout=10)
        except Exception as e:
            raise ValueError(str(e))

    def health(self): return self._get("/api/health")
    def login(self, username, password):
        return self._post("/api/auth/login", data={"username": username, "password": password})
    def register(self, username, password):
        return self._post("/api/auth/register", json={"username": username, "password": password})
    def me(self): return self._get("/api/users/me")
    def metrics(self): return self._get("/api/metrics")
    def system_info(self): return self._get("/api/system")
    def execute(self, command, sudo_password):
        return self._post("/api/execute", json={"command": command, "sudo_password": sudo_password})
    def scripts(self): return self._get("/api/scripts")
    def pages(self): return self._get("/api/pages")
    def create_page(self, name, icon="grid_view"): return self._post("/api/pages", json={"name": name, "icon": icon})
    def update_page(self, pid, **kwargs): return self._put(f"/api/pages/{pid}", json=kwargs)
    def delete_page(self, pid): return self._delete(f"/api/pages/{pid}")
    def buttons(self, pid): return self._get(f"/api/pages/{pid}/buttons")
    def create_button(self, pid, **kwargs): return self._post(f"/api/pages/{pid}/buttons", json=kwargs)
    def update_button(self, bid, **kwargs): return self._put(f"/api/buttons/{bid}", json=kwargs)
    def delete_button(self, bid): return self._delete(f"/api/buttons/{bid}")
    def prefs(self): return self._get("/api/prefs")
    def update_prefs(self, **kwargs): return self._put("/api/prefs", json=kwargs)

# ─── Colors & Styles ──────────────────────────────────────────────────────────
ACCENT = ft.Colors.CYAN_400
BG = "#0d1117"
SURFACE = "#161b22"
SURFACE2 = "#21262d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
DANGER = "#f85149"
SUCCESS = "#3fb950"

def card(content, padding=16, radius=12, color=SURFACE):
    return ft.Container(content=content, padding=padding, border_radius=radius, bgcolor=color,
                        border=ft.border.all(1, "#30363d"))

def metric_gauge(label, value_ref, pct_ref, accent=ACCENT):
    """A circular progress gauge for metrics."""
    ring = ft.ProgressRing(ref=pct_ref, width=60, height=60, stroke_width=6, color=accent, bgcolor="#30363d")
    val = ft.Text(ref=value_ref, size=13, weight=ft.FontWeight.BOLD, color=TEXT)
    lbl = ft.Text(label, size=10, color=MUTED)
    return ft.Column([ring, ft.Stack([
        ft.Container(width=60, height=60, content=ft.Column([val, lbl],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER, tight=True))
    ])], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)

def snack(page, msg, error=False):
    page.snack_bar = ft.SnackBar(ft.Text(msg, color=ft.Colors.WHITE),
                                  bgcolor=DANGER if error else "#238636")
    page.snack_bar.open = True
    page.update()

# ─── Main App ─────────────────────────────────────────────────────────────────
class ServboardApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Servboard"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = BG
        self.page.padding = 0
        self.page.fonts = {"Inter": "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2"}
        self.page.theme = ft.Theme(font_family="Inter")

        # State
        saved_url = self.page.client_storage.get("server_url") or "http://localhost:3000"
        saved_token = self.page.client_storage.get("token") or ""
        self.api = ApiClient(saved_url, saved_token)
        self.user = None
        self.sudo_password = ""
        self.current_page_id = None
        self.polling = True

        # Gauge refs
        self.cpu_val = ft.Ref[ft.Text]()
        self.cpu_pct = ft.Ref[ft.ProgressRing]()
        self.ram_val = ft.Ref[ft.Text]()
        self.ram_pct = ft.Ref[ft.ProgressRing]()
        self.disk_val = ft.Ref[ft.Text]()
        self.disk_pct = ft.Ref[ft.ProgressRing]()
        self.gpu_val = ft.Ref[ft.Text]()
        self.gpu_pct = ft.Ref[ft.ProgressRing]()
        self.sys_info_text = ft.Ref[ft.Text]()
        self.proc_list = ft.Ref[ft.DataTable]()
        self.console_ref = ft.Ref[ft.Text]()

        self._check_auth()

    def _check_auth(self):
        if self.api.token:
            result = self.api.me()
            if result:
                self.user = result
                self._build_main_ui()
                return
        self._build_login_ui()

    # ─── Login Screen ─────────────────────────────────────────────────────────
    def _build_login_ui(self):
        self.page.controls.clear()
        self.page.padding = 20

        username_ref = ft.Ref[ft.TextField]()
        password_ref = ft.Ref[ft.TextField]()
        server_ref = ft.Ref[ft.TextField]()
        status_ref = ft.Ref[ft.Text]()
        register_mode = [False]

        def toggle_mode(e):
            register_mode[0] = not register_mode[0]
            toggle_btn.text = "Switch to Login" if register_mode[0] else "Switch to Register"
            submit_btn.text = "Create Account" if register_mode[0] else "Sign In"
            self.page.update()

        def submit(e):
            status_ref.current.value = ""
            url = server_ref.current.value.strip()
            user = username_ref.current.value.strip()
            pw = password_ref.current.value

            if not url or not user or not pw:
                status_ref.current.value = "All fields required"
                self.page.update()
                return

            self.api = ApiClient(url, "")
            try:
                if register_mode[0]:
                    self.api.register(user, pw)
                    status_ref.current.value = "Account created — signing in..."
                    self.page.update()
                result = self.api.login(user, pw)
                token = result["access_token"]
                self.api.token = token
                self.page.client_storage.set("server_url", url)
                self.page.client_storage.set("token", token)
                self.user = self.api.me()
                self.page.padding = 0
                self._build_main_ui()
            except ValueError as ex:
                status_ref.current.value = str(ex)
                self.page.update()

        submit_btn = ft.ElevatedButton("Sign In", on_click=submit, expand=True,
                                       style=ft.ButtonStyle(bgcolor=ACCENT, color=ft.Colors.BLACK,
                                                            shape=ft.RoundedRectangleBorder(radius=8)))
        toggle_btn = ft.TextButton("Switch to Register", on_click=toggle_mode)

        self.page.add(
            ft.Column([
                ft.Container(height=60),
                ft.Text("SERVBOARD", size=28, weight=ft.FontWeight.BOLD, color=ACCENT, letter_spacing=4),
                ft.Text("Remote Server Control", size=14, color=MUTED),
                ft.Container(height=40),
                card(ft.Column([
                    ft.TextField(ref=server_ref, label="Server URL", value=self.api.base_url,
                                 prefix_icon=ft.icons.DNS, border_color="#30363d", focused_border_color=ACCENT),
                    ft.TextField(ref=username_ref, label="Username",
                                 prefix_icon=ft.icons.PERSON, border_color="#30363d", focused_border_color=ACCENT),
                    ft.TextField(ref=password_ref, label="Password", password=True, can_reveal_password=True,
                                 prefix_icon=ft.icons.LOCK, border_color="#30363d", focused_border_color=ACCENT,
                                 on_submit=submit),
                    ft.Text(ref=status_ref, value="", color=DANGER, size=12),
                    submit_btn,
                    ft.Row([toggle_btn], alignment=ft.MainAxisAlignment.CENTER)
                ], spacing=12), padding=24),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, width=400,
               scroll=ft.ScrollMode.ADAPTIVE),
            expand=True
        )
        self.page.update()

    # ─── Main UI Shell ────────────────────────────────────────────────────────
    def _build_main_ui(self):
        self.page.controls.clear()
        self.polling = True

        self.content_area = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=16, padding=16)

        # Bottom Nav
        self.nav = ft.NavigationBar(
            destinations=[
                ft.NavigationBarDestination(icon=ft.icons.DASHBOARD_OUTLINED, selected_icon=ft.icons.DASHBOARD, label="Dashboard"),
                ft.NavigationBarDestination(icon=ft.icons.GRID_VIEW_OUTLINED, selected_icon=ft.icons.GRID_VIEW, label="Remote"),
                ft.NavigationBarDestination(icon=ft.icons.FOLDER_OUTLINED, selected_icon=ft.icons.FOLDER, label="Scripts"),
                ft.NavigationBarDestination(icon=ft.icons.SETTINGS_OUTLINED, selected_icon=ft.icons.SETTINGS, label="Settings"),
            ],
            selected_index=0,
            bgcolor=SURFACE,
            on_change=self._nav_change,
            indicator_color=ft.Colors.with_opacity(0.15, ACCENT)
        )

        self.page.add(
            ft.Column([self.content_area, self.nav], expand=True, spacing=0)
        )

        self._show_dashboard()
        asyncio.create_task(self._metrics_poll())

    def _nav_change(self, e):
        idx = e.control.selected_index
        if idx == 0: self._show_dashboard()
        elif idx == 1: self._show_remote()
        elif idx == 2: self._show_scripts()
        elif idx == 3: self._show_settings()

    # ─── Dashboard Page ───────────────────────────────────────────────────────
    def _show_dashboard(self):
        self.content_area.controls.clear()

        gauges = ft.Row([
            metric_gauge("CPU", self.cpu_val, self.cpu_pct, ACCENT),
            metric_gauge("RAM", self.ram_val, self.ram_pct, ft.Colors.PURPLE_400),
            metric_gauge("DISK", self.disk_val, self.disk_pct, ft.Colors.ORANGE_400),
            metric_gauge("GPU", self.gpu_val, self.gpu_pct, ft.Colors.GREEN_400),
        ], alignment=ft.MainAxisAlignment.SPACE_AROUND, wrap=True)

        sys_card = card(ft.Column([
            ft.Text("SYSTEM", size=11, color=MUTED, letter_spacing=1, weight=ft.FontWeight.BOLD),
            ft.Text(ref=self.sys_info_text, value="Loading...", size=13, color=TEXT)
        ], spacing=6))

        proc_table = ft.DataTable(
            ref=self.proc_list,
            columns=[
                ft.DataColumn(ft.Text("PID", size=11, color=MUTED)),
                ft.DataColumn(ft.Text("PROCESS", size=11, color=MUTED)),
                ft.DataColumn(ft.Text("CPU %", size=11, color=MUTED)),
                ft.DataColumn(ft.Text("MEM %", size=11, color=MUTED)),
            ],
            rows=[],
            column_spacing=16,
            data_row_min_height=32,
            heading_row_color=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
        )

        self.content_area.controls += [
            ft.Text(f"Welcome, {self.user.get('username', '')} 👋", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
            card(gauges, padding=20),
            sys_card,
            card(ft.Column([
                ft.Text("TOP PROCESSES", size=11, color=MUTED, letter_spacing=1, weight=ft.FontWeight.BOLD),
                proc_table
            ], spacing=8)),
        ]
        self.page.update()
        asyncio.create_task(self._load_sys_info())

    async def _load_sys_info(self):
        info = self.api.system_info()
        if info and self.sys_info_text.current:
            self.sys_info_text.current.value = f"{info.get('hostname')} · {info.get('os')} · Up {info.get('uptime')}"
            self.page.update()

    async def _metrics_poll(self):
        while self.polling:
            data = self.api.metrics()
            if data:
                try:
                    def set_gauge(val_ref, pct_ref, value, suffix="%"):
                        if val_ref.current: val_ref.current.value = f"{value:.0f}{suffix}"
                        if pct_ref.current: pct_ref.current.value = value / 100

                    set_gauge(self.cpu_val, self.cpu_pct, data.get("cpu", 0))
                    set_gauge(self.ram_val, self.ram_pct, data["ram"]["percent"])
                    set_gauge(self.disk_val, self.disk_pct, data["disk"]["percent"])
                    gpu = data.get("gpu", [])
                    if gpu: set_gauge(self.gpu_val, self.gpu_pct, gpu[0].get("usage", 0))
                    else:
                        if self.gpu_val.current: self.gpu_val.current.value = "N/A"

                    if self.proc_list.current:
                        self.proc_list.current.rows = [
                            ft.DataRow(cells=[
                                ft.DataCell(ft.Text(str(p["pid"]), size=11, color=MUTED)),
                                ft.DataCell(ft.Text(p["name"], size=12, color=TEXT)),
                                ft.DataCell(ft.Text(f"{p['cpu']:.1f}", size=12, color=ACCENT if p['cpu'] > 20 else TEXT)),
                                ft.DataCell(ft.Text(f"{p['mem']:.1f}", size=12, color=TEXT)),
                            ]) for p in data.get("processes", [])
                        ]
                    self.page.update()
                except: pass
            prefs = getattr(self, '_prefs', {})
            await asyncio.sleep(prefs.get("poll_interval", 5))

    # ─── Remote Pages ─────────────────────────────────────────────────────────
    def _show_remote(self):
        self.content_area.controls.clear()
        self.page.update()

        pages = self.api.pages() or []

        page_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[],
            expand=True,
            label_color=ACCENT,
            unselected_label_color=MUTED,
            indicator_color=ACCENT,
        )

        for p in pages:
            page_tabs.tabs.append(ft.Tab(
                text=p["name"],
                content=self._build_button_grid(p)
            ))

        def add_page(e):
            name_ref = ft.Ref[ft.TextField]()
            def save(ev):
                name = name_ref.current.value.strip()
                if not name: return
                try:
                    self.api.create_page(name)
                    self.page.dialog.open = False
                    self._show_remote()
                except Exception as ex: snack(self.page, str(ex), error=True)

            self.page.dialog = ft.AlertDialog(
                title=ft.Text("New Page"),
                content=ft.TextField(ref=name_ref, label="Page Name", autofocus=True),
                actions=[ft.TextButton("Cancel", on_click=lambda e: self._close_dialog()),
                         ft.TextButton("Create", on_click=save)]
            )
            self.page.dialog.open = True
            self.page.update()

        header = ft.Row([
            ft.Text("REMOTE", size=13, color=MUTED, weight=ft.FontWeight.BOLD, letter_spacing=2),
            ft.IconButton(ft.icons.ADD_CIRCLE_OUTLINE, icon_color=ACCENT, on_click=add_page, tooltip="Add Page")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        if not pages:
            self.content_area.controls += [
                header,
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.GRID_VIEW_OUTLINED, size=48, color=MUTED),
                        ft.Text("No pages yet", size=16, color=MUTED),
                        ft.Text("Create a page to add buttons", size=12, color=MUTED),
                        ft.ElevatedButton("Create First Page", on_click=add_page,
                                          style=ft.ButtonStyle(bgcolor=ACCENT, color=ft.Colors.BLACK)),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    expand=True, alignment=ft.alignment.center, height=300
                )
            ]
        else:
            self.content_area.controls += [header, page_tabs]

        self.page.update()

    def _build_button_grid(self, page_data):
        pid = page_data["id"]
        buttons = self.api.buttons(pid) or []

        def run_button(cmd):
            if not self.sudo_password:
                self._ask_sudo(lambda pw: self._exec(cmd, pw))
            else:
                self._exec(cmd, self.sudo_password)

        def _make_btn(b):
            return ft.Container(
                content=ft.Column([
                    ft.IconButton(
                        icon=getattr(ft.icons, b["icon"].upper(), ft.icons.PLAY_ARROW),
                        icon_size=32, icon_color=ft.Colors.WHITE,
                        on_click=lambda e, c=b["command"]: run_button(c),
                        style=ft.ButtonStyle(bgcolor={ft.ControlState.DEFAULT: b["color"]},
                                             shape=ft.CircleBorder())
                    ),
                    ft.Text(b["name"].upper(), size=9, color=MUTED,
                            weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                col={"xs": 4, "sm": 3, "md": 2}, padding=8,
            )

        def add_button(e):
            name_r = ft.Ref[ft.TextField]()
            cmd_r = ft.Ref[ft.TextField]()
            color_r = ft.Ref[ft.Dropdown]()

            def save(ev):
                try:
                    self.api.create_button(pid, name=name_r.current.value,
                                           command=cmd_r.current.value, color=color_r.current.value or "#37474f")
                    self._close_dialog()
                    self._show_remote()
                except Exception as ex: snack(self.page, str(ex), error=True)

            self.page.dialog = ft.AlertDialog(
                title=ft.Text(f"Add Button to {page_data['name']}"),
                content=ft.Column([
                    ft.TextField(ref=name_r, label="Button Name", autofocus=True),
                    ft.TextField(ref=cmd_r, label="Shell Command or Script Path"),
                    ft.Dropdown(ref=color_r, label="Color", value="#37474f", options=[
                        ft.dropdown.Option("#37474f", "Grey"),
                        ft.dropdown.Option("#1565c0", "Blue"),
                        ft.dropdown.Option("#2e7d32", "Green"),
                        ft.dropdown.Option("#b71c1c", "Red"),
                        ft.dropdown.Option("#4a148c", "Purple"),
                        ft.dropdown.Option("#e65100", "Orange"),
                    ])
                ], tight=True, spacing=10),
                actions=[ft.TextButton("Cancel", on_click=lambda e: self._close_dialog()),
                         ft.TextButton("Add", on_click=save)]
            )
            self.page.dialog.open = True
            self.page.update()

        def delete_page(e):
            def confirm(ev):
                try:
                    self.api.delete_page(pid)
                    self._close_dialog()
                    self._show_remote()
                except Exception as ex: snack(self.page, str(ex), error=True)
            self.page.dialog = ft.AlertDialog(
                title=ft.Text("Delete Page?"),
                content=ft.Text(f"This will permanently delete '{page_data['name']}' and all its buttons."),
                actions=[ft.TextButton("Cancel", on_click=lambda e: self._close_dialog()),
                         ft.TextButton("Delete", on_click=confirm, style=ft.ButtonStyle(color=DANGER))]
            )
            self.page.dialog.open = True
            self.page.update()

        grid = ft.ResponsiveRow([_make_btn(b) for b in buttons], spacing=4, run_spacing=4)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.IconButton(ft.icons.ADD, icon_color=ACCENT, tooltip="Add Button", on_click=add_button),
                    ft.IconButton(ft.icons.DELETE_OUTLINE, icon_color=DANGER, tooltip="Delete Page", on_click=delete_page),
                ], alignment=ft.MainAxisAlignment.END),
                grid if buttons else ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.TOUCH_APP_OUTLINED, size=40, color=MUTED),
                        ft.Text("No buttons yet", color=MUTED),
                        ft.TextButton("Add Button", on_click=add_button)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    height=200, alignment=ft.alignment.center
                )
            ], spacing=8),
            padding=12
        )

    # ─── Script Explorer ──────────────────────────────────────────────────────
    def _show_scripts(self):
        self.content_area.controls.clear()
        scripts = self.api.scripts() or {}

        if not scripts:
            self.content_area.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.FOLDER_OPEN, size=48, color=MUTED),
                        ft.Text("No scripts found", color=MUTED),
                        ft.Text(f"Add .sh files to {self.api.base_url}", color=MUTED, size=12)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    height=300, alignment=ft.alignment.center
                )
            )
            self.page.update()
            return

        tiles = []
        for category, items in scripts.items():
            tiles.append(ft.Container(
                content=ft.Text(category, size=11, color=MUTED, weight=ft.FontWeight.BOLD, letter_spacing=1),
                padding=ft.padding.only(top=12, bottom=4)
            ))
            for item in items:
                def run_script(e, path=item["path"]):
                    if not self.sudo_password:
                        self._ask_sudo(lambda pw, p=path: self._exec(p, pw))
                    else:
                        self._exec(item["path"], self.sudo_password)

                tiles.append(card(
                    ft.Row([
                        ft.Column([
                            ft.Text(item["name"], size=14, weight=ft.FontWeight.W_500, color=TEXT),
                            ft.Text(item["path"], size=10, color=MUTED)
                        ], expand=True, spacing=2),
                        ft.IconButton(ft.icons.PLAY_CIRCLE_FILLED, icon_color=ACCENT, on_click=run_script, tooltip="Run")
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.symmetric(horizontal=12, vertical=8)
                ))

        self.content_area.controls += [
            ft.Text("SCRIPTS", size=13, color=MUTED, weight=ft.FontWeight.BOLD, letter_spacing=2),
            *tiles
        ]
        self.page.update()

    # ─── Settings Page ────────────────────────────────────────────────────────
    def _show_settings(self):
        self.content_area.controls.clear()
        prefs = self.api.prefs() or {}
        self._prefs = prefs

        url_ref = ft.Ref[ft.TextField]()
        status_ref = ft.Ref[ft.Text]()

        def test_connection(e):
            health = ApiClient(url_ref.current.value).health()
            if health:
                status_ref.current.value = "✅ Connected"
                status_ref.current.color = SUCCESS
            else:
                status_ref.current.value = "❌ Cannot connect"
                status_ref.current.color = DANGER
            self.page.update()

        def save_url(e):
            new_url = url_ref.current.value.strip()
            self.api = ApiClient(new_url, self.api.token)
            self.page.client_storage.set("server_url", new_url)
            snack(self.page, "Server URL saved")

        def change_sudo(e):
            pw_ref = ft.Ref[ft.TextField]()
            def save(ev):
                self.sudo_password = pw_ref.current.value
                self._close_dialog()
                snack(self.page, "Sudo password updated for this session")
            self.page.dialog = ft.AlertDialog(
                title=ft.Text("Set Sudo Password"),
                content=ft.Column([
                    ft.Text("This is used to authorize command execution.\nNot stored anywhere.", size=12, color=MUTED),
                    ft.TextField(ref=pw_ref, label="Sudo Password", password=True, can_reveal_password=True, autofocus=True)
                ], tight=True, spacing=8),
                actions=[ft.TextButton("Cancel", on_click=lambda e: self._close_dialog()),
                         ft.TextButton("Set", on_click=save)]
            )
            self.page.dialog.open = True
            self.page.update()

        def logout(e):
            self.polling = False
            self.page.client_storage.remove("token")
            self.api.token = ""
            self._build_login_ui()

        self.content_area.controls += [
            ft.Text("SETTINGS", size=13, color=MUTED, weight=ft.FontWeight.BOLD, letter_spacing=2),
            card(ft.Column([
                ft.Text("Server", size=12, color=MUTED, weight=ft.FontWeight.BOLD),
                ft.TextField(ref=url_ref, label="Server URL", value=self.api.base_url,
                             border_color="#30363d", focused_border_color=ACCENT),
                ft.Row([
                    ft.TextButton("Test Connection", on_click=test_connection),
                    ft.ElevatedButton("Save", on_click=save_url,
                                      style=ft.ButtonStyle(bgcolor=ACCENT, color=ft.Colors.BLACK))
                ]),
                ft.Text(ref=status_ref, value="", size=12)
            ], spacing=10)),
            card(ft.Column([
                ft.Text("Security", size=12, color=MUTED, weight=ft.FontWeight.BOLD),
                ft.Text("Sudo password is required to execute commands. It is never stored on disk.", size=12, color=MUTED),
                ft.Text(f"Sudo: {'Set ✅' if self.sudo_password else 'Not set ❌'}", size=13, color=TEXT),
                ft.OutlinedButton("Set Sudo Password", on_click=change_sudo,
                                  style=ft.ButtonStyle(side=ft.BorderSide(1, ACCENT), color=ACCENT))
            ], spacing=8)),
            card(ft.Column([
                ft.Text("Account", size=12, color=MUTED, weight=ft.FontWeight.BOLD),
                ft.Text(f"Logged in as: {self.user.get('username', '')}", size=13, color=TEXT),
                ft.OutlinedButton("Logout", on_click=logout,
                                  style=ft.ButtonStyle(side=ft.BorderSide(1, DANGER), color=DANGER))
            ], spacing=8)),
        ]
        self.page.update()

    # ─── Helpers ──────────────────────────────────────────────────────────────
    def _ask_sudo(self, callback):
        pw_ref = ft.Ref[ft.TextField]()
        def submit(e):
            self.sudo_password = pw_ref.current.value
            self._close_dialog()
            callback(self.sudo_password)
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Sudo Required"),
            content=ft.Column([
                ft.Text("Enter your sudo password to execute this command.", size=12, color=MUTED),
                ft.TextField(ref=pw_ref, label="Sudo Password", password=True, can_reveal_password=True, autofocus=True, on_submit=submit)
            ], tight=True, spacing=8),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self._close_dialog()),
                     ft.TextButton("Run", on_click=submit)]
        )
        self.page.dialog.open = True
        self.page.update()

    def _exec(self, command, sudo_password):
        snack(self.page, f"Running: {command[:40]}...")
        try:
            result = self.api.execute(command, sudo_password)
            if result and result.get("returncode") == 0:
                out = result.get("stdout", "")[:80].strip()
                snack(self.page, f"✅ {out or 'Done'}")
            else:
                err = (result or {}).get("stderr", "Failed")[:80]
                snack(self.page, f"❌ {err}", error=True)
        except ValueError as e:
            if "403" in str(e) or "sudo" in str(e).lower():
                self.sudo_password = ""  # Clear bad password
                snack(self.page, "Wrong sudo password", error=True)
            else:
                snack(self.page, str(e), error=True)

    def _close_dialog(self):
        if self.page.dialog: self.page.dialog.open = False
        self.page.update()


# ─── Entry Point ──────────────────────────────────────────────────────────────
def main(page: ft.Page):
    ServboardApp(page)

if __name__ == "__main__":
    ft.app(target=main,
           view=ft.AppView.WEB_BROWSER if __import__("os").environ.get("WEB_MODE") else ft.AppView.FLET_APP,
           port=int(__import__("os").environ.get("FLET_SERVER_PORT", 3000)))

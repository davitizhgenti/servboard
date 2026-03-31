import flet as ft
import psutil
import os
import subprocess
import json
import time
import asyncio

# Configuration
SCRIPTS_ROOT = os.environ.get("SCRIPTS_ROOT", "/home/user/main")

import requests
from urllib.parse import urljoin

class ApiClient:
    def __init__(self, base_url="http://localhost:8550"):
        self.base_url = base_url

    def get_metrics(self):
        try:
            res = requests.get(urljoin(self.base_url, "/api/metrics"), timeout=5)
            return res.json()
        except: return None

    def execute_command(self, command):
        try:
            res = requests.post(urljoin(self.base_url, "/api/execute"), json={"command": command}, timeout=30)
            return res.json()
        except Exception as e:
            return {"stderr": str(e), "returncode": 1}

    def get_scripts(self):
        try:
            res = requests.get(urljoin(self.base_url, "/api/scripts"), timeout=10)
            return res.json()
        except: return {}

class ServboardApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Servboard Remote"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 20
        self.page.spacing = 20
        self.page.scroll = ft.ScrollMode.ADAPTIVE
        
        # Connection Settings
        saved_url = self.page.client_storage.get("server_url")
        self.api = ApiClient(saved_url or "http://localhost:8550")
        
        # UI Elements
        self.cpu_text = ft.Text("0%", size=16, weight=ft.FontWeight.BOLD)
        self.ram_text = ft.Text("0%", size=16, weight=ft.FontWeight.BOLD)
        self.disk_text = ft.Text("0%", size=16, weight=ft.FontWeight.BOLD)
        
        self.macro_grid = ft.ResponsiveRow(spacing=10, run_spacing=10)
        self.script_list = ft.ListView(expand=True, spacing=10, padding=10)
        
        self.macros = []
        self.init_ui()

    def init_ui(self):
        # Premium Colors
        self.accent = ft.colors.CYAN_700
        self.bg_color = ft.colors.BLACK
        self.surface = ft.colors.BLUE_GREY_900
        
        self.page.bgcolor = self.bg_color
        
        # Header Metrics (Glassmorphism look)
        metrics_bar = ft.Container(
            content=ft.Row([
                ft.Column([ft.Text("CPU", size=10, color=ft.colors.GREY_400), self.cpu_text], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Column([ft.Text("RAM", size=10, color=ft.colors.GREY_400), self.ram_text], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Column([ft.Text("DISK", size=10, color=ft.colors.GREY_400), self.disk_text], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ], alignment=ft.MainAxisAlignment.SPACE_AROUND),
            padding=15,
            bgcolor=ft.colors.with_opacity(0.15, self.surface),
            border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.WHITE)),
            border_radius=20,
            blur=ft.Blur(10, 10),
            margin=ft.margin.only(bottom=10)
        )

        # Remote Grid Section
        remote_section = ft.Column([
            ft.Row([
                ft.Text("REMOTE", size=14, weight=ft.FontWeight.W_300, color=ft.colors.GREY_500, letter_spacing=2),
                ft.Row([
                    ft.IconButton(ft.icons.SETTINGS, icon_color=ft.colors.GREY_600, on_click=self.show_settings),
                    ft.IconButton(ft.icons.ADD_CIRCLE_OUTLINE, icon_color=self.accent, on_click=self.show_add_macro_dialog)
                ])
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            self.macro_grid,
        ], spacing=10)

        # Dynamic Scripts Section
        self.toggle_scripts_btn = ft.ElevatedButton(
            "BROWSE SCRIPTS", 
            icon=ft.icons.FOLDER_OPEN,
            on_click=self.toggle_scripts,
            style=ft.ButtonStyle(
                color=ft.colors.GREY_300,
                bgcolor=ft.colors.TRANSPARENT,
                side={ft.ControlState.DEFAULT: ft.BorderSide(1, ft.colors.GREY_800)},
                shape=ft.RoundedRectangleBorder(radius=10)
            )
        )

        scripts_section = ft.Column([
            self.toggle_scripts_btn,
            ft.Container(
                content=self.script_list,
                height=300,
                visible=False,
                border=ft.border.all(1, ft.colors.with_opacity(0.1, ft.colors.WHITE)),
                border_radius=15,
                bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE)
            )
        ], spacing=10)
        
        self.scripts_container = scripts_section.controls[1]

        # Console Log
        self.console_output = ft.Text("System ready...", size=12, color=ft.colors.GREY_400, italic=True)
        console_container = ft.Container(
            content=self.console_output,
            padding=10,
            bgcolor=ft.colors.with_opacity(0.1, ft.colors.BLACK),
            border_radius=10,
            margin=ft.margin.only(top=20)
        )

        self.page.add(
            metrics_bar,
            remote_section,
            ft.Divider(height=40, color=ft.colors.with_opacity(0.1, ft.colors.WHITE)),
            scripts_section,
            console_container
        )

        # Load Data
        self.load_macros()
        self.refresh_scripts(None)
        
        # Start Polling
        asyncio.create_task(self.update_metrics())

    def toggle_scripts(self, e):
        self.scripts_container.visible = not self.scripts_container.visible
        self.toggle_scripts_btn.text = "CLOSE EXPLORER" if self.scripts_container.visible else "BROWSE SCRIPTS"
        self.page.update()

    async def update_metrics(self):
        while True:
            data = self.api.get_metrics()
            if data:
                cpu = data.get('cpu', 0)
                ram = data.get('ram', 0)
                disk = data.get('disk', 0)
                
                self.cpu_text.value = f"{cpu}%"
                self.ram_text.value = f"{ram}%"
                self.disk_text.value = f"{disk}%"
                
                self.cpu_text.color = ft.colors.RED_400 if cpu > 80 else ft.colors.CYAN_300
                self.ram_text.color = ft.colors.RED_400 if ram > 80 else ft.colors.CYAN_300
                self.page.update()
            await asyncio.sleep(5)

    def log(self, msg, error=False):
        self.console_output.value = msg
        self.console_output.color = ft.colors.RED_400 if error else ft.colors.GREY_400
        self.page.update()

    def run_command(self, cmd):
        self.log(f"Executing: {os.path.basename(cmd)}...")
        result = self.api.execute_command(cmd)
        if result.get('returncode') == 0:
            self.log(f"Success: {result.get('stdout', '')[:50]}...")
        else:
            self.log(f"Error: {result.get('stderr', '')[:50]}...", error=True)

    def refresh_scripts(self, e):
        scripts = self.api.get_scripts()
        self.script_list.controls.clear()
        
        for category, items in scripts.items():
            self.script_list.controls.append(
                ft.Container(
                    content=ft.Text(category, size=12, weight=ft.FontWeight.BOLD, color=ft.colors.GREY_500, letter_spacing=1),
                    padding=ft.padding.only(top=10, left=5)
                )
            )
            for item in items:
                self.script_list.controls.append(
                    ft.ListTile(
                        title=ft.Text(item['name'], size=14, weight=ft.FontWeight.W_500),
                        subtitle=ft.Text(item['path'], size=10, color=ft.colors.GREY_600),
                        trailing=ft.IconButton(ft.icons.PLAY_CIRCLE_FILLED, icon_color=self.accent, on_click=lambda e, p=item['path']: self.run_command(p)),
                        dense=True,
                        hover_color=ft.colors.with_opacity(0.1, self.accent)
                    )
                )
        self.page.update()

    def show_settings(self, e):
        url_ref = ft.Ref[ft.TextField]()
        
        def save_settings(e):
            new_url = url_ref.current.value
            self.page.client_storage.set("server_url", new_url)
            self.api = ApiClient(new_url)
            self.page.dialog.open = False
            self.refresh_scripts(None)
            self.page.update()

        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Connection Settings"),
            content=ft.TextField(ref=url_ref, label="Server URL", value=self.api.base_url),
            actions=[ft.TextButton("Save", on_click=save_settings)]
        )
        self.page.dialog.open = True
        self.page.update()


    def load_macros(self):
        saved = self.page.client_storage.get("servboard_macros")
        if saved:
            self.macros = json.loads(saved)
        else:
            # Default example macro
            self.macros = [{"id": 1, "name": "UPTIME", "cmd": "uptime -p", "type": "server", "color": ft.colors.BLUE_GREY_700}]
        self.render_macros()

    def save_macros(self):
        self.page.client_storage.set("servboard_macros", json.dumps(self.macros))

    def render_macros(self):

        self.macro_grid.controls.clear()
        for i, m in enumerate(self.macros):
            self.macro_grid.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.IconButton(
                            icon=ft.icons.PLAY_ARROW if m.get('type') == 'server' else ft.icons.CODE,
                            icon_size=30,
                            icon_color=ft.colors.WHITE,
                            on_click=lambda e, cmd=m['cmd']: self.run_command(cmd),
                            style=ft.ButtonStyle(
                                shape=ft.CircleBorder(),
                                bgcolor={ft.ControlState.DEFAULT: m.get('color', ft.colors.BLUE_GREY_800)},
                            ),
                        ),
                        ft.Text(m['name'].upper(), size=10, weight=ft.FontWeight.W_600, color=ft.colors.GREY_400, text_align=ft.TextAlign.CENTER)
                    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    col={"xs": 4, "sm": 3, "md": 2},
                    padding=10,
                )
            )
        self.page.update()


    def show_add_macro_dialog(self, e):
        name_ref = ft.Ref[ft.TextField]()
        cmd_ref = ft.Ref[ft.TextField]()
        
        def close_dlg(e):
            self.page.dialog.open = False
            self.page.update()

        def save_new_macro(e):
            if not name_ref.current.value or not cmd_ref.current.value:
                return
            
            self.macros.append({
                "id": int(time.time()),
                "name": name_ref.current.value,
                "cmd": cmd_ref.current.value,
                "type": "server",
                "color": ft.colors.BLUE_900
            })
            self.save_macros()
            self.render_macros()
            close_dlg(e)

        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Add New Macro"),
            content=ft.Column([
                ft.TextField(ref=name_ref, label="Macro Name", autofocus=True),
                ft.TextField(ref=cmd_ref, label="Bash Command / Script Path"),
            ], tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=close_dlg),
                ft.TextButton("Save", on_click=save_new_macro),
            ],
        )
        self.page.dialog.open = True
        self.page.update()

def main(page: ft.Page):
    ServboardApp(page)

if __name__ == "__main__":
    port = int(os.environ.get("FLET_SERVER_PORT", 8550))
    ft.app(target=main, view=ft.AppView.WEB_BROWSER if os.environ.get("WEB_MODE") else ft.AppView.FLET_APP, port=port)


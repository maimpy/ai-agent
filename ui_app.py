import os
import sys
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
import threading
import uuid
from config import load_system_rules
from ai_engine import execute_ai_with_fallback

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ───────────────────────── Палітра ─────────────────────────
BG = "#0F1320"          # фон вікна
SIDEBAR = "#0B0F1A"     # ліва навігація
SURFACE = "#171C2D"     # панелі та картки
RAISED = "#1F2640"      # активні / підняті елементи
BORDER = "#2B3454"      # рамки
TEXT = "#E8ECF8"        # основний текст
TEXT_SOFT = "#C5CDEB"   # текст завдань користувача
MUTED = "#8B94B3"       # другорядний текст
ACCENT = "#7C93FF"      # головний акцент
ACCENT_HOVER = "#9AABFF"
ON_ACCENT = "#0B1030"   # текст на акцентній кнопці
OK = "#5BD6A0"
WARN = "#F2BE5A"
ERR = "#FF7A8A"
ERR_SOFT = "#FFB3BC"
SELECTION = "#36427A"

if sys.platform == "win32":
    FONT_UI = "Segoe UI"
elif sys.platform == "darwin":
    FONT_UI = "Helvetica Neue"
else:
    FONT_UI = "DejaVu Sans"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_UI, size=size, weight=weight)


class AIStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Agent Studio")
        self.geometry("1240x780")
        self.minsize(980, 640)
        self.configure(fg_color=BG)

        self.work_dir = os.getcwd()
        self.chats = {}  # chat_id -> {"title": str, "work_dir": str, "messages": list}
        self.current_chat_id = None
        self._welcome_shown = False

        # Головна сітка вікна
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── Ліва панель навігації ──
        self.sidebar = ctk.CTkFrame(self, width=232, corner_radius=0, fg_color=SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 22))
        ctk.CTkLabel(
            brand, text="AI", width=36, height=36, corner_radius=11,
            fg_color=ACCENT, text_color=ON_ACCENT, font=font(14, "bold")
        ).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(brand, text="Agent Studio", font=font(16, "bold"),
                     text_color=TEXT, anchor="w").grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(brand, text="Мультипровайдерний шлюз", font=font(11),
                     text_color=MUTED, anchor="w").grid(row=1, column=1, sticky="w")

        self.nav_buttons = {}
        self.btn_main = self._nav_button("main", "Консоль", 1)
        self.btn_providers = self._nav_button("providers", "Провайдери", 2)
        self.btn_api = self._nav_button("api", "Підключення (API)", 3)

        self.keys_summary = ctk.CTkLabel(
            self.sidebar, text="", font=font(12), text_color=MUTED, anchor="w"
        )
        self.keys_summary.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 22))

        # ── Область контенту ──
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Створення вкладок
        self.main_tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.providers_tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.api_tab = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        for tab in (self.main_tab, self.providers_tab, self.api_tab):
            tab.grid(row=0, column=0, sticky="nsew")

        self.setup_providers_tab()
        self.setup_api_tab()
        self.setup_main_tab()

        self.select_tab("main")

        # Створюємо перший чат при старті
        if not self.chats:
            self.create_new_chat()

    # ───────────────────────── Навігація ─────────────────────────
    def _nav_button(self, key, text, row):
        btn = ctk.CTkButton(
            self.sidebar, text=text, anchor="w", height=42, corner_radius=10,
            fg_color="transparent", hover_color=RAISED, text_color=MUTED,
            font=font(14), command=lambda: self.select_tab(key)
        )
        btn.grid(row=row, column=0, padx=14, pady=3, sticky="ew")
        self.nav_buttons[key] = btn
        return btn

    def select_tab(self, name):
        for tab in (self.main_tab, self.providers_tab, self.api_tab):
            tab.grid_remove()
        if name == "main":
            self.main_tab.grid()
        elif name == "providers":
            self.providers_tab.grid()
        elif name == "api":
            self.api_tab.grid()

        for key, btn in self.nav_buttons.items():
            active = key == name
            btn.configure(
                fg_color=RAISED if active else "transparent",
                text_color=TEXT if active else MUTED,
            )

    # ───────────────────────── Допоміжні віджети ─────────────────────────
    def _page_header(self, parent, title, subtitle):
        ctk.CTkLabel(parent, text=title, font=font(26, "bold"), text_color=TEXT,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=4, pady=(2, 2))
        ctk.CTkLabel(parent, text=subtitle, font=font(13), text_color=MUTED,
                     anchor="w", justify="left").grid(row=1, column=0, sticky="w", padx=4, pady=(0, 10))

    def _entry(self, parent, **kwargs):
        opts = dict(
            height=42, corner_radius=10, fg_color=BG, border_color=BORDER,
            border_width=1, text_color=TEXT, placeholder_text_color=MUTED,
            font=font(13),
        )
        opts.update(kwargs)
        return ctk.CTkEntry(parent, **opts)

    def _bind_clipboard(self, entry, on_change=None):
        """Ctrl+V / Ctrl+C / Ctrl+A — працюють і в українській розкладці."""
        def changed():
            if on_change:
                on_change()

        def paste_text(event=None):
            try:
                entry.insert("insert", self.clipboard_get())
            except Exception:
                pass
            changed()
            return "break"

        def copy_text(event=None):
            try:
                self.clipboard_clear()
                self.clipboard_append(entry.selection_get())
            except Exception:
                pass
            return "break"

        def select_all_text(event=None):
            entry.select_range(0, "end")
            entry.icursor("end")
            return "break"

        for seq, handler in (
            ("<Control-v>", paste_text), ("<Control-V>", paste_text),
            ("<Control-c>", copy_text), ("<Control-C>", copy_text),
            ("<Control-a>", select_all_text), ("<Control-A>", select_all_text),
        ):
            entry.bind(seq, handler)

        # У Windows при кириличній розкладці keysym інший — орієнтуємось на код клавіші
        if sys.platform == "win32":
            keycodes = {86: paste_text, 67: copy_text, 65: select_all_text}

            def on_ctrl_key(event):
                handler = keycodes.get(event.keycode)
                return handler() if handler else None

            entry.bind("<Control-KeyPress>", on_ctrl_key, add="+")

    # ───────────────────────── Вкладка «Провайдери» ─────────────────────────
    def setup_providers_tab(self):
        tab = self.providers_tab
        tab.grid_columnconfigure(0, weight=1)
        self._page_header(
            tab, "Провайдери",
            "Вставте ключі API. Вони діють, поки відкрита програма, а за наявності підтягуються зі змінних середовища."
        )

        self.provider_entries = {}
        self.provider_dots = {}
        providers_info = [
            ("Google Gemini", "GEMINI_API_KEY", "gemini/gemini-3.8-flash"),
            ("Groq", "GROQ_API_KEY", "groq/llama-3.1-8b-instant"),
            ("OpenRouter", "OPENROUTER_API_KEY", "openrouter/free")
        ]

        for idx, (p_name, env_name, default_model) in enumerate(providers_info):
            card = ctk.CTkFrame(tab, fg_color=SURFACE, corner_radius=16,
                                border_width=1, border_color=BORDER)
            card.grid(row=idx + 2, column=0, sticky="ew", pady=6)
            card.grid_columnconfigure(2, weight=1)

            dot = ctk.CTkLabel(card, text="●", font=font(14), text_color=BORDER, width=20)
            dot.grid(row=0, column=0, padx=(20, 4), pady=20)
            self.provider_dots[env_name] = dot

            info = ctk.CTkFrame(card, fg_color="transparent", width=210)
            info.grid(row=0, column=1, sticky="w", padx=(4, 16), pady=14)
            info.grid_columnconfigure(0, minsize=190)
            ctk.CTkLabel(info, text=p_name, font=font(15, "bold"),
                         text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(info, text=default_model, font=font(11),
                         text_color=MUTED, anchor="w").grid(row=1, column=0, sticky="w")

            entry = self._entry(card, show="•", placeholder_text=f"Ключ {env_name}")
            entry.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=14)

            if os.getenv(env_name):
                entry.insert(0, os.getenv(env_name))

            state = {"hidden": True}
            toggle_btn = ctk.CTkButton(
                card, text="Показати", width=96, height=42, corner_radius=10,
                fg_color=RAISED, hover_color=BORDER, text_color=TEXT_SOFT, font=font(13)
            )

            def toggle(e=entry, b=toggle_btn, s=state):
                s["hidden"] = not s["hidden"]
                e.configure(show="•" if s["hidden"] else "")
                b.configure(text="Показати" if s["hidden"] else "Сховати")

            toggle_btn.configure(command=toggle)
            toggle_btn.grid(row=0, column=3, padx=(0, 20), pady=14)

            self._bind_clipboard(entry, on_change=self.refresh_provider_state)
            entry.bind("<KeyRelease>", lambda e: self.refresh_provider_state(), add="+")

            self.provider_entries[env_name] = {"entry": entry, "model": default_model}

        self.refresh_provider_state()

    def refresh_provider_state(self):
        filled = 0
        for env_name, data in self.provider_entries.items():
            has_key = bool(data["entry"].get().strip())
            filled += has_key
            self.provider_dots[env_name].configure(text_color=OK if has_key else BORDER)
        self.keys_summary.configure(
            text=f"Ключів додано: {filled} з {len(self.provider_entries)}"
        )

    # ───────────────────────── Вкладка «API» ─────────────────────────
    def setup_api_tab(self):
        tab = self.api_tab
        tab.grid_columnconfigure(0, weight=1)
        self._page_header(tab, "Локальний API-шлюз",
                          "Налаштування локального середовища та інтеграцій.")

        card = ctk.CTkFrame(tab, fg_color=SURFACE, corner_radius=16,
                            border_width=1, border_color=BORDER)
        card.grid(row=2, column=0, sticky="ew", pady=6)
        ctk.CTkLabel(card, text="Налаштувань поки немає", font=font(15, "bold"),
                     text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="w", padx=22, pady=(20, 2))
        ctk.CTkLabel(card, text="Тут з'являться параметри шлюзу, коли їх буде додано.",
                     font=font(13), text_color=MUTED, anchor="w").grid(row=1, column=0, sticky="w", padx=22, pady=(0, 20))

    # ───────────────────────── Вкладка «Консоль» ─────────────────────────
    def setup_main_tab(self):
        self.main_tab.grid_rowconfigure(0, weight=1)
        self.main_tab.grid_columnconfigure(1, weight=1)

        # ── Список чатів ──
        chat_sidebar = ctk.CTkFrame(self.main_tab, width=260, fg_color=SURFACE,
                                    corner_radius=16, border_width=1, border_color=BORDER)
        chat_sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        chat_sidebar.grid_propagate(False)
        chat_sidebar.grid_rowconfigure(1, weight=1)
        chat_sidebar.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(chat_sidebar, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Чати", font=font(15, "bold"), text_color=TEXT,
                     anchor="w").grid(row=0, column=0, sticky="w")
        new_chat_btn = ctk.CTkButton(
            head, text="+ Новий", width=84, height=32, corner_radius=9,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT,
            font=font(12, "bold"), command=self.create_new_chat
        )
        new_chat_btn.grid(row=0, column=1)

        self.chats_scroll = ctk.CTkScrollableFrame(
            chat_sidebar, fg_color="transparent",
            scrollbar_button_color=BORDER, scrollbar_button_hover_color=MUTED
        )
        self.chats_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self.chats_scroll.grid_columnconfigure(0, weight=1)

        # ── Робочий простір ──
        right_container = ctk.CTkFrame(self.main_tab, fg_color="transparent")
        right_container.grid(row=0, column=1, sticky="nsew")
        right_container.grid_rowconfigure(2, weight=1)
        right_container.grid_columnconfigure(0, weight=1)

        # Заголовок чату + статус
        header = ctk.CTkFrame(right_container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)

        self.chat_title = ctk.CTkLabel(header, text="", font=font(22, "bold"),
                                       text_color=TEXT, anchor="w")
        self.chat_title.grid(row=0, column=0, sticky="w", padx=4)

        pill = ctk.CTkFrame(header, fg_color=SURFACE, corner_radius=16,
                            border_width=1, border_color=BORDER)
        pill.grid(row=0, column=1, sticky="e")
        self.status_dot = ctk.CTkLabel(pill, text="●", font=font(12), text_color=MUTED, width=14)
        self.status_dot.grid(row=0, column=0, padx=(14, 2), pady=6)
        self.status_label = ctk.CTkLabel(pill, text="Очікує завдання", font=font(12, "bold"),
                                         text_color=TEXT_SOFT)
        self.status_label.grid(row=0, column=1, padx=(0, 14), pady=6)

        # Вибір робочої папки
        dir_frame = ctk.CTkFrame(right_container, fg_color=SURFACE, corner_radius=14,
                                 border_width=1, border_color=BORDER)
        dir_frame.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        dir_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dir_frame, text="Папка", font=font(13, "bold"),
                     text_color=MUTED).grid(row=0, column=0, padx=(18, 10), pady=10)

        self.dir_path_entry = self._entry(dir_frame, height=38)
        self.dir_path_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=10)
        self.dir_path_entry.configure(state="readonly")

        browse_btn = ctk.CTkButton(
            dir_frame, text="Огляд…", width=96, height=38, corner_radius=10,
            fg_color=RAISED, hover_color=BORDER, text_color=TEXT_SOFT,
            font=font(13), command=self.browse_directory
        )
        browse_btn.grid(row=0, column=2, padx=(10, 12), pady=10)

        # Журнал розмови (tk.Text з тегами — текст можна виділяти й копіювати)
        text_container = ctk.CTkFrame(right_container, fg_color=SURFACE, corner_radius=16,
                                      border_width=1, border_color=BORDER)
        text_container.grid(row=2, column=0, sticky="nsew")
        text_container.grid_rowconfigure(0, weight=1)
        text_container.grid_columnconfigure(0, weight=1)

        self.log_textbox = tk.Text(
            text_container,
            wrap="word",
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground=SELECTION,
            selectforeground=TEXT,
            inactiveselectbackground=SELECTION,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=22,
            pady=18,
            font=(FONT_UI, 12),
            cursor="arrow",
        )
        self.log_textbox.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=8)
        self._configure_log_tags()

        scrollbar = ctk.CTkScrollbar(text_container, command=self.log_textbox.yview,
                                     fg_color="transparent", button_color=BORDER,
                                     button_hover_color=MUTED)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=10)
        self.log_textbox.configure(yscrollcommand=scrollbar.set)
        self.log_textbox.config(state="disabled")

        # Індикатор виконання
        self.progress = ctk.CTkProgressBar(
            right_container, height=3, mode="indeterminate",
            fg_color=BORDER, progress_color=ACCENT
        )
        self.progress.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.progress.grid_remove()

        # Поле вводу завдання
        input_frame = ctk.CTkFrame(right_container, fg_color="transparent")
        input_frame.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        input_frame.grid_columnconfigure(0, weight=1)

        self.task_entry = self._entry(
            input_frame, height=50, corner_radius=14, fg_color=SURFACE,
            placeholder_text="Опишіть завдання для агента й натисніть Enter"
        )
        self.task_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.task_entry.bind("<Return>", lambda event: self.start_task_thread())
        self._bind_clipboard(self.task_entry)

        self.send_btn = ctk.CTkButton(
            input_frame, text="Виконати", width=130, height=50, corner_radius=14,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT,
            text_color_disabled=MUTED, font=font(14, "bold"),
            command=self.start_task_thread
        )
        self.send_btn.grid(row=0, column=1)

    # ───────────────────────── Журнал ─────────────────────────
    def _configure_log_tags(self):
        tb = self.log_textbox
        label_font = (FONT_UI, 10, "bold")
        body_font = (FONT_UI, 12)

        tb.tag_configure("label_user", foreground=MUTED, font=label_font, spacing1=4, lmargin1=2, lmargin2=2)
        tb.tag_configure("label_agent", foreground=ACCENT, font=label_font, spacing1=4, lmargin1=2, lmargin2=2)
        tb.tag_configure("label_error", foreground=ERR, font=label_font, spacing1=4, lmargin1=2, lmargin2=2)

        body = dict(font=body_font, lmargin1=2, lmargin2=2, spacing1=3, spacing2=4, spacing3=22)
        tb.tag_configure("body_user", foreground=TEXT_SOFT, **body)
        tb.tag_configure("body_agent", foreground=TEXT, **body)
        tb.tag_configure("body_error", foreground=ERR_SOFT, **body)

        tb.tag_configure("welcome_title", foreground=TEXT, font=(FONT_UI, 20, "bold"), spacing1=70, lmargin1=2)
        tb.tag_configure("welcome_hint", foreground=MUTED, font=(FONT_UI, 12), spacing1=8, lmargin1=2, lmargin2=2)

    def _log_clear(self):
        self.log_textbox.config(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.config(state="disabled")
        self._welcome_shown = False

    def _show_welcome(self):
        tb = self.log_textbox
        tb.config(state="normal")
        tb.insert("end", "З чого почнемо?\n", "welcome_title")
        tb.insert(
            "end",
            "Оберіть папку проєкту вгорі й опишіть завдання внизу.\n"
            "Агент працюватиме саме в цій папці.\n",
            "welcome_hint",
        )
        tb.config(state="disabled")
        self._welcome_shown = True

    def _write_message(self, kind, text):
        """kind: 'user' | 'agent' | 'error'"""
        if self._welcome_shown:
            self._log_clear()

        labels = {"user": "Ви", "agent": "Агент", "error": "Помилка"}
        tb = self.log_textbox
        tb.config(state="normal")
        tb.insert("end", f"{labels[kind]}\n", f"label_{kind}")
        tb.insert("end", f"{text}\n", f"body_{kind}")
        tb.config(state="disabled")
        tb.see("end")

    def _render_chat(self, chat_data):
        self._log_clear()
        shown = False
        for msg in chat_data["messages"]:
            if msg["role"] == "user":
                self._write_message("user", msg["content"])
                shown = True
            elif msg["role"] == "assistant" and msg.get("content"):
                self._write_message("agent", msg["content"])
                shown = True
        if not shown:
            self._show_welcome()

    # ───────────────────────── Статус ─────────────────────────
    def set_status(self, kind, text):
        colors = {"idle": MUTED, "busy": WARN, "ok": OK, "error": ERR}
        self.status_dot.configure(text_color=colors.get(kind, MUTED))
        self.status_label.configure(text=text)

    def _set_busy(self, busy):
        if busy:
            self.send_btn.configure(state="disabled", text="Працює…", fg_color=RAISED)
            self.progress.grid()
            self.progress.start()
        else:
            self.send_btn.configure(state="normal", text="Виконати", fg_color=ACCENT)
            self.progress.stop()
            self.progress.grid_remove()

    # ───────────────────────── Логіка (без змін у поведінці) ─────────────────────────
    def browse_directory(self):
        dir_selected = filedialog.askdirectory()
        if dir_selected:
            self.work_dir = dir_selected
            self.dir_path_entry.configure(state="normal")
            self.dir_path_entry.delete(0, "end")
            self.dir_path_entry.insert(0, self.work_dir)
            self.dir_path_entry.configure(state="readonly")

            # Зберігаємо оновлену папку для активного чату
            if self.current_chat_id and self.current_chat_id in self.chats:
                self.chats[self.current_chat_id]["work_dir"] = self.work_dir
                self.refresh_chat_list_ui()

    def create_new_chat(self):
        chat_id = str(uuid.uuid4())[:8]
        default_title = f"Чат {len(self.chats) + 1}"

        self.chats[chat_id] = {
            "title": default_title,
            "work_dir": self.work_dir,
            "messages": [{"role": "system", "content": load_system_rules()}]
        }
        self.switch_to_chat(chat_id)

    def switch_to_chat(self, chat_id):
        if chat_id not in self.chats:
            return
        self.current_chat_id = chat_id
        chat_data = self.chats[chat_id]

        # Відновлюємо збережену робочу папку чату
        self.work_dir = chat_data["work_dir"]
        if hasattr(self, "dir_path_entry"):
            self.dir_path_entry.configure(state="normal")
            self.dir_path_entry.delete(0, "end")
            self.dir_path_entry.insert(0, self.work_dir)
            self.dir_path_entry.configure(state="readonly")

        # Відновлюємо журнал з історії повідомлень
        if hasattr(self, "log_textbox"):
            self._render_chat(chat_data)

        self.refresh_chat_list_ui()

    def refresh_chat_list_ui(self):
        for widget in self.chats_scroll.winfo_children():
            widget.destroy()

        if self.current_chat_id in self.chats:
            self.chat_title.configure(text=self.chats[self.current_chat_id]["title"])

        for c_id, c_data in self.chats.items():
            is_active = (c_id == self.current_chat_id)
            folder_name = os.path.basename(c_data['work_dir']) or c_data['work_dir']
            display_text = f"{c_data['title']}\n{folder_name}"

            btn = ctk.CTkButton(
                self.chats_scroll,
                text=display_text,
                anchor="w",
                height=54,
                corner_radius=10,
                font=font(13),
                fg_color=RAISED if is_active else "transparent",
                hover_color=RAISED,
                text_color=TEXT if is_active else TEXT_SOFT,
                border_width=1 if is_active else 0,
                border_color=ACCENT,
                command=lambda cid=c_id: self.switch_to_chat(cid)
            )
            btn.pack(fill="x", pady=3, padx=4)

    def start_task_thread(self):
        task_text = self.task_entry.get().strip()
        if not task_text:
            return
        if not self.current_chat_id:
            self.create_new_chat()
        if str(self.send_btn.cget("state")) == "disabled":
            return  # завдання вже виконується

        self.task_entry.delete(0, "end")
        self._set_busy(True)
        self.set_status("busy", "Виконується завдання…")

        chat_id = self.current_chat_id
        chat_data = self.chats[chat_id]
        if chat_data["title"].startswith("Чат "):
            chat_data["title"] = task_text[:18] + ("..." if len(task_text) > 18 else "")
            self.refresh_chat_list_ui()

        chat_data["messages"].append({"role": "user", "content": task_text})
        self._write_message("user", task_text)

        threading.Thread(
            target=self.run_ai_task,
            args=(task_text, chat_id, self.work_dir),
            daemon=True
        ).start()

    def run_ai_task(self, task_text, chat_id, work_dir):
        try:
            os.chdir(work_dir)
            print(f"\n[Робочу директорію змінено на: {work_dir}]")
            print(f"Завдання: {task_text}")

            chat_data = self.chats[chat_id]

            # Виклик рушія AI з виведенням fallback-логів у термінал
            response_content = execute_ai_with_fallback(
                messages=chat_data["messages"],
                provider_entries_getter=lambda: self.provider_entries,
                logger=print
            )

            chat_data["messages"].append({"role": "assistant", "content": response_content})

            def update_ui():
                # Показуємо відповідь, лише якщо користувач і далі в цьому чаті
                if self.current_chat_id == chat_id:
                    self._write_message("agent", response_content)
                self.set_status("ok", "Готово")
                self._set_busy(False)
                self.refresh_chat_list_ui()

            self.after(0, update_ui)

        except Exception as e:
            err_str = str(e)
            print(f"[Помилка виконання]: {err_str}")

            def update_ui_error():
                if self.current_chat_id == chat_id:
                    self._write_message("error", err_str)
                self.set_status("error", "Помилка виконання")
                self._set_busy(False)

            self.after(0, update_ui_error)


# Сумісність з main.py, який імпортує AIDesktopApp
AIDesktopApp = AIStudioApp


if __name__ == "__main__":
    app = AIStudioApp()
    app.mainloop()
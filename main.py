import json
import threading
import importlib
import random
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

try:
    import ttkbootstrap as ttk
except ImportError as exc:
    raise SystemExit(
        "ttkbootstrap is required. Install it with: pip install ttkbootstrap"
    ) from exc

APP_TITLE = "JSON Translator"
SETTINGS_FILE = Path("settings.json")
DEFAULT_SYSTEM_PROMPT = (
    "You are a professional game localization translator.\n"
    "Translate only natural language text into the target language specified by the user.\n"
    "Preserve placeholders, variables, markup tags, escape sequences, and line breaks exactly.\n"
    "Do not translate keys, IDs, code-like strings, or formatting tokens.\n"
    "Return only translated text."
)


class TranslatorUI(ttk.Window):
    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title(APP_TITLE)
        self.geometry("1200x900")
        self.minsize(1080, 820)

        self.selected_file = tk.StringVar()
        self.provider_var = tk.StringVar(value="OpenAI")
        self.model_var = tk.StringVar(value="gpt-5.4")
        self.source_lang_var = tk.StringVar(value="auto")
        self.target_lang_var = tk.StringVar(value="ko")
        self.save_path_var = tk.StringVar()
        self.save_path_auto_assigned = False
        self.api_key_input_var = tk.StringVar()
        self.api_key_summary_var = tk.StringVar(value="No API keys saved")
        self.gemini_thinking_level_var = tk.StringVar(value="minimal")
        self.gemini_temperature_var = tk.StringVar(value="1.0")
        self.exclude_keys_var = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Idle")
        self.key_summary_var = tk.StringVar(value="No keys analyzed yet")
        self.json_validated = False
        self.sections_enabled = False
        self.cached_json_path = ""
        self.cached_json_data = None
        self.all_keys: list[str] = []
        self.translate_keys: list[str] = []
        self.exclude_keys: list[str] = []
        self.api_keys_by_provider: dict[str, list[str]] = {"OpenAI": [], "Gemini": []}
        self.translation_running = False
        self.translated_result = None

        self._apply_theme()
        self._build_ui()
        self._load_settings()
        self._set_sections_enabled(False)
        self.after(10, self._center_window)

    def _get_active_provider(self) -> str:
        provider = self.provider_var.get().strip()
        return provider if provider in {"OpenAI", "Gemini"} else "OpenAI"

    def _get_provider_api_keys(self, provider: str) -> list[str]:
        if provider not in self.api_keys_by_provider:
            self.api_keys_by_provider[provider] = []
        return self.api_keys_by_provider[provider]

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_theme(self) -> None:
        style = ttk.Style()
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=5)
        style.configure("TProgressbar", thickness=12)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)

        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=0)
        root.rowconfigure(3, weight=1)
        root.rowconfigure(4, weight=1)
        root.rowconfigure(5, weight=0)

        self._build_file_section(root)
        self._build_key_selection_section(root)
        self._build_translation_section(root)
        self._build_system_prompt_section(root)
        self._build_log_section(root)
        self._build_footer_section(root)

    def _build_file_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="1) File", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="JSON File").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.file_path_entry = ttk.Entry(frame, textvariable=self.selected_file)
        self.file_path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.browse_file_btn = ttk.Button(frame, text="Browse", command=self._choose_file, bootstyle="secondary")
        self.browse_file_btn.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        self.preview_file_btn = ttk.Button(frame, text="Preview", command=self._preview_file, bootstyle="info")
        self.preview_file_btn.grid(row=0, column=3, sticky="ew", padx=(0, 4))
        self.analyze_keys_btn = ttk.Button(frame, text="Analyze Keys", command=self._analyze_keys, bootstyle="primary")
        self.analyze_keys_btn.grid(row=0, column=4, sticky="ew")

        ttk.Label(frame, text="Save Path").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.save_path_entry = ttk.Entry(frame, textvariable=self.save_path_var)
        self.save_path_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=(8, 0))
        self.browse_save_btn = ttk.Button(frame, text="Browse Save", command=self._choose_save_path, bootstyle="secondary")
        self.browse_save_btn.grid(row=1, column=4, sticky="ew", pady=(8, 0))

    def _build_key_selection_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="2) Key Selection", padding=12, bootstyle="primary")
        frame.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)
        self.key_selection_frame = frame

        self.open_key_manager_btn = ttk.Button(
            frame,
            text="Open Key Manager",
            command=self._open_key_manager,
            bootstyle="primary",
        )
        self.open_key_manager_btn.grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(frame, textvariable=self.key_summary_var).grid(row=0, column=1, sticky="w")

    def _build_translation_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="3) Translation Settings", padding=12, bootstyle="info")
        frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.translation_frame = frame

        for col in range(4):
            frame.columnconfigure(col, weight=1)

        ttk.Label(frame, text="Provider").grid(row=0, column=0, sticky="w")
        provider = ttk.Combobox(
            frame,
            textvariable=self.provider_var,
            state="readonly",
            values=["OpenAI", "Gemini"],
        )
        provider.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))
        provider.bind("<<ComboboxSelected>>", self._on_provider_change)
        self.provider_combo = provider

        ttk.Label(frame, text="Model").grid(row=0, column=1, sticky="w")
        self.model_combo = ttk.Combobox(frame, textvariable=self.model_var, state="readonly")
        self.model_combo.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(2, 8))
        self._update_model_options()

        ttk.Label(frame, text="Source Language").grid(row=0, column=2, sticky="w")
        self.source_lang_combo = ttk.Combobox(
            frame,
            textvariable=self.source_lang_var,
            state="readonly",
            values=["auto", "en", "ja", "ko"],
        )
        self.source_lang_combo.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(2, 8))

        ttk.Label(frame, text="Target Language").grid(row=0, column=3, sticky="w")
        self.target_lang_combo = ttk.Combobox(
            frame,
            textvariable=self.target_lang_var,
            state="readonly",
            values=["ko", "en", "ja"],
        )
        self.target_lang_combo.grid(row=1, column=3, sticky="ew", pady=(2, 8))

        self.manage_api_keys_btn = ttk.Button(
            frame,
            text="Manage API Keys",
            command=self._open_api_key_manager,
            bootstyle="secondary",
        )
        self.manage_api_keys_btn.grid(row=2, column=0, sticky="w", pady=(2, 0))
        ttk.Label(frame, textvariable=self.api_key_summary_var).grid(row=2, column=1, columnspan=3, sticky="w", pady=(2, 0))

        ttk.Label(frame, text="Gemini Thinking").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.gemini_thinking_combo = ttk.Combobox(
            frame,
            textvariable=self.gemini_thinking_level_var,
            state="readonly",
            values=["minimal", "low", "medium", "high"],
        )
        self.gemini_thinking_combo.grid(row=4, column=0, sticky="ew", padx=(0, 8), pady=(2, 0))

        ttk.Label(frame, text="Gemini Temperature").grid(row=3, column=1, sticky="w", pady=(8, 0))
        self.gemini_temp_entry = ttk.Entry(frame, textvariable=self.gemini_temperature_var)
        self.gemini_temp_entry.grid(row=4, column=1, sticky="ew", padx=(0, 8), pady=(2, 0))

    def _build_system_prompt_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="4) System Prompt", padding=12, bootstyle="warning")
        frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        self.system_prompt_frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="This prompt is sent as the system instruction for translation API calls.",
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.system_prompt_text = ScrolledText(frame, wrap=tk.WORD, height=10)
        self.system_prompt_text.grid(row=1, column=0, sticky="nsew")

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, sticky="e", pady=(8, 0))
        self.load_prompt_btn = ttk.Button(button_row, text="Load Default", command=self._load_default_prompt)
        self.load_prompt_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.clear_prompt_btn = ttk.Button(button_row, text="Clear", command=self._clear_prompt)
        self.clear_prompt_btn.pack(side=tk.LEFT)

    def _build_log_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="5) Run / Log", padding=12, bootstyle="secondary")
        frame.grid(row=4, column=0, sticky="nsew", pady=(0, 8))
        self.log_frame = frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        action_row = ttk.Frame(frame)
        action_row.grid(row=0, column=0, sticky="ew")
        action_row.columnconfigure(3, weight=1)

        self.start_translation_btn = ttk.Button(action_row, text="Start Translation", command=self._start_translation, bootstyle="success")
        self.start_translation_btn.grid(row=0, column=0, padx=(0, 6))
        self.stop_translation_btn = ttk.Button(action_row, text="Stop", command=self._stop_translation, bootstyle="danger")
        self.stop_translation_btn.grid(row=0, column=1, padx=(0, 6))
        ttk.Label(action_row, textvariable=self.status_var).grid(row=0, column=2, sticky="w", padx=(0, 10))
        self.save_log_btn = ttk.Button(action_row, text="Save Log", command=self._save_log, bootstyle="primary")
        self.save_log_btn.grid(row=0, column=4, padx=(0, 6), sticky="e")
        self.save_settings_btn = ttk.Button(action_row, text="Save Settings", command=self._save_settings, bootstyle="primary")
        self.save_settings_btn.grid(row=0, column=5, sticky="e")

        ttk.Progressbar(frame, maximum=100, variable=self.progress_var).grid(row=1, column=0, sticky="ew", pady=(8, 8))

        self.log_text = ScrolledText(frame, wrap=tk.WORD, height=10, state=tk.DISABLED)
        self.log_text.grid(row=2, column=0, sticky="nsew")

    def _build_footer_section(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=5, column=0, sticky="ew")
        ttk.Label(
            frame,
            text="Version 1.0.0",
            foreground="#555555",
        ).pack(anchor="w")

    def _choose_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if file_path:
            self.selected_file.set(file_path)
            self._append_log(f"Selected file: {file_path}")
            if self._validate_and_activate_selected_json(show_error=True):
                src = Path(file_path)
                self.save_path_var.set(str(src.with_name(f"{src.stem}.translated.json")))
                self.save_path_auto_assigned = True
                self.all_keys = []
                self.key_summary_var.set("No keys analyzed yet")
                self._set_sections_enabled(False)

    def _choose_save_path(self) -> None:
        src = self.selected_file.get().strip()
        initial_name = "translated.json"
        if src:
            p = Path(src)
            initial_name = f"{p.stem}.translated.json"

        save_path = filedialog.asksaveasfilename(
            title="Select output JSON path",
            defaultextension=".json",
            initialfile=initial_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if save_path:
            self.save_path_var.set(save_path)
            self.save_path_auto_assigned = False
            self._append_log(f"Selected save path: {save_path}")

    def _set_sections_enabled(self, enabled: bool) -> None:
        self.sections_enabled = enabled
        state = "normal" if enabled else "disabled"

        self._set_sections_2_to_4_enabled(enabled)

        run_controls = [
            getattr(self, "start_translation_btn", None),
            getattr(self, "stop_translation_btn", None),
            getattr(self, "save_log_btn", None),
            getattr(self, "save_settings_btn", None),
        ]
        for widget in run_controls:
            if widget is not None:
                widget.configure(state=state)

        if not enabled and hasattr(self, "key_manager_window") and self.key_manager_window.winfo_exists():
            self._close_key_manager()

        if not enabled and hasattr(self, "api_key_manager_window") and self.api_key_manager_window.winfo_exists():
            self._close_api_key_manager()

    def _set_sections_2_to_4_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"

        if hasattr(self, "open_key_manager_btn"):
            self.open_key_manager_btn.configure(state=state)

        translation_controls = [
            getattr(self, "provider_combo", None),
            getattr(self, "model_combo", None),
            getattr(self, "source_lang_combo", None),
            getattr(self, "target_lang_combo", None),
            getattr(self, "manage_api_keys_btn", None),
            getattr(self, "gemini_thinking_combo", None),
            getattr(self, "gemini_temp_entry", None),
        ]
        for widget in translation_controls:
            if widget is not None:
                if widget is self.manage_api_keys_btn:
                    widget.configure(state=state)
                elif widget is self.gemini_temp_entry:
                    widget.configure(state=state)
                else:
                    widget.configure(state="readonly" if enabled else "disabled")

        prompt_controls = [
            getattr(self, "load_prompt_btn", None),
            getattr(self, "clear_prompt_btn", None),
        ]
        for widget in prompt_controls:
            if widget is not None:
                widget.configure(state=state)

        if hasattr(self, "system_prompt_text"):
            self.system_prompt_text.configure(state=tk.NORMAL if enabled else tk.DISABLED)

        self._update_provider_dependent_ui(enabled)

    def _set_translation_ui_locked(self, locked: bool) -> None:
        file_state = "disabled" if locked else "normal"
        file_controls = [
            getattr(self, "file_path_entry", None),
            getattr(self, "browse_file_btn", None),
            getattr(self, "preview_file_btn", None),
            getattr(self, "analyze_keys_btn", None),
            getattr(self, "save_path_entry", None),
            getattr(self, "browse_save_btn", None),
        ]
        for widget in file_controls:
            if widget is not None:
                widget.configure(state=file_state)

        if locked:
            self._set_sections_2_to_4_enabled(False)
            if hasattr(self, "key_manager_window") and self.key_manager_window.winfo_exists():
                self._close_key_manager()
            if hasattr(self, "api_key_manager_window") and self.api_key_manager_window.winfo_exists():
                self._close_api_key_manager()
            return

        self._set_sections_2_to_4_enabled(self.sections_enabled)

    def _update_provider_dependent_ui(self, sections_enabled: bool | None = None) -> None:
        if sections_enabled is None:
            sections_enabled = True
            if hasattr(self, "provider_combo"):
                sections_enabled = self.provider_combo.cget("state") != "disabled"

        is_gemini_enabled = sections_enabled and self._get_active_provider() == "Gemini"

        if hasattr(self, "gemini_thinking_combo"):
            self.gemini_thinking_combo.configure(state="readonly" if is_gemini_enabled else "disabled")
        if hasattr(self, "gemini_temp_entry"):
            self.gemini_temp_entry.configure(state="normal" if is_gemini_enabled else "disabled")

    def _validate_and_activate_selected_json(self, show_error: bool = False) -> bool:
        path = self.selected_file.get().strip()
        if not path:
            self.json_validated = False
            self.cached_json_data = None
            self.cached_json_path = ""
            self._set_sections_enabled(False)
            self.key_summary_var.set("No keys analyzed yet")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.json_validated = True
            self.cached_json_data = data
            self.cached_json_path = path
            self.status_var.set("JSON validated")
            self._append_log("JSON validation passed. Click Analyze Keys to enable sections 2-5.")
            return True
        except Exception as exc:
            self.json_validated = False
            self.cached_json_data = None
            self.cached_json_path = ""
            self._set_sections_enabled(False)
            self.status_var.set("Invalid JSON")
            self._append_log(f"JSON validation failed: {exc}")
            if show_error:
                messagebox.showerror(APP_TITLE, f"Invalid JSON file:\n{exc}")
            return False

    def _extract_all_keys(self, data) -> set[str]:
        keys: set[str] = set()

        def walk(node) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    # Only include keys that map to natural-language text candidates.
                    if isinstance(value, str):
                        keys.add(str(key))
                    walk(value)
                return
            if isinstance(node, list):
                for item in node:
                    walk(item)

        walk(data)
        return keys

    def _analyze_keys(self) -> None:
        if not self._validate_and_activate_selected_json(show_error=True):
            return

        try:
            data = self.cached_json_data

            prev_translate = set(self.translate_keys)
            prev_exclude = set(self.exclude_keys)
            self.all_keys = sorted(self._extract_all_keys(data))
            current_key_set = set(self.all_keys)

            # Keep only keys that also exist in the newly analyzed file.
            self.exclude_keys = sorted(prev_exclude & current_key_set)
            # New keys that were not previously classified are added to translate keys.
            self.translate_keys = sorted(current_key_set - set(self.exclude_keys))
            self._refresh_key_listboxes()

            self._append_log(
                f"Key analysis complete. Found {len(self.all_keys)} keys, "
                f"translate={len(self.translate_keys)}, exclude={len(self.exclude_keys)}, "
                f"retained={(len((prev_translate | prev_exclude) & current_key_set))}"
            )
            self._set_sections_enabled(True)
            self.status_var.set("Keys analyzed")
        except Exception as exc:
            self._append_log(f"Key analysis failed: {exc}")
            self.status_var.set("Key analysis error")
            messagebox.showerror(APP_TITLE, f"Failed to analyze JSON keys:\n{exc}")

    def _refresh_key_listboxes(self) -> None:
        self.translate_keys = sorted(set(self.translate_keys))
        self.exclude_keys = sorted(set(self.exclude_keys))
        self._refresh_key_summary()

        if (
            not hasattr(self, "translate_keys_listbox")
            or not hasattr(self, "exclude_keys_listbox")
            or not self.translate_keys_listbox.winfo_exists()
            or not self.exclude_keys_listbox.winfo_exists()
        ):
            self.exclude_keys_var.set(",".join(self.exclude_keys))
            return

        translate_filter = ""
        if hasattr(self, "translate_filter_var"):
            translate_filter = self.translate_filter_var.get().strip().lower()

        exclude_filter = ""
        if hasattr(self, "exclude_filter_var"):
            exclude_filter = self.exclude_filter_var.get().strip().lower()

        self.translate_keys_listbox.delete(0, tk.END)
        for key in self.translate_keys:
            if translate_filter and translate_filter not in key.lower():
                continue
            self.translate_keys_listbox.insert(tk.END, key)

        self.exclude_keys_listbox.delete(0, tk.END)
        for key in self.exclude_keys:
            if exclude_filter and exclude_filter not in key.lower():
                continue
            self.exclude_keys_listbox.insert(tk.END, key)

        self.exclude_keys_var.set(",".join(self.exclude_keys))

    def _refresh_key_summary(self) -> None:
        if hasattr(self, "key_summary_var"):
            self.key_summary_var.set(
                f"All: {len(self.all_keys)} | Translate: {len(self.translate_keys)} | Exclude: {len(self.exclude_keys)}"
            )

    def _open_key_manager(self) -> None:
        if not self.json_validated:
            messagebox.showwarning(APP_TITLE, "Select and validate a JSON file first.")
            return

        if hasattr(self, "key_manager_window") and self.key_manager_window.winfo_exists():
            self.key_manager_window.lift()
            self.key_manager_window.focus_force()
            return

        win = ttk.Toplevel(self)
        self.key_manager_window = win
        win.title("Key Manager")
        win.geometry("980x620")
        win.minsize(860, 520)
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", self._close_key_manager)

        container = ttk.Frame(win, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=0)
        container.columnconfigure(2, weight=1)
        container.rowconfigure(1, weight=1)

        ttk.Label(container, text="Translate Keys", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(container, text="Exclude Keys", font=("Segoe UI", 10, "bold")).grid(row=0, column=2, sticky="w")

        self.translate_filter_var = tk.StringVar()
        self.exclude_filter_var = tk.StringVar()
        self.translate_filter_var.trace_add("write", lambda *_: self._refresh_key_listboxes())
        self.exclude_filter_var.trace_add("write", lambda *_: self._refresh_key_listboxes())

        ttk.Entry(container, textvariable=self.translate_filter_var).grid(row=0, column=0, sticky="e", padx=(180, 8))
        ttk.Entry(container, textvariable=self.exclude_filter_var).grid(row=0, column=2, sticky="e", padx=(180, 0))

        self.translate_keys_listbox = tk.Listbox(container, selectmode=tk.EXTENDED, exportselection=False)
        self.translate_keys_listbox.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(4, 6))
        self.translate_keys_listbox.configure(
            bg="#f8fafc",
            fg="#0f172a",
            selectbackground="#0d6efd",
            selectforeground="#ffffff",
            font=("Consolas", 10),
            borderwidth=1,
            relief=tk.SOLID,
        )

        control_frame = ttk.Frame(container)
        control_frame.grid(row=1, column=1, sticky="ns", pady=(4, 6))
        ttk.Button(control_frame, text="Exclude ->", command=self._move_to_exclude, bootstyle="danger").grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control_frame, text="<- Include", command=self._move_to_translate, bootstyle="success").grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control_frame, text="Exclude All", command=self._exclude_all, bootstyle="outline-danger").grid(row=2, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(control_frame, text="Include All", command=self._include_all, bootstyle="outline-success").grid(row=3, column=0, sticky="ew")

        self.exclude_keys_listbox = tk.Listbox(container, selectmode=tk.EXTENDED, exportselection=False)
        self.exclude_keys_listbox.grid(row=1, column=2, sticky="nsew", padx=(8, 0), pady=(4, 6))
        self.exclude_keys_listbox.configure(
            bg="#f8fafc",
            fg="#0f172a",
            selectbackground="#dc3545",
            selectforeground="#ffffff",
            font=("Consolas", 10),
            borderwidth=1,
            relief=tk.SOLID,
        )

        bottom = ttk.Frame(container)
        bottom.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(
            bottom,
            textvariable=self.key_summary_var,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Close", command=self._close_key_manager, bootstyle="secondary").grid(row=0, column=1, sticky="e")

        self._refresh_key_listboxes()
        self._center_child_window(win, 980, 620)

    def _close_key_manager(self) -> None:
        if hasattr(self, "key_manager_window") and self.key_manager_window.winfo_exists():
            self.key_manager_window.destroy()

        for attr in [
            "translate_keys_listbox",
            "exclude_keys_listbox",
            "translate_filter_var",
            "exclude_filter_var",
        ]:
            if hasattr(self, attr):
                delattr(self, attr)

    def _center_child_window(self, window: tk.Toplevel, width: int, height: int) -> None:
        self.update_idletasks()
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()

        x = max(parent_x + (parent_w - width) // 2, 0)
        y = max(parent_y + (parent_h - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.focus_force()

    def _move_to_exclude(self) -> None:
        selected = [self.translate_keys_listbox.get(i) for i in self.translate_keys_listbox.curselection()]
        if not selected:
            return
        self.translate_keys = [k for k in self.translate_keys if k not in selected]
        self.exclude_keys.extend(selected)
        self._refresh_key_listboxes()

    def _move_to_translate(self) -> None:
        selected = [self.exclude_keys_listbox.get(i) for i in self.exclude_keys_listbox.curselection()]
        if not selected:
            return
        self.exclude_keys = [k for k in self.exclude_keys if k not in selected]
        self.translate_keys.extend(selected)
        self._refresh_key_listboxes()

    def _exclude_all(self) -> None:
        self.exclude_keys.extend(self.translate_keys)
        self.translate_keys = []
        self._refresh_key_listboxes()

    def _include_all(self) -> None:
        self.translate_keys.extend(self.exclude_keys)
        self.exclude_keys = []
        self._refresh_key_listboxes()

    def _preview_file(self) -> None:
        path = self.selected_file.get().strip()
        if not path:
            messagebox.showwarning(APP_TITLE, "Please select a JSON file first.")
            return

        try:
            if not self._validate_and_activate_selected_json(show_error=True):
                return
            data = self.cached_json_data
            summary = f"Preview OK. Root type: {type(data).__name__}"
            self._append_log(summary)
            self.status_var.set("Preview OK")
        except Exception as exc:
            self._append_log(f"Preview failed: {exc}")
            self.status_var.set("Preview error")
            messagebox.showerror(APP_TITLE, f"Failed to read JSON:\n{exc}")

    def _start_translation(self) -> None:
        if self.translation_running:
            messagebox.showinfo(APP_TITLE, "Translation is already running.")
            return

        if not self._validate_and_activate_selected_json(show_error=True):
            return

        provider = self._get_active_provider()
        source_lang = self.source_lang_var.get().strip()
        target_lang = self.target_lang_var.get().strip()
        if source_lang and target_lang and source_lang == target_lang:
            self.status_var.set("Language configuration error")
            self._append_log(
                f"Blocked translation: source language and target language are the same ({source_lang})."
            )
            messagebox.showerror(
                APP_TITLE,
                "Source language and target language are the same. Change one of them before starting translation.",
            )
            return

        available_keys = [k for k in self._get_provider_api_keys(provider) if k.strip()]
        if not available_keys:
            messagebox.showwarning(APP_TITLE, f"Add at least one {provider} API key in API Key Manager first.")
            return

        if not self.all_keys:
            self._analyze_keys()

        output_path = self.save_path_var.get().strip()
        if output_path and self.save_path_auto_assigned and Path(output_path).exists():
            overwrite_ok = messagebox.askyesno(
                APP_TITLE,
                (
                    "An auto-selected output file already exists.\n\n"
                    f"{output_path}\n\n"
                    "Do you want to overwrite this file?"
                ),
            )
            if not overwrite_ok:
                self.status_var.set("Overwrite canceled")
                self._append_log(f"Canceled translation: overwrite not approved for '{output_path}'.")
                return
            self._append_log(f"Overwrite confirmed for auto-selected path: {output_path}")

        self.translation_running = True
        self.progress_var.set(0)
        self.status_var.set("Running translation")
        self._set_translation_ui_locked(True)
        self.start_translation_btn.configure(state="disabled")
        self.stop_translation_btn.configure(state="normal")
        self.save_log_btn.configure(state="normal")
        self._append_log(
            f"Starting {provider} translation with model={self.model_var.get()} "
            f"({self.source_lang_var.get()} -> {self.target_lang_var.get()})"
        )

        worker = threading.Thread(target=self._run_translation_job, daemon=True)
        worker.start()

    def _stop_translation(self) -> None:
        if not self.translation_running:
            self.status_var.set("Stopped")
            self._append_log("Stop clicked. No active job.")
            return

        self.translation_running = False
        self.status_var.set("Stopping...")
        self._append_log("Stop requested. Finishing current API call and stopping.")

    def _save_log(self) -> None:
        default_name = f"json_translator_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        save_path = filedialog.asksaveasfilename(
            title="Save log as text",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not save_path:
            return

        try:
            log_text = self.log_text.get("1.0", tk.END)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(log_text.rstrip() + "\n")
            self._append_log(f"Saved log file: {save_path}")
            self.status_var.set("Log saved")
        except Exception as exc:
            self._append_log(f"Failed to save log file: {exc}")
            messagebox.showerror(APP_TITLE, f"Failed to save log file:\n{exc}")

    def _run_translation_job(self) -> None:
        try:
            provider = self._get_active_provider()
            api_keys = [k for k in self._get_provider_api_keys(provider) if k.strip()]
            if not api_keys:
                raise RuntimeError(f"No {provider} API keys available. Add keys in API Key Manager.")

            key_state = {
                "provider": provider,
                "keys": api_keys,
                "index": 0,
                "client": self._create_provider_client(provider, api_keys[0]),
                "consecutive_errors": 0,
            }

            model = self.model_var.get().strip()
            source_lang = self.source_lang_var.get().strip()
            target_lang = self.target_lang_var.get().strip()
            system_prompt = self.system_prompt_text.get("1.0", tk.END).strip() or DEFAULT_SYSTEM_PROMPT

            self._post_ui(self._append_log, f"Using {provider} API key #1/{len(api_keys)}")

            data = self.cached_json_data
            translate_set = set(self.translate_keys) if self.translate_keys else set(self.all_keys)
            exclude_set = set(self.exclude_keys)

            total_targets = self._count_translatable_strings(data, translate_set, exclude_set)
            if total_targets == 0:
                self._post_ui(self._append_log, "No eligible text found to translate.")
                self._post_ui(self.status_var.set, "Nothing to translate")
                return

            counters = {"done": 0, "translated": 0, "skipped": 0, "failed": 0}
            result = self._translate_node(
                node=data,
                current_key=None,
                key_state=key_state,
                model=model,
                source_lang=source_lang,
                target_lang=target_lang,
                system_prompt=system_prompt,
                translate_set=translate_set,
                exclude_set=exclude_set,
                counters=counters,
                total_targets=total_targets,
            )

            if not self.translation_running:
                self._post_ui(self._append_log, "Translation stopped by user.")
                self._post_ui(self.status_var.set, "Stopped")
                return

            self.translated_result = result
            self._post_ui(self.progress_var.set, 100)

            output_path = self.save_path_var.get().strip()
            if output_path:
                try:
                    self._write_json_file(output_path, result)
                    self._post_ui(self._append_log, f"Auto-saved translated result: {output_path}")
                except Exception as exc:
                    self._post_ui(self._append_log, f"Auto-save failed: {exc}")

            self._post_ui(
                self._append_log,
                (
                    f"Translation complete. translated={counters['translated']}, "
                    f"skipped={counters['skipped']}, failed={counters['failed']}"
                ),
            )
            self._post_ui(self.status_var.set, "Completed")
        except Exception as exc:
            self._post_ui(self._append_log, f"Translation failed: {exc}")
            self._post_ui(self.status_var.set, "Translation error")
            self._post_ui(messagebox.showerror, APP_TITLE, f"Translation failed:\n{exc}")
        finally:
            self.translation_running = False
            self._post_ui(self._set_translation_ui_locked, False)
            self._post_ui(
                self.start_translation_btn.configure,
                state="normal" if self.sections_enabled else "disabled",
            )
            self._post_ui(self.stop_translation_btn.configure, state="normal")
            self._post_ui(
                self.save_log_btn.configure,
                state="normal" if self.sections_enabled else "disabled",
            )

    def _create_openai_client(self, api_key: str):
        try:
            module = importlib.import_module("openai")
            client_cls = getattr(module, "OpenAI", None)
            if client_cls is None:
                raise RuntimeError("OpenAI client class not found in openai package")
            return client_cls(api_key=api_key, timeout=60.0, max_retries=2)
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Install with: pip install openai") from exc

    def _create_gemini_client(self, api_key: str):
        try:
            module = importlib.import_module("google.genai")
            client_cls = getattr(module, "Client", None)
            if client_cls is None:
                raise RuntimeError("Gemini Client class not found in google.genai package")
            return client_cls(api_key=api_key)
        except ImportError as exc:
            raise RuntimeError("google-genai package is not installed. Install with: pip install google-genai") from exc

    def _create_provider_client(self, provider: str, api_key: str):
        if provider == "OpenAI":
            return self._create_openai_client(api_key)
        if provider == "Gemini":
            return self._create_gemini_client(api_key)
        raise RuntimeError(f"Unsupported provider: {provider}")

    def _post_ui(self, func, *args, **kwargs) -> None:
        self.after(0, lambda: func(*args, **kwargs))

    def _count_translatable_strings(self, node, translate_set: set[str], exclude_set: set[str], current_key: str | None = None) -> int:
        if isinstance(node, dict):
            count = 0
            for key, value in node.items():
                count += self._count_translatable_strings(value, translate_set, exclude_set, str(key))
            return count

        if isinstance(node, list):
            count = 0
            for item in node:
                count += self._count_translatable_strings(item, translate_set, exclude_set, current_key)
            return count

        if isinstance(node, str):
            if current_key is None:
                return 0
            if not node.strip():
                return 0
            if current_key in exclude_set:
                return 0
            if translate_set and current_key not in translate_set:
                return 0
            return 1

        return 0

    def _translate_node(
        self,
        node,
        current_key: str | None,
        key_state: dict,
        model: str,
        source_lang: str,
        target_lang: str,
        system_prompt: str,
        translate_set: set[str],
        exclude_set: set[str],
        counters: dict,
        total_targets: int,
    ):
        if isinstance(node, dict):
            out = {}
            for key, value in node.items():
                if not self.translation_running:
                    return out
                out[key] = self._translate_node(
                    value,
                    str(key),
                    key_state,
                    model,
                    source_lang,
                    target_lang,
                    system_prompt,
                    translate_set,
                    exclude_set,
                    counters,
                    total_targets,
                )
            return out

        if isinstance(node, list):
            out_list = []
            for item in node:
                if not self.translation_running:
                    return out_list
                out_list.append(
                    self._translate_node(
                        item,
                        current_key,
                        key_state,
                        model,
                        source_lang,
                        target_lang,
                        system_prompt,
                        translate_set,
                        exclude_set,
                        counters,
                        total_targets,
                    )
                )
            return out_list

        if not isinstance(node, str):
            return node

        if current_key is None or current_key in exclude_set:
            counters["skipped"] += 1
            return node

        if translate_set and current_key not in translate_set:
            counters["skipped"] += 1
            return node

        if not node.strip():
            counters["skipped"] += 1
            return node

        if not self.translation_running:
            return node

        try:
            translated = self._translate_text_with_provider(
                key_state=key_state,
                model=model,
                source_lang=source_lang,
                target_lang=target_lang,
                system_prompt=system_prompt,
                text=node,
            )
            counters["translated"] += 1
            self._post_ui(
                self._append_log,
                f"Translated[{current_key}] {node!r} -> {translated!r}",
            )
        except Exception as exc:
            translated = node
            counters["failed"] += 1
            self._post_ui(self._append_log, f"Translate failed for key '{current_key}': {exc}")

        counters["done"] += 1
        if total_targets > 0:
            progress = min((counters["done"] / total_targets) * 100, 100)
            self._post_ui(self.progress_var.set, progress)

        return translated

    def _translate_text_with_provider(
        self,
        key_state: dict,
        model: str,
        source_lang: str,
        target_lang: str,
        system_prompt: str,
        text: str,
    ) -> str:
        provider = key_state.get("provider", "OpenAI")
        if source_lang == "auto":
            source_instruction = (
                "Source language: auto\n"
                "Automatically detect the source language from Text.\n"
            )
        else:
            source_instruction = (
                f"Source language: {source_lang}\n"
                "Detect the actual language of Text first.\n"
                "If configured Source language differs from the actual language, ignore configured Source language and use the detected language for translation.\n"
            )

        prompt = (
            f"{source_instruction}"
            f"Target language: {target_lang}\n"
            "Translate the text exactly once into Target language.\n"
            "Return only the translated text.\n\n"
            f"Text:\n{text}"
        )
        while True:
            if not self.translation_running:
                return text

            client = key_state["client"]
            current_idx = key_state["index"]

            try:
                if provider == "OpenAI":
                    output = self._translate_text_openai_once(
                        client=client,
                        model=model,
                        system_prompt=system_prompt,
                        prompt=prompt,
                    )
                elif provider == "Gemini":
                    output = self._translate_text_gemini_once(
                        client=client,
                        model=model,
                        system_prompt=system_prompt,
                        prompt=prompt,
                    )
                else:
                    raise RuntimeError(f"Unsupported provider: {provider}")

                key_state["consecutive_errors"] = 0
                return output
            except Exception as exc:
                key_state["consecutive_errors"] += 1
                err_count = key_state["consecutive_errors"]
                self._post_ui(
                    self._append_log,
                    f"{provider} API error (key #{current_idx + 1}, consecutive={err_count}): {exc}",
                )

                # Exponential backoff with jitter helps recover from rate limits (e.g., HTTP 429).
                # Attempts: 1->~1s, 2->~2s, 3->~4s (capped to avoid excessive stalls).
                base_delay = min(2 ** (err_count - 1), 8)
                jitter = random.uniform(0.0, 0.5)
                sleep_s = base_delay + jitter
                self._post_ui(
                    self._append_log,
                    f"Retry backoff: waiting {sleep_s:.1f}s before next attempt.",
                )
                time.sleep(sleep_s)

                if err_count < 3:
                    continue

                next_index = current_idx + 1
                if next_index >= len(key_state["keys"]):
                    raise RuntimeError(f"All {provider} API keys exhausted after repeated API errors") from exc

                key_state["index"] = next_index
                key_state["client"] = self._create_provider_client(provider, key_state["keys"][next_index])
                key_state["consecutive_errors"] = 0
                self._post_ui(
                    self._append_log,
                    f"Switched to next {provider} API key #{next_index + 1}/{len(key_state['keys'])} after 3 errors.",
                )

    def _translate_text_openai_once(self, client, model: str, system_prompt: str, prompt: str) -> str:
        response = client.responses.create(
            model=model,
            instructions=system_prompt,
            input=prompt,
        )
        output = (response.output_text or "").strip()
        if not output:
            raise RuntimeError("Empty response from OpenAI model")
        return output

    def _write_json_file(self, path: str, data) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _translate_text_gemini_once(self, client, model: str, system_prompt: str, prompt: str) -> str:
        try:
            types_module = importlib.import_module("google.genai.types")
            config_cls = getattr(types_module, "GenerateContentConfig", None)
        except ImportError:
            config_cls = None

        if config_cls is not None:
            config_kwargs = {"system_instruction": system_prompt}

            thinking_level = self.gemini_thinking_level_var.get().strip()
            thinking_cls = getattr(types_module, "ThinkingConfig", None)
            if thinking_cls is not None and thinking_level in {"minimal", "low", "medium", "high"}:
                config_kwargs["thinking_config"] = thinking_cls(thinking_level=thinking_level)

            temp_str = self.gemini_temperature_var.get().strip()
            if temp_str:
                try:
                    temperature = float(temp_str)
                    config_kwargs["temperature"] = temperature
                except ValueError:
                    self._post_ui(self._append_log, f"Invalid Gemini temperature '{temp_str}'. Using default.")

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config_cls(**config_kwargs),
            )
        else:
            merged_prompt = f"System instruction:\n{system_prompt}\n\n{prompt}"
            response = client.models.generate_content(
                model=model,
                contents=merged_prompt,
            )

        output = (getattr(response, "text", None) or "").strip()
        if not output:
            raise RuntimeError("Empty response from Gemini model")
        return output

    def _refresh_api_key_summary(self) -> None:
        provider = self._get_active_provider()
        count = len([k for k in self._get_provider_api_keys(provider) if k.strip()])
        self.api_key_summary_var.set(f"{provider} keys: {count}")

    def _mask_api_key(self, key: str) -> str:
        key = key.strip()
        if len(key) <= 8:
            return "*" * len(key)
        return f"{key[:4]}...{key[-4:]}"

    def _open_api_key_manager(self) -> None:
        if hasattr(self, "api_key_manager_window") and self.api_key_manager_window.winfo_exists():
            self.api_key_manager_window.lift()
            self.api_key_manager_window.focus_force()
            return

        win = ttk.Toplevel(self)
        self.api_key_manager_window = win
        win.title("API Key Manager")
        win.geometry("720x500")
        win.minsize(640, 420)
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", self._close_api_key_manager)

        container = ttk.Frame(win, padding=12)
        container.pack(fill=tk.BOTH, expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        ttk.Label(container, text="Store keys by provider and rotate on repeated failures.").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        input_row = ttk.Frame(container)
        input_row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        input_row.columnconfigure(0, weight=1)

        self.api_key_input_entry = ttk.Entry(input_row, textvariable=self.api_key_input_var, show="*")
        self.api_key_input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(input_row, text="Add", command=self._add_api_key, bootstyle="success").grid(row=0, column=1, padx=(0, 6))
        ttk.Button(input_row, text="Remove Selected", command=self._remove_selected_api_keys, bootstyle="danger").grid(row=0, column=2, padx=(0, 6))
        ttk.Button(input_row, text="Move Up", command=self._move_api_key_up, bootstyle="outline-secondary").grid(row=0, column=3, padx=(0, 6))
        ttk.Button(input_row, text="Move Down", command=self._move_api_key_down, bootstyle="outline-secondary").grid(row=0, column=4)

        self.api_keys_listbox = tk.Listbox(container, selectmode=tk.EXTENDED, exportselection=False)
        self.api_keys_listbox.grid(row=2, column=0, sticky="nsew")
        self.api_keys_listbox.configure(
            bg="#f8fafc",
            fg="#0f172a",
            selectbackground="#0d6efd",
            selectforeground="#ffffff",
            font=("Consolas", 10),
            borderwidth=1,
            relief=tk.SOLID,
        )

        bottom = ttk.Frame(container)
        bottom.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.api_key_summary_var).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Close", command=self._close_api_key_manager, bootstyle="secondary").grid(row=0, column=1, sticky="e")

        self._refresh_api_key_listbox()
        self._center_child_window(win, 720, 500)

    def _close_api_key_manager(self) -> None:
        if hasattr(self, "api_key_manager_window") and self.api_key_manager_window.winfo_exists():
            self.api_key_manager_window.destroy()

        for attr in ["api_keys_listbox", "api_key_input_entry"]:
            if hasattr(self, attr):
                delattr(self, attr)

    def _refresh_api_key_listbox(self) -> None:
        provider = self._get_active_provider()
        self.api_keys_by_provider[provider] = [
            k.strip() for k in self._get_provider_api_keys(provider) if k.strip()
        ]
        self._refresh_api_key_summary()

        if not hasattr(self, "api_keys_listbox") or not self.api_keys_listbox.winfo_exists():
            return

        self.api_keys_listbox.delete(0, tk.END)
        keys = self._get_provider_api_keys(provider)
        for idx, key in enumerate(keys, start=1):
            self.api_keys_listbox.insert(tk.END, f"{idx}. {self._mask_api_key(key)}")

    def _add_api_key(self) -> None:
        key = self.api_key_input_var.get().strip()
        if not key:
            return
        provider = self._get_active_provider()
        keys = self._get_provider_api_keys(provider)
        if key in keys:
            messagebox.showinfo(APP_TITLE, "This API key is already saved.")
            return
        keys.append(key)
        self.api_key_input_var.set("")
        self._refresh_api_key_listbox()
        self._append_log(f"Added API key for {provider}.")

    def _remove_selected_api_keys(self) -> None:
        if not hasattr(self, "api_keys_listbox"):
            return
        indices = list(self.api_keys_listbox.curselection())
        if not indices:
            return
        provider = self._get_active_provider()
        keys = self._get_provider_api_keys(provider)
        to_remove = {keys[i] for i in indices if i < len(keys)}
        self.api_keys_by_provider[provider] = [k for k in keys if k not in to_remove]
        self._refresh_api_key_listbox()
        self._append_log(f"Removed {len(to_remove)} API key(s) for {provider}.")

    def _move_api_key_up(self) -> None:
        if not hasattr(self, "api_keys_listbox"):
            return
        indices = list(self.api_keys_listbox.curselection())
        if len(indices) != 1:
            messagebox.showinfo(APP_TITLE, "Select one key to move.")
            return

        index = indices[0]
        if index <= 0:
            return

        provider = self._get_active_provider()
        keys = self._get_provider_api_keys(provider)
        keys[index - 1], keys[index] = keys[index], keys[index - 1]
        self._refresh_api_key_listbox()
        self.api_keys_listbox.selection_set(index - 1)
        self._append_log(f"Moved API key up for {provider}.")

    def _move_api_key_down(self) -> None:
        if not hasattr(self, "api_keys_listbox"):
            return
        indices = list(self.api_keys_listbox.curselection())
        if len(indices) != 1:
            messagebox.showinfo(APP_TITLE, "Select one key to move.")
            return

        index = indices[0]
        provider = self._get_active_provider()
        keys = self._get_provider_api_keys(provider)
        if index >= len(keys) - 1:
            return

        keys[index + 1], keys[index] = keys[index], keys[index + 1]
        self._refresh_api_key_listbox()
        self.api_keys_listbox.selection_set(index + 1)
        self._append_log(f"Moved API key down for {provider}.")

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _on_provider_change(self, _event=None) -> None:
        self._update_model_options()
        self._refresh_api_key_summary()
        self._refresh_api_key_listbox()
        self._update_provider_dependent_ui()

    def _update_model_options(self) -> None:
        models_by_provider = {
            "OpenAI": ["gpt-5.4", "gpt-5-mini", "gpt-5-nano", "gpt-4.1"],
            "Gemini": [
                "gemini-3-flash-preview",
                "gemini-3.1-pro-preview",
                "gemini-3.1-flash-lite-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash",
            ],
        }
        models = models_by_provider.get(self.provider_var.get(), [])
        self.model_combo["values"] = models
        if models and self.model_var.get() not in models:
            self.model_var.set(models[0])

    def _load_default_prompt(self) -> None:
        self.system_prompt_text.delete("1.0", tk.END)
        self.system_prompt_text.insert("1.0", DEFAULT_SYSTEM_PROMPT)
        self._append_log("Loaded default system prompt.")

    def _clear_prompt(self) -> None:
        self.system_prompt_text.delete("1.0", tk.END)
        self._append_log("Cleared system prompt.")

    def _save_settings(self) -> None:
        payload = {
            "provider": self.provider_var.get(),
            "model": self.model_var.get(),
            "source_language": self.source_lang_var.get(),
            "target_language": self.target_lang_var.get(),
            "api_keys_by_provider": self.api_keys_by_provider,
            "gemini_thinking_level": self.gemini_thinking_level_var.get(),
            "gemini_temperature": self.gemini_temperature_var.get(),
            "system_prompt": self.system_prompt_text.get("1.0", tk.END).strip(),
        }

        try:
            SETTINGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._append_log(f"Saved settings to {SETTINGS_FILE}")
            self.status_var.set("Settings saved")
        except Exception as exc:
            self._append_log(f"Failed to save settings: {exc}")
            messagebox.showerror(APP_TITLE, f"Failed to save settings:\n{exc}")

    def _load_settings(self) -> None:
        self._load_default_prompt()
        if not SETTINGS_FILE.exists():
            self.exclude_keys = [key.strip() for key in self.exclude_keys_var.get().split(",") if key.strip()]
            self._refresh_key_listboxes()
            self._refresh_api_key_summary()
            return

        try:
            payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.provider_var.set(payload.get("provider", self.provider_var.get()))
            self._update_model_options()
            self.model_var.set(payload.get("model", self.model_var.get()))
            saved_source = payload.get("source_language", self.source_lang_var.get())
            saved_target = payload.get("target_language", self.target_lang_var.get())
            self.source_lang_var.set(saved_source if saved_source in {"auto", "en", "ja", "ko"} else "auto")
            self.target_lang_var.set(saved_target if saved_target in {"en", "ja", "ko"} else "ko")
            saved_thinking = payload.get("gemini_thinking_level", self.gemini_thinking_level_var.get())
            self.gemini_thinking_level_var.set(
                saved_thinking if saved_thinking in {"minimal", "low", "medium", "high"} else "minimal"
            )
            saved_temperature = str(payload.get("gemini_temperature", self.gemini_temperature_var.get()))
            self.gemini_temperature_var.set(saved_temperature)
            loaded_by_provider = payload.get("api_keys_by_provider", {})
            if isinstance(loaded_by_provider, dict):
                self.api_keys_by_provider = {
                    "OpenAI": [k.strip() for k in loaded_by_provider.get("OpenAI", []) if isinstance(k, str) and k.strip()],
                    "Gemini": [k.strip() for k in loaded_by_provider.get("Gemini", []) if isinstance(k, str) and k.strip()],
                }
            else:
                self.api_keys_by_provider = {"OpenAI": [], "Gemini": []}

            # Backward compatibility for older settings formats.
            if not self.api_keys_by_provider["OpenAI"] and not self.api_keys_by_provider["Gemini"]:
                loaded_keys = payload.get("api_keys", [])
                if not loaded_keys:
                    legacy_key = payload.get("api_key", "")
                    loaded_keys = [legacy_key] if legacy_key else []
                self.api_keys_by_provider["OpenAI"] = [
                    k.strip() for k in loaded_keys if isinstance(k, str) and k.strip()
                ]

            self._refresh_api_key_summary()
            self.exclude_keys_var.set("")
            self.exclude_keys = []
            self.translate_keys = []
            self._refresh_key_listboxes()

            prompt = payload.get("system_prompt", "").strip()
            if prompt:
                self.system_prompt_text.delete("1.0", tk.END)
                self.system_prompt_text.insert("1.0", prompt)

            self._append_log(f"Loaded settings from {SETTINGS_FILE}")
            self.status_var.set("Settings loaded")
            self._update_provider_dependent_ui()
        except Exception as exc:
            self._append_log(f"Failed to load settings: {exc}")
            self.status_var.set("Settings load error")


def main() -> None:
    app = TranslatorUI()
    app.mainloop()


if __name__ == "__main__":
    main()

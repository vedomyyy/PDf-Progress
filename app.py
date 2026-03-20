

import tkinter as tk
from tkinter import font as tkfont
import json, os, re

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
POLL_MS = 800

BG         = "#0e0f11"
BG2        = "#1a1b1e"
BG3        = "#252629"
ACCENT     = "#1D9E75"
ACCENT_DIM = "#0F6E56"
WARN       = "#EF9F27"
TEXT       = "#e8e6e0"
TEXT2      = "#9a9790"
TEXT3      = "#5a5855"
BORDER     = "#2e2f33"

# ── Читаем страницу из SumatraPDF через UI Automation ──────────────────────

_uia = None

def _get_uia():
    global _uia
    if _uia is not None:
        return _uia
    try:
        import comtypes.client
        UIA = comtypes.client.GetModule("UIAutomationCore.dll")
        obj = comtypes.client.CreateObject(
            "{ff48dba4-60ef-4201-aa87-54103eef594e}",
            interface=UIA.IUIAutomation)
        _uia = (obj, UIA)
    except Exception:
        _uia = None
    return _uia


def get_sumatra_page():
    """Возвращает (current_page, total_pages) или (None, None)."""
    try:
        import win32gui
        import comtypes

        res = _get_uia()
        if res is None:
            return None, None
        automation, UIA = res

        # Ищем окно SumatraPDF
        hwnd = None
        def cb(h, _):
            nonlocal hwnd
            if win32gui.IsWindowVisible(h) and 'SumatraPDF' in win32gui.GetWindowText(h):
                hwnd = h
                return False
            return True
        win32gui.EnumWindows(cb, None)
        if not hwnd:
            return None, None

        root = automation.ElementFromHandle(hwnd)

        # Ищем Edit-элементы
        cond = automation.CreatePropertyCondition(
            UIA.UIA_ControlTypePropertyId, UIA.UIA_EditControlTypeId)
        found = root.FindAll(UIA.TreeScope_Descendants, cond)

        for i in range(found.Length):
            el = found.GetElement(i)
            name = el.CurrentName or ""
            # Наш элемент: name вида ' / 352' или '/ 352'
            m = re.search(r'/\s*(\d+)', name)
            if not m:
                continue
            total = int(m.group(1))
            # Читаем value — текущая страница
            try:
                vp = el.GetCurrentPattern(UIA.UIA_ValuePatternId)
                vp = vp.QueryInterface(UIA.IUIAutomationValuePattern)
                cur = int(vp.CurrentValue)
                return cur, total
            except Exception:
                continue

    except Exception:
        pass
    return None, None


# ── Настройки ──────────────────────────────────────────────────────────────

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Главное окно ───────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()

        self.title("PDF Progress")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.attributes("-topmost", True)

        x = self.settings.get("win_x", 40)
        y = self.settings.get("win_y", 40)
        self.geometry(f"300x450+{x}+{y}")
        self.bind("<Configure>", self._on_move)

        self._build_ui()
        self._load_values()
        self._update_display()
        self._poll()

    # ── UI ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.f_mono_big  = tkfont.Font(family="Consolas", size=38, weight="bold")
        self.f_mono_med  = tkfont.Font(family="Consolas", size=12)
        self.f_body_bold = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.f_small     = tkfont.Font(family="Segoe UI", size=8)
        self.f_head      = tkfont.Font(family="Segoe UI", size=9, weight="bold")

        # Заголовок
        header = tk.Frame(self, bg=BG2, height=38)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📖  PDF Progress", bg=BG2, fg=TEXT2,
                 font=self.f_head).pack(side="left", padx=14)
        self.pin_btn = tk.Label(header, text="📌", bg=BG2, fg=ACCENT,
                                font=self.f_small, cursor="hand2")
        self.pin_btn.pack(side="right", padx=10)
        self.pin_btn.bind("<Button-1>", self._toggle_pin)
        tk.Label(header, text="поверх окон", bg=BG2, fg=TEXT3,
                 font=self.f_small).pack(side="right")
        header.bind("<ButtonPress-1>", self._drag_start)
        header.bind("<B1-Motion>",     self._drag_move)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Статус авто-определения
        status = tk.Frame(self, bg=BG2, pady=5)
        status.pack(fill="x")
        self.status_dot = tk.Label(status, text="●", bg=BG2, fg=TEXT3,
                                   font=self.f_small)
        self.status_dot.pack(side="left", padx=(14, 4))
        self.status_lbl = tk.Label(status, text="ожидание SumatraPDF...",
                                   bg=BG2, fg=TEXT3, font=self.f_small)
        self.status_lbl.pack(side="left")
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Большой процент
        pct_frame = tk.Frame(self, bg=BG, pady=12)
        pct_frame.pack(fill="x")
        self.pct_label = tk.Label(pct_frame, text="—",
                                   font=self.f_mono_big, bg=BG, fg=TEXT3)
        self.pct_label.pack()
        self.sub_label = tk.Label(pct_frame, text="введи диапазон страниц",
                                   font=self.f_small, bg=BG, fg=TEXT3)
        self.sub_label.pack()

        # Прогресс-бар
        bar_frame = tk.Frame(self, bg=BG, padx=20)
        bar_frame.pack(fill="x")
        bar_labels = tk.Frame(bar_frame, bg=BG)
        bar_labels.pack(fill="x")
        self.bar_from_lbl = tk.Label(bar_labels, text="", font=self.f_small,
                                      bg=BG, fg=TEXT3)
        self.bar_from_lbl.pack(side="left")
        self.bar_to_lbl   = tk.Label(bar_labels, text="", font=self.f_small,
                                      bg=BG, fg=TEXT3)
        self.bar_to_lbl.pack(side="right")
        self.bar_track = tk.Frame(bar_frame, bg=BG3, height=8)
        self.bar_track.pack(fill="x", pady=(2, 0))
        self.bar_track.pack_propagate(False)
        self.bar_fill = tk.Frame(self.bar_track, bg=ACCENT, height=8)
        self.bar_fill.place(x=0, y=0, width=0, height=8)

        # Статистика
        stats = tk.Frame(self, bg=BG, padx=16, pady=10)
        stats.pack(fill="x")
        for col, (lbl, attr) in enumerate([
            ("прочитано", "stat_read"),
            ("осталось",  "stat_left"),
            ("всего",     "stat_total"),
        ]):
            cell = tk.Frame(stats, bg=BG3)
            cell.grid(row=0, column=col, padx=4, ipadx=8, ipady=6, sticky="ew")
            stats.columnconfigure(col, weight=1)
            v = tk.Label(cell, text="—", font=self.f_body_bold, bg=BG3, fg=TEXT)
            v.pack()
            tk.Label(cell, text=lbl, font=self.f_small, bg=BG3, fg=TEXT3).pack()
            setattr(self, attr, v)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", pady=(8, 0))

        # Поля диапазона
        fields = tk.Frame(self, bg=BG, padx=16, pady=12)
        fields.pack(fill="x")

        self.from_var = tk.StringVar()
        self.to_var   = tk.StringVar()

        range_row = tk.Frame(fields, bg=BG)
        range_row.pack(fill="x")
        range_row.columnconfigure(0, weight=1)
        range_row.columnconfigure(1, weight=1)

        for col, (text, var) in enumerate([
            ("С страницы", self.from_var),
            ("По страницу", self.to_var),
        ]):
            cell = tk.Frame(range_row, bg=BG)
            cell.grid(row=0, column=col,
                      padx=(0, 8) if col == 0 else 0, sticky="ew")
            tk.Label(cell, text=text, font=self.f_small,
                     bg=BG, fg=TEXT3).pack(anchor="w")
            e = tk.Entry(cell, textvariable=var, font=self.f_mono_med,
                         bg=BG3, fg=TEXT, insertbackground=TEXT,
                         relief="flat", bd=0,
                         highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=ACCENT, width=7)
            e.pack(fill="x", ipady=5)
            var.trace_add("write", lambda *_: self._on_range_change())

        # Текущая страница (только для чтения — заполняется авто)
        cur_cell = tk.Frame(fields, bg=BG)
        cur_cell.pack(fill="x", pady=(10, 0))
        hdr = tk.Frame(cur_cell, bg=BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Текущая страница", font=self.f_small,
                 bg=BG, fg=TEXT3).pack(side="left")
        self.auto_badge = tk.Label(hdr, text=" АВТО ", font=self.f_small,
                                    bg=BG3, fg=TEXT3)
        self.auto_badge.pack(side="left", padx=(6, 0))

        self.cur_lbl = tk.Label(cur_cell, text="—",
                                 font=self.f_mono_med,
                                 bg=BG3, fg=ACCENT,
                                 anchor="w", padx=10, pady=6)
        self.cur_lbl.pack(fill="x", pady=(4, 0))

    # ── Авто-опрос ─────────────────────────────────────────────────────────

    def _poll(self):
        page, total = get_sumatra_page()
        if page is not None:
            self.cur_lbl.config(text=str(page), fg=ACCENT)
            self.auto_badge.config(bg=ACCENT_DIM, fg=ACCENT)
            self.status_dot.config(fg=ACCENT)
            self.status_lbl.config(text=f"SumatraPDF: стр. {page}", fg=TEXT2)
            # Подставляем total если поле пустое
            if total and not self.to_var.get():
                self.to_var.set(str(total))
            self._cur_page = page
        else:
            self.cur_lbl.config(text="—", fg=TEXT3)
            self.auto_badge.config(bg=BG3, fg=TEXT3)
            self.status_dot.config(fg=TEXT3)
            self.status_lbl.config(text="SumatraPDF не найден", fg=TEXT3)
            self._cur_page = None

        self._update_display()
        self.after(POLL_MS, self._poll)

    # ── Логика ─────────────────────────────────────────────────────────────

    def _on_range_change(self):
        self.settings["from"] = self.from_var.get()
        self.settings["to"]   = self.to_var.get()
        save_settings(self.settings)
        self._update_display()

    def _load_values(self):
        self.from_var.set(str(self.settings.get("from", "")))
        self.to_var.set(str(self.settings.get("to", "")))
        self._cur_page = None

    def _update_display(self):
        try:
            frm = int(self.from_var.get())
            to  = int(self.to_var.get())
            cur = int(self._cur_page or 0)
            assert frm >= 1 and to > frm and cur >= 1
        except Exception:
            self._show_empty()
            return

        total = to - frm + 1
        read  = max(0, min(cur - frm, total))
        left  = max(0, total - read)
        pct   = min(100, round(read / total * 100))
        done  = cur > to
        color = ACCENT if done or pct >= 30 else WARN

        self.pct_label.config(text="100%" if done else f"{pct}%", fg=color)
        self.sub_label.config(
            text="✓ Задание выполнено!" if done else f"стр. {cur}  ·  осталось {left}",
            fg=ACCENT if done else TEXT3)

        self.bar_from_lbl.config(text=f"стр. {frm}")
        self.bar_to_lbl.config(text=f"стр. {to}")
        self.bar_track.update_idletasks()
        w = max(0, int(self.bar_track.winfo_width() * pct / 100))
        self.bar_fill.place(x=0, y=0, width=w, height=8)
        self.bar_fill.config(bg=color)

        self.stat_read.config(text=str(read))
        self.stat_left.config(text=str(left))
        self.stat_total.config(text=str(total))

    def _show_empty(self):
        self.pct_label.config(text="—", fg=TEXT3)
        self.sub_label.config(text="введи диапазон страниц", fg=TEXT3)
        self.bar_fill.place(x=0, y=0, width=0, height=8)
        self.bar_from_lbl.config(text="")
        self.bar_to_lbl.config(text="")
        for a in ("stat_read", "stat_left", "stat_total"):
            getattr(self, a).config(text="—")

    # ── Утилиты ────────────────────────────────────────────────────────────

    def _drag_start(self, e): self._dx, self._dy = e.x, e.y
    def _drag_move(self, e):
        self.geometry(f"+{self.winfo_x()+e.x-self._dx}+{self.winfo_y()+e.y-self._dy}")
    def _on_move(self, e):
        if e.widget is self:
            self.settings.update({"win_x": self.winfo_x(), "win_y": self.winfo_y()})
            save_settings(self.settings)
    def _toggle_pin(self, e=None):
        cur = self.attributes("-topmost")
        self.attributes("-topmost", not cur)
        self.pin_btn.config(fg=ACCENT if not cur else TEXT3)


if __name__ == "__main__":
    app = App()
    app.mainloop()

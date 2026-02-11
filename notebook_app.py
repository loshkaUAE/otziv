#!/usr/bin/env python3
"""HyperNote — красивый офлайн блокнот на Python/Tkinter.

Возможности:
- живой поиск по названию, тексту и тегам;
- автосохранение каждые 1.2 секунды после изменений;
- данные сохраняются в SQLite (notes.db), всё переживает перезапуск;
- минималистичный тёмный интерфейс в духе Hyprland.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from notebook_storage import Note, NoteStorage


class HyperNoteApp:
    AUTOSAVE_DELAY_MS = 1200

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("HyperNote · Beautiful Notebook")
        self.root.geometry("1200x780")
        self.root.minsize(980, 620)

        self.storage = NoteStorage("notes.db")
        self.current_note_id: int | None = None
        self.pending_after_id: str | None = None
        self.current_notes: list[Note] = []

        self._build_style()
        self._build_layout()
        self._load_notes()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_style(self) -> None:
        self.root.configure(bg="#0d1117")
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.style.configure("Root.TFrame", background="#0d1117")
        self.style.configure("Panel.TFrame", background="#111827")
        self.style.configure("Card.TFrame", background="#161b22", relief="flat")

        self.style.configure(
            "Title.TLabel",
            background="#111827",
            foreground="#c9d1d9",
            font=("JetBrains Mono", 12, "bold"),
        )
        self.style.configure(
            "Hint.TLabel",
            background="#111827",
            foreground="#8b949e",
            font=("JetBrains Mono", 10),
        )

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, style="Root.TFrame", padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        left = ttk.Frame(container, style="Panel.TFrame", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.configure(width=350)

        ttk.Label(left, text="🧠 HyperNote", style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Быстрый поиск + вечная память", style="Hint.TLabel").pack(anchor="w")

        search_wrap = ttk.Frame(left, style="Panel.TFrame")
        search_wrap.pack(fill="x", pady=(12, 10))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_wrap,
            textvariable=self.search_var,
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="#58a6ff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#30363d",
            highlightcolor="#58a6ff",
            font=("JetBrains Mono", 11),
        )
        search_entry.pack(fill="x", ipady=7)
        search_entry.bind("<KeyRelease>", lambda _evt: self._load_notes())

        buttons = ttk.Frame(left, style="Panel.TFrame")
        buttons.pack(fill="x", pady=(2, 12))

        tk.Button(
            buttons,
            text="+ Новая",
            command=self.create_note,
            bg="#1f6feb",
            fg="white",
            activebackground="#2f81f7",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=7,
            font=("JetBrains Mono", 10, "bold"),
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            buttons,
            text="Удалить",
            command=self.delete_note,
            bg="#30363d",
            fg="#f0f6fc",
            activebackground="#484f58",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=7,
            font=("JetBrains Mono", 10),
        ).pack(side="left")

        list_card = ttk.Frame(left, style="Card.TFrame", padding=6)
        list_card.pack(fill="both", expand=True)

        self.notes_list = tk.Listbox(
            list_card,
            bg="#161b22",
            fg="#c9d1d9",
            selectbackground="#2f81f7",
            selectforeground="white",
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            font=("JetBrains Mono", 10),
        )
        self.notes_list.pack(fill="both", expand=True)
        self.notes_list.bind("<<ListboxSelect>>", self.on_note_selected)

        right = ttk.Frame(container, style="Card.TFrame", padding=14)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(4, weight=1)

        ttk.Label(right, text="Название", style="Hint.TLabel").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar()
        self.title_entry = tk.Entry(
            right,
            textvariable=self.title_var,
            bg="#0d1117",
            fg="#f0f6fc",
            insertbackground="#58a6ff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#30363d",
            highlightcolor="#58a6ff",
            font=("JetBrains Mono", 13, "bold"),
        )
        self.title_entry.grid(row=1, column=0, sticky="ew", pady=(4, 12), ipady=8)

        ttk.Label(right, text="Теги (через запятую)", style="Hint.TLabel").grid(row=2, column=0, sticky="w")
        self.tags_var = tk.StringVar()
        self.tags_entry = tk.Entry(
            right,
            textvariable=self.tags_var,
            bg="#0d1117",
            fg="#8b949e",
            insertbackground="#58a6ff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#30363d",
            highlightcolor="#58a6ff",
            font=("JetBrains Mono", 10),
        )
        self.tags_entry.grid(row=3, column=0, sticky="ew", pady=(4, 12), ipady=7)

        ttk.Label(right, text="Содержимое", style="Hint.TLabel").grid(row=4, column=0, sticky="nw")

        text_wrap = tk.Frame(right, bg="#0d1117", highlightthickness=1, highlightbackground="#30363d")
        text_wrap.grid(row=5, column=0, sticky="nsew")
        right.rowconfigure(5, weight=1)

        self.content_text = tk.Text(
            text_wrap,
            bg="#0d1117",
            fg="#c9d1d9",
            insertbackground="#58a6ff",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            undo=True,
            font=("JetBrains Mono", 11),
        )
        self.content_text.pack(fill="both", expand=True, padx=8, pady=8)

        status_bar = tk.Label(
            right,
            text="Готово",
            bg="#161b22",
            fg="#8b949e",
            anchor="w",
            font=("JetBrains Mono", 9),
            padx=8,
            pady=5,
        )
        status_bar.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        self.status = status_bar

        self.title_var.trace_add("write", lambda *_: self.queue_autosave())
        self.tags_var.trace_add("write", lambda *_: self.queue_autosave())
        self.content_text.bind("<<Modified>>", self._on_text_modified)

    def _load_notes(self) -> None:
        query = self.search_var.get().strip()
        self.current_notes = list(self.storage.search_notes(query))

        self.notes_list.delete(0, tk.END)
        for note in self.current_notes:
            title = note.title if note.title.strip() else "Без названия"
            preview = note.content.strip().replace("\n", " ")[:42]
            tag_mark = f"  #{note.tags}" if note.tags.strip() else ""
            line = f"{title} — {preview}{tag_mark}"
            self.notes_list.insert(tk.END, line)

        if not self.current_notes:
            self.clear_editor()
            return

        if self.current_note_id is None:
            self.select_note_by_id(self.current_notes[0].note_id)
            return

        for idx, note in enumerate(self.current_notes):
            if note.note_id == self.current_note_id:
                self.notes_list.selection_clear(0, tk.END)
                self.notes_list.selection_set(idx)
                self.notes_list.activate(idx)
                return

        self.select_note_by_id(self.current_notes[0].note_id)

    def select_note_by_id(self, note_id: int) -> None:
        for idx, note in enumerate(self.current_notes):
            if note.note_id == note_id:
                self.notes_list.selection_clear(0, tk.END)
                self.notes_list.selection_set(idx)
                self.notes_list.activate(idx)
                self.open_note(note)
                return

    def on_note_selected(self, _event: tk.Event) -> None:
        selection = self.notes_list.curselection()
        if not selection:
            return
        idx = int(selection[0])
        if idx >= len(self.current_notes):
            return
        self.open_note(self.current_notes[idx])

    def open_note(self, note: Note) -> None:
        self.current_note_id = note.note_id
        self.title_var.set(note.title)
        self.tags_var.set(note.tags)

        self.content_text.delete("1.0", tk.END)
        self.content_text.insert("1.0", note.content)
        self.content_text.edit_modified(False)
        self.set_status(f"Открыта заметка #{note.note_id}. Последнее обновление: {note.updated_at}")

    def create_note(self) -> None:
        note_id = self.storage.create_note()
        self.current_note_id = note_id
        self._load_notes()
        self.select_note_by_id(note_id)
        self.title_entry.focus_set()
        self.set_status("Создана новая заметка")

    def delete_note(self) -> None:
        if self.current_note_id is None:
            return

        answer = messagebox.askyesno("Удаление", "Точно удалить заметку? Это действие нельзя отменить.")
        if not answer:
            return

        deleted_id = self.current_note_id
        self.storage.delete_note(deleted_id)
        self.current_note_id = None
        self._load_notes()

        if self.current_notes:
            self.select_note_by_id(self.current_notes[0].note_id)
        else:
            self.clear_editor()

        self.set_status(f"Заметка #{deleted_id} удалена")

    def clear_editor(self) -> None:
        self.current_note_id = None
        self.title_var.set("")
        self.tags_var.set("")
        self.content_text.delete("1.0", tk.END)
        self.content_text.edit_modified(False)
        self.set_status("Заметок пока нет. Нажми «+ Новая»")

    def _on_text_modified(self, _event: tk.Event) -> None:
        if self.content_text.edit_modified():
            self.content_text.edit_modified(False)
            self.queue_autosave()

    def queue_autosave(self) -> None:
        if self.current_note_id is None:
            return

        if self.pending_after_id is not None:
            self.root.after_cancel(self.pending_after_id)

        self.pending_after_id = self.root.after(self.AUTOSAVE_DELAY_MS, self.autosave_now)
        self.set_status("Черновик… автосохранение")

    def autosave_now(self) -> None:
        self.pending_after_id = None

        if self.current_note_id is None:
            return

        title = self.title_var.get()
        tags = self.tags_var.get()
        content = self.content_text.get("1.0", tk.END).rstrip()

        self.storage.update_note(self.current_note_id, title, content, tags)
        self._load_notes()
        self.select_note_by_id(self.current_note_id)
        self.set_status("Сохранено ✅")

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def on_close(self) -> None:
        if self.pending_after_id is not None:
            self.root.after_cancel(self.pending_after_id)
        self.autosave_now()
        self.storage.close()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = HyperNoteApp(root)
    if not app.current_notes:
        app.create_note()
    root.mainloop()


if __name__ == "__main__":
    main()

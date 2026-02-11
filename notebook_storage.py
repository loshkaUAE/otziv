"""Хранилище для локального блокнота на SQLite."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass
class Note:
    """Доменная модель заметки."""

    note_id: int
    title: str
    content: str
    tags: str
    created_at: str
    updated_at: str


class NoteStorage:
    """Простое SQLite-хранилище с поддержкой поиска."""

    def __init__(self, db_path: str | Path = "notes.db") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def create_note(self, title: str = "Новая заметка", content: str = "", tags: str = "") -> int:
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.conn.execute(
            """
            INSERT INTO notes (title, content, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title.strip() or "Новая заметка", content, tags, now, now),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def update_note(self, note_id: int, title: str, content: str, tags: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """
            UPDATE notes
            SET title = ?, content = ?, tags = ?, updated_at = ?
            WHERE note_id = ?
            """,
            (title.strip() or "Без названия", content, tags, now, note_id),
        )
        self.conn.commit()

    def delete_note(self, note_id: int) -> None:
        self.conn.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
        self.conn.commit()

    def get_note(self, note_id: int) -> Note | None:
        row = self.conn.execute("SELECT * FROM notes WHERE note_id = ?", (note_id,)).fetchone()
        return self._to_note(row) if row else None

    def list_notes(self) -> Iterable[Note]:
        rows = self.conn.execute(
            "SELECT * FROM notes ORDER BY datetime(updated_at) DESC, note_id DESC"
        ).fetchall()
        return [self._to_note(row) for row in rows]

    def search_notes(self, query: str) -> Iterable[Note]:
        query = query.strip()
        if not query:
            return self.list_notes()

        pattern = f"%{query}%"
        rows = self.conn.execute(
            """
            SELECT * FROM notes
            WHERE title LIKE ? COLLATE NOCASE
               OR content LIKE ? COLLATE NOCASE
               OR tags LIKE ? COLLATE NOCASE
            ORDER BY datetime(updated_at) DESC, note_id DESC
            """,
            (pattern, pattern, pattern),
        ).fetchall()
        return [self._to_note(row) for row in rows]

    @staticmethod
    def _to_note(row: sqlite3.Row) -> Note:
        return Note(
            note_id=row["note_id"],
            title=row["title"],
            content=row["content"],
            tags=row["tags"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def close(self) -> None:
        self.conn.close()

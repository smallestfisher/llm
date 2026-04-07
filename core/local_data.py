import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import chainlit.data as cl_data
from chainlit.types import PaginatedResponse, Pagination, ThreadFilter
from chainlit.user import PersistedUser, User


class LocalSQLiteDataLayer(cl_data.BaseDataLayer):
    def __init__(self, db_path: str = "chainlit_ui.db"):
        self.db_path = db_path
        self._init_db()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _exec(self, query: str, params: tuple = ()):
        with self._connect() as conn:
            cur = conn.execute(query, params)
            return cur.fetchall()

    def _execute(self, query: str, params: tuple = ()) -> None:
        with self._connect() as conn:
            conn.execute(query, params)
            conn.commit()

    def _ensure_column(self, table: str, column: str, col_def: str) -> None:
        with self._connect() as conn:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                conn.commit()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "identifier TEXT PRIMARY KEY, "
                "metadata TEXT, "
                "created_at TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS threads ("
                "id TEXT PRIMARY KEY, "
                "user_id TEXT, "
                "created_at TEXT, "
                "name TEXT, "
                "metadata TEXT, "
                "tags TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS steps ("
                "id TEXT PRIMARY KEY, "
                "thread_id TEXT, "
                "created_at TEXT, "
                "raw TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS elements ("
                "id TEXT PRIMARY KEY, "
                "thread_id TEXT, "
                "created_at TEXT, "
                "raw TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS feedbacks ("
                "id TEXT PRIMARY KEY, "
                "step_id TEXT, "
                "raw TEXT"
                ")"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_thread ON steps(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_elements_thread ON elements(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_step ON feedbacks(step_id)")
            conn.commit()

        # Ensure columns exist for older DBs
        self._ensure_column("users", "created_at", "TEXT")
        self._ensure_column("threads", "metadata", "TEXT")
        self._ensure_column("threads", "tags", "TEXT")

    def _json_dumps(self, obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=True)

    def _json_loads(self, raw: Optional[str]) -> Any:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        rows = await asyncio.to_thread(
            self._exec, "SELECT * FROM users WHERE identifier = ?", (identifier,)
        )
        if not rows:
            return None
        row = rows[0]
        created_at = row["created_at"] or self._now_iso()
        metadata = self._json_loads(row["metadata"]) or {}
        return PersistedUser(
            id=row["identifier"],
            identifier=row["identifier"],
            metadata=metadata,
            createdAt=created_at,
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        now = self._now_iso()
        await asyncio.to_thread(
            self._execute,
            "INSERT OR REPLACE INTO users (identifier, metadata, created_at) VALUES (?, ?, ?)",
            (user.identifier, self._json_dumps(user.metadata), now),
        )
        return PersistedUser(
            id=user.identifier,
            identifier=user.identifier,
            metadata=user.metadata,
            createdAt=now,
        )

    async def delete_feedback(self, feedback_id: str) -> bool:
        await asyncio.to_thread(
            self._execute, "DELETE FROM feedbacks WHERE id = ?", (feedback_id,)
        )
        return True

    async def upsert_feedback(self, feedback: Any) -> str:
        feedback_id = getattr(feedback, "id", None) or str(uuid.uuid4())
        step_id = getattr(feedback, "forId", None)
        await asyncio.to_thread(
            self._execute,
            "INSERT OR REPLACE INTO feedbacks (id, step_id, raw) VALUES (?, ?, ?)",
            (feedback_id, step_id, self._json_dumps(feedback)),
        )
        return feedback_id

    async def create_element(self, element: Any):
        element_dict = getattr(element, "model_dump", None)
        if callable(element_dict):
            element_dict = element_dict()
        else:
            element_dict = getattr(element, "dict", lambda: None)() or element.__dict__
        element_id = element_dict.get("id") or str(uuid.uuid4())
        thread_id = element_dict.get("threadId")
        created_at = self._now_iso()
        element_dict["id"] = element_id
        await asyncio.to_thread(
            self._execute,
            "INSERT OR REPLACE INTO elements (id, thread_id, created_at, raw) VALUES (?, ?, ?, ?)",
            (element_id, thread_id, created_at, self._json_dumps(element_dict)),
        )

    async def get_element(self, thread_id: str, element_id: str) -> Optional[Dict]:
        rows = await asyncio.to_thread(
            self._exec,
            "SELECT raw FROM elements WHERE id = ? AND thread_id = ?",
            (element_id, thread_id),
        )
        if not rows:
            return None
        return self._json_loads(rows[0]["raw"]) or None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        if thread_id:
            await asyncio.to_thread(
                self._execute,
                "DELETE FROM elements WHERE id = ? AND thread_id = ?",
                (element_id, thread_id),
            )
        else:
            await asyncio.to_thread(
                self._execute, "DELETE FROM elements WHERE id = ?", (element_id,)
            )

    async def create_step(self, step_dict: Dict):
        step_id = step_dict.get("id") or str(uuid.uuid4())
        thread_id = step_dict.get("threadId")
        created_at = step_dict.get("createdAt") or self._now_iso()
        step_dict["id"] = step_id
        step_dict["createdAt"] = created_at
        await asyncio.to_thread(
            self._execute,
            "INSERT OR REPLACE INTO steps (id, thread_id, created_at, raw) VALUES (?, ?, ?, ?)",
            (step_id, thread_id, created_at, self._json_dumps(step_dict)),
        )

    async def update_step(self, step_dict: Dict):
        step_id = step_dict.get("id")
        if not step_id:
            return
        created_at = step_dict.get("createdAt")
        if not created_at:
            rows = await asyncio.to_thread(
                self._exec, "SELECT created_at FROM steps WHERE id = ?", (step_id,)
            )
            created_at = rows[0]["created_at"] if rows else self._now_iso()
            step_dict["createdAt"] = created_at
        await asyncio.to_thread(
            self._execute,
            "UPDATE steps SET raw = ?, created_at = ? WHERE id = ?",
            (self._json_dumps(step_dict), created_at, step_id),
        )

    async def delete_step(self, step_id: str):
        await asyncio.to_thread(
            self._execute, "DELETE FROM feedbacks WHERE step_id = ?", (step_id,)
        )
        await asyncio.to_thread(
            self._execute, "DELETE FROM steps WHERE id = ?", (step_id,)
        )

    async def get_thread_author(self, thread_id: str) -> str:
        rows = await asyncio.to_thread(
            self._exec, "SELECT user_id FROM threads WHERE id = ?", (thread_id,)
        )
        return rows[0]["user_id"] if rows else ""

    async def delete_thread(self, thread_id: str):
        await asyncio.to_thread(
            self._execute,
            "DELETE FROM feedbacks WHERE step_id IN (SELECT id FROM steps WHERE thread_id = ?)",
            (thread_id,),
        )
        await asyncio.to_thread(
            self._execute, "DELETE FROM elements WHERE thread_id = ?", (thread_id,)
        )
        await asyncio.to_thread(
            self._execute, "DELETE FROM steps WHERE thread_id = ?", (thread_id,)
        )
        await asyncio.to_thread(
            self._execute, "DELETE FROM threads WHERE id = ?", (thread_id,)
        )

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse:
        limit = pagination.first
        params: List[Any] = []
        where = []
        if filters.userId:
            where.append("user_id = ?")
            params.append(filters.userId)
        if filters.search:
            where.append("name LIKE ?")
            params.append(f"%{filters.search}%")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        rows = await asyncio.to_thread(
            self._exec,
            f"SELECT * FROM threads {where_sql} ORDER BY created_at DESC LIMIT ?",
            tuple(params + [limit]),
        )

        threads = []
        for row in rows:
            threads.append(
                {
                    "id": row["id"],
                    "createdAt": row["created_at"],
                    "name": row["name"],
                    "userId": row["user_id"],
                    "userIdentifier": row["user_id"],
                    "tags": self._json_loads(row["tags"]) or [],
                    "metadata": self._json_loads(row["metadata"]) or {},
                    "steps": [],
                    "elements": [],
                }
            )

        return PaginatedResponse(
            data=threads,
            pageInfo={"hasNextPage": False, "startCursor": None, "endCursor": None},
        )

    async def get_thread(self, thread_id: str) -> Optional[Dict]:
        thread_rows = await asyncio.to_thread(
            self._exec, "SELECT * FROM threads WHERE id = ?", (thread_id,)
        )
        if not thread_rows:
            return None
        thread = thread_rows[0]

        step_rows = await asyncio.to_thread(
            self._exec,
            "SELECT raw FROM steps WHERE thread_id = ? ORDER BY created_at ASC",
            (thread_id,),
        )
        steps = [self._json_loads(r["raw"]) for r in step_rows]
        steps = [s for s in steps if s]

        element_rows = await asyncio.to_thread(
            self._exec,
            "SELECT raw FROM elements WHERE thread_id = ? ORDER BY created_at ASC",
            (thread_id,),
        )
        elements = [self._json_loads(r["raw"]) for r in element_rows]
        elements = [e for e in elements if e]

        user_id = thread["user_id"]
        return {
            "id": thread["id"],
            "createdAt": thread["created_at"],
            "name": thread["name"],
            "userId": user_id,
            "userIdentifier": user_id,
            "tags": self._json_loads(thread["tags"]) or [],
            "metadata": self._json_loads(thread["metadata"]) or {},
            "steps": steps,
            "elements": elements,
        }

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        rows = await asyncio.to_thread(
            self._exec, "SELECT * FROM threads WHERE id = ?", (thread_id,)
        )
        if not rows:
            await asyncio.to_thread(
                self._execute,
                "INSERT INTO threads (id, user_id, created_at, name, metadata, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    user_id,
                    self._now_iso(),
                    name or "新对话",
                    self._json_dumps(metadata or {}),
                    self._json_dumps(tags or []),
                ),
            )
            return

        updates = []
        params: List[Any] = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if user_id is not None:
            updates.append("user_id = ?")
            params.append(user_id)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(self._json_dumps(metadata))
        if tags is not None:
            updates.append("tags = ?")
            params.append(self._json_dumps(tags))
        if not updates:
            return
        params.append(thread_id)
        await asyncio.to_thread(
            self._execute,
            f"UPDATE threads SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        return None

    async def get_favorite_steps(self, user_id: str) -> List[Dict]:
        rows = await asyncio.to_thread(
            self._exec,
            "SELECT s.raw FROM steps s JOIN threads t ON s.thread_id = t.id WHERE t.user_id = ?",
            (user_id,),
        )
        favorites: List[Dict] = []
        for row in rows:
            step = self._json_loads(row["raw"]) or {}
            metadata = step.get("metadata") or {}
            if metadata.get("favorite") is True:
                favorites.append(step)
        return favorites

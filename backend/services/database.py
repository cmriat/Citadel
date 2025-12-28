"""
数据库服务

使用SQLite存储任务数据，提供CRUD操作。
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import threading

from backend.models.task import Task, TaskStatus, TaskType


class DatabaseService:
    """SQLite数据库服务"""

    def __init__(self, db_path: str = "backend/data/tasks.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    @contextmanager
    def _cursor(self):
        """获取游标的上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """初始化数据库表"""
        with self._cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    config TEXT NOT NULL,
                    progress TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    result TEXT
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)
            ''')

    def _serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化datetime为ISO格式字符串"""
        return dt.isoformat() if dt else None

    def _deserialize_datetime(self, s: Optional[str]) -> Optional[datetime]:
        """反序列化ISO格式字符串为datetime"""
        return datetime.fromisoformat(s) if s else None

    def _task_to_row(self, task: Task) -> Dict[str, Any]:
        """将Task对象转换为数据库行"""
        return {
            'id': task.id,
            'type': task.type,
            'status': task.status,
            'config': json.dumps(task.config),
            'progress': json.dumps(task.progress.model_dump()),
            'created_at': self._serialize_datetime(task.created_at),
            'started_at': self._serialize_datetime(task.started_at),
            'finished_at': self._serialize_datetime(task.finished_at),
            'result': json.dumps(task.result.model_dump()) if task.result else None
        }

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        """将数据库行转换为Task对象"""
        from backend.models.task import TaskProgress, TaskResult

        data = {
            'id': row['id'],
            'type': row['type'],
            'status': row['status'],
            'config': json.loads(row['config']),
            'progress': json.loads(row['progress']),
            'created_at': self._deserialize_datetime(row['created_at']),
            'started_at': self._deserialize_datetime(row['started_at']),
            'finished_at': self._deserialize_datetime(row['finished_at']),
            'result': json.loads(row['result']) if row['result'] else None
        }
        return Task.model_validate(data)

    # ========================================================================
    # CRUD 操作
    # ========================================================================

    def create(self, task: Task) -> Task:
        """创建任务"""
        row = self._task_to_row(task)
        with self._cursor() as cursor:
            cursor.execute('''
                INSERT INTO tasks (id, type, status, config, progress, created_at, started_at, finished_at, result)
                VALUES (:id, :type, :status, :config, :progress, :created_at, :started_at, :finished_at, :result)
            ''', row)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        with self._cursor() as cursor:
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            row = cursor.fetchone()
            return self._row_to_task(row) if row else None

    def update(self, task: Task) -> Task:
        """更新任务"""
        row = self._task_to_row(task)
        with self._cursor() as cursor:
            cursor.execute('''
                UPDATE tasks SET
                    status = :status,
                    config = :config,
                    progress = :progress,
                    started_at = :started_at,
                    finished_at = :finished_at,
                    result = :result
                WHERE id = :id
            ''', row)
        return task

    def delete(self, task_id: str) -> bool:
        """删除任务"""
        with self._cursor() as cursor:
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            return cursor.rowcount > 0

    def list_all(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """列出任务"""
        query = 'SELECT * FROM tasks WHERE 1=1'
        params: List[Any] = []

        if status:
            query += ' AND status = ?'
            params.append(status.value if isinstance(status, TaskStatus) else status)

        if task_type:
            query += ' AND type = ?'
            params.append(task_type.value if isinstance(task_type, TaskType) else task_type)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_task(row) for row in rows]

    def count(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None
    ) -> int:
        """统计任务数量"""
        query = 'SELECT COUNT(*) FROM tasks WHERE 1=1'
        params: List[Any] = []

        if status:
            query += ' AND status = ?'
            params.append(status.value if isinstance(status, TaskStatus) else status)

        if task_type:
            query += ' AND type = ?'
            params.append(task_type.value if isinstance(task_type, TaskType) else task_type)

        with self._cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()[0]

    def get_running_tasks(self) -> List[Task]:
        """获取所有运行中的任务"""
        return self.list_all(status=TaskStatus.RUNNING)

    def cleanup_old_tasks(self, days: int = 30) -> int:
        """清理超过指定天数的已完成任务"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = self._serialize_datetime(cutoff)

        with self._cursor() as cursor:
            cursor.execute('''
                DELETE FROM tasks
                WHERE status IN (?, ?, ?)
                AND finished_at < ?
            ''', (
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
                cutoff_str
            ))
            return cursor.rowcount


# 全局数据库服务实例
_db_service: Optional[DatabaseService] = None


def get_database() -> DatabaseService:
    """获取数据库服务单例"""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service

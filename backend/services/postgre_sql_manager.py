try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import execute_values
except Exception:  # pragma: no cover
    # 在部分测试/CI 环境里可能不安装 psycopg2；dry-run 逻辑不依赖它。
    psycopg2 = None
    sql = None
    execute_values = None

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple, Union

import importlib

from backend.config import settings

try:
    pd = importlib.import_module("pandas")
except Exception:  # pragma: no cover
    # 测试/静态分析环境可能没有 pandas；仅在用到 DataFrame 功能时才会报错。
    pd = None


QCType = Literal["validity", "manual"]


@dataclass(frozen=True)
class DryRunStatement:
    """用于 dry-run：只返回 SQL 与参数，不执行。"""

    query: str
    params: Union[Tuple[Any, ...], Dict[str, Any], None] = None
    description: str = ""


class PostgreSqlManager:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize the database connection
        """
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is not installed; PostgreSqlManager cannot connect to Postgres"
            )

        # 延迟到运行时从 env/settings 读取，避免模块导入阶段因常量未定义导致 NameError。
        host = host or settings.POSTGRES_HOST
        port = int(port or settings.POSTGRES_PORT)
        database = database or settings.POSTGRES_DB
        user = user or settings.POSTGRES_USER
        password = password or settings.POSTGRES_PASSWORD

        if not user or not password:
            raise ValueError(
                "Missing Postgres credentials. Set POSTGRES_USER/POSTGRES_PASSWORD in .env"
            )

        try:
            self.conn = psycopg2.connect(
                host=host, port=port, database=database, user=user, password=password
            )
            self.cursor = self.conn.cursor()
            print("Success to connect to the database.")
        except Exception as e:
            print("Fail to connect to the database:", e)
            raise

    def execute(self, query, params=None):
        """
        Run the SQL query
        """
        try:
            self.cursor.execute(query, params)
            affected = int(getattr(self.cursor, "rowcount", 0) or 0)
            self.conn.commit()
            return affected
        except Exception as e:
            self.conn.rollback()
            # 让调用方感知失败（路由层会转换为 HTTPException/detail 给前端展示）。
            raise

    # ==========================
    # QC / dwd_episode helpers
    # ==========================

    @staticmethod
    def normalize_collect_date(collect_date: str) -> str:
        """将 collect_date 统一为数据库格式 yyyy-mm-dd。

        支持输入：
        - yyyymmdd（来自路径，如 20260210）
        - yyyy-mm-dd（数据库存储格式）
        """

        s = (collect_date or "").strip()
        if re.fullmatch(r"\d{8}", s):
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return s
        raise ValueError(f"Invalid collect_date: {collect_date!r}")

    @staticmethod
    def parse_episode_index(episode_name_or_index: Union[str, int]) -> int:
        """从 episode 名称（如 episode_0001）或数字中解析 episode_index。

        规则：去除前导 0（通过 int() 自然实现）。
        """

        if isinstance(episode_name_or_index, int):
            return episode_name_or_index

        s = (episode_name_or_index or "").strip()
        m = re.fullmatch(r"episode_(\d+)", s)
        if m:
            return int(m.group(1))
        if re.fullmatch(r"\d+", s):
            return int(s)
        raise ValueError(f"Invalid episode_name/index: {episode_name_or_index!r}")

    @staticmethod
    def resolve_dataset_root_from_base_dir(base_dir: Union[str, Path]) -> Path:
        """兼容前端 QC base_dir 传入 lerobot 目录的情况。

        - 若 base_dir 形如 */lerobot，则 dataset_root = base_dir.parent
        - 否则认为 base_dir 本身就是 dataset_root
        """

        p = Path(str(base_dir)).expanduser()
        try:
            p = p.resolve(strict=False)
        except Exception:
            p = p.absolute()

        if p.name == "lerobot":
            return p.parent
        return p

    @staticmethod
    def parse_pfs_lerobot_dataset_root(
        dataset_root: Union[str, Path],
    ) -> Dict[str, str]:
        """从本地数据路径解析出 device_id / collect_date / task_name。

        期望路径格式：
        /pfs/data/collect_data/v2/prod/lerobot_data/{device_id}/{device_id}_{yyyymmdd}/{task_name}/

        返回：
        - device_id
        - collect_date（yyyy-mm-dd）
        - task_name

        注意：如果你的数据不在上述路径规范下，请在调用侧显式传入 device_id/collect_date/task_name。
        """

        root = Path(str(dataset_root))
        parts = list(root.parts)
        if len(parts) < 3:
            raise ValueError(f"Invalid dataset_root: {str(dataset_root)!r}")

        task_name = root.name
        device_day = root.parent.name
        device_id = root.parent.parent.name

        # device_day 期望是 {device_id}_{yyyymmdd}
        m = re.fullmatch(re.escape(device_id) + r"_(\d{8})", device_day)
        if not m:
            raise ValueError(
                "dataset_root does not match expected layout: "
                f"device_id={device_id!r}, device_day={device_day!r}, root={str(root)!r}"
            )

        collect_date = PostgreSqlManager.normalize_collect_date(m.group(1))
        return {
            "device_id": device_id,
            "collect_date": collect_date,
            "task_name": task_name,
        }

    @staticmethod
    def build_dwd_episode_uuid_name(
        *,
        device_id: str,
        collect_date: str,
        task_name: str,
        episode_index: int,
        generated_from: str = "format_conversion",
        data_format: str = "lerobot",
    ) -> str:
        """构造 dwd_episode 的 UUID v5 name 字符串。

        必须 1:1 对齐 create_table_dwd_episode.py 的 uuid_generate_name：
        '/' || device_id || '/' || collect_date || '/' || generated_from || '/' || data_format || '/' || task_name || '/' || episode_index
        """

        cd = PostgreSqlManager.normalize_collect_date(collect_date)
        ep = int(episode_index)
        return f"/{device_id}/{cd}/{generated_from}/{data_format}/{task_name}/{ep}"

    @staticmethod
    def compute_dwd_episode_id(
        *,
        device_id: str,
        collect_date: str,
        task_name: str,
        episode_index: int,
        generated_from: str = "format_conversion",
        data_format: str = "lerobot",
        namespace_uuid: str = "00000000-0000-0000-0000-000000000000",
    ) -> str:
        """按 Postgres uuid_generate_v5 规则在客户端计算 dwd_episode.id。

        说明：绝大多数数据库 server_encoding 为 UTF8，此处使用 Python uuid.uuid5(UTF-8) 可对齐。
        """

        ns = uuid.UUID(namespace_uuid)
        name_text = PostgreSqlManager.build_dwd_episode_uuid_name(
            device_id=device_id,
            collect_date=collect_date,
            task_name=task_name,
            episode_index=episode_index,
            generated_from=generated_from,
            data_format=data_format,
        )
        return str(uuid.uuid5(ns, name_text))

    @staticmethod
    def build_select_dwd_episode_id_query(
        *,
        device_id: str,
        collect_date: str,
        task_name: str,
        episode_index: int,
        generated_from: str = "format_conversion",
        data_format: str = "lerobot",
    ) -> DryRunStatement:
        """构造按字段查询 dwd_episode.id 的 SQL（用于需要 DB 校验时）。"""

        query = (
            "SELECT id FROM dwd_episode "
            "WHERE device_id = %s AND collect_date = %s AND generated_from = %s "
            "AND data_format = %s AND task_name = %s AND episode_index = %s "
            "LIMIT 1;"
        )
        params = (
            device_id,
            PostgreSqlManager.normalize_collect_date(collect_date),
            generated_from,
            data_format,
            task_name,
            int(episode_index),
        )
        return DryRunStatement(
            query=query, params=params, description="select dwd_episode.id"
        )

    def fetch_dwd_episode_id(
        self,
        *,
        device_id: str,
        collect_date: str,
        task_name: str,
        episode_index: int,
        generated_from: str = "format_conversion",
        data_format: str = "lerobot",
    ) -> Optional[str]:
        """真实查询数据库以定位 dwd_episode.id；找不到返回 None。"""

        stmt = self.build_select_dwd_episode_id_query(
            device_id=device_id,
            collect_date=collect_date,
            task_name=task_name,
            episode_index=episode_index,
            generated_from=generated_from,
            data_format=data_format,
        )
        rows = self.fetch_data(stmt.query, stmt.params)
        if not rows:
            return None
        return str(rows[0][0])

    @staticmethod
    def build_update_dwd_episode_qc_query(
        *,
        episode_id: str,
        qc_type: QCType,
        passed: bool,
    ) -> DryRunStatement:
        """构造按主键更新 QC 字段的 SQL。

        - 人工质检：quality_problem_manual=1 表示有问题（不通过），0 表示无问题（通过）
        - 有效性校验：is_valid=1 表示通过，0 表示不通过
        """

        if qc_type == "manual":
            col = "quality_problem_manual"
            value = 0 if passed else 1
        elif qc_type == "validity":
            col = "is_valid"
            value = 1 if passed else 0
        else:
            raise ValueError(f"Invalid qc_type: {qc_type!r}")

        query = f"UPDATE dwd_episode SET {col} = %s WHERE id = %s;"
        params = (value, episode_id)
        return DryRunStatement(
            query=query,
            params=params,
            description=f"update dwd_episode.{col} by id",
        )

    def update_dwd_episode_qc_by_id(
        self,
        *,
        episode_id: str,
        qc_type: QCType,
        passed: bool,
        dry_run: bool = False,
    ) -> Union[DryRunStatement, None]:
        """更新 dwd_episode QC 字段；dry_run 时仅返回 SQL。"""

        stmt = self.build_update_dwd_episode_qc_query(
            episode_id=episode_id, qc_type=qc_type, passed=passed
        )
        if dry_run:
            return stmt
        self.execute(stmt.query, stmt.params)
        return None

    @staticmethod
    def build_qc_sync_statements(
        *,
        base_dir: Union[str, Path],
        passed_episodes: Sequence[str],
        failed_episodes: Sequence[str],
        qc_type: QCType,
        device_id: Optional[str] = None,
        collect_date: Optional[str] = None,
        task_name: Optional[str] = None,
        generated_from: str = "format_conversion",
        data_format: str = "lerobot",
        prefer_compute_id: bool = True,
    ) -> List[DryRunStatement]:
        """将 QC 结果转换为对 dwd_episode 的更新语句列表（默认仅靠规则计算 id）。

        - base_dir：前端传入的 lerobot 目录或 dataset_root
        - prefer_compute_id=True：优先按 UUID 规则计算 episode_id（不依赖 DB 查询）
        """

        dataset_root = PostgreSqlManager.resolve_dataset_root_from_base_dir(base_dir)

        if device_id is None or collect_date is None or task_name is None:
            parsed = PostgreSqlManager.parse_pfs_lerobot_dataset_root(dataset_root)
            device_id = device_id or parsed["device_id"]
            collect_date = collect_date or parsed["collect_date"]
            task_name = task_name or parsed["task_name"]

        assert device_id is not None
        assert collect_date is not None
        assert task_name is not None

        # 统一去重：以 failed 为准覆盖 passed（避免重复/冲突）
        passed_set = set(passed_episodes or [])
        failed_set = set(failed_episodes or [])
        passed_set -= failed_set

        def _episode_id(ep_name: str) -> str:
            ep_idx = PostgreSqlManager.parse_episode_index(ep_name)
            if prefer_compute_id:
                return PostgreSqlManager.compute_dwd_episode_id(
                    device_id=device_id,
                    collect_date=collect_date,
                    task_name=task_name,
                    episode_index=ep_idx,
                    generated_from=generated_from,
                    data_format=data_format,
                )
            # 若不计算 id，则先构造 SELECT 语句（调用侧可选择执行查询）
            return ""

        stmts: List[DryRunStatement] = []

        if not prefer_compute_id:
            # 返回两步：先查 id，再按 id 更新；调用侧可执行查询再拼 update。
            for ep_name in sorted(passed_set | failed_set):
                ep_idx = PostgreSqlManager.parse_episode_index(ep_name)
                stmts.append(
                    PostgreSqlManager.build_select_dwd_episode_id_query(
                        device_id=device_id,
                        collect_date=collect_date,
                        task_name=task_name,
                        episode_index=ep_idx,
                        generated_from=generated_from,
                        data_format=data_format,
                    )
                )
            return stmts

        for ep_name in sorted(passed_set):
            episode_id = _episode_id(ep_name)
            stmts.append(
                PostgreSqlManager.build_update_dwd_episode_qc_query(
                    episode_id=episode_id, qc_type=qc_type, passed=True
                )
            )
        for ep_name in sorted(failed_set):
            episode_id = _episode_id(ep_name)
            stmts.append(
                PostgreSqlManager.build_update_dwd_episode_qc_query(
                    episode_id=episode_id, qc_type=qc_type, passed=False
                )
            )
        return stmts

    def create_table(self, table_name, columns):
        """
        Create a table
        :param table_name: table name
        :param columns: column definition, for example, "id SERIAL PRIMARY KEY, name VARCHAR(50), age INT"
        """
        query = sql.SQL("CREATE TABLE IF NOT EXISTS {table} ({fields})").format(
            table=sql.Identifier(table_name), fields=sql.SQL(columns)
        )
        self.execute(query)

    def create_table_with_time(self, table_name: str, table_columns: str):
        """
        Create table with c_time, u_time and description
        :param table_name: table name
        :param table_columns: column definition, e.g., 'id SERIAL PRIMARY KEY, name TEXT'
        """
        try:
            # Create table (Add c_time, u_time and description automatically)
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {table_columns},
                c_time BIGINT NOT NULL DEFAULT (extract(epoch from now()) * 1000)::BIGINT,
                u_time BIGINT NOT NULL DEFAULT (extract(epoch from clock_timestamp()) * 1000)::BIGINT,
                description TEXT
            );
            """
            self.cursor.execute(create_sql)

            # Create the trigger function (only create once)
            func_sql = """
            CREATE OR REPLACE FUNCTION update_u_time()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.u_time := (extract(epoch from clock_timestamp()) * 1000)::BIGINT;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
            self.cursor.execute(func_sql)

            # Bind the trigger function (ensure uniqueness and do not create the trigger repeatedly)
            trigger_sql = f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger WHERE tgname = 'set_update_time_{table_name}'
                ) THEN
                    CREATE TRIGGER set_update_time_{table_name}
                    BEFORE UPDATE ON {table_name}
                    FOR EACH ROW
                    EXECUTE FUNCTION update_u_time();
                END IF;
            END;
            $$;
            """
            self.cursor.execute(trigger_sql)

            self.conn.commit()
            print(
                f"Success to create table {table_name} (with c_time, u_time and description)"
            )
        except Exception as e:
            self.conn.rollback()
            print(f"Fail to create table: {e}")

    def create_table_with_time_and_uuid(
        self,
        table_name: str,
        table_columns: str,
        uuid_generate_name: str = "NEW.device_id || NEW.collect_date",
    ):
        """
        Must have id column in table_columns!
        """
        # add uuid-ossp
        self.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

        # create table
        self.create_table_with_time(table_name=table_name, table_columns=table_columns)

        # Create the trigger function for generating UUID v5
        func_sql = f"""
        CREATE OR REPLACE FUNCTION {table_name}_set_uuid()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.id IS NULL THEN
                NEW.id := uuid_generate_v5(
                    '00000000-0000-0000-0000-000000000000',
                    {uuid_generate_name}
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
        self.execute(func_sql)

        # Bind the trigger
        trigger_sql = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgname = '{table_name}_uuid_trigger'
            ) THEN
                CREATE TRIGGER {table_name}_uuid_trigger
                BEFORE INSERT ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION {table_name}_set_uuid();
            END IF;
        END;
        $$;
        """
        self.execute(trigger_sql)

        print(
            f"Success to create table {table_name} with uuid, c_time, u_time and description."
        )

        return

    def insert_many(self, table_name, columns, values_list):
        """
        Batch insertion of data
        :param table_name: table name
        :param columns: column list, for example, ["name", "age"]
        :param values_list: value list, for example, [["Alice", 25], ["Bob", 30]]
        """
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))
        query = sql.SQL(
            "INSERT INTO {table} ({fields}) VALUES ({placeholders})"
        ).format(
            table=sql.Identifier(table_name),
            fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
            placeholders=placeholders,
        )
        try:
            self.cursor.executemany(query.as_string(self.conn), values_list)
            self.conn.commit()
            print(f"Success to insert {len(values_list)} rows")
        except Exception as e:
            self.conn.rollback()
            print("Fail to insert:", e)

    def insert_df(self, table_name: str, df: Any):
        """
        batch insertion of DataFrame
        :param table_name: table name
        :param df: pandas DataFrame
        """
        try:
            if df.empty:
                print("DataFrame is empty!")
                return

            cols = ",".join(
                [f'"{col}"' for col in df.columns]
            )  # avoid column name conflict
            values = [tuple(x) for x in df.to_numpy()]
            sql = f"INSERT INTO {table_name} ({cols}) VALUES %s"

            execute_values(self.cursor, sql, values)
            self.conn.commit()
            print(f"Success to insert {len(values)} rows to table {table_name}")

        except Exception as e:
            self.conn.rollback()
            print(f"Fail to insert dataframe: {e}")

        return

    def fetch_data(self, query, params=None):
        """
        Query a table
        """
        try:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            return rows
        except Exception as e:
            print("Fail to query:", e)
            return []

    def close(self):
        """
        Close the connection
        """
        self.cursor.close()
        self.conn.close()
        print("Success to close the connection of the database.")

    def get_table_name(self):
        """
        Get the name of all the tables
        """
        try:
            self.cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in self.cursor.fetchall()]
            print("Existing tables:", tables)
            return tables
        except Exception as e:
            print("Fail to get the table name:", e)
            return []

    def fetch_df(self, query, params=None):
        """
        run SQL query and return pandas DataFrame
        """
        try:
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()
            desc = self.cursor.description or []
            colnames = [d[0] for d in desc]  # get column names
            if pd is None:
                raise ImportError("pandas is required for fetch_df()")
            return pd.DataFrame(rows, columns=colnames)
        except Exception as e:
            print("Fail to query:", e)
            if pd is None:
                return []
            return pd.DataFrame()

    def describe_table(self, table_name):
        """
        Describe variables of a table
        """
        my_query = """
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_name = '{0}'
            ORDER BY ordinal_position;
        """.format(table_name)

        df = self.fetch_df(query=my_query)

        return df

    def grant_select_privilege(self, user, table, schema="public"):
        my_query = f'GRANT SELECT ON TABLE "{schema}"."{table}" TO "{user}";'
        self.execute(query=my_query)
        return

    def batch_update(self, table_name: str, df: Any, key_columns: list):
        """
        Batch update of table
        :param table_name: table name
        :param df: pandas DataFrame, must include key columns
        :param key_columns: primary keys, can be multiple columns
        """
        try:
            if df.empty:
                print("Empty dataFrame, no data to be updated.")
                return

            # get columns to be updated
            cols = [col for col in df.columns if col not in key_columns]
            set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in cols])

            # concatenate key_columns
            conflict_cols = ", ".join(key_columns)

            sql = f"""
            INSERT INTO {table_name} ({",".join(df.columns)})
            VALUES %s
            ON CONFLICT ({conflict_cols}) DO UPDATE
            SET {set_clause};
            """

            values = [tuple(x) for x in df.to_numpy()]
            execute_values(self.cursor, sql, values)
            self.conn.commit()
            print(f"Success to batch update {len(values)} rows of table {table_name}")
        except Exception as e:
            self.conn.rollback()
            print(f"Fail to batch update: {e}")

    def get_primary_keys(self, table_name: str):
        """
        get the primary key of a table
        :param table_name: table name
        :return: the list of primary keys
        """
        try:
            sql = """
            SELECT a.attname AS column_name
            FROM pg_index i
            JOIN pg_attribute a 
              ON a.attrelid = i.indrelid 
             AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass
              AND i.indisprimary;
            """
            self.cursor.execute(sql, (table_name,))
            keys = [row[0] for row in self.cursor.fetchall()]
            print(f"The primary key of table {table_name}: {keys}")
            return keys
        except Exception as e:
            print(f"Fail to get primary keys: {e}")
            return []


if __name__ == "__main__":
    db = PostgreSqlManager()

    # get the name of all the tables
    table_name_list = db.get_table_name()
    # print('table_name_list:', end=' ')
    # print(table_name_list)

    # # query table
    # table_name = 'ods_collect_data_upload_record'
    # my_query = f'SELECT * FROM {table_name}'
    # print('my_query:', my_query)

    # df = db.fetch_df(query=my_query)
    # print(df)

    # # describe table
    # table_name = 'ods_collect_data_upload_record'
    # df = db.describe_table(table_name=table_name)

    # print(df)

    # # grant select privilege to sundong (the public account)
    # table_name = 'ods_collect_data_device_day'
    # db.grant_select_privilege(user='sundong', table=table_name)

    # # batch update
    # table_name = 'ods_collect_data_upload_record'
    # my_query = f'SELECT * FROM {table_name}'
    # print('my_query:', my_query)

    # df = db.fetch_df(query=my_query)

    # df = df[df['collect_date'] == '2025-09-23']
    # df = df[['device_id', 'collect_date', 'is_uploaded']]
    # df['is_uploaded'] = df.apply(lambda x: 2, axis=1)

    # with pd.option_context('display.max_columns', None):
    #     print(df)

    # db.batch_update(table_name=table_name, df=df, key_columns=['device_id', 'collect_date'])

    # table_name = 'ods_collect_data_upload_record'
    # df = db.describe_table(table_name=table_name)
    # print(df)

    # table_name = 'ods_collect_data_upload_record'
    # db.get_primary_keys(table_name=table_name)

    db.close()

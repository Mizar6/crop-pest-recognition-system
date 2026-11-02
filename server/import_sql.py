"""导入建库 SQL。"""
from pathlib import Path

import pymysql

SQL_FILE = Path(__file__).resolve().parent / "sql" / "db_plant_diseases.sql"


def main():
    """读取 SQL 文件并在 MySQL 3308 上执行。"""
    sql = SQL_FILE.read_text(encoding="utf-8")
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3308,
        user="root",
        password="123456",
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        cursor = conn.cursor()
        # 按分号拆分但保留存储过程以外的普通语句
        statements = []
        buf = []
        for line in sql.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            buf.append(line)
            if stripped.endswith(";"):
                statements.append("\n".join(buf))
                buf = []
        for stmt in statements:
            cursor.execute(stmt)
        print(f"导入完成，共执行 {len(statements)} 条语句")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
双色球历史统计工具 —— 数据层
SQLite 本地数据库：存储全部历史开奖记录，程序运行不依赖网络。
"""
import os
import sqlite3
import csv
import re


def default_data_dir():
    """数据目录：优先 EXE 旁 data 目录，其次源码 data 目录。"""
    exe_dir = os.path.dirname(os.path.abspath(sys_executable_path()))
    data_dir = os.path.join(exe_dir, "data")
    if not os.path.isdir(data_dir):
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    if not os.path.isdir(data_dir):
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.normpath(data_dir)


def sys_executable_path():
    import sys
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(__file__)


class DrawDB:
    """双色球开奖记录数据库。"""

    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.join(default_data_dir(), "ssq.db")
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ssq_draws (
                issue  TEXT PRIMARY KEY,
                date   TEXT,
                week   TEXT,
                red1   INTEGER NOT NULL,
                red2   INTEGER NOT NULL,
                red3   INTEGER NOT NULL,
                red4   INTEGER NOT NULL,
                red5   INTEGER NOT NULL,
                red6   INTEGER NOT NULL,
                blue   INTEGER NOT NULL,
                sales  INTEGER DEFAULT 0,
                pool   INTEGER DEFAULT 0
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ssq_date ON ssq_draws(date)")
        self._conn.commit()

    # ---------- 写入 ----------
    def insert_draw(self, issue, date, week, reds, blue, sales=0, pool=0, replace=True):
        if len(reds) != 6:
            raise ValueError("红球必须是6个")
        r = sorted(int(x) for x in reds)
        if not all(1 <= x <= 33 for x in r):
            raise ValueError("红球范围 1-33")
        if not (1 <= int(blue) <= 16):
            raise ValueError("蓝球范围 1-16")
        cur = self._conn.cursor()
        if replace:
            cur.execute(
                """INSERT OR REPLACE INTO ssq_draws
                   (issue,date,week,red1,red2,red3,red4,red5,red6,blue,sales,pool)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (str(issue), date, week, r[0], r[1], r[2], r[3], r[4], r[5],
                 int(blue), int(sales or 0), int(pool or 0)),
            )
        else:
            cur.execute(
                "SELECT issue FROM ssq_draws WHERE issue=?", (str(issue),)
            )
            if cur.fetchone() is None:
                cur.execute(
                    """INSERT INTO ssq_draws
                       (issue,date,week,red1,red2,red3,red4,red5,red6,blue,sales,pool)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(issue), date, week, r[0], r[1], r[2], r[3], r[4], r[5],
                     int(blue), int(sales or 0), int(pool or 0)),
                )
        self._conn.commit()

    def insert_many(self, rows, replace=True):
        """rows: iterable of dict(issue,date,week,reds,blue,sales,pool)"""
        for row in rows:
            self.insert_draw(
                row["issue"], row.get("date", ""), row.get("week", ""),
                row["reds"], row["blue"], row.get("sales", 0), row.get("pool", 0),
                replace=replace,
            )

    # ---------- 查询 ----------
    def count(self):
        cur = self._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ssq_draws")
        return cur.fetchone()[0]

    def latest_issue(self):
        cur = self._conn.cursor()
        cur.execute("SELECT issue FROM ssq_draws ORDER BY issue DESC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None

    def first_issue(self):
        cur = self._conn.cursor()
        cur.execute("SELECT issue FROM ssq_draws ORDER BY issue ASC LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None

    def get_all(self, order="asc"):
        cur = self._conn.cursor()
        cur.execute(
            f"SELECT * FROM ssq_draws ORDER BY issue {('ASC' if order == 'asc' else 'DESC')}"
        )
        return [self._row_to_draw(r) for r in cur.fetchall()]

    def get_latest_n(self, n):
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM ssq_draws ORDER BY issue DESC LIMIT ?", (n,))
        rows = [self._row_to_draw(r) for r in cur.fetchall()]
        rows.reverse()
        return rows

    def get_by_issue(self, issue):
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM ssq_draws WHERE issue=?", (str(issue),))
        row = cur.fetchone()
        return self._row_to_draw(row) if row else None

    def delete_issue(self, issue):
        cur = self._conn.cursor()
        cur.execute("DELETE FROM ssq_draws WHERE issue=?", (str(issue),))
        self._conn.commit()
        return cur.rowcount

    def red_sequences(self):
        """返回按期号升序的红球号码列表。"""
        return [d["reds"] for d in self.get_all("asc")]

    def blue_sequences(self):
        return [d["blue"] for d in self.get_all("asc")]

    @staticmethod
    def _row_to_draw(row):
        return {
            "issue": row["issue"],
            "date": row["date"],
            "week": row["week"],
            "reds": [row["red1"], row["red2"], row["red3"],
                     row["red4"], row["red5"], row["red6"]],
            "blue": row["blue"],
            "sales": row["sales"],
            "pool": row["pool"],
        }

    # ---------- 导入导出 ----------
    def import_csv(self, csv_path):
        """CSV 列：issue,date,red1..red6,blue；可选 week,sales,pool。
        缺列或值非法时抛 ValueError，由界面层提示，不崩溃。"""
        imported = 0
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                missing = [c for c in
                           ("issue", "red1", "red2", "red3", "red4", "red5",
                            "red6", "blue") if c not in row]
                if missing:
                    raise ValueError(
                        f"缺少列: {', '.join(missing)}（第 {imported + 1} 行起）")
                issue = row["issue"].strip()
                reds = [int(row[f"red{i}"]) for i in range(1, 7)]
                blue = int(row["blue"])
                self.insert_draw(
                    issue, row.get("date", "").strip(), row.get("week", "").strip(),
                    reds, blue, row.get("sales", 0), row.get("pool", 0),
                )
                imported += 1
        return imported

    def import_text(self, text):
        """从粘贴文本导入。支持两种格式：
        1) 每行：期号 日期 红1 红2 红3 红4 红5 红6 蓝
        2) 每行：期号,日期,红1,...,红6,蓝
        """
        imported = 0
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("期号"):
                continue
            parts = re.split(r"[\s,，;；]+", line)
            parts = [p for p in parts if p]
            if len(parts) < 9:
                continue
            issue = parts[0]
            date = parts[1]
            reds = [int(parts[i]) for i in range(2, 8)]
            blue = int(parts[8])
            try:
                self.insert_draw(issue, date, "", reds, blue)
                imported += 1
            except ValueError:
                continue
        return imported

    def export_csv(self, csv_path):
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["issue", "date", "week", "red1", "red2", "red3",
                             "red4", "red5", "red6", "blue", "sales", "pool"])
            for d in self.get_all("asc"):
                writer.writerow([
                    d["issue"], d["date"], d["week"], *d["reds"], d["blue"],
                    d["sales"], d["pool"],
                ])

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

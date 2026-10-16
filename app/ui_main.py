# -*- coding: utf-8 -*-
"""
双色球智能选号系统 —— 桌面界面（PySide6）
标签页：选号 / 历史数据 / 统计参考 / 回测 / 数据管理
"""
import os
import sys
import csv
import json
import random
import subprocess
import tempfile

from PySide6.QtCore import Qt, QThread, QObject, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QProgressBar, QGroupBox, QFrame, QSpinBox,
    QCheckBox, QMessageBox, QFileDialog, QSplitter, QScrollArea, QSizePolicy,
)

from db import DrawDB, default_data_dir
from engine import SelectionEngine, RANDOM_BASE_RED, RANDOM_BASE_BLUE
from backtest import Backtest
from data_fetch import fetch_all, fetch_page

APP_TITLE = "双色球智能选号系统 V1.4.0"
APP_VERSION = "1.4.0"
APP_BUILD = "2026-10-09"
RED_HEX = "#e13c3c"
BLUE_HEX = "#1e6fd9"


# ============================================================
# 通用小组件
# ============================================================

class BallLabel(QLabel):
    """号码球。"""

    def __init__(self, num, color, size=34, parent=None):
        super().__init__(parent)
        self.num = num
        self.color = color
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background:{color};color:white;border-radius:{size//2}px;"
            f"font-size:{size//2}px;font-weight:bold;"
        )
        self.setText(f"{num:02d}" if isinstance(num, int) else str(num))


class ResultRow(QFrame):
    """一组结果：6 红球 + 1 蓝球 + 来源。"""

    def __init__(self, title, reds, blue, source, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(6)
        t = QLabel(title)
        t.setFixedWidth(52)
        t.setStyleSheet("font-weight:bold;font-size:14px;color:#333;")
        lay.addWidget(t)
        for r in reds:
            lay.addWidget(BallLabel(r, RED_HEX))
        if isinstance(blue, (list, tuple)):
            for b in blue:
                lay.addWidget(BallLabel(b, BLUE_HEX))
        else:
            lay.addWidget(BallLabel(blue, BLUE_HEX))
        src = QLabel(source)
        src.setStyleSheet("color:#888;font-size:12px;")
        src.setWordWrap(True)
        lay.addWidget(src, 1)


# ============================================================
# 后台任务
# ============================================================

class BacktestWorker(QObject):
    """滚动回测后台任务：分块子进程执行。
    本机安全软件对 Python 密集计算存在稳定性限制（实测约 40-60 秒），
    因此全量回测切成小块，每个块由独立子进程执行，结果合并，失败自动重试。"""
    progress = Signal(int, int)
    finished = Signal(dict)

    def __init__(self, db_path, window, max_rounds):
        super().__init__()
        self.db_path = db_path
        self.window = window
        self.max_rounds = max_rounds

    def run(self):
        try:
            db = DrawDB(self.db_path)
            n = db.count()
            db.close()
            start = min(self.window, n)
            rounds = n - start
            if rounds <= 0:
                self.finished.emit({"回测期数": 0, "窗口": self.window,
                                    "随机基准红球": RANDOM_BASE_RED,
                                    "随机基准蓝球": RANDOM_BASE_BLUE * 100,
                                    "大底命中分布": {}, "大底平均命中": 0,
                                    "结果1": None, "结果2": None, "结果3": None,
                                    "结果4": None, "结果5": None, "结果6": None})
                return
            if self.max_rounds and self.max_rounds > 0:
                rounds = min(rounds, self.max_rounds)
            begin = n - rounds

            BLOCK = 100  # 每块期数（实测安全上限约 200 期，100 期最稳）
            blocks_raw = []
            t = begin
            idx = 0
            while t < n:
                t_end = min(t + BLOCK, n)
                out_json = os.path.join(tempfile.gettempdir(),
                                        f"bt_{os.getpid()}_{idx}.json")
                # EXE 模式：sys.executable 即程序本身；源码模式需带上 main.py 入口
                if getattr(sys, "frozen", False):
                    base = [sys.executable]
                else:
                    base = [sys.executable,
                            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "main.py")]
                cmd = base + ["--bt-block",
                       "--start", str(t), "--end", str(t_end),
                       "--window", str(self.window), "--sample", "1500",
                       "--db-path", self.db_path, "--out-json", out_json]
                ok = False
                last_code = -1
                for _attempt in range(2):  # 单块失败自动重试一次
                    try:
                        p = subprocess.run(cmd, capture_output=True,
                                           timeout=1800)
                        last_code = p.returncode
                    except Exception:
                        last_code = -1
                    if last_code == 0 and os.path.exists(out_json):
                        with open(out_json, encoding="utf-8") as f:
                            blocks_raw.append(json.load(f))
                        ok = True
                        break
                    if os.path.exists(out_json):
                        os.remove(out_json)
                if not ok:
                    self.finished.emit(
                        {"error": f"回测块 {t}-{t_end} 执行失败（子进程退出码 {last_code}）"})
                    return
                os.path.exists(out_json) and os.remove(out_json)
                idx += 1
                self.progress.emit(min(t_end - begin, rounds), rounds)
                t = t_end
            res = Backtest.merge_blocks(blocks_raw, self.window)
            self.finished.emit(res)
        except Exception as e:
            self.finished.emit({"error": str(e)})


class FetchWorker(QObject):
    """联网拉取全量数据后台任务。"""
    progress = Signal(str)
    finished = Signal(dict)

    def __init__(self, db_path, force):
        super().__init__()
        self.db_path = db_path
        self.force = force

    def run(self):
        try:
            db = DrawDB(self.db_path)
            existing = db.count()
            already = set()
            if existing and not self.force:
                for d in db.get_all():
                    already.add(d["issue"])
            db.close()
            self.progress.emit(f"开始拉取（本地已有 {existing} 期）…")
            rows = fetch_all(
                already_issues=already,
                progress_cb=lambda n, issue: self.progress.emit(f"已拉取 {n} 期，最新到 {issue}"),
            )
            if rows:
                db = DrawDB(self.db_path)
                db.insert_many(rows)
                total = db.count()
                latest = db.latest_issue()
                db.close()
                self.finished.emit({"新增": len(rows), "总计": total, "最新": latest})
            else:
                # 无新增：数据库已是最新，不再操作已关闭的连接
                self.finished.emit({"新增": 0, "总计": existing, "最新": ""})
        except Exception as e:
            self.finished.emit({"error": str(e)})


# ============================================================
# 回测图表（自绘）
# ============================================================

class HitChart(QWidget):
    """大底命中分布柱状图 + 随机基准线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dist = {}      # {命中数: 期数}
        self.base = 1.09    # 随机基准红球期望
        self.avg = 0.0
        self.setMinimumHeight(220)

    def set_data(self, dist, base, avg):
        self.dist = dist
        self.base = base
        self.avg = avg
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#ffffff"))
        if not self.dist:
            p.setPen(QColor("#999"))
            p.drawText(self.rect(), Qt.AlignCenter, "暂无回测数据")
            return
        keys = sorted(self.dist)
        max_v = max(self.dist.values()) or 1
        n = len(keys)
        margin_l, margin_b, margin_t = 40, 34, 16
        chart_w = w - margin_l - 12
        chart_h = h - margin_b - margin_t
        bw = chart_w / n * 0.62
        gap = chart_w / n
        # 柱
        for i, k in enumerate(keys):
            v = self.dist[k]
            bh = chart_h * v / max_v
            x = margin_l + i * gap + (gap - bw) / 2
            y = margin_t + chart_h - bh
            p.setBrush(QBrush(QColor("#e13c3c" if k >= 3 else "#f6b0b0")))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(int(x), int(y), int(bw), int(bh), 3, 3)
            p.setPen(QColor("#555"))
            p.drawText(int(x) - 6, int(y) - 4, int(bw) + 12, 16,
                       Qt.AlignCenter, str(v))
        # 横轴标签
        p.setPen(QColor("#666"))
        for i, k in enumerate(keys):
            x = margin_l + i * gap + gap / 2
            p.drawText(int(x) - 20, h - 16, 40, 16, Qt.AlignCenter, f"{k}红")
        # 平均命中与随机基准（纵轴为“期数”，命中数期望不可同轴映射，
        # 故不画水平线，用文字标注，数值对照见下方表格）
        p.setPen(QColor("#555"))
        p.drawText(margin_l, margin_t + 6, w - margin_l - 12, 16,
                   Qt.AlignLeft,
                   f"系统平均 {self.avg:.2f} 红 / 随机基准 {self.base:.2f} 红"
                   "（对照见下方表格）")


# ============================================================
# 选号页
# ============================================================

class PickPage(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.exclude_red = set()
        self.exclude_blue = set()
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        top = QHBoxLayout()
        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("color:#1d6fb8;font-weight:bold;")
        top.addWidget(self.lbl_status)
        top.addStretch(1)
        btn_pick = QPushButton("智能选号（重跑引擎）")
        btn_pick.clicked.connect(self.pick)
        top.addWidget(btn_pick)
        btn_random = QPushButton("纯随机 5 注")
        btn_random.clicked.connect(self.pick_random_5)
        top.addWidget(btn_random)
        outer.addLayout(top)

        mid = QHBoxLayout()
        # 红球排除
        red_gb = QGroupBox("排除红球（1-33，勾选后智能选号不使用）")
        red_lay = QGridLayout(red_gb)
        self.red_checks = []
        for i in range(33):
            cb = QCheckBox(f"{i+1:02d}")
            cb.toggled.connect(lambda on, x=i + 1: self._toggle_red(x, on))
            self.red_checks.append(cb)
            red_lay.addWidget(cb, i // 11, i % 11)
        blue_gb = QGroupBox("排除蓝球（1-16）")
        blue_lay = QGridLayout(blue_gb)
        self.blue_checks = []
        for i in range(16):
            cb = QCheckBox(f"{i+1:02d}")
            cb.toggled.connect(lambda on, x=i + 1: self._toggle_blue(x, on))
            self.blue_checks.append(cb)
            blue_lay.addWidget(cb, i // 8, i % 8)
        mid.addWidget(red_gb, 2)
        mid.addWidget(blue_gb, 1)
        outer.addLayout(mid)

        self.results_box = QGroupBox("智能选号结果（6 组）")
        rv = QVBoxLayout(self.results_box)
        self.results_container = QVBoxLayout()
        self.results_container.addStretch(1)
        rv.addLayout(self.results_container)
        outer.addWidget(self.results_box, 1)

        self.pool_lbl = QLabel()
        self.pool_lbl.setWordWrap(True)
        self.pool_lbl.setStyleSheet("color:#555;")
        outer.addWidget(self.pool_lbl)
        self.refresh_status()

    def _toggle_red(self, x, on):
        if on:
            self.exclude_red.add(x)
        else:
            self.exclude_red.discard(x)

    def _toggle_blue(self, x, on):
        if on:
            self.exclude_blue.add(x)
        else:
            self.exclude_blue.discard(x)

    def refresh_status(self):
        n = self.db.count()
        latest = self.db.latest_issue()
        if n:
            self.lbl_status.setText(f"本地数据：{n} 期，最新期号 {latest}（历史统计模式）")
        else:
            self.lbl_status.setText("本地暂无历史数据：当前为纯随机选号，可在“数据管理”页同步")

    def _clear_results(self):
        while self.results_container.count() > 1:
            item = self.results_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def pick(self):
        self._clear_results()
        # 全量历史建模（2003001~最新期，与手机版口径一致）
        rows = self.db.get_all() if self.db.count() else []
        red_seq = [d["reds"] for d in rows]
        blue_seq = [d["blue"] for d in rows]
        # 排除号过滤：引擎直接剔除被排除号码
        eng = SelectionEngine(red_seq, blue_seq, rng=random.Random(),
                              big_pool=18,
                              exclude_red=self.exclude_red,
                              exclude_blue=self.exclude_blue)
        out = eng.run()
        if out.get("error"):
            QMessageBox.warning(self, "提示", out["error"])
            return
        if out["无数据"]:
            for k in range(1, 7):
                g = out["组"][f"结果{k}"]
                self.results_container.addWidget(
                    ResultRow(f"结果{k}", g["红球"], g["蓝球"], g["来源"]))
        else:
            for k in range(1, 7):
                g = out["组"][f"结果{k}"]
                src = g["来源"]
                if self.exclude_red or self.exclude_blue:
                    src += "（已按排除号过滤）"
                self.results_container.addWidget(
                    ResultRow(f"结果{k}", g["红球"], g["蓝球"], src))
            self.pool_lbl.setText(
                "红球大底（投票层前18）：" +
                " ".join(f"{x:02d}" for x in sorted(out["大底"])) +
                f"　|　蓝球候选：{out['蓝球候选']}")
        self.refresh_status()

    def pick_random_5(self):
        self._clear_results()
        pool_r = [x for x in range(1, 34) if x not in self.exclude_red]
        pool_b = [x for x in range(1, 17) if x not in self.exclude_blue]
        for k in range(1, 6):
            reds = sorted(random.sample(pool_r, 6))
            blue = random.choice(pool_b)
            self.results_container.addWidget(
                ResultRow(f"随机{k}", reds, blue, "纯随机（不依赖历史数据）"))


# ============================================================
# 历史数据页
# ============================================================

class HistoryPage(QWidget):
    """历史数据页：支持双击编辑红球/蓝球并保存回数据库（测试用）。"""
    dataChanged = Signal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        info = QHBoxLayout()
        self.lbl_info = QLabel()
        info.addWidget(self.lbl_info)
        info.addStretch(1)
        lay.addLayout(info)

        hint = QLabel(
            "双击“红1~红6/蓝球”单元格可直接修改号码（红球 1-33 互不重复、蓝球 1-16）；"
            "修改后点“保存修改”写回数据库，选号与统计立即按新数据重算。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;font-size:12px;")
        lay.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            ["期号", "开奖日期", "红1", "红2", "红3", "红4", "红5", "红6", "蓝球"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(
            QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        lay.addWidget(self.table, 1)

        btns = QHBoxLayout()
        self.btn_save = QPushButton("保存修改")
        self.btn_save.clicked.connect(self.save_changes)
        self.btn_del = QPushButton("删除选中行")
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_revert = QPushButton("放弃修改")
        self.btn_revert.clicked.connect(self.reload)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_del)
        btns.addWidget(self.btn_revert)
        btns.addStretch(1)
        lay.addLayout(btns)
        self.reload()

    def reload(self):
        n = self.db.count()
        latest = self.db.latest_issue()
        first = self.db.first_issue()
        self.lbl_info.setText(
            f"共 {n} 期　|　范围：{first} ~ {latest}" if n else "暂无历史数据")
        self.table.setRowCount(0)
        draws = self.db.get_all("desc")
        self.table.setRowCount(len(draws))
        for i, d in enumerate(draws):
            vals = [d["issue"], d["date"]] + \
                [f"{x:02d}" for x in d["reds"]] + [f"{d['blue']:02d}"]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                if j >= 2:
                    item.setForeground(QColor(RED_HEX if j < 8 else BLUE_HEX))
                    item.setBackground(QColor("#fff5f5" if j < 8 else "#f0f6ff"))
                if j < 2:  # 期号/日期只读
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, j, item)

    def delete_selected(self):
        rows = sorted({i.row() for i in self.table.selectedItems()})
        if not rows:
            QMessageBox.information(self, "提示",
                                    "请先选中要删除的行（点击行首或任意单元格）。")
            return
        issues = []
        for r in rows:
            it = self.table.item(r, 0)
            if it and it.text().strip():
                issues.append(it.text().strip())
        if not issues:
            return
        shown = "、".join(issues[:5]) + ("…" if len(issues) > 5 else "")
        ok = QMessageBox.question(
            self, "确认删除",
            f"确定删除以下 {len(issues)} 期开奖记录？\n{shown}\n\n"
            "删除后选号与统计立即按新数据重算。", QMessageBox.Yes | QMessageBox.No)
        if ok != QMessageBox.Yes:
            return
        for iss in issues:
            self.db.delete_issue(iss)
        self.reload()
        self.dataChanged.emit()
        QMessageBox.information(self, "已删除",
                                f"已删除 {len(issues)} 期开奖记录。")

    def save_changes(self):
        errors = []
        updated = 0
        for i in range(self.table.rowCount()):
            issue_item = self.table.item(i, 0)
            if issue_item is None:
                continue
            issue = issue_item.text().strip()
            old = self.db.get_by_issue(issue)
            if old is None:
                continue  # 期号不存在（新行不在此保存，新增请用数据管理页）
            # 读红球
            reds = []
            ok = True
            for j in range(2, 8):
                item = self.table.item(i, j)
                txt = item.text().strip() if item else ""
                if not txt.isdigit():
                    errors.append(f"期号 {issue} 红{j-1} 不是数字：{txt!r}")
                    ok = False
                    break
                v = int(txt)
                if not 1 <= v <= 33:
                    errors.append(f"期号 {issue} 红球 {v} 超出 1-33")
                    ok = False
                    break
                reds.append(v)
            if not ok:
                continue
            if len(set(reds)) != 6:
                errors.append(f"期号 {issue} 红球存在重复号码")
                continue
            # 读蓝球
            b_item = self.table.item(i, 8)
            b_txt = b_item.text().strip() if b_item else ""
            if not b_txt.isdigit():
                errors.append(f"期号 {issue} 蓝球不是数字：{b_txt!r}")
                continue
            blue = int(b_txt)
            if not 1 <= blue <= 16:
                errors.append(f"期号 {issue} 蓝球 {blue} 超出 1-16")
                continue
            if old["reds"] == reds and old["blue"] == blue:
                continue  # 无变化
            self.db.insert_draw(issue, old["date"], old["week"], reds, blue,
                                old["sales"], old["pool"], replace=True)
            updated += 1
        if errors:
            QMessageBox.warning(self, "校验失败",
                                "以下行未保存（请修正后重试）：\n" +
                                "\n".join(errors[:20]))
        if updated:
            self.reload()
            self.dataChanged.emit()
            QMessageBox.information(self, "保存成功",
                                    f"已更新 {updated} 期开奖记录，选号与统计已按新数据重算。")
        elif not errors:
            QMessageBox.information(self, "保存", "没有检测到修改。")


# ============================================================
# 统计参考页
# ============================================================

class StatsPage(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        self.lbl = QLabel()
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet("color:#333;font-size:13px;line-height:1.6;")
        lay.addWidget(self.lbl)
        self.refresh()

    def refresh(self):
        n = self.db.count()
        if n == 0:
            self.lbl.setText("暂无历史数据，请先在“数据管理”页同步或导入。")
            return
        rows = self.db.get_all("asc")
        red_seq = [d["reds"] for d in rows]
        blue_seq = [d["blue"] for d in rows]
        from engine import _freq_window, _miss_info, PRIMES
        from collections import Counter
        parts = []
        # 冷热号
        for win in (30, 60, 100):
            f = _freq_window(red_seq, min(win, len(red_seq)))
            hot = sorted(f, key=f.get, reverse=True)[:10]
            cold = sorted(f, key=f.get)[:10]
            parts.append(
                f"【最近 {win} 期】\n冷门（出现最少）：" +
                " ".join(f"{x:02d}" for x in cold) +
                "\n热门（出现最多）：" +
                " ".join(f"{x:02d}" for x in hot))
        # 遗漏
        cur, avg, mx = _miss_info(red_seq)
        top_miss = sorted(range(1, 34), key=lambda x: cur[x], reverse=True)[:10]
        parts.append("【当前遗漏最大 TOP10】" +
                     " ".join(f"{x:02d}({cur[x]}期)" for x in top_miss))
        # 形态分布
        from engine import _morph_stats, _top_forms
        st = _morph_stats(red_seq)
        fv, fc = _top_forms(st["和值"])
        oo, oc = _top_forms(st["奇偶比"])
        bs, bc = _top_forms(st["大小比"])
        parts.append(
            f"【历史最常形态】和值 {fv}（出现 {fc} 期）｜奇偶比 {oo[0]}:{oo[1]}（{oc} 期）"
            f"｜大小比 {bs[0]}:{bs[1]}（{bc} 期）")
        # 蓝球
        bc_cnt = Counter(blue_seq)
        top_b = bc_cnt.most_common(8)
        parts.append("【蓝球冷热 TOP8】" +
                     " ".join(f"{x:02d}({c}次)" for x, c in top_b))
        self.lbl.setText("\n\n".join(parts))


# ============================================================
# 回测页
# ============================================================

class BacktestPage(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.worker_thread = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("建模窗口："))
        self.spin_window = QSpinBox()
        self.spin_window.setRange(50, 300)
        self.spin_window.setValue(100)
        top.addWidget(self.spin_window)
        top.addWidget(QLabel("回测期数："))
        self.spin_rounds = QSpinBox()
        self.spin_rounds.setRange(30, 6000)
        self.spin_rounds.setValue(200)
        top.addWidget(self.spin_rounds)
        self.btn_run = QPushButton("开始滚动回测")
        self.btn_run.clicked.connect(self.run_backtest)
        top.addWidget(self.btn_run)
        top.addStretch(1)
        lay.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.chart = HitChart()
        lay.addWidget(self.chart, 3)

        # 随机基准对照表（5 列指标：程序实测 / 随机基准 / 对比）
        self.cmp_table = QTableWidget(5, 4)
        self.cmp_table.setHorizontalHeaderLabels(
            ["指标", "程序实测", "随机基准", "对比"])
        self.cmp_table.verticalHeader().setVisible(False)
        self.cmp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cmp_table.setSelectionMode(QTableWidget.NoSelection)
        self.cmp_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        rows_meta = [
            ("大底18码平均命中", 0.30),
            ("结果1红球平均命中（注单）", 0.10),
            ("结果2红球平均命中（集合10码）", 0.15),
            ("蓝球命中率（规则型）", 1.5),
            ("蓝球命中率（统计型·集合3码）", 1.5),
        ]
        for i, (name, tol) in enumerate(rows_meta):
            self.cmp_table.setItem(i, 0, QTableWidgetItem(name))
            self.cmp_table.item(i, 0).setData(Qt.UserRole, tol)
        self.cmp_table.setMaximumHeight(180)
        lay.addWidget(self.cmp_table)

        lbl_note = QLabel(
            "口径说明：回测对区块轨道采用 1500 组合抽样近似，与选号页全枚举略有差异；"
            "蓝球双轨：结果1/2 用号码轨道候选（模块38-40），结果3/4 用区块轨道候选（模块41-43），"
            "结果6 为两轨候选并集；命中按集合含中判定；"
            "熵权权重按当期各模块得分区分度计算（非历史回测区分度），属既定方法论口径。")
        lbl_note.setWordWrap(True)
        lbl_note.setStyleSheet("color:#888;font-size:12px;")
        lay.addWidget(lbl_note)

        self.lbl_conclusion = QLabel()
        self.lbl_conclusion.setWordWrap(True)
        self.lbl_conclusion.setStyleSheet(
            "font-size:13px;line-height:1.7;color:#c0392b;"
            "background:#fdf2f2;border:1px solid #e6c3c3;"
            "border-radius:6px;padding:10px 12px;")
        lay.addWidget(self.lbl_conclusion)

        self.lbl_result = QLabel()
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setStyleSheet("color:#333;font-size:13px;line-height:1.7;")
        lay.addWidget(self.lbl_result)

    def run_backtest(self):
        if self.db.count() < 60:
            QMessageBox.information(self, "提示", "历史数据不足 60 期，无法进行有意义的回测。")
            return
        # 回测期数上限 = 全部可用期数（全量回测）
        max_r = max(30, self.db.count() - self.spin_window.value())
        self.spin_rounds.setMaximum(max_r)
        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.lbl_result.setText("回测进行中…（逐期用历史统计建模对下一期评分并比对开奖）")

        self.worker_thread = QThread(self)
        self.worker = BacktestWorker(
            self.db.db_path, self.spin_window.value(), self.spin_rounds.value())
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._on_thread_done)
        self.worker_thread.start()

    def _on_progress(self, done, total):
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _on_finished(self, res):
        if "error" in res:
            self.lbl_result.setText("回测出错：" + res["error"])
            self.btn_run.setEnabled(True)
            return
        n = res["回测期数"]
        if n == 0:
            self.lbl_result.setText("数据不足，无法回测。")
            self.btn_run.setEnabled(True)
            return
        self.chart.set_data(res["大底命中分布"], res["随机基准红球"], res["大底平均命中"])
        lines = []
        lines.append(
            f"回测 {n} 期（窗口 {res['窗口']} 期）　|　"
            f"中奖情况见下方各结果行。")
        # 随机基准对照表
        # 随机基准：大底18码=6*18/33≈3.273；注单6红=6*6/33≈1.091；集合10码=6*10/33≈1.818；
        #          规则蓝球=1/16=6.25%；统计型集合3码蓝球=3/16=18.75%
        base_pool = 6 * 18 / 33.0
        base_r1 = 6 * 6 / 33.0
        base_r2 = 6 * 10 / 33.0
        base_blue = 6.25
        base_blue_set = 3 / 16.0 * 100
        r2_val = None
        if res.get("结果2"):
            r2_val = res["结果2"].get("平均红球命中")
        r2_blue = None
        if res.get("结果2"):
            r2_blue = res["结果2"].get("蓝球命中率")
        vals = [res["大底平均命中"], res["结果1"]["平均红球命中"],
                r2_val, res["结果1"]["蓝球命中率"] * 100,
                (r2_blue * 100) if r2_blue is not None else None]
        bases = [base_pool, base_r1, base_r2, base_blue, base_blue_set]
        for i in range(5):
            v, b = vals[i], bases[i]
            tol = self.cmp_table.item(i, 0).data(Qt.UserRole)
            if v is None:
                self.cmp_table.setItem(i, 1, QTableWidgetItem("—"))
                self.cmp_table.setItem(i, 2, QTableWidgetItem(f"{b:.3f}"))
                self.cmp_table.setItem(i, 3, QTableWidgetItem("—"))
                continue
            unit = "%" if i >= 3 else ""
            d = v - b
            if abs(d) < tol:
                cmp = "≈ 随机基准"
            else:
                cmp = f"{'高于' if d > 0 else '低于'}随机（差 {abs(d):.2f}{unit}）"
            self.cmp_table.setItem(i, 1, QTableWidgetItem(f"{v:.3f}{unit}"))
            self.cmp_table.setItem(i, 2, QTableWidgetItem(f"{b:.3f}{unit}"))
            self.cmp_table.setItem(i, 3, QTableWidgetItem(cmp))
        # 结论（以事实为唯一依据）
        dev = []
        for i in range(5):
            if vals[i] is None:
                continue
            v, b, tol = vals[i], bases[i], self.cmp_table.item(i, 0).data(Qt.UserRole)
            if abs(v - b) >= tol:
                dev.append(self.cmp_table.item(i, 0).text())
        if dev:
            self.lbl_conclusion.setText(
                f"结论：{'、'.join(dev)} 与随机基准存在明显差异，其余指标与随机相当——"
                "统计选号整体不具备稳定预测能力（单次差异属抽样波动）。"
                "每期开奖独立随机，历史统计不含未来信息。")
        else:
            self.lbl_conclusion.setText(
                "结论：以上指标均与随机基准相当——统计选号对双色球无预测能力。"
                "每期开奖独立随机，历史统计不包含未来信息；本程序如实展示验证结果，不虚构中奖提升。")
        # 凯利准则（资金管理章）：按结果1奖级分布估算期望回报
        try:
            prize = (res.get("结果1") or {}).get("奖级分布", {})
            if n and prize:
                # 固定奖金估算：一二等奖为浮动奖，此处按常见区间估算并如实标注
                payout = {0: 0.0, 1: 5000000.0, 2: 100000.0, 3: 3000.0,
                          4: 200.0, 5: 10.0, 6: 5.0}
                ev = sum(payout.get(k, 0.0) * v for k, v in prize.items()) / n
                if ev < 2.0:
                    kelly_txt = (f"期望回报约 {ev:.2f} 元/2 元注（低于注价），"
                                 "简化凯利上限 0 元（不建议投注）")
                else:
                    f_star = (ev - 2.0) / ev if ev > 0 else 0.0
                    kelly_txt = (f"期望回报约 {ev:.2f} 元/2 元注，"
                                 f"简化凯利上限约 {max(f_star, 0.0) * 100:.1f}% 可支配资金")
                lines.append(
                    "资金管理（凯利准则·估算）：" + kelly_txt +
                    "（一二等奖为浮动奖，按固定估算值计算）")
        except Exception:
            pass
        for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6"):
            s = res[k]
            if s is None:
                continue
            prize = s.get("奖级分布", {})
            tag = "（集合10码）" if k in ("结果2", "结果4", "结果6") else ""
            # 蓝球命中率带随机基准对照：单号 6.25%，集合按实际候选码数 n/16
            sz = s.get("蓝球候选码数", 1)
            if sz > 1.0:
                blue_txt = (f"蓝球命中率 {s['蓝球命中率']*100:.1f}%"
                            f"（集合{sz:.0f}码·随机基准 {sz/16*100:.1f}%）")
            else:
                blue_txt = f"蓝球命中率 {s['蓝球命中率']*100:.1f}%（随机基准 6.25%）"
            lines.append(
                f"{k}{tag}：平均命中红球 {s['平均红球命中']:.2f} 个，"
                f"{blue_txt}"
                + (f"，中奖 {sum(prize.values())} 次" if prize else ""))
        self.lbl_result.setText("\n".join(lines))
        self.btn_run.setEnabled(True)

    def _on_thread_done(self):
        self.progress.setVisible(False)
        self.worker_thread = None


# ============================================================
# 数据管理页
# ============================================================

class DataPage(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.worker_thread = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        info = QGroupBox("当前数据状态")
        il = QVBoxLayout(info)
        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size:13px;line-height:1.6;")
        lbl_ver = QLabel(
            f"当前版本：V{APP_VERSION}（固定版，{APP_BUILD}）")
        lbl_ver.setStyleSheet(
            "font-weight:bold;font-size:13px;color:#e13c3c;")
        il.addWidget(lbl_ver)
        il.addWidget(self.lbl_status)
        lay.addWidget(info)

        fetch_gb = QGroupBox("方式一：联网自动同步（需联网一次，之后完全离线）")
        fl = QVBoxLayout(fetch_gb)
        desc = QLabel(
            "从中国福利彩票官网公开接口拉取全部历史开奖记录（2003 年至今），"
            "写入本地数据库。同步完成后程序运行不依赖网络。")
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#555;")
        fl.addWidget(desc)
        btn_row = QHBoxLayout()
        self.btn_fetch = QPushButton("联网同步全部历史")
        self.btn_fetch.clicked.connect(self.fetch_all)
        btn_row.addWidget(self.btn_fetch)
        self.btn_force = QPushButton("强制重新拉取全量")
        self.btn_force.clicked.connect(lambda: self.fetch_all(force=True))
        btn_row.addWidget(self.btn_force)
        btn_row.addStretch(1)
        fl.addLayout(btn_row)
        self.lbl_fetch = QLabel()
        self.lbl_fetch.setStyleSheet("color:#1d6fb8;")
        fl.addWidget(self.lbl_fetch)
        lay.addWidget(fetch_gb)

        manual_gb = QGroupBox("方式二：手动填充（无需网络）")
        ml = QVBoxLayout(manual_gb)
        hint = QLabel(
            "每行一条：期号 日期 红1 红2 红3 红4 红5 红6 蓝\n"
            "示例：2026113 2026-09-29 03 04 20 24 29 30 11\n"
            "也可以先点“导出模板”生成 CSV 填好后再“导入 CSV”。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#555;")
        ml.addWidget(hint)
        self.text_manual = QTextEdit()
        self.text_manual.setPlaceholderText("在此粘贴开奖数据…")
        self.text_manual.setFixedHeight(120)
        ml.addWidget(self.text_manual)
        btn_row2 = QHBoxLayout()
        self.btn_import_text = QPushButton("导入粘贴数据")
        self.btn_import_text.clicked.connect(self.import_text)
        btn_row2.addWidget(self.btn_import_text)
        self.btn_import_csv = QPushButton("导入 CSV")
        self.btn_import_csv.clicked.connect(self.import_csv)
        btn_row2.addWidget(self.btn_import_csv)
        self.btn_export = QPushButton("导出模板 CSV")
        self.btn_export.clicked.connect(self.export_csv)
        btn_row2.addWidget(self.btn_export)
        self.btn_refresh = QPushButton("刷新状态")
        self.btn_refresh.clicked.connect(self.refresh_status)
        btn_row2.addWidget(self.btn_refresh)
        btn_row2.addStretch(1)
        ml.addLayout(btn_row2)
        lay.addWidget(manual_gb)

        lay.addStretch(1)
        self.refresh_status()

    def refresh_status(self):
        n = self.db.count()
        latest = self.db.latest_issue()
        first = self.db.first_issue()
        path = self.db.db_path
        if n:
            self.lbl_status.setText(
                f"本地数据库：{n} 期\n范围：{first} ~ {latest}\n数据文件：{path}")
        else:
            self.lbl_status.setText(
                f"本地数据库：0 期（选号将使用纯随机模式）\n数据文件：{path}")

    def fetch_all(self, force=False):
        self.btn_fetch.setEnabled(False)
        self.btn_force.setEnabled(False)
        self.lbl_fetch.setText("正在联网拉取…")
        self.worker_thread = QThread(self)
        self.worker = FetchWorker(self.db.db_path, force)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.lbl_fetch.setText)
        self.worker.finished.connect(self._on_fetch_done)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._on_fetch_thread_done)
        self.worker_thread.start()

    def _on_fetch_done(self, res):
        if "error" in res:
            self.lbl_fetch.setText("同步失败：" + res["error"])
        else:
            latest_txt = f"，最新 {res['最新']}" if res.get("最新") else "（本地已是最新）"
            self.lbl_fetch.setText(
                f"同步完成：新增 {res['新增']} 期，库内共 {res['总计']} 期{latest_txt}")
            self.refresh_status()
        self.btn_fetch.setEnabled(True)
        self.btn_force.setEnabled(True)

    def _on_fetch_thread_done(self):
        self.worker_thread = None

    def import_text(self):
        text = self.text_manual.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先粘贴数据。")
            return
        n = self.db.import_text(text)
        QMessageBox.information(self, "导入结果", f"成功导入 {n} 条开奖记录。")
        self.refresh_status()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV 文件", "", "CSV (*.csv)")
        if not path:
            return
        try:
            n = self.db.import_csv(path)
        except Exception as e:
            QMessageBox.warning(
                self, "导入失败",
                f"CSV 格式有误：{e}\n请确认包含列：issue,date,red1~red6,blue。")
            return
        QMessageBox.information(self, "导入结果", f"成功导入 {n} 条开奖记录。")
        self.refresh_status()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 CSV", os.path.join(default_data_dir(), "双色球历史数据模板.csv"),
            "CSV (*.csv)")
        if not path:
            return
        if self.db.count() == 0:
            # 空模板
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write("issue,date,red1,red2,red3,red4,red5,red6,blue\n")
        else:
            self.db.export_csv(path)
        QMessageBox.information(self, "导出结果", f"已导出到：\n{path}")


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.db_path = db_path or os.path.join(default_data_dir(), "ssq.db")
        self.db = DrawDB(self.db_path)
        self.setWindowTitle(APP_TITLE)
        self.resize(1150, 760)
        self.setFont(QFont("Microsoft YaHei", 10))

        tabs = QTabWidget()
        self.pick_page = PickPage(self.db)
        self.history_page = HistoryPage(self.db)
        self.stats_page = StatsPage(self.db)
        self.backtest_page = BacktestPage(self.db)
        self.data_page = DataPage(self.db)
        tabs.addTab(self.pick_page, "智能选号")
        tabs.addTab(self.history_page, "历史数据")
        tabs.addTab(self.stats_page, "统计参考")
        tabs.addTab(self.backtest_page, "回测")
        tabs.addTab(self.data_page, "数据管理")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage("就绪")
        # 历史数据修改后联动刷新：选号状态、统计参考、数据管理状态
        self.history_page.dataChanged.connect(self.pick_page.refresh_status)
        self.history_page.dataChanged.connect(self.stats_page.refresh)
        self.history_page.dataChanged.connect(self.data_page.refresh_status)
        # 各页数据变化后联动刷新
        self.data_page.refresh_status()

    def closeEvent(self, event):
        try:
            self.db.close()
        except Exception:
            pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

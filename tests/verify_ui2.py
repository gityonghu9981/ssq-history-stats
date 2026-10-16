# -*- coding: utf-8 -*-
"""修复后 UI 离屏回归：选号页蓝球集合渲染/来源文案、回测页对照表/凯利行、db 缺列防护。"""
import os
import sys

sys.path.insert(0, r"E:\双色球智能选号\app")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt
from db import DrawDB
from ui_main import (MainWindow, BallLabel, ResultRow, BacktestPage, BLUE_HEX)

app = QApplication([])

# ---- 1. 数据页缺列防护（db 层） ----
bad_csv = os.path.join(os.environ["TEMP"], "bad_cols.csv")
with open(bad_csv, "w", encoding="utf-8") as f:
    f.write("issue,date,red1,red2,red3,red4,red5\n")
    f.write("2026001,2026-01-01,1,2,3,4,5,6\n")
db = DrawDB(os.path.join(os.environ["TEMP"], "ui2.db"))
try:
    db.import_csv(bad_csv)
    print("✗ 缺列 CSV 未报错")
except ValueError as e:
    print(f"✓ 缺列 CSV 抛 ValueError: {str(e)[:40]}")
finally:
    db.close()
os.remove(bad_csv)
if os.path.exists(os.path.join(os.environ["TEMP"], "ui2.db")):
    os.remove(os.path.join(os.environ["TEMP"], "ui2.db"))

# ---- 2. 选号页：蓝球集合渲染与来源文案 ----
win = MainWindow(r"E:\双色球智能选号\dist\data\ssq.db")
page = win.pick_page
page.exclude_red = set()
page.exclude_blue = set()
page.pick()
blue_counts = []
for k in range(6):
    w = page.results_container.itemAt(k + 1).widget()
    balls = [c for c in w.findChildren(BallLabel) if c.color == BLUE_HEX]
    blue_counts.append(len(balls))
print(f"✓ 选号页各结果蓝球球数: {blue_counts}（规则型应为1，统计型应为3）")
ok = blue_counts in ([1, 3, 1, 3, 1, 3], [1, 1, 1, 3, 1, 3], [1, 3, 1, 3, 1, 3])
# 统计型（结果2/4/6）应显示 3 个蓝球候选
ok = blue_counts[1] == 3 and blue_counts[3] == 3 and blue_counts[5] == 3
print(f"  统计型蓝球集合渲染: {'✓' if ok else '✗'}")

# ---- 3. 回测页：对照表 4 行 + 凯利行 ----
bt = win.backtest_page
res = {
    "回测期数": 3410, "窗口": 100,
    "大底平均命中": 3.277, "随机基准红球": 3.273, "大底命中分布": {},
    "结果1": {"平均红球命中": 1.094, "蓝球命中率": 0.0622,
              "奖级分布": {"0": 3178, "6": 199, "5": 33}},
    "结果2": {"平均红球命中": 1.840, "蓝球命中率": 0.1865},
    "结果3": {"平均红球命中": 1.092, "蓝球命中率": 0.0622},
    "结果4": {"平均红球命中": 1.791, "蓝球命中率": 0.1865},
    "结果5": {"平均红球命中": 1.096, "蓝球命中率": 0.0622},
    "结果6": {"平均红球命中": 1.838, "蓝球命中率": 0.1865},
}
bt._on_finished(res)
rows_filled = all(bt.cmp_table.item(i, 0) and bt.cmp_table.item(i, 1)
                  for i in range(5))
print(f"  回测对照表 4 行全部填充: {'✓' if rows_filled else '✗'}")
txt = bt.lbl_result.text()
has_kelly = "凯利" in txt
has_note = "口径说明" in " ".join(
    c.text() for c in bt.findChildren(QLabel) if "口径说明" in c.text())
print(f"  凯利建议行存在: {'✓' if has_kelly else '✗'}")
print(f"  口径说明存在: {'✓' if has_note else '✗'}")
concl = bt.lbl_conclusion.text()
print(f"  结论: {concl[:30]}…")

# ---- 4. ResultRow 蓝球集合渲染（直接构造） ----
rr = ResultRow("测试", [1, 2, 3, 4, 5, 6], [2, 4, 5], "统计型测试")
n_blue = len([c for c in rr.findChildren(BallLabel) if c.color == BLUE_HEX])
print(f"  ResultRow 集合蓝球球数: {n_blue}（{'✓' if n_blue == 3 else '✗'}）")

print("\nUI 离屏回归完成")

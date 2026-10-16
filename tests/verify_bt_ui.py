# -*- coding: utf-8 -*-
"""回测页随机基准对照功能验证：真实小回测 + 离屏 UI。"""
import os
import sys
import shutil
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\双色球智能选号\app")

from PySide6.QtWidgets import QApplication
from db import DrawDB
from backtest import Backtest
from ui_main import BacktestPage

SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_bp_test.db")
shutil.copy2(SRC, tmp)

db = DrawDB(tmp)
rows = db.get_all("asc")
red = [r["reds"] for r in rows]
blue = [r["blue"] for r in rows]
print(f"数据: {len(red)} 期")

app = QApplication([])
page = BacktestPage(db)

# 真实回测：窗口 50，回测 30 期（单进程安全区）
res = Backtest(red, blue, window=50, max_rounds=30,
               use_seed=True, block_sample=1500).run()
print(f"回测期数: {res['回测期数']}, 大底平均: {res['大底平均命中']:.3f}")

page._on_finished(res)

# 检查对照表
tbl = page.cmp_table
print("\n对照表:")
for i in range(5):
    name = tbl.item(i, 0).text()
    v = tbl.item(i, 1).text()
    b = tbl.item(i, 2).text()
    c = tbl.item(i, 3).text()
    print(f"  {name}: 实测={v} 随机={b} 对比={c}")
    assert v and b and c, f"第{i}行未填充"

# 检查结论
concl = page.lbl_conclusion.text()
print(f"\n结论: {concl}")
assert concl.startswith("结论："), "结论文字缺失"
assert "随机" in concl and "统计选号" in concl, "结论内容不完整"

# 检查概况行
print(f"\n概况: {page.lbl_result.text().splitlines()[0]}")

db.close()
os.remove(tmp)
print("\n回测页随机基准对照功能验证通过 ✅")

# -*- coding: utf-8 -*-
"""验证"均与随机基准相当"结论分支（全量回测时的形态）。"""
import os
import sys
import shutil
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\双色球智能选号\app")

from PySide6.QtWidgets import QApplication
from db import DrawDB
from ui_main import BacktestPage

SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_bp2.db")
shutil.copy2(SRC, tmp)

db = DrawDB(tmp)
app = QApplication([])
page = BacktestPage(db)

# 构造接近随机基准的全量回测形态数据（V1.2.0 全量实测：大底 3.277/结果1 1.094/结果2 1.840/
# 规则蓝球 6.22%/集合蓝球 18.65%≈3/16）
res = {
    "回测期数": 3410, "窗口": 100,
    "随机基准红球": 1.091, "随机基准蓝球": 6.25,
    "大底命中分布": {0: 5, 1: 60, 2: 350, 3: 1100, 4: 1250, 5: 500, 6: 145},
    "大底平均命中": 3.277,
    "结果1": {"平均红球命中": 1.094, "蓝球命中率": 0.0622, "奖级分布": {0: 3178, 6: 199, 5: 33}},
    "结果2": {"平均红球命中": 1.840, "蓝球命中率": 0.1865, "奖级分布": {}},
    "结果3": {"平均红球命中": 1.092, "蓝球命中率": 0.0622, "奖级分布": {0: 3179, 6: 198, 5: 33}},
    "结果4": {"平均红球命中": 1.791, "蓝球命中率": 0.1865, "奖级分布": {}},
    "结果5": {"平均红球命中": 1.096, "蓝球命中率": 0.0622, "奖级分布": {0: 3178, 6: 200, 5: 32}},
    "结果6": {"平均红球命中": 1.838, "蓝球命中率": 0.1865, "奖级分布": {}},
}
page._on_finished(res)

print("对照表:")
for i in range(5):
    print("  ", " | ".join(page.cmp_table.item(i, c).text() for c in range(4)))

concl = page.lbl_conclusion.text()
print(f"\n结论: {concl}")
assert "均与随机基准相当" in concl, "应走'相当'分支"
assert "无预测能力" in concl, "应含无预测能力结论"
db.close()
os.remove(tmp)
print("\n全量形态'≈随机'结论分支验证通过 ✅")

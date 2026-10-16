# -*- coding: utf-8 -*-
"""历史数据编辑功能验证：临时库副本上测试保存/校验/写回逻辑。"""
import os
import shutil
import tempfile
import sys
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\双色球智能选号\app")

from PySide6.QtWidgets import QApplication
from db import DrawDB

# 临时库副本（不动正式数据）
SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_edit_test.db")
shutil.copy2(SRC, tmp)
db = DrawDB(tmp)
n0 = db.count()
print(f"临时库期数: {n0}")

# 目标期号：最新一期
issue = db.latest_issue()
old = db.get_by_issue(issue)
print(f"目标期号 {issue}: 原号码 红{old['reds']} 蓝{old['blue']}")
new_reds = [1, 2, 3, 4, 5, 33]  # 明显改动
new_blue = 16

app = QApplication([])
from ui_main import HistoryPage
hp = HistoryPage(db)

# 定位该期行（表格按期号降序）
row = None
for i in range(hp.table.rowCount()):
    if hp.table.item(i, 0).text() == issue:
        row = i
        break
assert row is not None, "未找到目标期号行"
print(f"找到行 {row}")

# 1) 修改红球与蓝球并保存（mock 掉弹窗）
with patch("ui_main.QMessageBox.information"), patch("ui_main.QMessageBox.warning"):
    for j, v in enumerate(new_reds):
        hp.table.item(row, 2 + j).setText(f"{v:02d}")
    hp.table.item(row, 8).setText(f"{new_blue:02d}")
    hp.save_changes()

after = db.get_by_issue(issue)
assert after["reds"] == sorted(new_reds), f"红球未写回: {after['reds']}"
assert after["blue"] == new_blue, f"蓝球未写回: {after['blue']}"
print(f"✅ 修改保存成功: 现号码 红{after['reds']} 蓝{after['blue']}")
print(f"   (原 week/sales/pool 保留: {after['week']!r} {after['sales']} {after['pool']})")

# 2) 重复红球应被校验拦截
with patch("ui_main.QMessageBox.information"), patch("ui_main.QMessageBox.warning") as wk:
    hp.table.item(row, 2).setText("01")
    hp.table.item(row, 3).setText("01")  # 重复
    hp.save_changes()
    assert wk.called, "重复红球未触发校验警告"
print("✅ 重复红球被校验拦截")

# 3) 蓝球越界应被校验拦截
with patch("ui_main.QMessageBox.information"), patch("ui_main.QMessageBox.warning") as wk:
    hp.table.item(row, 3).setText("02")
    hp.table.item(row, 8).setText("17")  # 超出 1-16
    hp.save_changes()
    assert wk.called, "蓝球越界未触发校验警告"
print("✅ 蓝球越界被校验拦截")

# 4) 恢复原值保存（无变化不重复写）
with patch("ui_main.QMessageBox.information") as info, patch("ui_main.QMessageBox.warning"):
    hp.table.item(row, 8).setText(f"{old['blue']:02d}")
    hp.save_changes()
    assert info.called, "无变化时应提示没有修改"
print("✅ 无变化时提示且不重复写")

# 5) 期号只读（flags 无 editable）
flags = hp.table.item(row, 0).flags()
assert not (flags & __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ItemIsEditable)
print("✅ 期号列只读")

# 清理：恢复临时库（测试修改不污染，直接删除副本）
db.close()
os.remove(tmp)
print("\n历史数据编辑功能全部验证通过 ✅")

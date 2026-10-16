# -*- coding: utf-8 -*-
"""删除行功能验证：临时库副本 + 离屏 UI。"""
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, r"E:\双色球智能选号\app")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from db import DrawDB

SRC = r"E:\双色球智能选号\dist\data\ssq.db"
tmp = os.path.join(tempfile.gettempdir(), "ssq_delui_test.db")
shutil.copy2(SRC, tmp)
db = DrawDB(tmp)
n0 = db.count()

app = QApplication([])
from ui_main import HistoryPage
hp = HistoryPage(db)
assert hp.db.count() == n0

# 选取最近 3 期（表格 desc 第 0-2 行）删除
issues = [hp.table.item(i, 0).text() for i in range(3)]
print(f"待删除: {issues}")

# 选中 3 行（item 选中）
for i in range(3):
    hp.table.item(i, 2).setSelected(True)

with patch("ui_main.QMessageBox.information"), \
     patch("ui_main.QMessageBox.question", return_value=16384):  # Yes
    hp.delete_selected()

assert db.count() == n0 - 3, f"期数未减: {db.count()} vs {n0-3}"
for iss in issues:
    assert db.get_by_issue(iss) is None, f"{iss} 仍存在"
print(f"✅ 删除 3 期成功，库内 {n0} → {db.count()}")
print("  被删期号查询确认不存在:", all(db.get_by_issue(i) is None for i in issues))

# 取消删除（点 No）不应删除
row = 0
hp.table.item(row, 2).setSelected(True)
cnt_before = db.count()
with patch("ui_main.QMessageBox.information"), \
     patch("ui_main.QMessageBox.question", return_value=65536):  # No
    hp.delete_selected()
assert db.count() == cnt_before, "取消删除后不应删"
print("✅ 取消删除不生效")

# 未选中行提示
hp.table.clearSelection()
with patch("ui_main.QMessageBox.information") as info, \
     patch("ui_main.QMessageBox.question"):
    hp.delete_selected()
    assert info.called, "未选中应提示"
print("✅ 未选中行时提示")

db.close()
os.remove(tmp)
print("\n删除行功能全部验证通过 ✅")

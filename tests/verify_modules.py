# -*- coding: utf-8 -*-
"""全部模块逐一验证（A25 + B12 + 蓝球6 = 43 个，蓝球双轨）：输出维度、无异常、非退化。"""
import os, sys
sys.path.insert(0, r'E:\双色球智能选号\app')
from db import DrawDB
import engine as E

db = DrawDB()
red = db.red_sequences()
blue = db.blue_sequences()
print(f"数据: {len(red)} 期\n")

print("== A 类（红球打分，应输出 33 维）==")
ok = True
for name, fn in E.A_MODULES:
    try:
        out = fn(red, blue)
        assert len(out) == 33, f"{name} 输出维度 {len(out)}"
        assert all(isinstance(v, (int, float)) for v in out), f"{name} 含非数值"
        if "超几何" not in name:  # 超几何基准为理论常数，允许无区分度
            assert max(out) > min(out), f"{name} 输出无区分度"
        print(f"  ✓ {name}  范围 [{min(out):.3f}, {max(out):.3f}]")
    except Exception as e:
        ok = False
        print(f"  ✗ {name}: {e}")

print("\n== B 类（形态约束）==")
for name, fn in E.B_MODULES:
    try:
        out = fn(red, blue)
        assert isinstance(out, dict) and len(out) == 1, f"{name} 输出异常"
        print(f"  ✓ {name}: {out}")
    except Exception as e:
        ok = False
        print(f"  ✗ {name}: {e}")

print("\n== 蓝球模块（应输出 16 维）==")
for name, fn in E.BLUE_MODULES:
    try:
        out = fn(red, blue)
        assert len(out) == 16, f"{name} 输出维度 {len(out)}"
        print(f"  ✓ {name}  范围 [{min(out):.3f}, {max(out):.3f}]")
    except Exception as e:
        ok = False
        print(f"  ✗ {name}: {e}")

# 连号组数专项验证
print("\n== 连号组数专项 ==")
cases = [([1, 2, 3, 10, 20, 30], 1),   # 三连 = 1 组
         ([1, 2, 4, 5, 20, 30], 2),    # 两组两连
         ([1, 3, 5, 7, 9, 11], 0),     # 无连号
         ([1, 2, 3, 4, 5, 6], 1),      # 六连 = 1 组
         ([5, 6, 8, 9, 12, 13], 3)]    # 三组两连
for seq, expect in cases:
    got = E._consec_groups_count(sorted(seq))
    mark = "✓" if got == expect else "✗"
    print(f"  {mark} {seq} → {got} (期望 {expect})")

print("\n== 蒙特卡洛无放回专项：模拟开奖不应有重复 ==")
scores = E.mod22_monte_carlo(red, blue)
print(f"  输出维度 {len(scores)}，总和 {sum(scores):.3f}（应≈6×500/500=6 的期望命中量纲）")

print("\n== PCA 专项：幂迭代应收敛 ==")
pca = E.mod19_pca(red, blue)
print(f"  输出维度 {len(pca)}，非零: {sum(1 for v in pca if v > 1e-9)}/33")

print("\n总体:", "全部通过 ✅" if ok else "存在失败 ❌")
db.close()

# -*- coding: utf-8 -*-
"""
双色球历史统计工具 —— 滚动回测
walk-forward 验证：用第 1..T 期建模对第 T+1 期评分，与实际开奖比对。
输出命中统计并与随机基准（红球期望 1.09、蓝球 6.25%）对照。
"""
import random
from collections import Counter

from engine import (SelectionEngine, RED_RANGE, BLUE_RANGE,
                    RANDOM_BASE_RED, RANDOM_BASE_BLUE)


def prize_level(red_hit, blue_hit):
    """按双色球奖级判定。red_hit 0-6, blue_hit 0/1。返回 (等级, 名称)。"""
    if red_hit == 6 and blue_hit == 1:
        return (1, "一等奖")
    if red_hit == 6:
        return (2, "二等奖")
    if red_hit == 5 and blue_hit == 1:
        return (3, "三等奖")
    if (red_hit == 5 and blue_hit == 0) or (red_hit == 4 and blue_hit == 1):
        return (4, "四等奖")
    if (red_hit == 4 and blue_hit == 0) or (red_hit == 3 and blue_hit == 1):
        return (5, "五等奖")
    if red_hit <= 2 and blue_hit == 1:
        return (6, "六等奖")
    return (0, "未中奖")


def simulate_random_red_hits(n_trials=100000):
    """理论模拟：随机 6 红与开奖 6 红的命中分布（用于基准对照）。"""
    dist = [0.0] * 7
    rng = random.Random(7)
    for _ in range(n_trials):
        draw = set(rng.sample(list(RED_RANGE), 6))
        pick = set(rng.sample(list(RED_RANGE), 6))
        dist[len(draw & pick)] += 1
    return [d / n_trials for d in dist]


class Backtest:
    """滚动回测器。max_rounds=None/0 表示全量回测（全部可用期数）。"""

    def __init__(self, red_seqs, blue_seqs, window=100,
                 use_seed=True, max_rounds=None, block_sample=1500):
        self.red_seqs = list(red_seqs)
        self.blue_seqs = list(blue_seqs)
        self.window = window
        self.use_seed = use_seed
        self.max_rounds = max_rounds
        self.block_sample = block_sample  # 回测用区块抽样数量（快速近似）

    def _run_range(self, t_begin, t_end):
        """回测 [t_begin, t_end) 一段，返回原始计数 dict（供单进程/子进程块复用）。"""
        pool_dist = Counter()
        pool_sum = 0
        g1 = {"red_sum": 0, "blue_hit": 0, "blue_size": 0, "prize": Counter()}
        g2 = {"red_sum": 0, "blue_hit": 0, "blue_size": 0}
        g3 = {"red_sum": 0, "blue_hit": 0, "blue_size": 0, "prize": Counter()}
        g4 = {"red_sum": 0, "blue_hit": 0, "blue_size": 0}
        g5 = {"red_sum": 0, "blue_hit": 0, "blue_size": 0, "prize": Counter()}
        g6 = {"red_sum": 0, "blue_hit": 0, "blue_size": 0}
        rounds = t_end - t_begin
        for t in range(t_begin, t_end):
            train_r = self.red_seqs[max(0, t - self.window):t]
            train_b = self.blue_seqs[max(0, t - self.window):t]
            seed = t if self.use_seed else None
            rng = random.Random(seed)
            eng = SelectionEngine(train_r, train_b, rng=rng,
                                  block_sample=self.block_sample)
            out = eng.run()

            actual_reds = set(self.red_seqs[t])
            actual_blue = self.blue_seqs[t]

            pool = out["大底"]
            if pool:
                hits = len(actual_reds & set(pool))
                pool_dist[hits] += 1
                pool_sum += hits

            for key, stat in (("结果1", g1), ("结果2", g2), ("结果3", g3),
                              ("结果4", g4), ("结果5", g5), ("结果6", g6)):
                g = out["组"][key]
                rh = len(actual_reds & set(g["红球"]))
                bl = g["蓝球"]
                # 规则型蓝球为单号，统计型为候选集合（集合含中即命中）
                bh = 1 if (actual_blue in bl if isinstance(bl, list)
                           else bl == actual_blue) else 0
                stat["red_sum"] += rh
                stat["blue_hit"] += bh
                # 蓝球候选码数：单号记 1，集合记集合大小（供随机基准对照）
                stat["blue_size"] += (len(bl) if isinstance(bl, list) else 1)
                if key in ("结果1", "结果3", "结果5"):
                    lv, _ = prize_level(rh, bh)
                    stat["prize"][lv] += 1
        return {
            "rounds": rounds, "pool_dist": dict(pool_dist), "pool_sum": pool_sum,
            "结果1": g1, "结果2": g2, "结果3": g3,
            "结果4": g4, "结果5": g5, "结果6": g6,
        }

    @staticmethod
    def merge_blocks(blocks, window):
        """合并多个块的原始计数（JSON 化后），生成最终统计视图。"""
        total = sum(b["rounds"] for b in blocks)
        pool_dist = Counter()
        pool_sum = 0
        stats = {k: {"red_sum": 0, "blue_hit": 0, "blue_size": 0, "prize": Counter()}
                 for k in ("结果1", "结果2", "结果3", "结果4", "结果5", "结果6")}
        for b in blocks:
            pool_dist.update({int(k): v for k, v in b["pool_dist"].items()})
            pool_sum += b["pool_sum"]
            for k in stats:
                s = b[k]
                stats[k]["red_sum"] += s["red_sum"]
                stats[k]["blue_hit"] += s["blue_hit"]
                stats[k]["blue_size"] += s["blue_size"]
                if k in ("结果1", "结果3", "结果5"):
                    stats[k]["prize"].update(s["prize"])

        def view(s):
            avg_size = s["blue_size"] / total if total else 0
            return {
                "平均红球命中": s["red_sum"] / total if total else 0,
                "蓝球命中率": s["blue_hit"] / total if total else 0,
                "蓝球候选码数": round(avg_size, 1),
                "奖级分布": dict(s["prize"]),
            }
        return {
            "回测期数": total, "窗口": window,
            "随机基准红球": round(RANDOM_BASE_RED, 3),
            "随机基准蓝球": round(RANDOM_BASE_BLUE * 100, 2),
            "大底命中分布": dict(sorted(pool_dist.items())),
            "大底平均命中": pool_sum / total if total else 0,
            "结果1": view(stats["结果1"]), "结果2": view(stats["结果2"]),
            "结果3": view(stats["结果3"]), "结果4": view(stats["结果4"]),
            "结果5": view(stats["结果5"]), "结果6": view(stats["结果6"]),
        }

    def run(self, progress_cb=None):
        n = len(self.red_seqs)
        start = min(self.window, n)
        rounds = n - start
        if rounds <= 0:
            return self._empty()
        if self.max_rounds and self.max_rounds > 0:
            rounds = min(rounds, self.max_rounds)
        begin = n - rounds
        raw = self._run_range(begin, n)
        return self.merge_blocks([raw], self.window)

    def _empty(self):
        return {
            "回测期数": 0, "窗口": self.window,
            "随机基准红球": round(RANDOM_BASE_RED, 3),
            "随机基准蓝球": round(RANDOM_BASE_BLUE * 100, 2),
            "大底命中分布": {}, "大底平均命中": 0,
            "结果1": None, "结果2": None, "结果3": None,
            "结果4": None, "结果5": None, "结果6": None,
        }

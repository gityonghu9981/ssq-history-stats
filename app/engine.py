# -*- coding: utf-8 -*-
"""
双色球智能选号系统 —— 选号引擎
43 个统计模块（A类25个号码打分 + B类12个形态约束 + 蓝球双轨6个：38-43）
熵权法自动权重 + 双轨并行（号码轨道 / 区块轨道，红球与蓝球均双轨）+ 6 组结果输出。
全部基于本地历史数据计算，纯标准库实现，可复现。
"""
import itertools
import math
import random
import statistics
from collections import Counter

RED_RANGE = range(1, 34)   # 1..33
BLUE_RANGE = range(1, 17)  # 1..16
PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}

RANDOM_BASE_RED = 6 * 6 / 33.0       # 随机选6红的期望命中数 ≈ 1.0909
RANDOM_BASE_BLUE = 1 / 16.0          # 随机蓝球命中率 = 6.25%


# ============================================================
# 基础工具
# ============================================================

def _freq_window(red_seqs, n):
    """最近 n 期每个红球出现次数。"""
    c = Counter()
    for seq in red_seqs[-n:]:
        c.update(seq)
    return {x: c.get(x, 0) for x in RED_RANGE}


def _miss_info(red_seqs):
    """每个号码：当前遗漏、平均遗漏、最大遗漏、出现间隔列表。"""
    last_seen = {}
    gaps = {x: [] for x in RED_RANGE}
    cur_miss = {x: 0 for x in RED_RANGE}
    total = len(red_seqs)
    for i, seq in enumerate(red_seqs):
        for x in RED_RANGE:
            if x in seq:
                if x in last_seen:
                    gaps[x].append(i - last_seen[x] - 1)
                else:
                    gaps[x].append(i)
                last_seen[x] = i
                cur_miss[x] = 0
            else:
                cur_miss[x] += 1
    avg = {x: (sum(gaps[x]) / len(gaps[x]) if gaps[x] else float(total))
           for x in RED_RANGE}
    mx = {x: (max(gaps[x]) if gaps[x] else 0) for x in RED_RANGE}
    return cur_miss, avg, mx


def _binary_series(red_seqs, x):
    """号码 x 是否在每期出现的 0/1 序列。"""
    return [1 if x in seq else 0 for seq in red_seqs]


def _norm(vals):
    """min-max 归一化到 0-1。"""
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def _entropy_weight(score_rows):
    """熵权法：score_rows 为多个模块的得分向量（每行33维）。
    信息熵越小（区分度越大）权重越高。每行先做 min-max 非负归一化，
    消除负值产生的非法概率与量纲差异（模块17峰度等可输出负值）。"""
    n_mod, m = len(score_rows), 33
    if n_mod == 0:
        return [1.0 / m] * m
    weights = []
    for row in score_rows:
        row = _norm(row)
        s = sum(row)
        if s <= 1e-12:
            weights.append(0.0)
            continue
        p = [v / s for v in row]
        e = -sum(pi * math.log(pi) if pi > 1e-12 else 0.0 for pi in p)
        e = e / math.log(m) if m > 1 else 0.0
        weights.append(max(1.0 - e, 0.0))
    tot = sum(weights)
    if tot <= 1e-12:
        return [1.0 / m] * m
    return [w / tot for w in weights]


# ============================================================
# A 类：号码打分模块（25 个）
# 每个输入红球序列，输出 33 维得分向量
# ============================================================

def mod01_cold_hot(red_seqs, blue_seqs):
    """冷热号频次：综合 30/60/100 期频次。"""
    s = [0.0] * 33
    for n in (30, 60, 100):
        f = _freq_window(red_seqs, min(n, len(red_seqs)))
        for x in RED_RANGE:
            s[x - 1] += f[x]
    return s


def mod02_miss_current(red_seqs, blue_seqs):
    cur, _, _ = _miss_info(red_seqs)
    return [cur[x] for x in RED_RANGE]


def mod03_avg_miss(red_seqs, blue_seqs):
    _, avg, _ = _miss_info(red_seqs)
    # 平均遗漏越大，得分越高（补偿欠出）
    return [avg[x] for x in RED_RANGE]


def mod04_max_miss(red_seqs, blue_seqs):
    _, _, mx = _miss_info(red_seqs)
    return [mx[x] for x in RED_RANGE]


def mod05_miss_ratio(red_seqs, blue_seqs):
    cur, avg, _ = _miss_info(red_seqs)
    return [cur[x] / (avg[x] + 1e-9) for x in RED_RANGE]


def mod06_repeat_rate(red_seqs, blue_seqs):
    """重号率：号码出现后下一期继续出现的比例（历史重号率）。"""
    appears = [0.0] * 33   # 每期出现次数
    repeats = [0.0] * 33   # 出现后下期重号次数
    for i in range(len(red_seqs) - 1):
        cur = set(red_seqs[i])
        nxt = set(red_seqs[i + 1])
        for x in cur:
            appears[x - 1] += 1.0
            if x in nxt:
                repeats[x - 1] += 1.0
    return [repeats[x - 1] / (appears[x - 1] + 1e-9) for x in RED_RANGE]


def mod07_neighbor_rate(red_seqs, blue_seqs):
    """邻号率：号码 ±1 邻号的历史出现频率。"""
    s = [0.0] * 33
    for seq in red_seqs:
        nb = set()
        for x in seq:
            for dx in (-1, 1):
                if 1 <= x + dx <= 33:
                    nb.add(x + dx)
        for v in nb:
            s[v - 1] += 1.0
    return s


def mod08_diagonal(red_seqs, blue_seqs):
    """斜连号：本期号码与上期号码形成 ±1 斜连的趋势强度。"""
    s = [0.0] * 33
    if len(red_seqs) >= 3:
        prev2 = set(red_seqs[-3])
        prev1 = set(red_seqs[-2])
        for x in RED_RANGE:
            if (x - 1 in prev1 and x - 2 in prev2) or (x + 1 in prev1 and x + 2 in prev2):
                s[x - 1] += 3.0
            if (x - 1 in prev1) or (x + 1 in prev1):
                s[x - 1] += 1.0
    return s


def mod09_bayesian(red_seqs, blue_seqs):
    """贝叶斯后验：均匀先验 + 频次似然 → 后验概率。"""
    n = max(len(red_seqs), 1)
    f = _freq_window(red_seqs, n)
    alpha = 1.0  # 均匀先验伪计数
    total = n * 6 + alpha * 33
    return [(f[x] + alpha) / total for x in RED_RANGE]


def mod10_poisson(red_seqs, blue_seqs):
    """泊松拟合检验：号码出现次数相对泊松期望的卡方偏离贡献。"""
    n = max(len(red_seqs), 1)
    lam = 6 * n / 33.0
    f = _freq_window(red_seqs, n)
    s = []
    for x in RED_RANGE:
        k = f[x]
        s.append(((k - lam) ** 2) / (lam + 1e-9))
    return s


def mod11_markov_red(red_seqs, blue_seqs):
    """马尔可夫红球转移：上期号码 → 下期号码的转移吸引。"""
    s = [0.0] * 33
    for i in range(len(red_seqs) - 1):
        prev = set(red_seqs[i])
        for x in red_seqs[i + 1]:
            s[x - 1] += 1.0 if x not in prev else 2.0
    return s


def mod12_hypergeo(red_seqs, blue_seqs):
    """超几何命中概率：号码被开奖组合包含的概率（理论均匀基准）。"""
    return [6 / 33.0] * 33


def mod13_chi2(red_seqs, blue_seqs):
    """卡方均匀性检验：各号码频次对均匀期望的偏离贡献。"""
    n = max(len(red_seqs), 1)
    f = _freq_window(red_seqs, n)
    exp = 6 * n / 33.0
    return [((f[x] - exp) ** 2) / (exp + 1e-9) for x in RED_RANGE]


def mod14_autocorr(red_seqs, blue_seqs):
    """自相关系数：号码出现 0/1 序列的 lag-1 自相关绝对值。"""
    s = []
    for x in RED_RANGE:
        b = _binary_series(red_seqs, x)
        n = len(b)
        if n < 3:
            s.append(0.0)
            continue
        mu = sum(b) / n
        num = sum((b[i] - mu) * (b[i + 1] - mu) for i in range(n - 1))
        den = sum((b[i] - mu) ** 2 for i in range(n)) + 1e-9
        s.append(abs(num / den))
    return s


def mod15_std_cv(red_seqs, blue_seqs):
    """标准差/离散系数：号码出现间隔的离散程度（补偿不规律号）。"""
    _, _, _ = _miss_info(red_seqs)
    s = []
    for x in RED_RANGE:
        b = _binary_series(red_seqs, x)
        idx = [i for i, v in enumerate(b) if v]
        if len(idx) < 2:
            s.append(0.0)
            continue
        gaps = [idx[i + 1] - idx[i] for i in range(len(idx) - 1)]
        mu = statistics.mean(gaps)
        sd = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
        s.append(sd / (mu + 1e-9))
    return s


def mod16_skewness(red_seqs, blue_seqs):
    """偏度：号码出现间隔分布的偏斜程度。"""
    s = []
    for x in RED_RANGE:
        b = _binary_series(red_seqs, x)
        idx = [i for i, v in enumerate(b) if v]
        if len(idx) < 3:
            s.append(0.0)
            continue
        gaps = [idx[i + 1] - idx[i] for i in range(len(idx) - 1)]
        mu = statistics.mean(gaps)
        sd = statistics.pstdev(gaps) + 1e-9
        s.append(statistics.mean((g - mu) ** 3 for g in gaps) / (sd ** 3))
    return s


def mod17_kurtosis(red_seqs, blue_seqs):
    """峰度：号码出现间隔分布的峰度。"""
    s = []
    for x in RED_RANGE:
        b = _binary_series(red_seqs, x)
        idx = [i for i, v in enumerate(b) if v]
        if len(idx) < 3:
            s.append(0.0)
            continue
        gaps = [idx[i + 1] - idx[i] for i in range(len(idx) - 1)]
        mu = statistics.mean(gaps)
        sd = statistics.pstdev(gaps) + 1e-9
        s.append(statistics.mean((g - mu) ** 4 for g in gaps) / (sd ** 4) - 3.0)
    return s


def mod18_shannon_entropy(red_seqs, blue_seqs):
    """号码香农熵：各号码频次对信息熵的贡献。"""
    n = max(len(red_seqs), 1)
    f = _freq_window(red_seqs, n)
    s = []
    for x in RED_RANGE:
        p = f[x] / (6 * n + 1e-9)
        s.append(-p * math.log(p + 1e-12))
    return s


def mod19_pca(red_seqs, blue_seqs):
    """PCA 降维贡献度：号码共现协方差矩阵第一主成分载荷（幂迭代近似）。"""
    n = len(red_seqs)
    if n < 20:
        return [0.5] * 33
    # 共现矩阵（对称）
    co = [[0.0] * 33 for _ in range(33)]
    for seq in red_seqs:
        for i in range(len(seq)):
            for j in range(len(seq)):
                co[seq[i] - 1][seq[j] - 1] += 1.0
    # 转为协方差：E[(X_i-μ_i)(X_j-μ_j)]，用自身出现率近似 μ
    for i in range(33):
        mi = co[i][i] / (n + 1e-9)
        for j in range(33):
            mj = co[j][j] / (n + 1e-9)
            co[i][j] = co[i][j] / (n + 1e-9) - mi * mj
    # 幂迭代求第一主成分
    v = [1.0] * 33
    for _ in range(60):
        nv = [sum(co[i][j] * v[j] for j in range(33)) for i in range(33)]
        norm = math.sqrt(sum(x * x for x in nv)) + 1e-12
        v = [x / norm for x in nv]
    return [abs(x) for x in v]


def mod20_rotation_cover(red_seqs, blue_seqs):
    """旋转矩阵覆盖度：号码对最近历史组合的贪心覆盖贡献。
    覆盖最多未覆盖历史组合的号码得分最高（旋转矩阵覆盖思想）。"""
    n = min(len(red_seqs), 80)
    if n == 0:
        return [0.5] * 33
    target = [set(seq) for seq in red_seqs[-n:]]
    covered = [False] * n
    s = [0.0] * 33
    pool = list(RED_RANGE)
    # 贪心选覆盖增益最大的号码（最多 12 轮）
    for _ in range(12):
        gains = [sum(1 for i, t in enumerate(target)
                     if not covered[i] and x in t) for x in pool]
        best = max(gains)
        if best <= 0:
            break
        x = pool[gains.index(best)]
        s[x - 1] += 1.0
        pool.remove(x)
        for i, t in enumerate(target):
            if not covered[i] and x in t:
                covered[i] = True
    # 剩余号码按未覆盖组合中的出现次数给分
    for x in pool:
        s[x - 1] = sum(1 for i, t in enumerate(target)
                       if not covered[i] and x in t) * 0.1
    return s


def mod21_dan_tuo(red_seqs, blue_seqs):
    """胆拖组合优化分：号码作为胆码的覆盖收益（共现加权）。"""
    s = [0.0] * 33
    n = min(len(red_seqs), 80)
    for seq in red_seqs[-n:]:
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                s[seq[i] - 1] += 1.0
                s[seq[j] - 1] += 1.0
    return s


def mod22_monte_carlo(red_seqs, blue_seqs):
    """蒙特卡洛模拟期望：按历史频次加权无放回模拟开奖，号码被抽中期望次数。"""
    n = min(len(red_seqs), 100)
    if n == 0:
        return [0.5] * 33
    f = _freq_window(red_seqs, n)
    rng = random.Random(20261003)
    hits = [0.0] * 33
    trials = 500
    for _ in range(trials):
        weights = [f[x] + 1e-9 for x in RED_RANGE]
        picked = []
        for _k in range(6):  # 加权无放回（与双色球无重复规则一致）
            total = sum(weights)
            r = rng.random() * total
            cum = 0.0
            for i in range(33):
                cum += weights[i]
                if r <= cum:
                    picked.append(i + 1)
                    weights[i] = 0.0
                    break
        for x in picked:
            hits[x - 1] += 1.0
    return [h / trials for h in hits]


def mod23_window_backtest(red_seqs, blue_seqs):
    """滑动窗口回测得分：号码在过去若干窗口期被频次 TOP 法命中的次数。"""
    if len(red_seqs) < 60:
        return [0.5] * 33
    hits = [0.0] * 33
    for i in range(30, len(red_seqs) - 1, 7):  # 步长7取样，控制计算量
        win = red_seqs[max(0, i - 30):i]
        f = Counter()
        for seq in win:
            f.update(seq)
        top = {x for x, _ in f.most_common(18)}
        for x in red_seqs[i]:
            if x in top:
                hits[x - 1] += 1.0
    return hits


def mod24_zone_balance(red_seqs, blue_seqs):
    """区间均衡度：号码所在区间的历史均衡偏离（1-8/9-16/17-24/25-33）。"""
    zones = [(1, 8), (9, 16), (17, 24), (25, 33)]
    s = [0.0] * 33
    n = max(len(red_seqs), 1)
    zone_cnt = [0, 0, 0, 0]
    for seq in red_seqs:
        for x in seq:
            for zi, (a, b) in enumerate(zones):
                if a <= x <= b:
                    zone_cnt[zi] += 1
    for zi, (a, b) in enumerate(zones):
        avg = zone_cnt[zi] / (6 * n + 1e-9)
        for x in range(a, b + 1):
            s[x - 1] = avg  # 均衡偏离用区块均值，欠出区块给高分
    return [1.0 - v for v in s]


def mod25_tail_entropy(red_seqs, blue_seqs):
    """尾数分布熵：号码尾数 0-9 的分布信息量贡献。"""
    n = max(len(red_seqs), 1)
    tails = Counter()
    for seq in red_seqs:
        for x in seq:
            tails[x % 10] += 1
    s = []
    for x in RED_RANGE:
        p = tails[x % 10] / (6 * n + 1e-9)
        s.append(-p * math.log(p + 1e-12))
    return s


A_MODULES = [
    ("01冷热号频次", mod01_cold_hot),
    ("02当前遗漏", mod02_miss_current),
    ("03平均遗漏", mod03_avg_miss),
    ("04最大遗漏", mod04_max_miss),
    ("05遗漏比", mod05_miss_ratio),
    ("06重号率", mod06_repeat_rate),
    ("07邻号率", mod07_neighbor_rate),
    ("08斜连号", mod08_diagonal),
    ("09贝叶斯后验", mod09_bayesian),
    ("10泊松拟合", mod10_poisson),
    ("11马尔可夫红球", mod11_markov_red),
    ("12超几何基准", mod12_hypergeo),
    ("13卡方均匀性", mod13_chi2),
    ("14自相关", mod14_autocorr),
    ("15离散系数", mod15_std_cv),
    ("16偏度", mod16_skewness),
    ("17峰度", mod17_kurtosis),
    ("18号码香农熵", mod18_shannon_entropy),
    ("19PCA贡献度", mod19_pca),
    ("20旋转覆盖", mod20_rotation_cover),
    ("21胆拖优化", mod21_dan_tuo),
    ("22蒙特卡洛", mod22_monte_carlo),
    ("23窗口回测", mod23_window_backtest),
    ("24区间均衡", mod24_zone_balance),
    ("25尾数熵", mod25_tail_entropy),
]


# ============================================================
# B 类：形态约束模块（12 个）
# 每个输出历史最常见形态（区间/比例），用于过滤组合
# ============================================================

def _consec_groups_count(s):
    """统计 6 个升序号码中的连号组数（01 02 03 算 1 组，01 02 04 05 算 2 组）。"""
    groups = 0
    i = 0
    while i < 5:
        if s[i + 1] - s[i] == 1:
            groups += 1
            while i < 5 and s[i + 1] - s[i] == 1:
                i += 1
        i += 1
    return groups


def _morph_stats(red_seqs):
    """统计各形态的分布。返回 dict：name -> Counter(形态值)。"""
    stats = {
        "和值": Counter(), "跨度": Counter(), "奇偶比": Counter(),
        "大小比": Counter(), "质合比": Counter(), "012路": Counter(),
        "四区比": Counter(), "尾数分布": Counter(), "AC值": Counter(),
        "连号组数": Counter(), "同尾组数": Counter(), "红球均值": Counter(),
    }
    for seq in red_seqs:
        s = sorted(seq)
        stats["和值"][sum(s)] += 1
        stats["跨度"][max(s) - min(s)] += 1
        odd = sum(1 for x in s if x % 2 == 1)
        stats["奇偶比"][(odd, 6 - odd)] += 1
        small = sum(1 for x in s if x <= 16)
        stats["大小比"][(small, 6 - small)] += 1
        prime = sum(1 for x in s if x in PRIMES)
        stats["质合比"][(prime, 6 - prime)] += 1
        r0 = sum(1 for x in s if x % 3 == 0)
        r1 = sum(1 for x in s if x % 3 == 1)
        stats["012路"][(r0, r1, 6 - r0 - r1)] += 1
        z = [0, 0, 0, 0]
        for x in s:
            z[min((x - 1) // 8, 3)] += 1
        stats["四区比"][tuple(z)] += 1
        tails = sorted(x % 10 for x in s)
        stats["尾数分布"][tuple(tails)] += 1
        diffs = {abs(a - b) for i, a in enumerate(s) for b in s[i + 1:]}
        stats["AC值"][len(diffs) - 5] += 1
        stats["连号组数"][_consec_groups_count(s)] += 1
        tc = Counter(x % 10 for x in s)
        same = sum(1 for v in tc.values() if v > 1)
        stats["同尾组数"][same] += 1
        stats["红球均值"][round(sum(s) / 6.0)] += 1
    return stats


def _top_forms(counter, top=1):
    """出现次数最多的形态（并列取第一个）。返回 (值, 次数)。"""
    if not counter:
        return None, 0
    val, cnt = counter.most_common(1)[0]
    return val, cnt


def _top_forms_multi(counter, top_n=3):
    """历史频率最高的 top_n 个形态取值（合格取值集合）。"""
    if not counter:
        return []
    return [v for v, _ in counter.most_common(top_n)]


def mod26_sum_value(red_seqs, blue_seqs):
    """和值：历史最常见区间（中位数 ± 半宽）。"""
    st = _morph_stats(red_seqs)
    vals = sorted(st["和值"].elements())
    if not vals:
        return {"和值": (75, 145)}
    lo, hi = vals[len(vals) // 4], vals[3 * len(vals) // 4]
    return {"和值": (lo, hi)}


def mod27_red_mean(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = sorted(st["红球均值"].elements())
    if not vals:
        return {"红球均值": (13, 21)}
    lo, hi = vals[len(vals) // 4], vals[3 * len(vals) // 4]
    return {"红球均值": (lo, hi)}


def mod28_span(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = sorted(st["跨度"].elements())
    if not vals:
        return {"跨度": (15, 32)}
    lo, hi = vals[len(vals) // 4], vals[3 * len(vals) // 4]
    return {"跨度": (lo, hi)}


def mod29_odd_even(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["奇偶比"], 3)
    return {"奇偶比": vals if vals else [(3, 3)]}


def mod30_big_small(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["大小比"], 3)
    return {"大小比": vals if vals else [(3, 3)]}


def mod31_prime_comp(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["质合比"], 3)
    return {"质合比": vals if vals else [(2, 4)]}


def mod32_road012(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["012路"], 3)
    return {"012路": vals if vals else [(2, 2, 2)]}


def mod33_zone4(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["四区比"], 3)
    return {"四区比": vals if vals else [(2, 1, 1, 2)]}


def mod34_tail_dist(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["尾数分布"], 3)
    return {"尾数分布": vals if vals else [(0, 2, 3, 4, 8, 9)]}


def mod35_ac_value(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["AC值"], 3)
    return {"AC值": vals if vals else [8]}


def mod36_consec_groups(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["连号组数"], 3)
    return {"连号组数": vals if vals else [1]}


def mod37_same_tail(red_seqs, blue_seqs):
    st = _morph_stats(red_seqs)
    vals = _top_forms_multi(st["同尾组数"], 3)
    return {"同尾组数": vals if vals else [1]}


def mod38_markov_blue(red_seqs, blue_seqs):
    """马尔可夫蓝球转移：以最近一期蓝球为状态的条件转移分布。"""
    if len(blue_seqs) < 3:
        return [0.5] * 16
    last = blue_seqs[-2]  # 上一期蓝球作为当前状态
    cnt = Counter()
    for i in range(len(blue_seqs) - 1):
        if blue_seqs[i] == last:
            cnt[blue_seqs[i + 1]] += 1
    total = sum(cnt.values())
    if total <= 0:
        return [0.5] * 16
    return [cnt.get(x, 0) / total for x in BLUE_RANGE]


def mod39_blue_mean_revert(red_seqs, blue_seqs):
    """蓝球均值回归：偏离历史均值越远得分越高。"""
    if not blue_seqs:
        return [0.5] * 16
    mu = statistics.mean(blue_seqs)
    return [abs(x - mu) for x in BLUE_RANGE]


def mod40_blue_cold_hot(red_seqs, blue_seqs):
    """蓝球冷热频次：最近 30/60/100 期频次。"""
    s = [0.0] * 16
    for n in (30, 60, 100):
        c = Counter(blue_seqs[-n:])
        for x in BLUE_RANGE:
            s[x - 1] += c.get(x, 0)
    return s


# ---------- 蓝球形态模块（区块轨道视角，41-43） ----------

def mod41_blue_zone(red_seqs, blue_seqs):
    """蓝球区间分布：1-4/5-8/9-12/13-16 四区，近 60 期各区占比（形态视角）。"""
    if not blue_seqs:
        return [0.5] * 16
    window = blue_seqs[-60:]
    n = max(len(window), 1)
    zones = [(1, 4), (5, 8), (9, 12), (13, 16)]
    counts = [sum(1 for x in window if a <= x <= b) / n
              for a, b in zones]
    s = [0.0] * 16
    for x in BLUE_RANGE:
        for (a, b), p in zip(zones, counts):
            if a <= x <= b:
                s[x - 1] = p
    return s


def mod42_blue_parity_size(red_seqs, blue_seqs):
    """蓝球奇偶大小形态：奇大/奇小/偶大/偶小 四形态，近 60 期占比（形态视角）。"""
    if not blue_seqs:
        return [0.5] * 16
    window = blue_seqs[-60:]
    n = max(len(window), 1)
    f4 = {(0, 0): 0, (0, 1): 0, (1, 0): 0, (1, 1): 0}
    for x in window:
        f4[(x % 2, 1 if x > 8 else 0)] += 1
    s = [0.0] * 16
    for x in BLUE_RANGE:
        s[x - 1] = f4[(x % 2, 1 if x > 8 else 0)] / n
    return s


def mod43_blue_gap(red_seqs, blue_seqs):
    """蓝球遗漏形态：各号距上次出现的遗漏期数，遗漏越久得分越高（形态视角）。"""
    if not blue_seqs:
        return [0.5] * 16
    last = blue_seqs[-1]
    gaps = []
    for x in BLUE_RANGE:
        g = 0
        for v in reversed(blue_seqs[:-1]):
            if v == x:
                break
            g += 1
        gaps.append(0 if x == last else g)
    m = max(gaps) if gaps and max(gaps) > 0 else 1
    return [g / m for g in gaps]


B_MODULES = [
    ("26和值", mod26_sum_value),
    ("27红球均值", mod27_red_mean),
    ("28跨度", mod28_span),
    ("29奇偶比", mod29_odd_even),
    ("30大小比", mod30_big_small),
    ("31质合比", mod31_prime_comp),
    ("32 012路", mod32_road012),
    ("33四区比", mod33_zone4),
    ("34尾数分布", mod34_tail_dist),
    ("35 AC值", mod35_ac_value),
    ("36连号组数", mod36_consec_groups),
    ("37同尾组数", mod37_same_tail),
]

BLUE_MODULES_NUM = [
    ("38马尔可夫蓝球", mod38_markov_blue),
    ("39蓝球均值回归", mod39_blue_mean_revert),
    ("40蓝球冷热频次", mod40_blue_cold_hot),
]

BLUE_MODULES_FORM = [
    ("41蓝球区间形态", mod41_blue_zone),
    ("42蓝球奇偶大小形态", mod42_blue_parity_size),
    ("43蓝球遗漏形态", mod43_blue_gap),
]

BLUE_MODULES = BLUE_MODULES_NUM + BLUE_MODULES_FORM  # 蓝球模块完整性清单（38-43）


# ============================================================
# 形态校验
# ============================================================

def check_forms(seq, forms, min_ratio=0.8):
    """检查 6 个红球是否满足形态约束（合格区间或历史 TOP 取值集合）。
    返回 (是否满足, 不满足项列表)。"""
    s = sorted(int(x) for x in seq)  # 强制 int，防御类型污染
    if len(s) != 6:
        return False, ["长度"]
    if not forms:
        return True, []
    bad = []
    odd = sum(1 for x in s if x % 2 == 1)
    small = sum(1 for x in s if x <= 16)
    prime = sum(1 for x in s if x in PRIMES)
    r0 = sum(1 for x in s if x % 3 == 0)
    r1 = sum(1 for x in s if x % 3 == 1)
    z = [0, 0, 0, 0]
    for x in s:
        z[min((x - 1) // 8, 3)] += 1
    diffs = {abs(a - b) for i, a in enumerate(s) for b in s[i + 1:]}
    for key, val in forms.items():
        ok = True
        if key == "和值":
            ok = val[0] <= sum(s) <= val[1]
        elif key == "红球均值":
            ok = val[0] <= round(sum(s) / 6.0) <= val[1]
        elif key == "跨度":
            ok = val[0] <= max(s) - min(s) <= val[1]
        elif key == "奇偶比":
            ok = (odd, 6 - odd) in val
        elif key == "大小比":
            ok = (small, 6 - small) in val
        elif key == "质合比":
            ok = (prime, 6 - prime) in val
        elif key == "012路":
            ok = (r0, r1, 6 - r0 - r1) in val
        elif key == "四区比":
            ok = tuple(z) in val
        elif key == "尾数分布":
            ok = tuple(sorted(x % 10 for x in s)) in val
        elif key == "AC值":
            ok = (len(diffs) - 5) in val
        elif key == "连号组数":
            ok = _consec_groups_count(s) in val
        elif key == "同尾组数":
            tc = Counter(x % 10 for x in s)
            ok = sum(1 for v in tc.values() if v > 1) in val
        if not ok:
            bad.append(key)
    hit = len(forms) - len(bad)
    return (hit / max(len(forms), 1)) >= min_ratio, bad


# ============================================================
# 选号主流程
# ============================================================

class SelectionEngine:
    """选号引擎：输入本地历史数据，输出 6 组结果与大底。"""

    def __init__(self, red_seqs, blue_seqs, rng=None, require_forms=True,
                 big_pool=18, max_tries=4000,
                 exclude_red=(), exclude_blue=(),
                 block_sample=None):
        """block_sample：None=区块轨道全枚举（精确）；int=回测用随机抽样数量（快速）。"""
        self.red_seqs = list(red_seqs)
        self.blue_seqs = list(blue_seqs)
        self.rng = rng or random.Random()
        self.require_forms = require_forms
        self.big_pool = big_pool
        self.max_tries = max_tries
        self.exclude_red = set(exclude_red)
        self.exclude_blue = set(exclude_blue)
        self.block_sample = block_sample
        self.has_data = len(self.red_seqs) > 0

    # ---------- A 类打分与熵权 ----------
    def score_red(self):
        """运行 25 个 A 类模块，返回 (模块得分行, 加权总分向量)。"""
        rows = []
        for name, fn in A_MODULES:
            try:
                rows.append(fn(self.red_seqs, self.blue_seqs))
            except Exception:
                rows.append([0.5] * 33)
        weights = _entropy_weight(rows)
        total = [0.0] * 33
        for i, row in enumerate(rows):
            for j in range(33):
                total[j] += weights[i] * row[j]
        return rows, weights, total

    # ---------- B 类形态 ----------
    def forms(self):
        """运行 B 类形态模块，输出形态约束 dict。"""
        forms = {}
        for name, fn in B_MODULES:
            try:
                forms.update(fn(self.red_seqs, self.blue_seqs))
            except Exception:
                pass
        return forms

    # ---------- 投票层：蓝球（双轨独立投票） ----------
    def vote_blue(self, modules=None):
        """蓝球投票：给定模块组各自打分并取 TOP5 候选投票。
        默认全量蓝球模块；号码轨道传 BLUE_MODULES_NUM，区块轨道传 BLUE_MODULES_FORM。
        返回 (综合得分向量, 候选蓝球 TOP3, 票数数组)。"""
        modules = modules or BLUE_MODULES
        votes = [0] * 16
        scores = [0.0] * 16
        for name, fn in modules:
            try:
                row = fn(self.red_seqs, self.blue_seqs)
            except Exception:
                row = [0.5] * 16
            order = sorted(range(16), key=lambda i: row[i], reverse=True)[:5]
            for i in order:
                votes[i] += 1
            m = max(row) if max(row) > 0 else 1.0
            for j in range(16):
                scores[j] += row[j] / m
        mx = max(scores) if max(scores) > 0 else 1.0
        combined = [votes[i] + scores[i] / mx for i in range(16)]
        cand = sorted(range(16), key=lambda i: combined[i], reverse=True)[:3]
        return combined, [c + 1 for c in cand], votes

    # ---------- 组合生成 ----------
    def _enum_blocks(self, pool, forms):
        """区块轨道：取大底 6 红组合，按满足 B 类形态数（重叠率）排序。
        全枚举求精确最高；block_sample 给定时间随机抽样求近似最高（回测用）。
        返回 [(组合, 重叠率), ...] 降序。"""
        pool = sorted(set(pool))
        if self.exclude_red:
            pool = [x for x in pool if x not in self.exclude_red]
        if len(pool) < 6:
            pool = [x for x in RED_RANGE if x not in self.exclude_red]
            if len(pool) < 6:
                pool = list(RED_RANGE)
        total_forms = max(len(forms), 1)
        cands = []
        if self.block_sample and self.block_sample > 0:
            for _ in range(self.block_sample):
                combo = tuple(sorted(self.rng.sample(pool, 6)))
                bad = check_forms(list(combo), forms, 0.0)[1]
                cands.append((combo, (len(forms) - len(bad)) / total_forms))
        else:
            for combo in itertools.combinations(pool, 6):
                bad = check_forms(list(combo), forms, 0.0)[1]
                cands.append((combo, (len(forms) - len(bad)) / total_forms))
        cands.sort(key=lambda t: t[1], reverse=True)
        return cands

    # ---------- 主流程：投票层 + 双轨 + 6 组结果 ----------
    def run(self):
        """按方案原文执行：
        1) A 类模块各自独立打分、各输出 TOP18 候选集；
        2) 投票层统计每号被选次数，结合熵权加权分，降序取前 N 作红球大底；
        3) B 类模块输出形态约束；区块轨道枚举组合取重叠率最高的形态区块；
        4) 蓝球双轨独立投票：号码轨道 38-40（微观统计）输出候选，区块轨道 41-43（形态统计）输出候选；
        5) 号码轨道出结果1(注单)/2(集合)，区块轨道出结果3(注单)/4(集合)，
           横向叠加出结果5(注单)/6(集合)。
        返回 dict：{大底, 组, 形态, 蓝球候选, 投票详情, 无数据}"""
        if not self.has_data:
            # 无历史数据：纯随机 6 组（仍遵循排除号）
            pool_r = [x for x in RED_RANGE if x not in self.exclude_red] or list(RED_RANGE)
            pool_b = [x for x in BLUE_RANGE if x not in self.exclude_blue] or list(BLUE_RANGE)
            groups = {}
            for k in range(1, 7):
                reds = sorted(self.rng.sample(pool_r, 6))
                blue = self.rng.choice(pool_b)
                groups[f"结果{k}"] = {"红球": reds, "蓝球": blue,
                                     "来源": "纯随机（无历史数据）"}
            return {"大底": None, "组": groups, "形态": {}, "蓝球候选": [],
                    "无数据": True, "投票": {}}

        rows, weights, total = self.score_red()   # A 类：25 模块打分 + 熵权加权
        # 蓝球双轨：号码轨道（38-40 微观统计）与区块轨道（41-43 形态统计）独立投票
        blue_comb_num, blue_cands_num, _ = self.vote_blue(BLUE_MODULES_NUM)
        blue_comb_form, blue_cands_form, _ = self.vote_blue(BLUE_MODULES_FORM)
        forms = self.forms()                      # B 类：12 个形态约束

        # 投票层：每个 A 类模块各自取 TOP18 候选集，统计被选次数
        votes = [0] * 33
        for row in rows:
            order = sorted(range(33), key=lambda i: row[i], reverse=True)[:18]
            for i in order:
                votes[i] += 1
        tmax = max(total) if max(total) > 0 else 1.0
        combined = [votes[i] + total[i] / tmax for i in range(33)]
        order = sorted(range(33), key=lambda i: combined[i], reverse=True)
        pool = [i + 1 for i in order if (i + 1) not in self.exclude_red][:self.big_pool]
        if len(pool) < 6:  # 排除过多时补全
            pool = [x for x in RED_RANGE if x not in self.exclude_red][:self.big_pool]
            if len(pool) < 6:
                pool = list(RED_RANGE)[:self.big_pool]

        # 轨道一：号码轨道（微观打分）
        # 结果1：评分最高的6红（注单·严格6+1）
        # 结果2：同一评分体系 TOP10 红球集合（统计型·非注单）——保证 结果2 ⊇ 结果1
        r1 = pool[:6]
        r2 = pool[:10]

        def _filter_blue_cands(raw_cands, comb_vec):
            """蓝球候选过滤排除号；候选全被排除时从全范围按综合分取同数量
            非排除号（与红球侧兜底对齐），仅当 16 个号全被排除时才退回原始候选。"""
            f = [c for c in raw_cands if c not in self.exclude_blue]
            if f:
                return f
            rest = [x for x in BLUE_RANGE if x not in self.exclude_blue]
            if rest:
                return sorted(rest, key=lambda x: comb_vec[x - 1],
                              reverse=True)[:len(raw_cands)]
            return list(raw_cands)

        # 号码轨道蓝球候选（模块38-40）：排除过滤 + 对称兜底
        b_cands_num = _filter_blue_cands(blue_cands_num, blue_comb_num)
        b1 = b_cands_num[0]            # 号码轨道注单蓝球（候选内评分最优）
        b2 = list(b_cands_num)         # 号码轨道候选集合 TOP3

        # 轨道二：区块轨道（宏观形态，投票取重叠率最高的形态区块）
        # 目标区块 = 重叠率最高组合；并列组合按组合内综合评分和二级排序，
        #            仅取评分最高的前 K 个组合并集作区块池（避免并列池≈大底）
        # 结果3 = 区块号码池内评分最高6红（注单）；结果4 = 同一池评分前10（统计型）
        # 同一排序 → 结果4 ⊇ 结果3 自然成立（与号码轨道、横向叠加完全对称）
        blocks = self._enum_blocks(pool, forms)
        if blocks:
            best_ov = blocks[0][1]
            tied = [c for c, ov in blocks if ov >= best_ov - 0.001]
            top_combos = sorted(
                tied, key=lambda c: sum(combined[x - 1] for x in c),
                reverse=True)[:5]
            block_pool = sorted({x for c in top_combos for x in c})
            if len(block_pool) < 6:
                block_pool = sorted({x for c in tied for x in c})
            if self.exclude_red:
                block_pool = [x for x in block_pool if x not in self.exclude_red]
            if len(block_pool) < 6:
                block_pool = pool
            ordered = sorted(block_pool, key=lambda x: combined[x - 1], reverse=True)
            r3 = sorted(ordered[:6])
            r4 = ordered[:10]
        else:
            r3 = pool[:6]
            r4 = pool[:10]
        # 结果3 = 执行结果4 同一评分命令 + 6+1 严格规定：
        # 红球 = 区块候选池内评分前6；蓝球 = 区块轨道蓝球候选内评分最优1个
        # （注单蓝球必在候选名单内——双层验证，评分最高号不可能落榜）
        b_cands_form = _filter_blue_cands(blue_cands_form, blue_comb_form)
        b3 = b_cands_form[0]             # 区块轨道注单蓝球（候选内评分最优）
        b4 = list(b_cands_form)          # 区块轨道候选集合 TOP3

        # 横向叠加：集合运算（真正融合两轨信息，不做重排序）
        # 结果5：两轨共识码（r1∩r3）优先，不足从两轨扩展池（r2∪r4 新增码）按综合分补
        # 结果6：同一扩展池排序的超集 → 6 ⊇ 5 自然成立
        inter = sorted(set(r1) & set(r3))
        ext = sorted((set(r2) | set(r4)) - set(r1) - set(r3),
                     key=lambda x: combined[x - 1], reverse=True)
        r5 = list(inter)
        for x in ext:
            if len(r5) >= 6:
                break
            r5.append(x)
        if len(r5) < 6:  # 兜底：从两轨已有码按综合分补
            more = sorted((set(r1) | set(r3)) - set(r5),
                          key=lambda x: combined[x - 1], reverse=True)
            r5 = (r5 + more)[:6]
        r5 = sorted(r5)
        r6 = list(r5)
        for x in ext:
            if len(r6) >= 10:
                break
            if x in r6:  # 扩展码已入结果5，跳过避免重复
                continue
            r6.append(x)
        if len(r6) < 10:  # 兜底
            more6 = sorted((set(r1) | set(r3) | set(ext)) - set(r6),
                           key=lambda x: combined[x - 1], reverse=True)
            r6 = (r6 + more6)[:10]
        r6 = sorted(r6)

        # 蓝球：结果1/3 = 各自轨道候选集合内评分最优（注单蓝球必在候选内，双层验证）；
        # 结果6 = 两轨候选并集（叠加轨道覆盖面更大，多显示覆盖并列）；
        # 结果5 = 跨轨共识蓝球：两轨候选交集优先（号码轨 ∩ 区块轨——两轨都提名的号，
        #          正是"横向叠加"的有效共识信号，不再排除 b1）；
        # 无交集时取两轨提名中两轨平均分最高者；必落在结果6 并集候选内
        b6_cands = sorted(set(b_cands_num) | set(b_cands_form),
                          key=lambda x: (blue_comb_num[x - 1]
                                         + blue_comb_form[x - 1]) / 2,
                          reverse=True)
        b6 = list(b6_cands)              # 叠加轨道蓝球候选：两轨并集
        b5 = b1
        consensus = [x for x in b2 if x in b4]  # b2/b4 已过滤排除号，天然不含被排除号
        if consensus:
            b5 = max(consensus, key=lambda x: blue_comb_num[x - 1]
                                             + blue_comb_form[x - 1])
        else:
            b5 = max(set(b2) | set(b4),
                     key=lambda x: blue_comb_num[x - 1]
                                   + blue_comb_form[x - 1])
        if b5 not in b6_cands:
            b5 = b6_cands[0]  # 兜底：叠加注单蓝球必在结果6 候选内

        groups = {
            "结果1": {"红球": r1, "蓝球": b1, "来源": "号码轨道 · 评分最高 6 红+号码轨候选内最优蓝球（注单·严格6+1）"},
            "结果2": {"红球": r2, "蓝球": b2, "来源": "号码轨道 · 评分最高红球集合10码+号码轨蓝球候选 TOP3（统计型·非注单）"},
            "结果3": {"红球": r3, "蓝球": b3, "来源": "区块轨道 · 区块候选评分 TOP6+区块轨候选内最优蓝球（注单·严格6+1）"},
            "结果4": {"红球": r4, "蓝球": b4, "来源": "区块轨道 · 重叠最高区块集合10码+区块轨蓝球候选 TOP3（统计型·非注单）"},
            "结果5": {"红球": r5, "蓝球": b5, "来源": "横向叠加 · 两轨共识+扩展池补全 TOP6（注单·严格6+1）"},
            "结果6": {"红球": r6, "蓝球": b6, "来源": "横向叠加 · 共识+扩展池集合10码+两轨蓝球候选并集（统计型·非注单）"},
        }
        return {"大底": pool, "组": groups, "形态": forms,
                "蓝球候选": b6_cands, "无数据": False,
                "投票": {"红球得票": votes, "模块权重": weights,
                         "区块重叠率": blocks[0][1] if blocks else 0.0}}

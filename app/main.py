# -*- coding: utf-8 -*-
"""双色球智能选号系统 —— 程序入口
无参数：启动桌面界面。
--bt-block start end window sample db_path out_json：子进程回测块执行（分块回测用）。
"""
import argparse
import json
import sys


def run_block(args):
    """子进程回测一块：[start, end) 期，输出原始计数 JSON。"""
    from db import DrawDB
    from backtest import Backtest
    db = DrawDB(args.db_path)
    red = db.red_sequences()
    blue = db.blue_sequences()
    db.close()
    bt = Backtest(red, blue, window=args.window,
                  max_rounds=None, block_sample=args.sample)
    raw = bt._run_range(args.start, args.end)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    print(f"BLOCK_OK {args.start}-{args.end}")


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "--bt-block":
        parser = argparse.ArgumentParser()
        parser.add_argument("--bt-block", action="store_true")
        parser.add_argument("--start", type=int, required=True)
        parser.add_argument("--end", type=int, required=True)
        parser.add_argument("--window", type=int, default=100)
        parser.add_argument("--sample", type=int, default=1500)
        parser.add_argument("--db-path", required=True)
        parser.add_argument("--out-json", required=True)
        run_block(parser.parse_args(argv))
        return 0
    from ui_main import main as ui_main
    return ui_main()


if __name__ == "__main__":
    sys.exit(main())

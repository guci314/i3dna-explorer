#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收桩聊天:先流式思考(无【答】前缀=思考过程),再【答】正式回答。
argv[-1]=prompt。

手艺模式(8-19):prompt 带读桥协议而尚无查询结果 → 先发【查】tasks
(走【查】工具环,真 API 由 UI 侧代跑);喂回后再数着 JSON 里的任务条目
作答——判据=真 API 结果,桩只替 LLM 一环。无手艺协议的树保持旧行为。"""
import sys
import time

prompt = sys.argv[-1]

if "【查】" in prompt and "[查]" not in prompt:
    print("💭 桩思考：树上有手艺卡——先盘问再答…", flush=True)
    time.sleep(0.5)
    print("【查】tasks", flush=True)
elif "[查]" in prompt:
    n = prompt.count('"路径"')          # tasks JSON 每任务一个「路径」键
    print("💭 桩思考：查到了，数一数…", flush=True)
    time.sleep(0.5)
    print(f"【答】桩答（查过）：任务 {n} 个。", flush=True)
else:
    print("💭 桩思考：读包状态快照，比对账与新鲜度…", flush=True)
    time.sleep(1.5)
    print("【答】桩答：全网新鲜，下一炮点火出库。", flush=True)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""omp rpc 桩服务器（tests 用）：说 omp --mode rpc 同款帧协议——
ready → 逐 prompt 回 response/agent_start/message_update(text_delta×N,
带 20ms 间隔)/message_end/prompt_result。多 prompt 循环＝持久进程。"""
import json
import sys
import time

REPLY = "这是来自桩 omp 的流式回答：一共三段，逐帧到达。"

print(json.dumps({"type": "ready", "protocolVersion": 1}), flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        m = json.loads(line)
    except ValueError:
        continue
    if m.get("type") != "prompt":
        continue
    mid = m.get("id", "x")
    emit = lambda o: print(json.dumps(o, ensure_ascii=False), flush=True)
    emit({"type": "response", "id": mid, "ok": True})
    emit({"type": "agent_start"})
    emit({"type": "turn_start"})
    emit({"type": "message_start", "message": {"role": "user", "content": []}})
    emit({"type": "message_end", "message": {"role": "user", "content": []}})
    emit({"type": "message_start", "message": {"role": "assistant",
                                               "content": []}})
    for i in range(0, len(REPLY), 4):
        time.sleep(0.02)
        emit({"type": "message_update", "assistantMessageEvent": {
            "type": "text_delta", "contentIndex": 0, "delta": REPLY[i:i + 4]}})
    emit({"type": "message_end", "message": {"role": "assistant",
                                             "content": [{"type": "text",
                                                          "text": REPLY}]}})
    emit({"type": "turn_end"})
    emit({"type": "agent_end"})       # 真协议终帧：prompt_result 只在
    # agentInvoked=false（本地命令）时发，agent 回合不发——误等即永久占线

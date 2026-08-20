#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""右键对话桩（101号 验收）：argv[-1]=prompt。

只在 prompt 含【右键对话协议】时作答；其它车道（代笔 omp/老子 chat）
的 prompt 不含此标记，打印占位行不干扰。按话语标记返回固定信封：
- 「查一查…」→ 查询 JSON（tasks）；喂回后（转录含 [查]）→ 普通回答
- 「…点火/办结/推进…这一单」→ 签字 JSON（话语提到的方法名优先，
  否则闭包首个方法；案卷号取【案卷】头）
- 「非法动词」→ 非法动词签字 JSON（UI 须拒）
- 其它 → 普通文字回答（非信封）
"""
import json
import os
import re
import sys

prompt = sys.argv[-1]
if "【右键对话协议】" not in prompt:
    print("（对话桩只答右键对话协议）")
    sys.exit(0)

if "[查]" in prompt:
    print("查过了：树上有任务，账上可对。")
    sys.exit(0)


def say(obj):
    print(json.dumps(obj, ensure_ascii=False))


m = re.search(r"案卷号：(\S+?)）", prompt)
case = m.group(1) if m else ""
tasks = re.findall(r"─── (域/\S+/方法/\S+) ───", prompt)
sm = re.search(r"【用户话语】(.*)\s*$", prompt)
speech = sm.group(1).strip() if sm else ""

if "非法动词" in speech:
    say({"模式": "签字",
         "动词序列": [{"动词": "rm_tree_everything", "参数": {}}]})
elif "查一查" in speech:
    say({"模式": "查询", "读桥": [{"动词": "tasks", "参数": {}}]})
elif "立个域" in speech:
    # 103号 起草模式（柜员的手）：把话语要点落域意.md 进案卷，任务填
    # 蓝起草站——UI 自动点火蓝站让引擎（桩 omp）产出 申请+域.md 草稿。
    hit = next((t for t in tasks if t.endswith("/方法/立域起草")), None)
    say({"模式": "起草", "任务": hit or (tasks[0] if tasks else ""),
         "案卷号": case,
         "草稿": [{"路径": "域意.md",
                   "内容": "域名: sample_domain\n域主: 研发部\n"
                           "职责: 示范域\n说明: 银行场景演示\n"}]})
elif "批准" in speech:
    # 审批（顾客的签字）：先 draft 落位（源=案卷草稿，免重打全文），
    # 再 settle 绿审批站——意图=「批准」话语原文。
    dn = re.search(r"域名[:：]\s*(\S+)", prompt)
    green = next((t for t in tasks if t.endswith("/方法/立域")), None)
    say({"模式": "签字", "动词序列": [
        {"动词": "draft", "参数": {
            "任务": green or (tasks[0] if tasks else ""), "案卷号": case,
            "草稿": [{"路径": f"域/{dn.group(1) if dn else '?'}/域.md",
                      "源": "域.md"}]}},
        {"动词": "settle", "参数": {
            "任务": green or (tasks[0] if tasks else ""), "案卷号": case}}]})
elif any(k in speech for k in ("点火", "办结", "推进")):
    verb = "fire" if "点火" in speech else \
        ("settle" if "办结" in speech else "advance")
    hit = next((t for t in tasks if os.path.basename(t) in speech), None)
    task = hit or (tasks[0] if tasks else "")
    参数 = {"任务": task}
    if verb != "advance":
        参数["案卷号"] = case
    say({"模式": "签字", "动词序列": [{"动词": verb, "参数": 参数}]})
else:
    print("好的，我在听（桩只答标记话语）。")

# -*- coding: utf-8 -*-
"""test_laozi_skill — 老师傅手艺（8-19）：树上 API手艺卡＝presence-based
技能（卡在=老子可【查】读桥）；写桥白名单外、拒绝也机读。
判据=真 API 结果与 prompt 注入断言；桩只替 LLM 一环——泰勒主义干不了
爱因斯坦的工作，老师傅得有盘问的仪器。"""
import importlib
import json
import os
import subprocess
import sys

import pytest

TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
x
"""

CARD = "# API手艺（老师傅的读桥）\n\n只许读：tree/tasks/task/account/lint/coverage。\n"

FAKE_CHAT = '''
import sys
p = sys.argv[-1]
if "【查】" in p and "[查]" not in p:
    print("💭 桩思考：先盘问再答…")
    print("【查】tasks")
elif "[查]" in p:
    n = p.count('"路径"')
    print(f"【答】查过，任务 {n} 个。")
else:
    print("【答】没手艺，只看快照。")
'''


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


@pytest.fixture
def tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n")
    return r


@pytest.mark.unit
def test_读桥白名单_写桥归人(tree):
    import i3dna_core as core
    ok, text = core.api_query(tree, "tasks")
    assert ok and json.loads(text)["任务"]
    for verb in ("fire", "settle", "advance", "login", "rm -rf"):
        ok, text = core.api_query(tree, verb.split()[0])
        assert not ok and "白名单" in text, verb


@pytest.mark.unit
def test_手艺卡_presence_based(tree, qapp):
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    assert w._laozi_skill() == "", "无卡=无手艺（零第二登记）"
    _mk(tree, "域/治理域/类/目录树元知识/知识/API手艺.md", CARD)
    w2 = ex.Explorer(tree)
    assert "API手艺" in w2._laozi_skill()
    w.close()
    w2.close()


@pytest.mark.integration
def test_先查后答闭环(tree, qtbot, monkeypatch):
    """老师傅两轮：发【查】→ 真 API JSON 喂回 → 答案带真任务数。"""
    _mk(tree, "域/治理域/类/目录树元知识/知识/API手艺.md", CARD)
    fake = _mk(tree, "_fake_chat.py", FAKE_CHAT)
    monkeypatch.setenv("I3DNA_CHAT_CMD", f"{sys.executable} -u {fake}")
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    api = os.path.join(importlib.import_module("i3dna_core").BASE,
                       "i3dna-engine", "i3dna_api.py")
    n = len(json.loads(subprocess.run(
        [sys.executable, api, "tasks", tree],
        capture_output=True, text=True).stdout)["任务"])
    w.chat_input.setText("树里几个任务？")
    w.ask_laozi()
    qtbot.waitUntil(lambda: w._chat_log
                    and w._chat_log[-1][0] == "老子"
                    and "查过" in w._chat_log[-1][1], timeout=15000)
    queries = [t for who, t in w._chat_log if who == "查"]
    assert queries and "【查】tasks" in queries[0] and '"任务"' in queries[0]
    assert f"任务 {n} 个" in w._chat_log[-1][1]
    assert w._laozi_rounds == 1
    w.close()

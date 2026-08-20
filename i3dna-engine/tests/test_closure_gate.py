# -*- coding: utf-8 -*-
"""办结悬账门（8-19 符合性审计落地）：结账＝对账点——本案卷在途消息
未清零＝守恒破坏，backfill 拒绝办结（零副作用，未写账）。
三臂：在途消息拒绝／清零后放行／无消息法定路径休眠。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")

TASK = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
x
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, with_msg=True):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "域主: 甲\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    _mk(r, "消息/回执单.md",
        "---\n路径: 实例/甲/{案卷号}/回执单.md\n发送方: 甲\n接收方: 甲\n---\n")
    if with_msg:
        _mk(r, "实例/甲/c1/回执单.md", "在途\n")
    return r


def _backfill(root, case):
    return subprocess.run(
        [sys.executable, ENGINE, "backfill",
         os.path.join(root, "域/x域/类/甲/方法/办"),
         "--root", root, "--case", case],
        capture_output=True, text=True)


def test_在途消息拒绝办结(tmp_path):
    r = _tree(tmp_path, with_msg=True)
    p = _backfill(r, "c1")
    assert p.returncode != 0, "在途消息在场，办结应被悬账门拒绝"
    assert "悬账" in (p.stderr + p.stdout), "拒绝理由须指认悬账"
    assert "回执单" in (p.stderr + p.stdout), "须点名在途消息"
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__账")), \
        "零副作用：拒绝时不得写账"


def test_清零后放行(tmp_path):
    r = _tree(tmp_path, with_msg=False)
    p = _backfill(r, "c1")
    assert p.returncode == 0, p.stderr
    assert os.path.isfile(os.path.join(r, "实例/甲/c1/__账/办/__结果.json"))


def test_无法定路径休眠(tmp_path):
    """树上无 消息/*.md 类型文件 → 检查自然休眠（不误伤无消息树）。"""
    r = _tree(tmp_path, with_msg=True)
    os.remove(os.path.join(r, "消息/回执单.md"))
    p = _backfill(r, "c1")
    assert p.returncode == 0, p.stderr


def test_共享信箱按案卷号匹配(tmp_path):
    """收件箱型消息（法定路径含 {案卷号} 通配）：他案的单不拦我，我的单拦我。"""
    r = _tree(tmp_path, with_msg=False)
    _mk(r, "消息/请求单.md",
        "---\n路径: 实例/甲/收件箱/请求单__{案卷号}.md\n---\n")
    _mk(r, "实例/甲/收件箱/请求单__别人.md", "他案\n")
    assert _backfill(r, "c1").returncode == 0, "他案在途单不拦本案卷"
    _mk(r, "实例/甲/收件箱/请求单__c1.md", "我案\n")
    p = _backfill(r, "c1")
    assert p.returncode != 0 and "请求单" in (p.stderr + p.stdout)

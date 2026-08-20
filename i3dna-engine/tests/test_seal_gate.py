# -*- coding: utf-8 -*-
"""封存门（8-20 立法口归一配套）：类根 封存.md 在场＝类已封存——
封不删＝证据保留不是通道保留：点火拒绝、办结拒绝（零副作用未写账）；
API tasks 对封存类方法标注「封存」。四臂。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")
API = os.path.join(os.path.dirname(HERE), "i3dna_api.py")

TASK = """---
i3dna: 微任务
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


def _tree(tmp_path, sealed=True):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "域主: 甲\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    if sealed:
        _mk(r, "域/x域/类/甲/封存.md",
            "---\ni3dna: 封存\n封存: 真\n封存理由: 测试\n"
            "封存案卷号: t\n---\n")
    return r


def _backfill(root, case="c1"):
    return subprocess.run(
        [sys.executable, ENGINE, "backfill",
         os.path.join(root, "域/x域/类/甲/方法/办"),
         "--root", root, "--case", case],
        capture_output=True, text=True)


def test_封存类办结拒绝(tmp_path):
    r = _tree(tmp_path, sealed=True)
    p = _backfill(r)
    assert p.returncode != 0, "封存类旧法不应再受理新案卷"
    assert "封存" in (p.stderr + p.stdout)
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__账")), \
        "零副作用：拒绝时不得写账"


def test_未封存照常办结(tmp_path):
    r = _tree(tmp_path, sealed=False)
    _mk(r, "实例/甲/c1/出.md", "产物\n")
    p = _backfill(r)
    assert p.returncode == 0, p.stderr
    assert os.path.isfile(os.path.join(r, "实例/甲/c1/__账/办/__结果.json"))


def test_封存类点火拒绝(tmp_path):
    r = _tree(tmp_path, sealed=True)
    p = subprocess.run(
        [sys.executable, ENGINE, "run",
         os.path.join(r, "域/x域/类/甲/方法/办"),
         "--root", r, "--case", "c1"],
        capture_output=True, text=True)
    assert p.returncode != 0 and "封存" in (p.stderr + p.stdout)


def test_api_tasks标封存位(tmp_path):
    r = _tree(tmp_path, sealed=True)
    p = subprocess.run([sys.executable, API, "tasks", r],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    ts = json.loads(p.stdout)["任务"]
    assert len(ts) == 1 and ts[0]["封存"] is True

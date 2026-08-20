# -*- coding: utf-8 -*-
"""回收弧（撤域/撤并场所族）：办结删目标＋旧 sha 入回收清单＋空壳清扫
（8-20 用户实证「撤了 sample_domain 树上还在」——只删文件留空目录残壳，
渲染成空域节点还触发空域悬空 lint）；非空域不收（只吃空域）；回收空气
响亮拒。判据=磁盘与账 JSON（97号）。"""
import json
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
  - 路径: "域/{申请.域名}/域.md"
    回收: 真
---
结构手术·撤域。
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/撤/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n域名: d9\n---\n申请。\n")
    _mk(r, "域/d9/域.md", "---\n域主: 张三\n---\n域。\n")
    return r


def _settle(r, case="c1"):
    return subprocess.run(
        [sys.executable, ENGINE, "backfill",
         os.path.join(r, "域/x域/类/甲/方法/撤"),
         "--root", r, "--case", case],
        capture_output=True, text=True, timeout=60)


def test_回收空域_删文件清壳_账记旧sha(tmp_path):
    r = _tree(tmp_path)
    p = _settle(r)
    assert p.returncode == 0, p.stderr
    assert not os.path.exists(os.path.join(r, "域/d9/域.md")), "目标已删"
    assert not os.path.exists(os.path.join(r, "域/d9")), \
        "空壳随扫——树面即目录面，残壳会渲染成空域（用户实证）"
    assert os.path.isdir(os.path.join(r, "域/x域")), "清扫止于非空父目录"
    rec = json.load(open(os.path.join(
        r, "实例/甲/c1/__账/撤/__结果.json"), encoding="utf-8"))
    it = rec["回收清单"][0]
    assert it["名称"] == "域/d9/域.md" and it["回收"] is True
    assert it["sha256"] and it["字节"], "旧 sha 入账（git 历史留尸可对勘）"


def test_回收非空域_文件删目录留(tmp_path):
    """「只吃空域」的机械面：域目录还有类/知识 → 清扫遇非空即止。"""
    r = _tree(tmp_path)
    _mk(r, "域/d9/知识/说明.md", "知识还在（须先迁出或封清）。\n")
    p = _settle(r)
    assert p.returncode == 0, p.stderr
    assert not os.path.exists(os.path.join(r, "域/d9/域.md")), "目标已删"
    assert os.path.isdir(os.path.join(r, "域/d9/知识")), "非空即止，不误伤"


def test_回收空气_响亮拒(tmp_path):
    r = _tree(tmp_path)
    os.remove(os.path.join(r, "域/d9/域.md"))
    p = _settle(r)
    assert p.returncode != 0
    assert "回收空气" in (p.stdout + p.stderr)
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__账")), "零副作用"

# -*- coding: utf-8 -*-
"""绿语义回音四件套（形状定律 8-21·工单4，缺陷18 三落空齐闭）：
①回音: 有|无 类型键；②空夹门（目录弧 清空: 真——零文件才使能，非空＝
物理挂起，闭 a）；③办结两牙（草稿转正 __草稿/<产物名>→落位 sha 入账，
闭 b；办结查使能 fail-closed，闭 c）；④回音: 无＝收讫两件套（核销＋
入账，无转正）。判据=needs_fire 返回值+磁盘+账+退出码（97号）。"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")

TYPE_ECHO = """---
i3dna: 消息
主题: "实例/审批/{案卷号}/审批单"
命名: uuid
回音: __ECHO__
键:
  - 申请人
---
审批单种（回音：__ECHO__）。
""".replace("__ECHO__", "%s")

EAT_TASK = """---
i3dna: 微任务
执行者: 人
输入:
  - "实例/审批/{案卷号}/审批单"
产物:
  - "{实例}/回执.md"
---
办一张审批单（绿站：人过目后办结）。
"""

WAIT_TASK = """---
i3dna: 微任务
输入:
  - 路径: "实例/审批/{案卷号}/审批单"
    清空: 真
产物:
  - "{实例}/等后.md"
---
等回音核销完再动（send-and-wait 的等＝空夹门）。
"""

NEXT_TASK = """---
i3dna: 微任务
输入:
  - "{实例}/回执.md"
产物:
  - "{实例}/终件.md"
---
下游：回执转正前不使能。
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, echo="有", with_wait=True, with_next=False):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/消息/审批单.md", TYPE_ECHO % (echo, echo))
    _mk(r, "域/x域/类/甲/方法/办单/任务.md", EAT_TASK)
    if with_wait:
        _mk(r, "域/x域/类/甲/方法/等回音/任务.md", WAIT_TASK)
    if with_next:
        _mk(r, "域/x域/类/甲/方法/下游/任务.md", NEXT_TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n申请人: 张三\n---\n申请。\n")
    return r


BOX = os.path.join("实例", "审批", "c1", "审批单")


def _seed(r, n=1):
    box = os.path.join(r, BOX)
    os.makedirs(box, exist_ok=True)
    for i in range(n):
        _mk(r, f"{BOX}/审批单__{i}.md",
            f"---\n申请人: 张三\n---\n第 {i} 张单。\n")


def _needs(r, task_rel, case="c1"):
    spec = importlib.util.spec_from_file_location("i3dna_engine_g", ENGINE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m._task_needs_fire(os.path.join(r, task_rel), r, case=case)


def _backfill(r, task_rel, case="c1"):
    return subprocess.run(
        [sys.executable, ENGINE, "backfill", os.path.join(r, task_rel),
         "--root", r, "--case", case],
        capture_output=True, text=True, timeout=60)


def _acc(r, case, method):
    return json.load(open(os.path.join(
        r, "实例", "甲", case, "__账", method, "__结果.json"), encoding="utf-8"))


def test_空夹门_夹内有单挂起_核销后放行(tmp_path):
    """验收①：挂门任务 needs_fire——非空＝挂起（物理停，闭 a）；
    夹清空＝使能（与 blank_slot 目录语义对偶）。"""
    r = _tree(tmp_path)
    _seed(r, n=2)
    need, why = _needs(r, "域/x域/类/甲/方法/等回音")
    assert not need and "空夹门" in why, (need, why)
    for i in (0, 1):
        os.remove(os.path.join(r, f"{BOX}/审批单__{i}.md"))
    need2, why2 = _needs(r, "域/x域/类/甲/方法/等回音")
    assert need2, why2                     # 夹空＝使能（等后.md 缺失→要点火）


def test_草稿转正_三件套一次成_转正前下游不使能(tmp_path):
    """验收②：草稿在 __草稿/ 不是产物——下游不使能；办结原子三件：
    消费清单＋产物落位（sha 入账）＋backfill 署名。"""
    import hashlib
    r = _tree(tmp_path, with_wait=True, with_next=True)
    _seed(r, n=1)
    _mk(r, "实例/甲/c1/__草稿/回执.md", "草稿回执（在途稿）。\n")
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/回执.md"))
    need, _why = _needs(r, "域/x域/类/甲/方法/下游")
    assert not need, "草稿不是产物——下游不得使能（闭 b）"
    p = _backfill(r, "域/x域/类/甲/方法/办单")
    assert p.returncode == 0, (p.stdout + p.stderr)[-500:]
    body = open(os.path.join(r, "实例/甲/c1/回执.md"), encoding="utf-8").read()
    assert body == "草稿回执（在途稿）。\n", "草稿转正落位"
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/__草稿/回执.md")), \
        "在途稿随转正出夹"
    acc = _acc(r, "c1", "办单")
    assert acc["状态"] == "事后追认", "backfill 署名"
    assert len(acc["消费清单"]) == 1, "核销一张"
    assert acc["产物清单"][0]["sha256"] == \
        hashlib.sha256(body.encode()).hexdigest(), "sha 入账"
    need2, _ = _needs(r, "域/x域/类/甲/方法/下游")
    assert need2, "转正后下游使能"


def test_办结拒_必选输入缺席(tmp_path):
    """验收③：必选输入（文件空槽）缺席的办结被拒——fail-closed（闭 c）。"""
    r = _tree(tmp_path, with_wait=False, with_next=True)
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/回执.md"))
    p = _backfill(r, "域/x域/类/甲/方法/下游")
    assert p.returncode != 0
    assert "使能门" in (p.stdout + p.stderr) and "必选输入缺席" in (p.stdout + p.stderr)
    assert not os.path.exists(
        os.path.join(r, "实例/甲/c1/__账", "下游")), "零副作用未入账"


def test_收讫两件套_回音无_核销入账无转正(tmp_path):
    """验收④：回音: 无 类型＝fire-and-forget——办结＝核销＋入账两件，
    在途稿不转正（产物照旧缺席）。"""
    r = _tree(tmp_path, echo="无", with_wait=False)
    _seed(r, n=1)
    _mk(r, "实例/甲/c1/__草稿/回执.md", "不该转正的稿。\n")
    p = _backfill(r, "域/x域/类/甲/方法/办单")
    assert p.returncode == 0, (p.stdout + p.stderr)[-500:]
    assert os.listdir(os.path.join(r, BOX)) == [], "核销一张"
    acc = _acc(r, "c1", "办单")
    assert len(acc["消费清单"]) == 1, "入账（消费清单）"
    assert not os.path.exists(os.path.join(r, "实例/甲/c1/回执.md")), \
        "收讫无转正"
    assert os.path.isfile(os.path.join(r, "实例/甲/c1/__草稿/回执.md")), \
        "在途稿留在夹里"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_org_place — 场所变更案卷化规格面测试（自建组织形树测机制）。

裁决：组织变更也是业务，走案卷（88 号泰勒推论）；8-20 立法口归一后
立场所/撤并场所住女娲（本文件以自建组织形树测同一机制——记号代入/
校验门/回收弧与类住哪无关）；
树知识住树不住脑——场所声明格式是 类/知识/ 文档，经输入弧喂给办单 agent。
机械契约（零 LLM）：
1) 记号代入：方法可发现；产物弧 场所/{申请.场所名} 代入后＝场所/<申请.场所名>.md
2) 工位依据：通用界面的依据面含类侧知识（域/ 前缀输入弧全文）
"""
import os

import pytest


TASK = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
  - "{类}/知识/场所声明格式.md"
产物:
  - "场所/{申请.场所名}.md"
---
按《场所声明格式》起草，按内容取名。
"""


APPLY = """---
场所名: 广州开发一部
装配: [研发域]
---
# 申请
理由：独立成部。
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


@pytest.fixture
def tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/治理域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/治理域/类/组织/方法/成立场所/任务.md", TASK)
    _mk(r, "域/治理域/类/组织/知识/场所声明格式.md", "格式知识")
    _mk(r, "实例/组织/广州开发一部/申请.md", APPLY)
    os.makedirs(os.path.join(r, "场所"), exist_ok=True)
    return r


@pytest.mark.unit
def test_org_task_marks_resolve(tree):
    import i3dna_core as core
    eng = core.eng
    tdir = os.path.abspath(os.path.join(
        tree, "域/治理域/类/组织/方法/成立场所"))
    assert tdir in eng.find_tasks(tree)
    task = eng.load_task(tdir, tree, case="广州开发一部")
    prods = [r for r in task["rows"] if r["kind"] == "产物"]
    assert prods and prods[0]["path"].endswith(
        os.path.join("场所", "广州开发一部.md"))      # 按内容取名（申请.场所名）
    ins = [r["pname"] for r in task["rows"] if r["kind"] == "输入"]
    assert "申请.md" in ins and "场所声明格式.md" in ins


@pytest.mark.unit
def test_content_mark_loud_reject(tree):
    """内容记号纪律：申请缺「场所名」键＝载荷缺失，响亮拒绝（不猜产物名）。"""
    import i3dna_core as core
    eng = core.eng
    _mk(tree, "实例/组织/坏申请/申请.md", "# 无 frontmatter 的裸申请\n")
    tdir = os.path.join(tree, "域/治理域/类/组织/方法/成立场所")
    with pytest.raises(SystemExit, match="取值失败|无对应在场输入"):
        eng.load_task(tdir, tree, case="坏申请")


TASK_GATE = TASK.replace(
    "执行者: 人\n",
    "执行者: 人\n校验: 门.py\n")
GATE_FAIL = "import sys\nsys.stderr.write('不合法：测试拒绝\\n')\nsys.exit(1)\n"
GATE_PASS = "print('过（测试）')\n"


@pytest.mark.unit
def test_backfill_gate(tmp_path):
    """办结校验门：任务声明「校验:」→ 引擎代跑；非零＝拒入账零副作用。"""
    import glob as _glob
    import i3dna_core as core
    eng = core.eng
    r = str(tmp_path)
    _mk(r, "域/治理域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/治理域/类/组织/方法/成立场所/任务.md", TASK_GATE)
    _mk(r, "域/治理域/类/组织/知识/场所声明格式.md",
        "格式（测试桩）。\n")     # 必选输入须在场——办结查使能（工单4 牙）
    _mk(r, "实例/组织/广州开发一部/申请.md", APPLY)
    _mk(r, "场所/广州开发一部.md",
        "---\ni3dna: 场所\n场所主: x\n职责: y\n装配: [研发域]\n---\n正文\n")
    _mk(r, "门.py", GATE_FAIL)
    tdir = os.path.join(r, "域/治理域/类/组织/方法/成立场所")
    t = eng.load_task(tdir, r, case="广州开发一部")
    with pytest.raises(SystemExit, match="校验程序拒绝"):
        eng.cmd_backfill(t, "试")
    assert not _glob.glob(os.path.join(r, "实例", "**", "__账", "**", "*.json"),
                          recursive=True), "拒绝时不得写账"
    _mk(r, "门.py", GATE_PASS)
    eng.cmd_backfill(t, "试")
    assert _glob.glob(os.path.join(r, "实例", "**", "__账", "**", "*.json"),
                      recursive=True), "放行后入账"


import i3dna_core as _core   # 引擎家解析（内嵌/旧仓/环境变量统一走 core）

M1_VALIDATOR = os.path.join(
    _core.BASE, "md-devloop-m1", "域", "治理域", "类",
    "目录树元知识", "校验程序", "主程序.py")

AGG_CLS = """---
i3dna: 类
范畴: 过程
关系:
  - 类型: 部件
    方向: 甲类 → 乙类
    种: 聚合
  - 类型: 客户
    方向: 甲类 → 丙类
    种: 关联
---
# 甲类
"""

AGG_TASK = """---
i3dna: 微任务
输入:
  - "{类}/知识/甲规.md"
产物:
  - "{实例}/出.md"
---
干活。
"""


@pytest.mark.unit
def test_part_index_cascade(tmp_path):
    """类知识索引（读桥第二腿）：①本类（模板）知识进索引，已声明为
    输入弧的文件去重；②聚合/组合边一跳部件进索引；③关联不级联；
    ④stdout 车道（裸 LLM 无工具）不进。"""
    import i3dna_core as core
    eng = core.eng
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲类/类.md", AGG_CLS)
    _mk(r, "域/x域/类/甲类/知识/甲规.md", "规")      # 已声明弧→全文在 prompt
    _mk(r, "域/x域/类/甲类/知识/甲备.md", "备")      # 未声明→进索引
    _mk(r, "域/x域/类/甲类/方法/办/任务.md", AGG_TASK)
    _mk(r, "域/x域/类/乙类/类.md", "---\ni3dna: 类\n范畴: 实体\n---\n")
    _mk(r, "域/x域/类/乙类/知识/乙卡.md", "乙知识")
    _mk(r, "域/x域/类/丙类/知识/丙卡.md", "丙知识")
    _mk(r, "实例/甲类/c1/x.md", "1")
    tdir = os.path.join(r, "域", "x域", "类", "甲类", "方法", "办")
    t = eng.load_task(tdir, r, case="c1")
    idx = eng._part_index(t)
    assert [i["类"] for i in idx] == ["甲类", "乙类"], \
        "本类（模板）在前，部件随后，关联不入"
    own = idx[0]
    assert own["种"] == "本类（模板）" and "甲备.md" in own["文件"]
    assert "甲规.md" not in own["文件"], "已声明输入弧的文件去重（全文已在 prompt）"
    assert "类.md" in idx[1]["文件"] and "乙卡.md" in idx[1]["文件"]
    outs = [x for x in t["rows"] if x["kind"] == "产物" and x["path"]]
    dst = {x["pname"]: x["path"] for x in outs}
    pr = eng.build_prompt(t, outs, "write", dst)
    assert "类知识索引" in pr and "本类（模板）" in pr and "甲备" in pr
    assert "乙类（聚合）" in pr and "乙卡" in pr
    assert "丙类" not in pr and "丙卡" not in pr, "关联目标不得级联"
    pr2 = eng.build_prompt(t, outs, "stdout", dst)
    assert "类知识索引" not in pr2, "stdout 车道不进索引"


@pytest.mark.unit
def test_lint_edge_cycle(tmp_path):
    """lint 边环守卫：A◇B 且 B◇A＝整体-部分成环，建模错误。"""
    import i3dna_core as core
    r = str(tmp_path)
    _mk(r, "域/x域/类/甲类/方法/m/任务.md", "---\ni3dna: 微任务\n---\nx\n")
    _mk(r, "域/x域/类/乙类/方法/m/任务.md", "---\ni3dna: 微任务\n---\nx\n")
    _mk(r, "域/x域/类/甲类/类.md",
        "---\n关系:\n  - {类型: p, 方向: 甲类 → 乙类, 种: 聚合}\n---\n")
    _mk(r, "域/x域/类/乙类/类.md",
        "---\n关系:\n  - {类型: q, 方向: 乙类 → 甲类, 种: 组合}\n---\n")
    rep = core.lint.Report()
    core.lint.lint_entity_edges(r, rep)
    assert any("成环" in m for _, m in rep.errors)


@pytest.mark.unit
def test_meta_validator(tmp_path):
    """元知识校验程序（真脚本）：干净树过；装配认领撞车=费米律拒绝；
    他类案卷（无场所名申请）不越权——结构层覆盖。"""
    import subprocess
    import sys as _s
    r = str(tmp_path)
    _mk(r, "域/研发域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/研发域/类/研发/方法/开发/任务.md",
        "---\ni3dna: 微任务\n---\nx\n")
    _mk(r, "实例/研发/c1/x.md", "1")
    _mk(r, "场所/A台.md", "---\n装配: [研发域]\n---\n正文\n")
    ok = subprocess.run([_s.executable, M1_VALIDATOR, r],
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    _mk(r, "场所/B台.md", "---\n装配: [研发域]\n---\n正文\n")
    bad = subprocess.run([_s.executable, M1_VALIDATOR, r],
                         capture_output=True, text=True)
    assert bad.returncode == 1 and "费米律" in bad.stderr
    # 他类案卷（女娲式申请，无场所名）：case 态不越权，结构层放行
    os.remove(os.path.join(r, "场所", "B台.md"))
    _mk(r, "实例/研发/立类案/申请.md", "---\n类名: 新类\n---\n")
    other = subprocess.run([_s.executable, M1_VALIDATOR, r, "立类案"],
                           capture_output=True, text=True)
    assert other.returncode == 0, other.stderr


TASK_RETRACT = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
产物:
  - 路径: "场所/{申请.场所名}.md"
    回收: 真
---
撤销该场所。
"""


@pytest.mark.unit
def test_retract_arc(tmp_path):
    """回收弧：目标在场=先记旧 sha 入账再删；缺席=回收空气响亮拒绝。"""
    import glob as _glob
    import json
    import i3dna_core as core
    eng = core.eng
    r = str(tmp_path)
    _mk(r, "域/治理域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/治理域/类/组织/方法/撤并场所/任务.md", TASK_RETRACT)
    _mk(r, "实例/组织/撤A/申请.md",
        "---\n场所名: A台\n---\n理由。\n")
    _mk(r, "场所/A台.md", "---\n装配: [治理域]\n---\n旧声明。\n")
    tdir = os.path.join(r, "域/治理域/类/组织/方法/撤并场所")
    t = eng.load_task(tdir, r, case="撤A")
    assert any(rr.get("retract") for rr in t["rows"] if rr["kind"] == "产物")
    eng.cmd_backfill(t, "撤并")
    assert not os.path.exists(os.path.join(r, "场所", "A台.md")), "未删"
    accs = _glob.glob(os.path.join(r, "实例", "**", "__账", "**", "*.json"),
                      recursive=True)
    assert accs, "未入账"
    payload = json.load(open(accs[0], encoding="utf-8"))
    回收 = payload.get("回收清单") or []
    assert 回收 and 回收[0]["名称"].endswith("A台.md") \
        and 回收[0].get("sha256"), "账未记回收（名称+旧 sha）"
    # 缺席=回收空气
    _mk(r, "实例/组织/撤B/申请.md", "---\n场所名: B台\n---\n理由。\n")
    t2 = eng.load_task(tdir, r, case="撤B")
    with pytest.raises(SystemExit, match="回收空气"):
        eng.cmd_backfill(t2, "撤并")


@pytest.mark.unit
def test_work_context_carries_class_knowledge(tree, qapp):
    import importlib
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    w._assist_proc_run = lambda p: None      # 桩 LLM 车道
    w._engine_qproc = lambda args, msg, verb=None: None   # 桩引擎
    w.open_work_ui(os.path.join(tree, "域/治理域/类/组织/方法/成立场所"),
                   "广州开发一部")
    assert w._work and w._work["case"] == "广州开发一部"
    assert "申请.md" in w._work["inputs"]
    assert "场所声明格式.md" in w._work["inputs"]     # 类侧知识进依据面
    assert "格式知识" in w._work["inputs"]["场所声明格式.md"]
    w.close()

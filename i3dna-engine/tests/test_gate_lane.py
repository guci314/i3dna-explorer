# -*- coding: utf-8 -*-
"""三车道同门＋悬账门收窄（ARCHITECTURE §8 缺陷19/20，8-21 报销003 实证）：
①条件门三车道接线（fire 拒火/settle 拒办结/推进挂起——_cond_block 从
019ef8d 埋桩到今日通电，fail-closed）；②空夹门进直火（门弧非空拒火）
＋门弧（清空: 真）不进消费候选（核销权归声明消费它的方法——打款吃审批函
＝核销权旁落，实证）；③悬账门收窄：普通站对非消费目录休眠（审批夹/
知会夹各一单两站互等＝环形等待），全夹盘点挂结账站（结账: 真）。
判据=磁盘+账+退出码（97号：断言与账不是像素）。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")

LAW函 = """---
i3dna: 消息
主题: "实例/报/{案卷号}/审批夹"
命名: uuid
回音: 有
键:
  - 呈批金额
---
审批函种（send-and-wait：审批人办结核销）。
"""

LAW单 = """---
i3dna: 消息
主题: "实例/报/{案卷号}/知会夹"
命名: uuid
回音: 无
键:
  - 知会事由
---
知会单种（fire-and-forget：收讫两件套）。
"""

TASK审批 = """---
i3dna: 微任务
执行者: 人
输入:
  - 路径: "{实例}/报销/核算单.md"
    描述: 审批矩阵·门上（认定金额 ≥5000）
    使能条件: {取值: 认定金额, 不小于: 5000}
  - "实例/报/{案卷号}/审批夹"
产物:
  - "{实例}/审批/审批单.md"
---
人工工位：办结核销审批夹一张。
"""

TASK收阅 = """---
i3dna: 微任务
执行者: 人
输入:
  - "实例/报/{案卷号}/知会夹"
---
人工工位：收讫两件套（核销＋入账）。
"""

TASK付款 = """---
i3dna: 微任务
输入:
  - 路径: "{实例}/审批/审批单.md"
    描述: 批示门
    使能条件: {取值: 批示, 等于: 同意}
  - 路径: "实例/报/{案卷号}/审批夹"
    描述: 空夹门（函不清不付款）
    清空: 真
产物:
  - "{实例}/结算/回单.md"
---
出纳：按认定金额出回单。
"""

STUB = """import os, re, sys
prompt = sys.stdin.read()
for p in re.findall(r"【产物→写到】(\\S+)", prompt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"桩产物 {os.path.basename(p)}\\n")
print("完成")
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, closing=False):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/报/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 报\n")
    _mk(r, "域/x域/类/报/消息/审批函.md", LAW函)
    _mk(r, "域/x域/类/报/消息/知会单.md", LAW单)
    _mk(r, "域/x域/类/报/方法/审批/任务.md", TASK审批)
    _mk(r, "域/x域/类/报/方法/收阅/任务.md", TASK收阅)
    pay = TASK付款 if not closing else \
        TASK付款.replace("i3dna: 微任务\n", "i3dna: 微任务\n结账: 真\n")
    _mk(r, "域/x域/类/报/方法/付款/任务.md", pay)
    _mk(r, "实例/报/c1/报销/核算单.md",
        "---\n认定金额: 12800\n---\n核算。\n")
    _mk(r, "实例/报/c1/审批/审批单.md",
        "---\n批示: 同意\n---\n批。\n")
    box = os.path.join(r, "实例", "报", "c1", "审批夹")
    os.makedirs(box, exist_ok=True)
    _mk(r, "实例/报/c1/审批夹/审批函__a1.md",
        "---\n呈批金额: 12800\n---\n函。\n")
    _mk(r, "实例/报/c1/知会夹/知会单__a1.md",
        "---\n知会事由: 已送审\n---\n单。\n")
    _mk(r, "桩.py", STUB)
    return r


def _fire(r, task_rel="域/x域/类/报/方法/付款", case="c1"):
    return subprocess.run(
        [sys.executable, ENGINE, "run", os.path.join(r, task_rel),
         "--root", r, "--case", case,
         "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}"],
        capture_output=True, text=True, timeout=120)


def _settle(r, task_rel, case="c1"):
    return subprocess.run(
        [sys.executable, ENGINE, "backfill", os.path.join(r, task_rel),
         "--root", r, "--case", case],
        capture_output=True, text=True, timeout=60)


def _acc(r, method):
    return json.load(open(os.path.join(
        r, "实例", "报", "c1", "__账", method, "__结果.json"), encoding="utf-8"))


def test_条件门_批示不同意拒火_零副作用(tmp_path):
    """①fire 前置接使能条件（fail-closed）：批示不同意＝付款永不使能；
    拒火零副作用——无产物、无账、门弧单不动。"""
    r = _tree(tmp_path)
    _mk(r, "实例/报/c1/审批/审批单.md", "---\n批示: 不同意\n---\n批。\n")
    p = _fire(r)
    assert p.returncode != 0
    out = p.stdout + p.stderr
    assert "使能条件不满足" in out and "批示" in out
    assert not os.path.exists(os.path.join(r, "实例/报/c1/结算/回单.md"))
    assert not os.path.exists(os.path.join(r, "实例/报/c1/__账/付款"))
    assert os.listdir(os.path.join(r, "实例/报/c1/审批夹")) \
        == ["审批函__a1.md"], "拒火不吃任何单"


def test_条件门_审批矩阵越权拒办结(tmp_path):
    """①settle 同接使能条件：门上站（≥5000）收 300＝越权，拒办结零入账；
    12800 正路放行（审批矩阵两臂）。"""
    r = _tree(tmp_path)
    _mk(r, "实例/报/c1/报销/核算单.md", "---\n认定金额: 300\n---\n核算。\n")
    p = _settle(r, "域/x域/类/报/方法/审批")
    assert p.returncode != 0
    out = p.stdout + p.stderr
    assert "使能条件不满足" in out and "300" in out
    assert not os.path.exists(os.path.join(r, "实例/报/c1/__账/审批"))
    assert os.listdir(os.path.join(r, "实例/报/c1/审批夹")) \
        == ["审批函__a1.md"], "拒办结不吃单"
    _mk(r, "实例/报/c1/报销/核算单.md", "---\n认定金额: 12800\n---\n核算。\n")
    p2 = _settle(r, "域/x域/类/报/方法/审批")
    assert p2.returncode == 0, p2.stderr[-400:]


def test_空夹门_直火拒火_门弧不被吃(tmp_path):
    """②空夹门进直火（此前只在推进判据——直火绕过＝门弧被吃）：审批函
    在场＝悬账在场，拒火；任何火不消费门弧（清空: 真 只读）的单——
    核销权归声明消费它的方法（审批），不归付款。"""
    r = _tree(tmp_path)
    p = _fire(r)
    assert p.returncode != 0
    out = p.stdout + p.stderr
    assert "空夹门" in out and "审批夹" in out
    assert os.listdir(os.path.join(r, "实例/报/c1/审批夹")) \
        == ["审批函__a1.md"], "门弧的单不被吃（核销权不旁落）"
    assert not os.path.exists(os.path.join(r, "实例/报/c1/__账/付款"))


def test_普通站_他队列不拦_死锁破(tmp_path):
    """③悬账门收窄（缺陷19）：普通办结对非消费主题目录休眠——审批夹/
    知会夹各一单、审批与收阅互等＝环形等待（报销003 实证）。两站各办
    各的，互不拦；消费方办结即吃一张（豁免语义原样）。"""
    r = _tree(tmp_path)
    p1 = _settle(r, "域/x域/类/报/方法/审批")     # 知会夹 1 单在场
    assert p1.returncode == 0, p1.stderr[-400:]
    assert os.listdir(os.path.join(r, "实例/报/c1/审批夹")) == []
    assert _acc(r, "审批")["消费清单"][0]["名称"].endswith("审批函__a1.md")
    p2 = _settle(r, "域/x域/类/报/方法/收阅")     # 审批夹已空，老法也过——
    assert p2.returncode == 0, p2.stderr[-400:]   # 但若审批夹有单也不拦
    assert os.listdir(os.path.join(r, "实例/报/c1/知会夹")) == []


def test_结账站_全夹盘点两臂(tmp_path):
    """③结账站（结账: 真）：点火即打烊——本案卷全部主题夹盘点，有单拒火
    （终点站等全夹清零）；清零放行。消费弧容恰一张（本火即吃）。"""
    r = _tree(tmp_path, closing=True)
    _settle(r, "域/x域/类/报/方法/审批")           # 吃函；知会夹仍有 1 单
    p = _fire(r)                                   # 空夹门过（审批夹空）
    assert p.returncode != 0
    out = p.stdout + p.stderr
    assert "结账门" in out and "知会夹" in out
    assert not os.path.exists(os.path.join(r, "实例/报/c1/__账/付款"))
    _settle(r, "域/x域/类/报/方法/收阅")           # 吃单——全夹清零
    p2 = _fire(r)
    assert p2.returncode == 0, p2.stderr[-500:]
    assert os.path.isfile(os.path.join(r, "实例/报/c1/结算/回单.md"))


def test_收讫两件套_行为不变(tmp_path):
    """③钉：回音: 无＝收讫两件套（核销＋入账，无转正无产物）——收窄
    悬账门不扰此语义。"""
    r = _tree(tmp_path)
    p = _settle(r, "域/x域/类/报/方法/收阅")
    assert p.returncode == 0, p.stderr[-400:]
    acc = _acc(r, "收阅")
    assert acc["产物清单"] == [] and not acc.get("回收清单")
    assert acc["消费清单"][0]["名称"].endswith("知会单__a1.md")
    assert os.listdir(os.path.join(r, "实例/报/c1/知会夹")) == []


def test_推进侧_条件门与结账门挂起(tmp_path):
    """①③推进判据同门挂起（converge 不炸）：批示不同意→条件门挂起跳过
    （不点火）；批示同意但知会单在→结账站等全夹清零。"""
    sys.path.insert(0, os.path.dirname(ENGINE))
    import i3dna_engine as eng  # noqa: E402
    r = _tree(tmp_path, closing=True)
    tdir = os.path.join(r, "域/x域/类/报/方法/付款")
    need, why = eng._task_needs_fire(tdir, r, case="c1")
    assert not need and "空夹门" in why          # 审批夹 1 函＝第一道拦
    _settle(r, "域/x域/类/报/方法/审批")           # 吃函
    _mk(r, "实例/报/c1/审批/审批单.md", "---\n批示: 不同意\n---\n批。\n")
    need2, why2 = eng._task_needs_fire(tdir, r, case="c1")
    assert not need2 and ("条件门" in why2 or "使能条件" in why2)
    _mk(r, "实例/报/c1/审批/审批单.md", "---\n批示: 同意\n---\n批。\n")
    need3, why3 = eng._task_needs_fire(tdir, r, case="c1")
    assert not need3 and "结账门" in why3        # 知会夹 1 单＝打烊拦

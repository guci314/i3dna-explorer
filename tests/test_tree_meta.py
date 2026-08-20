#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_tree_meta — 树自描述性规格面测试（类「目录树元知识」，纯 M1 元层）。

裁决（2026-08-19）：元知识是定义不是数据——类不实例化（无档案袋，
99 号：类树是容器，本容器不装 bean）。知识卡住类自带 知识/（与
研发/知识/ 同款正统形态），可执行自检住 校验程序/。
机械契约（零 LLM）：
1) 类种：目录树元知识＝实体类（类.md 范畴=实体、无 方法/）
2) 不实例化：实例/目录树元知识 不在场
3) 自描述完备：知识/ 九卡同名非空；校验程序在场
"""
import os

import pytest

# 树在引擎仓（explorer 已迁出独立安家）：环境变量可指路，缺省认旧仓
M1 = os.path.join(os.environ.get("I3DNA_HOME")
                  or os.path.expanduser("~/work/report_generate"),
                  "md-devloop-m1")
CARDS = ["双网", "弧记号", "槽家族", "点火与账", "悬账与持有单",
         "域与场所", "主体与登录", "组织变更案卷化", "类手术", "lint判据",
         "案卷与实例"]


QT_CARDS = ["验收五条律", "三条死路", "三层体系与打桩", "对象名驱动"]


@pytest.mark.unit
def test_qt_knowledge_class():
    """Qt知识类（研发域，纯 M1）：平台验收知识上树——出处 vault 97 号。"""
    import i3dna_core as core
    t = core.mdl.树根(M1)
    c = t.找类("Qt知识")
    assert c is not None, "类「Qt知识」不在树（研发域）"
    assert core.eng.get_value(os.path.join(c.path, "类.md"), "实例化") == "否"
    assert not os.path.isdir(os.path.join(M1, "实例", "Qt知识")), \
        "纯 M1 元层——不得有实例架"
    for k in QT_CARDS:
        card = os.path.join(c.path, "知识", f"{k}.md")
        assert os.path.isfile(card), f"知识/ 缺卡片「{k}」"
        assert open(card, encoding="utf-8").read().strip(), f"空卡「{k}」"


@pytest.mark.unit
def test_first_edge_aggregation():
    """首例关系边（缺陷#8 还债）：女娲 ◇→ 目录树元知识，UML 聚合。"""
    import i3dna_core as core
    t = core.mdl.树根(M1)
    es = t.找类("女娲").关系们()
    assert es, "女娲→目录树元知识 聚合边缺席"
    e = es[0]
    assert e.种 == "聚合" and e.类型 == "手术参照"
    assert "目录树元知识" in e.目标类名
    assert t.找类(e.目标类名) is not None, "边悬空：目标类不在树"


@pytest.mark.unit
def test_tree_meta_pure_m1_class():
    import i3dna_core as core
    t = core.mdl.树根(M1)
    c = t.找类("目录树元知识")
    assert c is not None, "类「目录树元知识」不在树"
    assert not os.path.isdir(os.path.join(c.path, "方法")), "应为实体类"
    类md = os.path.join(c.path, "类.md")
    assert os.path.isfile(类md)
    v = core.eng.get_value(类md, "范畴")
    assert v == "实体"
    assert core.eng.get_value(类md, "实例化") == "否"
    # 不实例化：无档案袋
    assert not os.path.isdir(os.path.join(M1, "实例", "目录树元知识")), \
        "纯 M1 元层——不得有实例架"
    # 自描述完备：九卡 + 校验程序
    for k in CARDS:
        card = os.path.join(c.path, "知识", f"{k}.md")
        assert os.path.isfile(card), f"知识/ 缺卡片「{k}」"
        assert open(card, encoding="utf-8").read().strip(), f"空卡「{k}」"
    assert os.path.isfile(os.path.join(c.path, "校验程序", "主程序.py"))

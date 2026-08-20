#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_place_view — 场所视角规格面测试（ARCHITECTURE §4 运行时投影面）。

裁决依据：域=物理聚簇（类住 域/<域>/类/）、场所=派生拓扑（根场所=企业，
部门场所=域，场内实例集=域内类的实例架并集）——Bean 平铺不搬目录，
场所是同一份实例库的运行时分组视图（99/95/91 号）。
机械契约（零 LLM）：
1) core.场所拓扑：根场所=全类；部门场所类集=域.类们()；无域树退化为仅根场所
2) 视角切换：目录视角=文件系统直射；场所视角=企业→部门场所→架→实例，
   节点全带真路径（选中/菜单与目录视角同源）；域外架与企业共享面挂根场所
"""
import os

import pytest


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


TASK = """---
i3dna: 微任务
输入:
  - "{实例}/订单/订单.md"
产物:
  - "{实例}/结算/结算单.md"
---
按订单结算。
"""


@pytest.fixture
def tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/堂食域/域.md", "---\ni3dna: 域\n域主: 堂食部\n职责: 堂食\n---\n")
    _mk(r, "域/外卖域/域.md", "---\ni3dna: 域\n域主: 外卖部\n职责: 外卖\n---\n")
    _mk(r, "域/夜宵域/域.md", "---\ni3dna: 域\n域主: 夜宵部\n职责: 夜宵\n---\n")
    _mk(r, "域/外卖域/类/购/方法/下单/任务.md", TASK)
    _mk(r, "域/堂食域/类/仓/方法/盘点/任务.md", TASK)
    _mk(r, "域/夜宵域/类/摆/方法/出摊/任务.md", TASK)   # 未认领域=引导态
    _mk(r, "类/散/方法/巡检/任务.md", TASK)          # 老形平铺类=域外
    _mk(r, "实例/购/A/订单/订单.md", "x")
    _mk(r, "实例/仓/B/订单/订单.md", "x")
    _mk(r, "实例/摆/E/订单/订单.md", "x")
    _mk(r, "实例/散/C/订单/订单.md", "x")
    _mk(r, "消息/持有单.md",
        "---\n键: [k]\n路径: 实例/*/*/持有单__{案卷号}.md\n---\n")
    _mk(r, "知识/执行契约.md", "契约")
    _mk(r, "场所/联营台.md",
        "---\ni3dna: 场所\n装配: [外卖域, 堂食域]\n---\n")
    return r


@pytest.mark.unit
def test_place_topology(tree):
    import i3dna_core as core
    topo = core.场所拓扑(tree)
    roots = [t for t in topo if t[1]]
    doms = {t[0]: sorted(t[2]) for t in topo if not t[1]}
    assert len(roots) == 1 and roots[0][2]          # 根场所=全类（含散类）
    # 费米律（8-19）：已认领域（外卖/堂食）的部门场所退出，由联营台接管
    assert "外卖域" not in doms and "堂食域" not in doms
    assert doms["夜宵域"] == ["摆"]                  # 未认领域保留引导态
    decl = {t[0]: t for t in topo if t[3] == "声明"}
    assert sorted(decl["联营台"][2]) == ["仓", "购"]   # 装配=跨域类集并集
    assert os.path.isfile(decl["联营台"][4])           # 锚=声明文件本身


@pytest.mark.unit
def test_place_topology_no_domain(tmp_path):
    import i3dna_core as core
    topo = core.场所拓扑(str(tmp_path))
    assert len(topo) == 1 and topo[0][1] and topo[0][2] == []


@pytest.mark.unit
def test_lint_place_assembly(tmp_path):
    """lint ⑥：装配清单域名须真在树；缺装配清单=警告（空场所不入拓扑）。"""
    import i3dna_core as core
    r = str(tmp_path)
    _mk(r, "域/真域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "场所/好台.md", "---\ni3dna: 场所\n装配: [真域]\n---\n")
    _mk(r, "场所/坏台.md", "---\ni3dna: 场所\n装配: [不存在域]\n---\n")
    _mk(r, "场所/空台.md", "---\ni3dna: 场所\n---\n")
    rep = core.lint.Report()
    core.lint.lint_logical_model(r, rep)
    assert any("不在树" in m for _, m in rep.errors)
    assert any("缺「装配」" in m for _, m in rep.warnings)


@pytest.mark.unit
def test_view_switch(tree, qapp):
    import importlib
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    w._assist_proc_run = lambda p: None      # 桩 LLM 车道
    w._engine_qproc = lambda args, msg, verb=None: None   # 桩引擎
    # 目录视角：文件系统直射，顶层含 域/ 与 案卷（实例库）
    top = w.tree.model().item(0, 0)
    texts0 = [top.child(i).text() for i in range(top.rowCount())]
    assert any(t == "域" for t in texts0)
    assert any("案卷" in t for t in texts0)
    # 切场所视角：企业→部门场所→架→实例，节点带真路径
    w.cb_view.setCurrentIndex(1)
    ent = w.tree.model().item(0, 0)
    assert "企业" in ent.text()
    assert os.path.isdir(ent.data(ex.ROLE_PATH))
    kids = [ent.child(i) for i in range(ent.rowCount())]
    dom_nodes = [k for k in kids if "部门场所" in k.text()]
    # 费米律（8-19）：只有未认领域（夜宵域）保留部门场所
    assert {n.text().split("（")[0].replace("🏭", "").strip()
            for n in dom_nodes} == {"夜宵域"}
    for n in dom_nodes:
        assert os.path.isdir(n.data(ex.ROLE_PATH))   # 场所节点=真目录
        if "夜宵域" in n.text():
            架 = n.child(0)
            assert "摆" in 架.text()
            assert 架.data(ex.ROLE_PATH) == os.path.join(tree, "实例", "摆")
            assert "E" in 架.child(0).text()         # 实例在架下
    # 声明场所（N:M 装配）：跨域并集挂同一场所，锚=声明文件
    asm = [k for k in kids if "装配场所" in k.text()]
    assert len(asm) == 1 and "联营台" in asm[0].text()
    架名 = [asm[0].child(i).text() for i in range(asm[0].rowCount())]
    assert any("购" in x for x in 架名) and any("仓" in x for x in 架名)
    assert os.path.isfile(asm[0].data(ex.ROLE_PATH))
    # 域外架（散）与企业共享面挂根场所
    flat = [k.text() for k in kids]
    assert any("散" in t for t in flat)
    assert any("消息" in t for t in flat) and any("知识" in t for t in flat)
    # 切回目录视角恢复直射
    w.cb_view.setCurrentIndex(0)
    top = w.tree.model().item(0, 0)
    assert "企业" not in top.text()
    w.close()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_new_case — 女娲可用性三刀（8-19）：
①新案卷入口（方法节点一键立案，免手工 mkdir）
②办结即导航（产物落点自动定位——建完不用找）
③重办结防覆盖（同案卷有账且输入变→明示将改写旧账，格式卡第四条）
判据=文件/树选中/状态栏/账面，桩在边界（QInputDialog/QMessageBox）。"""
import importlib
import json
import os

import pytest

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


@pytest.fixture
def tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    return r


@pytest.mark.unit
def test_新案卷_建架开稿(tree, qtbot, monkeypatch):
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    monkeypatch.setattr(ex.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("案X", True)))
    item = w.items_by_path[os.path.join(tree, "域/x域/类/甲/方法/办")]
    w.do_new_case(item)
    apply_path = os.path.join(tree, "实例", "甲", "案X", "申请.md")
    assert os.path.isfile(apply_path), "未建案卷/申请稿"
    assert w._edit_path == apply_path, "编辑器没开在申请上"
    assert "案卷已立" in w.statusBar().currentMessage()
    w.close()


@pytest.mark.unit
def test_新案卷_重名拒绝(tree, qtbot, monkeypatch):
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    monkeypatch.setattr(ex.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("c1", True)))   # 已在
    warns = []
    monkeypatch.setattr(ex.QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warns.append(a) or None))
    item = w.items_by_path[os.path.join(tree, "域/x域/类/甲/方法/办")]
    w.do_new_case(item)
    assert warns and "已存在" in str(warns)
    assert getattr(w, "_edit_path", None) != os.path.join(tree, "实例", "甲", "c1", "申请.md")
    w.close()


@pytest.mark.unit
def test_办结即导航(tree, qtbot):
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    if w.cb_view.count() > 1:
        w.cb_view.setCurrentText("场所")            # 先切走，验证导航切回
    prod = os.path.join(tree, "实例", "甲", "c1", "出.md")
    open(prod, "w", encoding="utf-8").write("产物\n")
    w.refresh()
    w._nav_to(prod)
    assert w.cb_view.currentText() == "目录"
    sel = w.tree.currentIndex().data(ex.ROLE_PATH)
    assert sel in (prod, os.path.dirname(prod))
    assert "产物 →" in w.statusBar().currentMessage()
    w.close()


@pytest.mark.unit
def test_重办结防覆盖(tree, qtbot, monkeypatch):
    """同案卷有账且申请已变 → 问询；答 No=不办结。无漂移=直接放行。"""
    import i3dna_core as core
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    tdir = os.path.join(tree, "域/x域/类/甲/方法/办")
    old = core.eng.sha256(os.path.join(tree, "实例/甲/c1/申请.md"))
    _mk(tree, "实例/甲/c1/__账/办/__结果.json", json.dumps(
        {"输入清单": [{"名称": "实例/甲/c1/申请.md", "sha256": old}]},
        ensure_ascii=False))
    assert w._reenter_ok(tdir, "c1") is True        # 无漂移：不问
    with open(os.path.join(tree, "实例/甲/c1/申请.md"), "a",
              encoding="utf-8") as f:
        f.write("\n改了\n")                          # 申请漂移
    answers = []
    monkeypatch.setattr(
        ex.QMessageBox, "question",
        staticmethod(lambda *a, **k: answers.append(1)
                     or ex.QMessageBox.StandardButton.No))
    assert w._reenter_ok(tdir, "c1") is False       # 答 No=拦下
    assert answers, "输入已变却未问询"
    w.close()


@pytest.mark.unit
def test_confirm_work_挂导航hook(tree, qtbot):
    """确认办结时把作业面路径挂进 nav hook——办结完成即跳。"""
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    tdir = os.path.join(tree, "域/x域/类/甲/方法/办")
    w.open_work_ui(tdir, "c1")
    cap = []
    w._engine_qproc = lambda args, header, verb="执行中", hook=None: \
        cap.append(hook)
    w.confirm_work()
    assert cap and cap[0] and cap[0][0] == "nav"
    assert cap[0][1].endswith(os.path.join("c1", "出.md"))
    w.close()


@pytest.mark.unit
def test_类节点直通实例架(tree, qtbot):
    """类→实例直通（Bean 平铺两枝迷路的一键回程）：类根右键菜单
    「🥚 本类实例（N）」→ 跳到 实例/<类名> 架并选中。"""
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    item = w.items_by_path[os.path.join(tree, "域/x域/类/甲")]
    menu = w.build_dir_menu(item)
    act = next(a for a in menu.actions() if "本类实例" in a.text())
    assert "（1）" in act.text(), act.text()
    act.trigger()
    sel = w.tree.currentIndex().data(ex.ROLE_PATH)
    assert sel == os.path.join(tree, "实例", "甲")
    assert "实例架" in w.statusBar().currentMessage()
    w.close()

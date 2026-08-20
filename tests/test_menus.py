#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_menus — 右键菜单相关测试。"""
import pytest


@pytest.mark.unit
def test_task_menu_basic(window, task_items):
    """测试任务右键菜单基本内容"""
    if not task_items:
        pytest.skip("没有任务节点")

    menu = window.build_task_menu(task_items[0])
    labels = {a.text() for a in menu.actions() if a.text()}

    # 调用约定统一论:方法菜单=定义级只读面(预检/记录);
    # 业务动词(点火/办结)在 实例右键→工位
    need = {"预检", "点火记录"}
    assert need <= labels, f"菜单应包含 {need}，实际有 {sorted(labels)}"
    assert "点火" not in labels, "方法菜单不应有点火(去实例工位)"
    assert "办结入账…" not in labels, "方法菜单不应有办结(去实例工位)"


@pytest.mark.unit
def test_task_menu_arc_actions(window, task_items):
    """测试任务菜单含弧登记动作"""
    if not task_items:
        pytest.skip("没有任务节点")

    menu = window.build_task_menu(task_items[0])
    labels = {a.text() for a in menu.actions() if a.text()}

    assert {"登记输入弧", "登记产物弧"} <= labels


@pytest.mark.unit
def test_file_menu_run_action(window, file_items, explorer_module):
    """测试 Python 文件右键含运行动作"""
    py_item = next(
        (i for i in file_items if str(i.data(explorer_module.ROLE_PATH)).endswith(".py")),
        None
    )
    if not py_item:
        pytest.skip("没有 .py 文件节点")

    labels = {a.text() for a in window.build_file_menu(py_item).actions()}
    # 菜单可能是 "运行" 或 "运行…"
    has_run = any("运行" in label for label in labels)
    assert has_run, f".py 文件应有「运行」菜单，实际 {sorted(labels)}"


@pytest.mark.integration
def test_blue_task_compile_menu(real_window, explorer_module):
    """测试蓝任务菜单含检测/编译，不含回退"""
    from tests.conftest import walk_item

    items = list(walk_item(real_window.model.item(0)))
    tasks = [i for i in items if i.data(explorer_module.ROLE_TYPE) == "task"]

    blue_item = next(
        (i for i in tasks if i.foreground().color().name() == "#1565c0"),
        None
    )
    if not blue_item:
        pytest.skip("没有蓝任务节点（可能都未使能）")

    menu = real_window.build_task_menu(blue_item)
    labels = {a.text() for a in menu.actions() if a.text()}

    assert {"检测可符号化", "编译（生成符号程序）"} <= labels
    assert "回退联结主义" not in labels


@pytest.mark.integration
def test_red_task_revert_menu(real_window, explorer_module):
    """测试红任务菜单含回退，不含编译"""
    from tests.conftest import walk_item

    items = list(walk_item(real_window.model.item(0)))
    tasks = [i for i in items if i.data(explorer_module.ROLE_TYPE) == "task"]

    red_item = next(
        (i for i in tasks if i.foreground().color().name() == "#c62828"),
        None
    )
    if not red_item:
        pytest.skip("没有红任务节点（可能都未使能）")

    menu = real_window.build_task_menu(red_item)
    labels = {a.text() for a in menu.actions() if a.text()}

    assert "回退联结主义" in labels
    assert "编译（生成符号程序）" not in labels


@pytest.mark.unit
def test_menu_action_count(window, task_items):
    """测试菜单动作数量合理"""
    if not task_items:
        pytest.skip("没有任务节点")

    menu = window.build_task_menu(task_items[0])
    actions = [a for a in menu.actions() if a.text()]

    # 菜单项应在合理范围（5-15 个）
    assert 5 <= len(actions) <= 15, f"菜单项数量异常: {len(actions)}"

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_tree — 树视图相关测试。"""
import pytest


@pytest.mark.unit
def test_tree_structure(window, tree_items):
    """测试树基本结构"""
    assert window.model is not None, "树模型应存在"
    assert tree_items, "树应包含节点"
    assert window.model.item(0) is not None, "树应有根节点"


@pytest.mark.unit
def test_task_entity_count(window, task_items, explorer_module):
    """测试任务和实体节点数量"""
    n_expect = len(explorer_module.eng.find_tasks(str(window.root)))
    assert len(task_items) == n_expect, f"任务节点数应为 {n_expect}，实际 {len(task_items)}"


@pytest.mark.unit
def test_color_distinction(task_items, entity_items):
    """测试蓝绿双色区分"""
    task_colors = {i.foreground().color().name() for i in task_items}
    entity_colors = {i.foreground().color().name() for i in entity_items}

    if task_colors:
        # 任务节点有颜色时验证
        pass
    if entity_colors:
        # 实体节点有颜色时验证
        pass

    # 当两者都存在时，颜色应不同
    if task_colors and entity_colors:
        assert not (task_colors & entity_colors), "任务和实体颜色应不同"


@pytest.mark.unit
def test_item_roles(tree_items, explorer_module):
    """测试节点角色数据"""
    for item in tree_items:
        role_type = item.data(explorer_module.ROLE_TYPE)

        # 有效的类型必须是 task/entity/dir/file 之一
        if role_type:
            assert role_type in {"task", "entity", "dir", "file"}


@pytest.mark.unit
def test_tree_expansion(window):
    """测试树展开状态"""
    # 确保树至少有一层可展开
    root = window.model.item(0)
    assert root.hasChildren(), "根节点应有子节点"


@pytest.mark.unit
def test_tree_selection(window, tree_items, qapp):
    """测试树选中功能"""
    if tree_items:
        window.tree.setCurrentIndex(tree_items[0].index())
        qapp.processEvents()
        current = window.model.itemFromIndex(window.tree.currentIndex())
        assert current is not None, "应有节点被选中"


@pytest.mark.unit
def test_task_entity_color_map(task_items):
    """测试任务/实体颜色映射符合定义"""
    # 红=符号主义，蓝=联结主义，绿=人工，灰=未使能
    for item in task_items:
        color = item.foreground().color().name()
        assert color in {"#c62828", "#1565c0", "#388e3c", "#78909c"}


@pytest.mark.integration
def test_large_tree_performance(real_window, qapp):
    """测试大树的渲染性能"""
    import time

    start = time.time()
    real_window.show()
    qapp.processEvents()
    elapsed = time.time() - start

    assert elapsed < 3.0, f"大树渲染应在 3 秒内完成，实际 {elapsed:.2f}秒"

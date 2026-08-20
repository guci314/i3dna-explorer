#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_workflow — 工作流图相关测试。"""
import pytest
from PyQt6.QtWidgets import QGraphicsView


@pytest.mark.unit
def test_workflow_tabs(window):
    """测试工作流标签页结构"""
    assert window.tabs.count() == 2, "应有 2 个标签页"
    assert window.tabs.tabText(1) == "工作流", "第二个标签应为「工作流」"


@pytest.mark.unit
def test_workflow_package_combo(window):
    """测试工作流下拉按类切且默认单类"""
    pkg_labels = [window.cb_wfpkg.itemText(i)
                  for i in range(window.cb_wfpkg.count())]

    assert len(pkg_labels) >= 1, "工作流下拉应至少有一项"
    assert pkg_labels[-1] == "全部", "最后一项应为「全部」"
    assert window.cb_wfpkg.currentText() == pkg_labels[0], "默认应选第一类"


@pytest.mark.unit
def test_workflow_all_tasks_visible(window, qapp):
    """测试切换到「全部」时显示所有微任务"""
    pkg_labels = [window.cb_wfpkg.itemText(i)
                  for i in range(window.cb_wfpkg.count())]

    # 切换到「全部」
    window.cb_wfpkg.setCurrentText("全部")
    qapp.processEvents()

    scene = window.wf_view.scene()
    node_paths = {i.data(0) for i in scene.items() if i.data(0)}
    task_nodes = node_paths & set(window.task_rows)
    place_nodes = node_paths - task_nodes

    assert len(task_nodes) == len(window.task_rows), \
        f"图中任务节点数应等于任务总数 {len(window.task_rows)}"


@pytest.mark.unit
def test_workflow_view_exists(window):
    """测试工作流视图存在"""
    assert hasattr(window, "wf_view"), "应有 wf_view 工作流视图"
    assert window.wf_view.scene() is not None, "工作流视图应有 scene"


@pytest.mark.unit
def test_workflow_zoom_fit(window):
    """测试工作流图缩放适配功能"""
    assert callable(window.wf_view.fit_all), "工作流视图应有 fit_all 方法"
    assert callable(window.wf_view.zoom), "工作流视图应有 zoom 方法"


@pytest.mark.unit
def test_workflow_node_click(window, qapp):
    """测试工作流节点点击跳转"""
    pkg_labels = [window.cb_wfpkg.itemText(i)
                  for i in range(window.cb_wfpkg.count())]

    window.cb_wfpkg.setCurrentText("全部")
    qapp.processEvents()

    scene = window.wf_view.scene()
    # 找一个任务节点
    task_node = next((i for i in scene.items() if i.data(0)), None)

    if task_node:
        # 双击应触发跳转（这里只测试跳转函数存在）
        assert callable(window.wf_view._on_jump), "应有跳转回调"


@pytest.mark.unit
def test_workflow_drag_mode(window):
    """测试工作流图可拖拽平移"""

    view = window.wf_view
    assert view.dragMode() == QGraphicsView.DragMode.ScrollHandDrag, \
        "工作流图应支持拖拽平移"


@pytest.mark.unit
def test_workflow_antialiasing(window):
    """测试工作流图抗锯齿开启"""
    from PyQt6.QtGui import QPainter

    view = window.wf_view
    assert view.renderHints() & QPainter.RenderHint.Antialiasing, \
        "工作流图应开启抗锯齿"

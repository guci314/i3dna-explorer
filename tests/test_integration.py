#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_integration — 集成测试（原 test_explorer.py 的完整场景）。"""
import os
import pytest


@pytest.mark.integration
def test_full_smoke(real_window, explorer_module):
    """完整冒烟测试：模拟原 test_explorer.py 的主要场景"""
    from tests.conftest import walk_item

    win = real_window
    items = list(walk_item(win.model.item(0)))

    # T3: 微任务节点数
    tasks = [i for i in items if i.data(explorer_module.ROLE_TYPE) == "task"]
    entities = [i for i in items if i.data(explorer_module.ROLE_TYPE) == "entity"]
    n_expect = len(explorer_module.eng.find_tasks(str(win.root)))
    assert len(tasks) == n_expect, f"任务节点数应为 {n_expect}"

    # T4: 蓝绿双色
    ct = {i.foreground().color().name() for i in tasks}
    ce = {i.foreground().color().name() for i in entities}
    assert bool(ct) and bool(ce) and not (ct & ce)

    # T5: 右键动作集
    menu = win.build_task_menu(tasks[0])
    labels = {a.text() for a in menu.actions() if a.text()}
    assert {"预检", "点火记录"} <= labels   # 只读面;业务动词在实例工位

    # T8: 登记弧动作
    assert {"登记输入弧", "登记产物弧"} <= labels

    # T18: 引擎下拉
    assert hasattr(win, "cb_engine")
    assert win.cb_engine.count() >= 3
    assert not win.cb_engine.isEditable()

    # T10: 平台钉概念已除（2026-08-19 裁决）——工具栏不得再有平台下拉
    assert not hasattr(win, "cb_platform")

    # T14: 老子聊天条
    from PyQt6.QtWidgets import QLineEdit
    assert isinstance(getattr(win, "chat_input", None), QLineEdit)
    assert len(win._status_context()) > 50

    # T15: 编辑器按钮
    from PyQt6.QtWidgets import QPushButton
    btns = {b.text() for b in win.stack.widget(1).findChildren(QPushButton)}
    assert {"代笔", "保存"} <= btns

    # T17: 工具栏
    from PyQt6.QtGui import QAction
    tb_acts = {a.text() for a in win.findChildren(QAction)}
    assert "推进" in tb_acts

    # T16a: 工作流标签页
    assert win.tabs.count() == 2
    assert win.tabs.tabText(1) == "工作流"


@pytest.mark.integration
def test_highline_flow(real_window, qapp, explorer_module):
    """测试血缘高亮流程"""
    from tests.conftest import walk_item

    win = real_window
    items = list(walk_item(win.model.item(0)))
    m1 = next((i for i in items
               if i.data(explorer_module.ROLE_TYPE) == "task"
               and i.data(explorer_module.ROLE_PATH).endswith("_通用程序")), None)

    if m1 is not None:
        win.tree.setCurrentIndex(m1.index())
        qapp.processEvents()
        hl = {i.data(explorer_module.ROLE_PATH) for i in win.hl_items}
        assert len(hl) > 0, "选中任务应有血缘高亮"


@pytest.mark.integration
def test_file_content_render(real_window, qapp, explorer_module):
    """测试文件内容渲染"""
    from tests.conftest import walk_item

    win = real_window
    items = list(walk_item(win.model.item(0)))

    # 找索引文件
    idx_leaf = next((i for i in items
                     if i.data(explorer_module.ROLE_TYPE) == "file"
                     and str(i.data(explorer_module.ROLE_PATH)).endswith("索引文件.xlsx")), None)

    if idx_leaf is not None:
        win.tree.setCurrentIndex(idx_leaf.index())
        qapp.processEvents()
        html = win.detail.toHtml()
        assert "目录-文件名称" in html or len(html) > 100


@pytest.mark.integration
@pytest.mark.slow
def test_large_package_performance(real_window, qapp):
    """测试大包性能（应该 < 3 秒）"""
    import time
    from tests.conftest import walk_item

    start = time.time()
    real_window.show()
    qapp.processEvents()

    items = list(walk_item(real_window.model.item(0)))
    elapsed = time.time() - start

    assert elapsed < 3.0, f"大包渲染应在 3 秒内完成，实际 {elapsed:.2f}秒"
    assert len(items) > 10, "大包应有足够多的节点"


@pytest.mark.integration
def test_combo_engines(real_window):
    """测试引擎组合"""
    win = real_window

    # 验证引擎选项（引擎名称可能变化，只要至少有选项即可）
    engines = [win.cb_engine.itemText(i) for i in range(win.cb_engine.count())]
    assert len(engines) >= 3, f"应至少有 3 个引擎选项，实际 {len(engines)}"
    # 检查包含一些已知的关键词
    has_known = any(kw in " ".join(engines).lower() for kw in ["glm", "deepseek", "qwen", "zai"])
    assert has_known, f"引擎列表应包含已知引擎，实际 {engines}"


@pytest.mark.integration
def test_progressive_symbolization(real_window, qapp, explorer_module):
    """测试渐进式符号化：蓝→红菜单变化"""
    from tests.conftest import walk_item
    import shutil

    win = real_window
    items = list(walk_item(win.model.item(0)))

    # 找一个蓝任务
    blue_task = next(
        (i for i in items
         if i.data(explorer_module.ROLE_TYPE) == "task"
         and i.foreground().color().name() == "#1565c0"
         and i.data(explorer_module.ROLE_PATH)), None
    )

    if not blue_task:
        pytest.skip("没有蓝任务")

    t_dir = blue_task.data(explorer_module.ROLE_PATH)
    ed_dir = os.path.join(t_dir, "执行程序")

    # 临时创建执行程序目录
    os.makedirs(ed_dir, exist_ok=True)
    try:
        with open(os.path.join(ed_dir, "主程序.py"), "w") as f:
            f.write("print('test')")

        win.refresh()
        qapp.processEvents()

        # 重新查找该任务
        items2 = list(walk_item(win.model.item(0)))
        red_item = next(i for i in items2 if i.data(explorer_module.ROLE_PATH) == t_dir)
        c_red = red_item.foreground().color().name()

        # 验证变为红色
        assert c_red == "#c62828", f"创建执行程序后应变红，实际 {c_red}"

        # 验证菜单变化
        menu = win.build_task_menu(red_item)
        labels = {a.text() for a in menu.actions() if a.text()}
        assert "回退联结主义" in labels
        assert "编译（生成符号程序）" not in labels

    finally:
        shutil.rmtree(ed_dir, ignore_errors=True)
        win.refresh()

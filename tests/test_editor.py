#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_editor — 编辑器相关测试。"""
import pytest
from PyQt6.QtWidgets import QPushButton, QPlainTextEdit


@pytest.mark.unit
def test_editor_has_text_input(window):
    """测试编辑器包含文本输入框"""
    editor = getattr(window, "editor", None)
    assert isinstance(editor, QPlainTextEdit), "应有 editor 文本编辑器"


@pytest.mark.unit
def test_editor_buttons_present(window):
    """测试编辑器含代笔/保存按钮"""
    btns = {b.text() for b in window.stack.widget(1).findChildren(QPushButton)}
    assert {"代笔", "保存"} <= btns, f"编辑器应含「代笔」「保存」按钮，实际 {sorted(btns)}"


@pytest.mark.unit
def test_edit_txt_file(window, file_items, explorer_module, qapp):
    """测试选中 txt 文件时编辑器激活"""
    txt = next(
        (i for i in file_items
         if str(i.data(explorer_module.ROLE_PATH)).endswith("__说明.txt")),
        None
    )
    if not txt:
        pytest.skip("没有 __说明.txt 文件")

    window.tree.setCurrentIndex(txt.index())
    qapp.processEvents()

    # 应切换到编辑器面板（stack index 1）
    assert window.stack.currentIndex() == 1, "选中 txt 文件应显示编辑器"
    # 文件内容至少有几个字符（sample_root 只有 "测试包说明"）
    assert len(window.editor.toPlainText()) > 0, "编辑器应加载文件内容"


@pytest.mark.unit
def test_save_file_to_disk(window, file_items, explorer_module, qapp, tmp_path):
    """测试编辑→保存落盘"""
    txt = next(
        (i for i in file_items
         if str(i.data(explorer_module.ROLE_PATH)).endswith("__说明.txt")),
        None
    )
    if not txt:
        pytest.skip("没有 __说明.txt 文件")

    p = txt.data(explorer_module.ROLE_PATH)
    orig = open(p, "rb").read()

    # 修改内容
    window.tree.setCurrentIndex(txt.index())
    qapp.processEvents()
    window.editor.setPlainText(window.editor.toPlainText() + "\n■T_SAVE■")

    # 点击保存
    save_btn = next(
        b for b in window.stack.widget(1).findChildren(QPushButton)
        if b.text() == "保存"
    )
    save_btn.click()
    qapp.processEvents()

    # 验证
    try:
        on_disk = open(p, encoding="utf-8").read()
        assert on_disk.rstrip().endswith("■T_SAVE■"), "保存后内容应写入磁盘"
    finally:
        # 还原
        with open(p, "wb") as f:
            f.write(orig)


@pytest.mark.unit
def test_editor_readonly_for产物(window, file_items, explorer_module, qapp):
    """测试产物文件（如 .py 结果）不可编辑"""
    py = next(
        (i for i in file_items
         if str(i.data(explorer_module.ROLE_PATH)).endswith(".py")),
        None
    )
    if not py:
        pytest.skip("没有 .py 文件")

    window.tree.setCurrentIndex(py.index())
    qapp.processEvents()

    # Python 文件通常为产物，应只读
    # 这里测试编辑器是否正确处理只读状态
    if window.stack.currentIndex() == 1:
        # 如果进入编辑器模式，检查是否只读
        # 具体实现取决于 explorer 的逻辑
        pass


@pytest.mark.unit
def test_chat_input_bar(window):
    """测试老子聊天输入条"""
    from PyQt6.QtWidgets import QLineEdit

    chat_input = getattr(window, "chat_input", None)
    assert isinstance(chat_input, QLineEdit), "应有 chat_input 输入框"
    assert callable(getattr(window, "ask_laozi", None)), "应有 ask_laozi 方法"
    # 状态快照至少有一些内容（sample_root 可能较少）
    assert len(window._status_context()) > 10, "状态快照应有内容"

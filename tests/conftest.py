#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conftest — pytest fixtures for i3dna-explorer testing."""
import os
import sys
from pathlib import Path

import pytest

# 确保 QT_QPA_PLATFORM 设置为 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = Path(__file__).parent
ROOT = HERE.parent
PROJECT_ROOT = ROOT.parent

# 添加模块路径
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 导入主模块（延迟导入，确保 QT_QPA_PLATFORM 生效）
import importlib.util
spec = importlib.util.spec_from_file_location(
    "i3dna_explorer", str(ROOT / "i3dna_explorer.py"))
if spec is None:
    raise ImportError(f"无法从 {ROOT / 'i3dna_explorer.py'} 创建模块规范")
ex = importlib.util.module_from_spec(spec)
if spec.loader is None:
    raise ImportError("模块规范缺少 loader")
spec.loader.exec_module(ex)

# 导入 PyQt6
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """全局 QApplication 实例（session 级别复用）"""
    app = QApplication.instance() or QApplication([])
    yield app
    # session 结束时不退出 QApplication（可能被其他测试使用）


@pytest.fixture
def sample_root(tmp_path):
    """创建最小测试包结构"""
    # 基础目录结构
    dirs = [
        "_通用程序",
        "_智能体-地质勘察",
        "_测试蓝任务",
        "_测试红任务",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # 创建必要文件
    (tmp_path / "_通用程序" / "主程序.py").write_text("print('通用程序')", encoding="utf-8")
    (tmp_path / "_智能体-地质勘察" / "开发文本.md").write_text("# 地质勘察\n\n上下文合成文本", encoding="utf-8")

    # 创建任务节点（需要 任务.md）
    (tmp_path / "_测试蓝任务" / "任务.md").write_text(
        "---\n执行者: LLM\n---\n# 测试蓝任务\n",
        encoding="utf-8"
    )
    (tmp_path / "_测试红任务" / "任务.md").write_text(
        "---\n执行者: 程序\n---\n# 测试红任务\n",
        encoding="utf-8"
    )
    # 红任务需要有执行程序
    (tmp_path / "_测试红任务" / "执行程序").mkdir(exist_ok=True)
    (tmp_path / "_测试红任务" / "执行程序" / "主程序.py").write_text(
        "print('红任务')",
        encoding="utf-8"
    )

    (tmp_path / "__说明.txt").write_text("测试包说明", encoding="utf-8")
    (tmp_path / "索引文件.xlsx").write_bytes(b"PK")  # 模拟 Excel 文件头

    yield tmp_path


@pytest.fixture
def window(qapp, sample_root):
    """创建 Explorer 窗口实例（每个测试独立）"""
    wcls = next(
        (o for _, o in __import__("inspect").getmembers(ex, __import__("inspect").isclass)
         if issubclass(o, __import__("PyQt6.QtWidgets", fromlist=["QMainWindow"]).QMainWindow)
         and o is not __import__("PyQt6.QtWidgets", fromlist=["QMainWindow"]).QMainWindow),
        None
    )
    if wcls is None:
        pytest.skip("无法找到主窗口类")

    win = wcls(str(sample_root))
    yield win
    win.close()


@pytest.fixture
def real_window(qapp):
    """使用真实 8.5 包的窗口（用于集成测试）"""
    real_root = ROOT.parent / "8.5"
    if not real_root.exists():
        pytest.skip(f"真实包根不存在: {real_root}")

    wcls = next(
        (o for _, o in __import__("inspect").getmembers(ex, __import__("inspect").isclass)
         if issubclass(o, __import__("PyQt6.QtWidgets", fromlist=["QMainWindow"]).QMainWindow)
         and o is not __import__("PyQt6.QtWidgets", fromlist=["QMainWindow"]).QMainWindow),
        None
    )
    if wcls is None:
        pytest.skip("无法找到主窗口类")

    win = wcls(str(real_root))
    yield win
    win.close()


@pytest.fixture(autouse=True)
def _isolate_recent(monkeypatch, tmp_path):
    """隔离最近目录文件:窗口构造会写 recent,测试不得污染真实 ~/.i3dna-explorer。"""
    import i3dna_core as core
    monkeypatch.setattr(core, "RECENT_FILE", str(tmp_path / "recent.json"))


def walk_item(item):
    """递归遍历 QStandardItem 树"""
    yield item
    for i in range(item.rowCount()):
        yield from walk_item(item.child(i))


@pytest.fixture
def tree_items(window):
    """获取树的所有节点"""
    return list(walk_item(window.model.item(0)))


@pytest.fixture
def task_items(tree_items):
    """获取所有任务节点"""
    return [i for i in tree_items if i.data(ex.ROLE_TYPE) == "task"]


@pytest.fixture
def entity_items(tree_items):
    """获取所有实体节点"""
    return [i for i in tree_items if i.data(ex.ROLE_TYPE) == "entity"]


@pytest.fixture
def file_items(tree_items):
    """获取所有文件节点"""
    return [i for i in tree_items if i.data(ex.ROLE_TYPE) == "file"]


@pytest.fixture(scope="session")
def explorer_module():
    """提供 explorer 模块（包含 ROLE_TYPE, ROLE_PATH 等常量）"""
    return ex


# pytest 配置
def pytest_configure(config):
    """pytest 配置钩子"""
    config.addinivalue_line("markers", "slow: 标记慢速测试")
    config.addinivalue_line("markers", "visual: 标记视觉/快照测试")
    config.addinivalue_line("markers", "integration: 标记集成测试（需真实包）")
    config.addinivalue_line("markers", "unit: 标记单元测试")

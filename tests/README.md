# i3dna-explorer 测试

PyQt6 应用的现代测试套件，使用 pytest-qt 框架。

## 安装

```bash
pip install -r requirements-test.txt
```

## 运行测试

```bash
# 所有测试
pytest

# 只运行单元测试（快）
pytest -m unit

# 只运行集成测试（需真实包）
pytest -m integration

# 跳过慢速测试
pytest -m "not slow"

# 详细输出
pytest -vv

# 覆盖率报告
pytest --cov=i3dna_explorer --cov-report=html
```

## 测试结构

```
tests/
├── conftest.py              # 共享 fixtures
├── test_tree.py             # 树视图测试
├── test_menus.py            # 右键菜单测试
├── test_editor.py           # 编辑器测试
├── test_workflow.py         # 工作流图测试
├── test_lint.py             # Lint/修复提案测试
└── test_integration.py      # 集成测试
```

## Fixtures

- `qapp` - QApplication 实例（session 级别）
- `window` - 测试窗口实例（使用临时测试数据）
- `real_window` - 真实包窗口实例（需 8.5 目录存在）
- `sample_root` - 最小测试包结构
- `explorer_module` - explorer 模块（含常量）
- `tree_items` / `task_items` / `entity_items` / `file_items` - 节点集合

## 标记

- `unit` - 单元测试（独立、快速）
- `integration` - 集成测试（需真实环境）
- `slow` - 慢速测试（>1 秒）
- `visual` - 视觉/快照测试

## 最佳实践

1. **分层测试**：业务逻辑 → 组件 → 集成
2. **Fixture 复用**：使用 conftest 共享
3. **标记明确**：用 markers 区分测试类型
4. **独立性**：每个测试应独立运行
5. **快速失败**：关键路径优先

## 无头模式

测试默认使用 `QT_QPA_PLATFORM=offscreen`，不弹窗。

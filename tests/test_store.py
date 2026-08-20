#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_store — 持久化层测试：底物识别 / 弧 round-trip / 账双底物。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "..", "i3dna-engine")
sys.path.insert(0, ENGINE)
import i3dna_store as st  # type: ignore[import]  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def md_task(tmp_path):
    d = tmp_path / "任务.md"
    d.write_text("---\ni3dna: 微任务\n输入:\n  - 路径: 实例/K1/钻孔.md\n"
                 "    描述: 钻孔\n产物:\n  - 路径: 实例/K1/分层.md\n"
                 "---\n按孔深划分地层。\n", encoding="utf-8")
    return tmp_path


class TestDefStoreDetect:
    def test_md_family(self, md_task):
        s = st.open_def_store(str(md_task))
        assert s is not None and s.kind == "frontmatter"

    def test_unknown_dir(self, tmp_path):
        assert st.open_def_store(str(tmp_path)) is None

    def test_xlsx_family(self, tmp_path):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.create_sheet("参数")
        ws.append(["【序号】", "【参数文件目录】", "【参数文件名称】",
                   "【参数文件类型】", "【参数文件版本】", "【描述】"])
        ws.append([1, "*", "钻孔.md", "xxx_输入参数文件】", "", "钻探数据"])
        wb.save(str(tmp_path / "__demo_大模型智能体_v1版本.xlsx"))
        s = st.open_def_store(str(tmp_path))
        assert s is not None and s.kind == "参数表"
        rows = s.load_arcs()[1]
        assert rows[0]["pname"] == "钻孔.md" and rows[0]["kind"] == "输入"


class TestMdRoundTrip:
    def test_load_save_load(self, md_task):
        s = st.open_def_store(str(md_task))
        instruction, rows = s.load_arcs()
        s.save_arcs(rows, instruction, extra_fm={"i3dna": "微任务"})
        instruction2, rows2 = s.load_arcs()
        assert instruction2 == instruction
        assert [(r["kind"], r["pdir"], r["pname"]) for r in rows2] == \
            [(r["kind"], r["pdir"], r["pname"]) for r in rows]


class TestAccountStores:
    PAYLOAD = {"状态": "执行", "批次标识": "run-1",
               "输入清单": [{"名称": "a.md", "字节": 3, "sha256": "x"}],
               "产物清单": [{"名称": "b.md", "字节": 5, "sha256": "y"}]}

    def test_json_default_roundtrip(self, tmp_path):
        rec = str(tmp_path / "r")
        p = st.save_account(rec, dict(self.PAYLOAD))
        assert p.endswith("__结果.json")
        back = st.load_account(rec, str(tmp_path))
        assert back["输入清单"] == self.PAYLOAD["输入清单"]

    def test_xlsx_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("I3DNA_ACCOUNT_STORE", "xlsx")
        rec = str(tmp_path / "r")
        p = st.save_account(rec, dict(self.PAYLOAD))
        assert p.endswith("__账.xlsx")
        back = st.load_account(rec, str(tmp_path))
        assert back["状态"] == "执行"
        assert back["输入清单"][0]["名称"] == "a.md"
        assert back["产物清单"][0]["sha256"] == "y"

    def test_xlsx_falls_back_to_json(self, tmp_path, monkeypatch):
        import json
        monkeypatch.setenv("I3DNA_ACCOUNT_STORE", "xlsx")
        rec = tmp_path / "r"
        rec.mkdir()
        (rec / "__结果.json").write_text(
            json.dumps({"状态": "旧json"}, ensure_ascii=False), encoding="utf-8")
        assert st.load_account(str(rec), str(tmp_path))["状态"] == "旧json"

    def test_config_file_overrides(self, tmp_path, monkeypatch):
        monkeypatch.delenv("I3DNA_ACCOUNT_STORE", raising=False)
        (tmp_path / "__底物.yaml").write_text("账: xlsx\n", encoding="utf-8")
        assert st.account_format(str(tmp_path)) == "xlsx"
        p = st.save_account(str(tmp_path / "r"), dict(self.PAYLOAD),
                            root=str(tmp_path))
        assert p.endswith("__账.xlsx")

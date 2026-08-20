# -*- coding: utf-8 -*-
"""i3dna_model 显式领域类层的单测——锁定逻辑模型总图(docs/逻辑模型总图.md,95号)
的每个概念在真树上的行为。树=唯一权威,对象=视图:测试读真树 trade-v4/fixtures。

九概念:树/类/方法/弧/实例/账/身份/边界/边。剃刀已裁:投影并入产物弧、
部门并入档案、案卷库并入树根、范畴删除（8-19：档案袋更名档案）。
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(os.path.dirname(HERE), "i3dna_model.py")
sys.path.insert(0, os.path.dirname(MODEL))
from i3dna_model import (树根, 域, 场所, 实体类, 过程类, 方法,  # noqa: E402
                         线, 弧, 边, 输入弧, 产物弧, 档案, 案卷)

V4 = os.path.join(os.path.dirname(os.path.dirname(HERE)), "trade-v4")

@pytest.fixture(scope="module")
def 树():
    return 树根(V4)


# ── 正交层 ────────────────────────────────────────

def test_树根_域聚簇(树):
    域名 = [d.名 for d in 树.域们()]
    assert "产品域" in 域名 and "组织域" in 域名
    assert all(d.域主 for d in 树.域们() if d.名 != "组织域" or True)


def test_域_声明读取(树):
    产品域 = [d for d in 树.域们() if d.名 == "产品域"][0]
    assert 产品域.域主 == "产品经理"
    assert 产品域.职责


def test_域_类们_无None_污染树(tmp_path):
    """剃刀修:域.类们() 与 树根.类们() 同口径过滤非类根(污染树实测)。"""
    base = str(tmp_path)
    os.makedirs(os.path.join(base, "域", "XX", "类", "产品"))
    os.makedirs(os.path.join(base, "域", "XX", "类", "共享资料"))  # 非类根
    open(os.path.join(base, "域", "XX", "类", "产品", "schema.md"), "w").write(
        "---\n键说明:\n  产品号: 主键\n---\n")
    open(os.path.join(base, "域", "XX", "域.md"), "w").write("域主: 甲\n---\n")
    t = 树根(base)
    assert [c.名 for c in t.类们()] == ["产品"]
    assert all(c is not None for c in t.域们()[0].类们())


# ── 图数据库网(静) ────────────────────────────────────────

def test_实体类_schema三件套(树):
    产品 = 树.找类("产品")
    assert isinstance(产品, 实体类)
    assert "单价" in 产品.键说明
    assert 产品.属主表.get("状态") == "产品管理"
    assert 产品.默认表.get("状态") == "在售"


def test_实体类_无方法_过程类_必有方法(树):
    产品 = 树.找类("产品")
    assert not isinstance(产品, 过程类)
    产品管理 = 树.找类("产品管理")
    assert isinstance(产品管理, 过程类)
    assert len(产品管理.方法们()) >= 2   # 上市+修改产品


def test_边_关系声明解析(树):
    """边=图网的线(四型枚举)。方向 产品→品类 / 产品←库存 解析目标类。
    品类类已补建(2026-08-17 图网闭合),双向边都可解析到实体类。"""
    产品 = 树.找类("产品")
    边们 = 产品.关系们()
    assert all(isinstance(e, 边) for e in 边们)
    隶属 = [e for e in 边们 if e.类型 == "隶属品类"][0]
    assert 隶属.种 == "关联", "种缺省应为 关联(四型枚举)"
    assert 隶属.目标类名 == "品类"
    目标 = 隶属.目标类()
    assert isinstance(目标, 实体类) and 目标.名 == "品类"
    持有 = [e for e in 边们 if e.类型 == "由…持有库存"][0]
    assert 持有.目标类名 == "库存"
    assert 持有.目标类().名 == "库存"
    # 反向边(品类侧):品类 ← 产品
    品类 = 树.找类("品类")
    assert 品类.关系们()[0].目标类().名 == "产品"


def test_线_管道共享(树):
    """95附录:弧/边共享 线 基类(实现层),概念分立(语义层)。"""
    上市 = [x for x in 树.找类("产品管理").方法们() if x.名 == "上市"][0]
    assert isinstance(上市.输入弧们()[0], 线) and isinstance(上市.输入弧们()[0], 弧)
    assert isinstance(树.找类("产品").关系们()[0], 线)
    assert isinstance(树.找类("产品").关系们()[0], 边)


# ── Petri 网(动) ────────────────────────────────────────

def test_方法_色与执行者声明(树):
    m = 树.找类("产品管理").方法们()
    上市 = [x for x in m if x.名 == "上市"][0]
    assert 上市.色 == "蓝" and 上市.执行者声明 == "agent"
    出库 = 树.找类("库存管理").方法们()[0]
    assert 出库.色 == "红"


def test_弧对象_两种线各自结构(树):
    修改 = [x for x in 树.找类("产品管理").方法们() if x.名 == "修改产品"][0]
    输入 = 修改.输入弧们()
    assert any(isinstance(a, 输入弧) and a.路径声明 == "域/产品域/类/产品"
               for a in 输入), "类目录弧(裁决九)应在输入弧里"
    assert all(a.描述 for a in 输入)
    产物 = 修改.产物弧们()
    assert all(isinstance(a, 产物弧) for a in 产物)
    assert any(a.跨架产出 for a in 产物)   # 同键双柜:案卷号=实体号也是跨架记号
    assert any(a.落点 == "文件" for a in 产物)
    assert any(a.落点 == "字段区" and a.键 and a.规则 for a in 产物), \
        "投影段应并入产物弧(落点=字段区,键/规则保留)"


def test_输入弧_类型文件查找链(树):
    变更 = [x for x in 树.找类("物流管理").方法们() if x.名 == "变更地址"][0]
    typed = [a for a in 变更.输入弧们() if a.类型声明 == "需求澄清单"]
    assert typed and typed[0].类型文件().endswith("需求澄清单.md")


def test_产物弧_跨架产出记号(树):
    上市 = [x for x in 树.找类("产品管理").方法们() if x.名 == "上市"][0]
    arc = [a for a in 上市.产物弧们()][0]
    assert arc.跨架产出, "上市产物弧应含 {案卷号}(实体出生跨架)"
    assert arc.落点 == "文件"


def test_类们_两树形同形(树):
    名单 = {c.名 for c in 树.类们()}
    assert {"产品", "产品管理", "库存", "部门"} <= 名单
    for d in 树.域们():
        for c in d.类们():
            assert c.根.path == 树.path, f"{c} 的根错: {c.根.path}"


# ── 实例层(两网各半;案卷库已并入树根) ────────────────────────────────────────

def test_树根_实例导航(树):
    assert "产品" in 树.架们() and "部门" in 树.架们()
    assert "P005" in 树.全案卷号()


def test_档案_键值区即schema投影(树):
    档 = 树.档案("产品", "P005")
    assert isinstance(档, 档案)
    kv = 档.键值区()
    assert kv.get("产品号") == "P005" and kv.get("名称") == "小米电视"


def test_案卷_文件与账与凝固(树):
    卷 = 树.案卷("产品管理", "P005")
    assert isinstance(卷, 案卷)
    assert "上市申请.md" in 卷.文件们()
    recs = 卷.账.记录们()
    assert {"上市", "修改产品"} <= set(recs)      # 事件史累积
    assert 卷.账.最后执行者() == "实例/部门/D02"   # 主体值入账


def test_同键双柜_案卷找到档案(树):
    卷 = 树.案卷("产品管理", "P005")
    档 = 卷.同档案()
    assert 档.实体号 == "P005" and 档.键值区().get("单价") == 4299


def test_部门_已并入档案(树):
    """部门类已剃:部门们() 返回档案对象,名称/职能们 保留。"""
    部门们 = 树.部门们()
    assert all(isinstance(d, 档案) for d in 部门们)
    d01 = [d for d in 部门们 if d.名 == "D01"][0]
    assert d01.名称 == "产品管理一部"
    assert "产品管理" in d01.职能们              # 职能=过程类引用


# ── 域与场所显式建模(ARCHITECTURE.md §1/§5:域静态管类,场所运行时管实例) ──

def test_域_docstring语义_归纳改类(树):
    """域=Java package:管理类的集合;归纳=修改域的类(生殖隔离)。"""
    产品域 = next(d for d in 树.域们() if d.名 == "产品域")
    assert len(产品域.类们()) >= 2          # package 面:类聚簇
    assert "归纳就是修改域的类" in 域.__doc__  # 概念语义入 docstring


def test_场所_根场所与子场所(树):
    """企业=场所树:根场所=企业,子场所=域(部门,bounded context)。"""
    场s = 树.场所们()
    assert 场s[0].是根场所                  # 首位=根场所
    名集 = {s.名 for s in 场s}
    assert "产品域" in 名集 and "库存域" in 名集  # 域名=部门场所名


def test_场所_实例们与词表(树):
    """运行时管实例:场内实例集=域内类的实例架并集;词表=键并集。"""
    根 = 树.根场所
    assert len(根.实例们()) >= 4            # 根场所=全实例
    库存场 = next(s for s in 树.场所们() if s.名 == "库存域")
    库存实例 = [p.split(os.sep) for p in 库存场.实例们()]
    assert all(seg[-2] in {"仓库", "库存", "库存管理", "仓储管理"}
               for seg in 库存实例)        # 实例架⊆域内类
    assert any(seg[-2] == "库存" for seg in 库存实例)
    assert isinstance(库存场.词表(), set)    # 词表机械可算
    assert 根.锚路径 == 树.path             # 记忆锚


def test_场所_认领域部门场所退出(tmp_path):
    """费米律（8-19 审计落定）：已认领域的部门场所由声明场所接管，
    未认领域保留引导态部门场所——一实例恰属一场所，场所视角不双入场。"""
    base = str(tmp_path)
    for d in ("甲域", "乙域"):
        os.makedirs(os.path.join(base, "域", d, "类"))
        open(os.path.join(base, "域", d, "域.md"), "w").write("域主: x\n")
    os.makedirs(os.path.join(base, "场所"), exist_ok=True)
    open(os.path.join(base, "场所", "台A.md"), "w").write(
        "---\n场所主: x\n职责: y\n装配: [甲域]\n---\n")
    t = 树根(base)
    名集 = {s.名 for s in t.场所们()}
    assert "台A" in 名集
    assert "乙域" in 名集, "未认领域保留部门场所（引导态）"
    assert "甲域" not in 名集, "已认领域的部门场所应退出（声明接管）"

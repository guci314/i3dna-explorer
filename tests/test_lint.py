#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_lint — Lint 和修复提案相关测试。"""
import pytest


@pytest.mark.unit
def test_lint_view_exists(window):
    """测试 lint 视图存在"""
    assert hasattr(window, "lint_rep"), "应有 lint_rep 报告对象"
    assert callable(window.show_lint), "应有 show_lint 方法"


@pytest.mark.unit
def test_show_lint_renders(window, qapp):
    """测试 show_lint 渲染内容"""
    window.show_lint()
    qapp.processEvents()

    html = window.detail.toHtml()
    n_err = len(window.lint_rep.errors)
    n_warn = len(window.lint_rep.warnings)

    assert "全树对账" in html, "应显示「全树对账」视图"
    assert f"错误 {n_err}" in html, f"应显示错误数量 {n_err}"


@pytest.mark.unit
def test_lint_error_jump(window, qapp, explorer_module):
    """测试点击错误跳转到节点"""
    window.show_lint()
    qapp.processEvents()

    if not window.lint_rep.errors:
        pytest.skip("没有 lint 错误")

    from PyQt6.QtCore import QUrl

    # 取第一个错误
    first_err = window.lint_rep.errors[0]
    fpart = first_err[0].split("#")[0].split("·")[0]

    # 模拟点击锚点
    window.on_anchor(QUrl(f"i3dna:{fpart}"))
    qapp.processEvents()

    cur = window.model.itemFromIndex(window.tree.currentIndex())
    assert cur is not None, "点击错误后应选中节点"
    assert fpart.split("/")[-1] in (cur.data(explorer_module.ROLE_PATH) or ""), \
        "选中节点应匹配错误路径"


@pytest.mark.unit
def test_fix_proposals_triage(window, qapp):
    """测试修复提案三桶分诊全覆盖"""
    b1, b2, b3 = window._triage()
    total = len(window.lint_rep.errors) + len(window.lint_rep.warnings)

    assert len(b1) + len(b2) + len(b3) == total, \
        f"三桶分诊应覆盖所有问题：规范空白{len(b1)} 过期{len(b2)} 可修{len(b3)} / 共{total}"


@pytest.mark.unit
def test_show_fix_proposals(window, qapp):
    """测试显示修复提案"""
    window.show_fix_proposals()
    qapp.processEvents()

    html = window.detail.toHtml()
    assert "规范空白" in html, "应显示「规范空白」分类"


@pytest.mark.integration
def test_real_package_lint(real_window, qapp):
    """测试真实包的 lint 功能"""
    real_window.show_lint()
    qapp.processEvents()

    # 真实包应有至少一些数据
    assert real_window.lint_rep is not None
    html = real_window.detail.toHtml()
    assert len(html) > 100, "lint 视图应有内容"


@pytest.mark.unit
def test_lint_categories(window):
    """测试 lint 报告分类"""
    b1, b2, b3 = window._triage()

    # 三桶代表：规范空白 / 过期 / 可修
    # 验证返回值是列表
    assert isinstance(b1, list), "第一桶应为列表"
    assert isinstance(b2, list), "第二桶应为列表"
    assert isinstance(b3, list), "第三桶应为列表"


# ── 产物后账覆盖（103号 立域拆站：改弧案卷合法改写旧产物文件）──

def _load_lint():
    import importlib.util, os
    import i3dna_core as _core                   # 引擎家解析（explorer 已迁出独立安家）
    p = os.path.join(_core.BASE, "i3dna-lint", "i3dna_lint.py")
    spec = importlib.util.spec_from_file_location("i3dna_lint_t", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _mk_tree(tmp, product_txt, old_sha):
    """迷你树：任务A产物 p.md（旧账=旧sha），改弧账可选覆盖现态。"""
    import hashlib, json, os
    r = str(tmp)
    td = os.path.join(r, "类/甲/方法/办")
    os.makedirs(os.path.join(td, "__账"), exist_ok=True)
    os.makedirs(os.path.join(r, "类/甲/方法/改"), exist_ok=True)
    open(os.path.join(td, "任务.md"), "w").write("---\ni3dna: 微任务\n---\n干活\n")
    os.makedirs(os.path.join(r, "类/甲/方法/改/__账"), exist_ok=True)
    p = os.path.join(r, "类/甲/产物/p.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(product_txt)
    cur = hashlib.sha256(product_txt.encode()).hexdigest()

    def acc(dir_, prod_sha):
        json.dump({"任务": "类/甲/方法/办", "状态": "事后追认",
                   "输入清单": [], "产物清单": [
                       {"名称": "类/甲/产物/p.md", "字节": len(product_txt),
                        "sha256": prod_sha}]},
                  open(os.path.join(dir_, "__账", "__结果.json"), "w",
                       encoding="utf-8"), ensure_ascii=False)
    acc(td, old_sha)
    return r, cur, os.path.join(r, "类/甲/方法/改/__账")


@pytest.mark.unit
def test_产物后账覆盖_改写不报错(tmp_path):
    """旧账产物被改弧案卷改写并再入账＝出处链完整，对账不报错（信息级）。"""
    lint = _load_lint()
    r, cur, cover_acc = _mk_tree(tmp_path, "改写后的产物\n", "0" * 64)
    import hashlib, json, os
    open(os.path.join(cover_acc, "__结果.json"), "w", encoding="utf-8").write(
        json.dumps({"任务": "类/甲/方法/改", "状态": "事后追认",
                    "输入清单": [], "产物清单": [
                        {"名称": "类/甲/产物/p.md", "字节": 21,
                         "sha256": cur}]}, ensure_ascii=False))
    rep = lint.lint_tree(r)
    drift = [m for w, m in rep.errors + rep.warnings if "产物在记账后被改动" in m]
    assert not drift, drift
    assert any("后账重审覆盖" in m for _w, m in rep.infos)


@pytest.mark.unit
def test_产物无覆盖_真悬空仍报错(tmp_path):
    """无任何账盖住现态＝真悬空，错误保留（覆盖表不许吞真问题）。"""
    lint = _load_lint()
    r, _cur, _cover = _mk_tree(tmp_path, "被偷偷改过的产物\n", "0" * 64)
    rep = lint.lint_tree(r)
    assert any("产物在记账后被改动" in m for _w, m in rep.errors)


@pytest.mark.unit
def test_顺号类型文件弧错配_警告目录弧静默(tmp_path):
    """104修订2 lint 门（工单106）：声明 顺号: 真 的类型被输入**文件弧**
    消费（按固定名读单）→ 警告 __rN 错配；目录弧（收件箱消费）与未声明
    类型 → 静默。带 __ 段后缀形同查（单A__X__r2 → 剥出单A）。"""
    import os
    lint = _load_lint()
    r = str(tmp_path)

    def mk(rel, text):
        p = os.path.join(r, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)

    mk("消息/单A.md", "---\ni3dna: 消息\n顺号: 真\n---\n种（声明顺号）。\n")
    mk("消息/单B.md", "---\ni3dna: 消息\n---\n种（未声明）。\n")
    mk("类/甲/方法/吃文件弧/任务.md", "---\ni3dna: 微任务\n输入:\n  - "
       "\"{实例}/x/单A.md\"\n产物:\n  - \"{实例}/y/出.md\"\n---\n按固定名吃单。\n")
    mk("类/甲/方法/吃后缀形/任务.md", "---\ni3dna: 微任务\n输入:\n  - "
       "\"{实例}/x/单A__X__r2.md\"\n产物:\n  - \"{实例}/y/出2.md\"\n---\n吃后缀形单。\n")
    mk("类/甲/方法/吃目录弧/任务.md", "---\ni3dna: 微任务\n输入:\n  - "
       "\"实例/甲/收件箱\"\n产物:\n  - \"{实例}/y/出3.md\"\n---\n吃收件箱目录。\n")
    mk("类/甲/方法/吃未声明/任务.md", "---\ni3dna: 微任务\n输入:\n  - "
       "\"{实例}/x/单B.md\"\n产物:\n  - \"{实例}/y/出4.md\"\n---\n吃未声明类型的单。\n")
    rep = lint.lint_tree(r)
    hits = [m for _w, m in rep.warnings if "消费弧是文件弧" in m]
    assert len(hits) == 2, (hits, rep.warnings)          # 裸名＋__后缀形两任务
    assert all("单A" in m for m in hits)
    assert not any("单B" in m or "收件箱" in m
                   for _w, m in rep.warnings), "目录弧/未声明 → 静默"


def _mk_inbox_tree(tmp, inv_files):
    """迷你树：吃单任务账带收盘盘点（实例/甲/收件箱 目录弧，§8.12 形）；
    inv_files: {收件箱内文件名: 内容}——先落盘并按此记账，测试再自行改现场。"""
    import hashlib, json, os
    r = str(tmp)
    td = os.path.join(r, "类/甲/方法/吃")
    os.makedirs(os.path.join(td, "__账"))
    open(os.path.join(td, "任务.md"), "w", encoding="utf-8").write(
        "---\ni3dna: 微任务\n输入:\n  - \"实例/甲/收件箱\"\n产物:\n  - "
        "\"{实例}/y/出.md\"\n---\n吃收件箱（点火收尾删除本次处理的单）。\n")
    box = os.path.join(r, "实例/甲/收件箱")
    os.makedirs(box)
    man = {}
    for fn, txt in inv_files.items():
        open(os.path.join(box, fn), "w", encoding="utf-8").write(txt)
        man[fn] = hashlib.sha256(txt.encode()).hexdigest()
    json.dump({"任务": "类/甲/方法/吃", "状态": "执行", "输入清单": [
        {"名称": "实例/甲/收件箱", "目录": True, "清单": man, "可缺": True}],
        "产物清单": []},
        open(os.path.join(td, "__账", "__结果.json"), "w", encoding="utf-8"),
        ensure_ascii=False)
    os.makedirs(os.path.join(r, "消息"))
    open(os.path.join(r, "消息/单A.md"), "w", encoding="utf-8").write(
        "---\ni3dna: 消息\n---\n种。\n")
    open(os.path.join(r, "消息/说明.md"), "w", encoding="utf-8").write(
        "纯正文说明，无 frontmatter——不算类型。\n")
    return r


def _leftover_hits(rep):
    return [m for _w, m in rep.warnings if "疑似漏吃" in m]


@pytest.mark.unit
def test_漏吃_盘点单据在场同sha_警告(tmp_path):
    """臂1（工单107 B 档核心）：收盘盘点里的单据过了本火仍在场且 sha
    未变 → 疑似漏吃（消费删除未执行或未覆盖）。"""
    import os
    lint = _load_lint()
    r = _mk_inbox_tree(tmp_path, {"单A__X.md": "第一张单\n"})
    rep = lint.lint_tree(r)
    hits = _leftover_hits(rep)
    assert len(hits) == 1, (hits, rep.warnings)
    assert "单A__X.md" in hits[0]


@pytest.mark.unit
def test_漏吃_单据已不在场_静默(tmp_path):
    """臂2：盘点后单据已被（后续火）消费删除 → 静默。"""
    import os
    lint = _load_lint()
    r = _mk_inbox_tree(tmp_path, {"单A__X.md": "第一张单\n"})
    os.remove(os.path.join(r, "实例/甲/收件箱/单A__X.md"))
    assert _leftover_hits(lint.lint_tree(r)) == []


@pytest.mark.unit
def test_漏吃_在场但sha变_新单顶替静默(tmp_path):
    """臂3：同名新单顶替（sha 变）＝旧单已消费、新单在途 → 静默。"""
    import os
    lint = _load_lint()
    r = _mk_inbox_tree(tmp_path, {"单A__X.md": "第一张单\n"})
    open(os.path.join(r, "实例/甲/收件箱/单A__X.md"), "w",
         encoding="utf-8").write("顶替的新单（内容不同）\n")
    assert _leftover_hits(lint.lint_tree(r)) == []


@pytest.mark.unit
def test_漏吃_非单据文件_静默(tmp_path):
    """臂4：盘点里的普通知识件（名不中类型）与无 frontmatter 的正文型
    说明名 → 都不是单据，静默。"""
    lint = _load_lint()
    r = _mk_inbox_tree(tmp_path, {"普通件.md": "知识件\n",
                                  "说明__附注.md": "长得像单的说明\n"})
    assert _leftover_hits(lint.lint_tree(r)) == []


@pytest.mark.unit
def test_回收弧产物_缺席是退役不是悬空(tmp_path):
    """8-20 用户实证（撤 sample_domain 后旧立域账报「清单文件不存在」）：
    产物被回收清单盖住（名称+sha 同）＝依法退役——info 留痕，不报错误。"""
    import hashlib, json, os
    lint = _load_lint()
    r = str(tmp_path)

    def mk(rel, text):
        p = os.path.join(r, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)

    body = "---\n域主: 张三\n---\n域。\n"
    sha = hashlib.sha256(body.encode()).hexdigest()
    mk("类/甲/方法/立/任务.md", "---\ni3dna: 微任务\n---\n立。\n")
    mk("类/甲/方法/撤/任务.md", "---\ni3dna: 微任务\n---\n撤。\n")
    for m, extra in (("立", {"产物清单": [
                        {"名称": "域/d9/域.md", "字节": len(body),
                         "sha256": sha}]}),
                     ("撤", {"回收清单": [
                        {"名称": "域/d9/域.md", "字节": len(body),
                         "sha256": sha, "回收": True}]})):
        d = os.path.join(r, "类/甲/方法", m, "__账")
        os.makedirs(d)
        json.dump({"任务": f"类/甲/方法/{m}", "状态": "事后追认",
                   "输入清单": [], **extra},
                  open(os.path.join(d, "__结果.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
    # 文件已删（被回收）、空目录也不在——旧立账不得再报悬空
    rep = lint.lint_tree(r)
    assert not any("清单文件不存在" in m for _w, m in rep.errors), rep.errors
    assert any("依法回收" in m for _w, m in rep.infos)
    # 无回收清单盖住时（真悬空）错误保留——豁免不许吞真问题
    os.remove(os.path.join(r, "类/甲/方法/撤/__账/__结果.json"))
    rep2 = lint.lint_tree(r)
    assert any("清单文件不存在" in m for _w, m in rep2.errors)


# ── 主题判型对账（形状定律 8-21·工单1号：目录即类型）──

def _mk_theme_tree(tmp, themed):
    """迷你树：类甲消息类型 审批单（有/无 主题: 声明）；主题目录里
    乱名缺键单、键齐单、豁免件（__/点前缀）三种在场。"""
    import os
    r = str(tmp)
    tdir = os.path.join(r, "类/甲/消息")
    os.makedirs(tdir, exist_ok=True)
    law = "主题: \"实例/甲/{案卷号}/审批单\"\n" if themed else ""
    open(os.path.join(tdir, "审批单.md"), "w", encoding="utf-8").write(
        f"---\ni3dna: 消息\n{law}键:\n  - 申请人\n---\n审批单种。\n")
    open(os.path.join(tdir, "悬空单.md"), "w", encoding="utf-8").write(
        "---\ni3dna: 消息\n"
        + ("主题: \"实例/无处/{案卷号}/盒\"\n" if themed else "")
        + "---\n悬空种。\n")
    box = os.path.join(r, "实例/甲/c1/审批单")
    os.makedirs(box, exist_ok=True)
    open(os.path.join(box, "乱名缺键.md"), "w", encoding="utf-8").write(
        "---\n事由: 补件\n---\n单。\n")
    open(os.path.join(box, "键齐单__任意.md"), "w", encoding="utf-8").write(
        "---\n申请人: 张三\n事由: 落户\n---\n单。\n")
    open(os.path.join(box, "__批注.md"), "w", encoding="utf-8").write(
        "账不进账（豁免）。\n")
    open(os.path.join(box, ".隐藏.md"), "w", encoding="utf-8").write(
        "点前缀豁免。\n")
    return r


def _theme_hits(rep):
    return [m for _w, m in rep.warnings if "主题" in m]


@pytest.mark.unit
def test_主题目录_缺键警告_乱名也是单(tmp_path):
    """验收②/④：目录即类型——主题目录里的乱名文件也按类型键表对账，
    缺键＝单不合规；键齐 → 静默。"""
    lint = _load_lint()
    r = _mk_theme_tree(tmp_path, themed=True)
    rep = lint.lint_tree(r)
    hits = [m for m in _theme_hits(rep) if "缺键" in m]
    assert len(hits) == 1, (hits, rep.warnings)
    assert "乱名缺键.md" in hits[0] and "申请人" in hits[0]
    assert not any("键齐单" in m for m in _theme_hits(rep)), "键齐静默"


@pytest.mark.unit
def test_主题悬空_警告(tmp_path):
    """验收④：主题模式全树无一目录命中 → 立法指空处，警告。"""
    lint = _load_lint()
    r = _mk_theme_tree(tmp_path, themed=True)
    rep = lint.lint_tree(r)
    hits = [m for m in _theme_hits(rep) if "主题悬空" in m]
    assert len(hits) == 1, (hits, rep.warnings)
    assert "悬空单" in hits[0] and "实例/无处" in hits[0]


@pytest.mark.unit
def test_主题豁免_账与隐藏件不进门(tmp_path):
    """验收④：__/点前缀文件豁免主题判型（§8.12 同源）——不按单对账。"""
    lint = _load_lint()
    r = _mk_theme_tree(tmp_path, themed=True)
    rep = lint.lint_tree(r)
    assert not any("__批注" in m or ".隐藏" in m for m in _theme_hits(rep)), \
        "豁免件不得进主题对账"


@pytest.mark.unit
def test_零主题声明_检查休眠(tmp_path):
    """验收①：全树零 主题: 声明 → 主题检查零输出（逐字节兼容律）。"""
    lint = _load_lint()
    r = _mk_theme_tree(tmp_path, themed=False)
    rep = lint.lint_tree(r)
    assert _theme_hits(rep) == [], rep.warnings


@pytest.mark.unit
def test_uuid类型文件弧消费_警告目录弧静默(tmp_path):
    """形状定律 8-21·工单2 验收⑤：声明 命名: uuid 的类型被输入**文件弧**
    消费 → 警告（引擎代起名，消费者按固定名永远读不到新单）；目录弧与
    未声明类型 → 静默。与顺号共用一门（104修订2 推广）。"""
    import os
    lint = _load_lint()
    r = str(tmp_path)

    def mk(rel, text):
        p = os.path.join(r, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)

    mk("消息/票A.md", "---\ni3dna: 消息\n命名: uuid\n---\n种。\n")
    mk("消息/票B.md", "---\ni3dna: 消息\n---\n种。\n")
    mk("类/甲/方法/吃文件弧/任务.md", "---\ni3dna: 微任务\n输入:\n  - "
       "\"{实例}/x/票A.md\"\n产物:\n  - \"{实例}/y/出.md\"\n---\n按固定名吃。\n")
    mk("类/甲/方法/吃目录弧/任务.md", "---\ni3dna: 微任务\n输入:\n  - "
       "\"实例/甲/收件箱\"\n产物:\n  - \"{实例}/y/出2.md\"\n---\n吃队列。\n")
    rep = lint.lint_tree(r)
    hits = [m for _w, m in rep.warnings if "消费弧是文件弧" in m]
    assert len(hits) == 1, (hits, rep.warnings)
    assert "uuid类型「票A」" in hits[0]


@pytest.mark.unit
def test_消费清单对账_已吃单缺席不算漂移_其余单不算漏吃(tmp_path):
    """形状定律 8-21·工单2：主题车道账带消费清单——盘点里被本火吃掉的
    单缺席＝依法核销（不算目录已变）；在场的其余单＝队列余额（B 档漏吃
    检查对主题车道休眠——删除已机制化）。"""
    import hashlib, json, os
    lint = _load_lint()
    r = str(tmp_path)
    td = os.path.join(r, "类/甲/方法/办")
    os.makedirs(os.path.join(td, "__账"))
    open(os.path.join(td, "任务.md"), "w", encoding="utf-8").write(
        "---\ni3dna: 微任务\n输入:\n  - \"实例/甲/收件箱\"\n产物:\n  - "
        "\"{实例}/y/回执.md\"\n---\n一火一单吃队列。\n")
    box = os.path.join(r, "实例/甲/收件箱")
    os.makedirs(box)
    os.makedirs(os.path.join(r, "消息"))
    open(os.path.join(r, "消息/票.md"), "w", encoding="utf-8").write(
        "---\ni3dna: 消息\n命名: uuid\n---\n种。\n")
    man, kept, eaten = {}, "票__留.md", "票__吃.md"
    for fn, eaten_flag in ((kept, False), (eaten, True)):
        body = f"---\n事由: {fn}\n---\n单。\n"
        if not eaten_flag:                    # 吃掉的单已删——只在盘点里
            open(os.path.join(box, fn), "w", encoding="utf-8").write(body)
        man[fn] = hashlib.sha256(body.encode()).hexdigest()
    json.dump({"任务": "类/甲/方法/办", "状态": "执行",
               "输入清单": [{"名称": "实例/甲/收件箱", "目录": True,
                             "清单": man, "可缺": True}],
               "消费清单": [{"名称": f"实例/甲/收件箱/{eaten}",
                             "sha256": man[eaten], "消费": True}],
               "产物清单": []},
              open(os.path.join(td, "__账", "__结果.json"), "w",
                   encoding="utf-8"), ensure_ascii=False)
    rep = lint.lint_tree(r)
    assert not any("目录已变" in m for _w, m in rep.warnings), \
        "已吃单缺席＝依法核销，不是漂移"
    assert not any("疑似漏吃" in m for _w, m in rep.warnings), \
        "主题车道在场其余单＝队列余额，B 档休眠"


# ── 表声明对账（形状定律 8-21·工单3：目录即表）──

def _mk_table_tree(tmp, mode="full"):
    """迷你树：实体类甲（类.md 声明 表:+schema 指针，schema.md 键说明
    p1/p2），表 实例/甲 两行——r1 主文件形、r2 档案袋槽文件形。
    mode: full=齐 / miss=缺列 / dangling=表悬空 / clash=乙类撞表 / none=零声明"""
    import os
    r = str(tmp)

    def mk(rel, text):
        p = os.path.join(r, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)

    table = "" if mode == "none" else '表: "实例/甲"\n'
    mk("域/x域/类/甲/类.md", f"---\ni3dna: 类\n范畴: 实体\n{table}"
       "schema: 域/x域/类/甲/schema.md\n---\n甲实体类。\n")
    mk("域/x域/类/甲/schema.md",
       "---\n键说明:\n  p1: 甲列一\n  p2: 甲列二\n---\n# 甲 schema\n")
    if mode == "dangling":
        mk("域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 实体\n"
           '表: "实例/无处"\nschema: 域/x域/类/甲/schema.md\n---\n甲。\n')
        return r
    if mode == "clash":
        mk("域/x域/类/乙/类.md", "---\ni3dna: 类\n范畴: 实体\n"
           '表: "实例/甲"\n---\n乙实体类（撞表）。\n')
    mk("实例/甲/r1/r1.md", "---\np1: v1\n"
       + ("p2: v2\n" if mode != "miss" else "")
       + "---\n行一（主文件键值区形）。\n")
    mk("实例/甲/r2/p1.md", "行二列一（槽文件形）。\n")
    mk("实例/甲/r2/p2.md", "行二列二（槽文件形）。\n")
    return r


@pytest.mark.unit
def test_表行缺列_警告(tmp_path):
    """验收①：行主文件缺 schema 键说明要求的列（双形皆缺）→ 警告。"""
    lint = _load_lint()
    r = _mk_table_tree(tmp_path, mode="miss")
    rep = lint.lint_tree(r)
    hits = [m for _w, m in rep.warnings if "缺列" in m]
    assert len(hits) == 1, (hits, rep.warnings)
    assert "p2" in hits[0] and "r1" in hits[0]


@pytest.mark.unit
def test_表悬空_警告(tmp_path):
    """验收②：表目录不存在 → 悬空警告。"""
    lint = _load_lint()
    r = _mk_table_tree(tmp_path, mode="dangling")
    rep = lint.lint_tree(r)
    hits = [m for _w, m in rep.warnings if "表悬空" in m]
    assert len(hits) == 1, (hits, rep.warnings)
    assert "实例/无处" in hits[0]


@pytest.mark.unit
def test_两类撞一表_错误(tmp_path):
    """验收③：一表一类（Pauli）被破 → 错误。"""
    lint = _load_lint()
    r = _mk_table_tree(tmp_path, mode="clash")
    rep = lint.lint_tree(r)
    hits = [m for _w, m in rep.errors if "一表一类" in m]
    assert len(hits) == 1, (hits, rep.errors)
    assert "类/乙" in hits[0] and "类/甲" in hits[0]


@pytest.mark.unit
def test_表行键齐_两形皆过_零声明休眠(tmp_path):
    """验收④：主文件形/槽文件形键齐 → 静默；零 表: 声明 → 检查零输出。"""
    lint = _load_lint()
    rep = lint.lint_tree(_mk_table_tree(tmp_path, mode="full"))
    assert not any("表" in m for _w, m in rep.warnings
                   if "悬" not in m and "疑似漏吃" not in m
                   and "主题" not in m), rep.warnings   # 键齐静默
    rep2 = lint.lint_tree(_mk_table_tree(tmp_path, mode="none"))
    assert not any("一表一类" in m or "表悬空" in m or "缺列" in m
                   for _w, m in rep2.errors + rep2.warnings)


# ── 回音双向门（形状定律 8-21·工单4：绿语义 send-and-wait/fire-and-forget）──

def _mk_echo_tree(tmp, echo="有", gate=False):
    """迷你树：消息类型 审批单 声明 主题+回音；等回音任务按 gate 挂/不挂
    清空: 真空夹门。"""
    import os
    r = str(tmp)

    def mk(rel, text):
        p = os.path.join(r, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)

    mk("消息/审批单.md", f"---\ni3dna: 消息\n主题: \"实例/审批/{{案卷号}}/审批单\""
       f"\n回音: {echo}\n---\n审批单种。\n")
    arc = ('  - 路径: "实例/审批/{案卷号}/审批单"\n    清空: 真\n'
           if gate else '  - "实例/审批/{案卷号}/审批单"\n')
    mk("类/甲/方法/等回音/任务.md", "---\ni3dna: 微任务\n输入:\n"
       + arc + "产物:\n  - \"{实例}/等后.md\"\n---\n等回音。\n")
    return r


@pytest.mark.unit
def test_回音有_无人等_空承诺错误_有人等静默(tmp_path):
    """验收⑤a：回音: 有 而全树无人挂空夹门 → 空承诺错误；挂门 → 静默。"""
    lint = _load_lint()
    rep = lint.lint_tree(_mk_echo_tree(tmp_path, echo="有", gate=False))
    hits = [m for _w, m in rep.errors if "空承诺" in m]
    assert len(hits) == 1, (hits, rep.errors)
    assert "审批单" in hits[0]
    rep2 = lint.lint_tree(_mk_echo_tree(tmp_path, echo="有", gate=True))
    assert not any("空承诺" in m or "死等" in m for _w, m in rep2.errors), \
        rep2.errors


@pytest.mark.unit
def test_回音无_有人等_死等错误_无人等静默(tmp_path):
    """验收⑤b：回音: 无（收讫）而有人挂空夹门 → 死等错误；无人等 → 静默。"""
    lint = _load_lint()
    rep = lint.lint_tree(_mk_echo_tree(tmp_path, echo="无", gate=True))
    hits = [m for _w, m in rep.errors if "死等" in m]
    assert len(hits) == 1, (hits, rep.errors)
    assert "审批单" in hits[0] and "等回音" in hits[0]
    rep2 = lint.lint_tree(_mk_echo_tree(tmp_path, echo="无", gate=False))
    assert not any("空承诺" in m or "死等" in m for _w, m in rep2.errors), \
        rep2.errors


# ── 主题即法定路径（形状定律 8-21·工单5：主题类型两难正解）──

def _mk_path_tree(tmp, theme=False):
    """迷你树：消息类型 审批函——theme 真＝仅 主题:（无 路径:）；
    假＝无 主题: 无 路径:（老法对照：缺路径应报错）。"""
    import os
    r = str(tmp)
    tdir = os.path.join(r, "消息")
    os.makedirs(tdir, exist_ok=True)
    theme_line = '主题: "实例/审批/{案卷号}/审批夹"\n' if theme else ""
    open(os.path.join(tdir, "审批函.md"), "w", encoding="utf-8").write(
        f"---\ni3dna: 消息\n{theme_line}---\n审批函种。\n")
    return r


@pytest.mark.unit
def test_主题类型无路径_缺路径检查休眠(tmp_path):
    """验收①：声明 主题: 的类型无 路径: → 主题目录即存在性判据，零报错
    （两键并挂也休眠——双记是待清旧态不是新错）。"""
    lint = _load_lint()
    rep = lint.lint_tree(_mk_path_tree(tmp_path, theme=True))
    assert not any("缺「路径」" in m for _w, m in rep.errors), rep.errors


@pytest.mark.unit
def test_无主题无路径_照报错_旧钉不破(tmp_path):
    """验收③：未声明 主题: 的类型缺 路径: → 照报错（文件槽老法不动）。"""
    lint = _load_lint()
    rep = lint.lint_tree(_mk_path_tree(tmp_path, theme=False))
    hits = [(w, m) for w, m in rep.errors if "缺「路径」" in m]
    assert len(hits) == 1, (hits, rep.errors)
    assert "审批函" in hits[0][0]

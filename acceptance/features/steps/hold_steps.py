# -*- coding: utf-8 -*-
"""持有单隔离验收步骤——ACID 的 I。
判据=needs_fire 判定与 lint 悬账(账面事实),零像素零 LLM。"""
import os

from behave import given, then   # noqa: F401

import i3dna_core as core

eng = core.eng


@given("磁盘铺持有单 {ent} {case}")
def step_seed_hold(context, ent, case):
    fp = os.path.join(context.tree_root, "实例/人员", ent,
                      f"持有单__{case}.md")
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"---\n持有方案卷: {case}\n---\n持有中。\n")

@given("磁盘撤持有单 {ent} {case}")
def step_drop_hold(context, ent, case):
    fp = os.path.join(context.tree_root, "实例/人员", ent,
                      f"持有单__{case}.md")
    if os.path.exists(fp):
        os.remove(fp)


def _tdir(root, cname, mname):
    cands = list(core.class_roots(os.path.join(root, "类"))) \
        + list(core.class_roots(root))
    for cand in cands:
        if os.path.basename(cand) == cname:
            return os.path.join(cand, "方法", mname)
    raise AssertionError(f"类根不存在: {cname}")


@then("任务判定 {task} 为 {verdict} 且原因含 {word}")
def step_needs_fire_holds(context, task, verdict, word):
    root = context.tree_root
    cname, mname = ("社保", "办卡") if task == "社保办卡" \
        else ("迁居", "改户口")
    fire, reason = eng._task_needs_fire(_tdir(root, cname, mname), root,
                                        "迁20260818"
                                        if cname == "迁居" else None)
    if verdict == "未使能":
        assert not fire, f"应未使能: {reason}"
    else:
        assert fire, f"应将点火: {reason}"
    assert word in reason, f"原因缺「{word}」: {reason}"


@then("任务判定 {task} 为 {verdict} 且原因不含 {word}")
def step_needs_fire_free(context, task, verdict, word):
    root = context.tree_root
    fire, reason = eng._task_needs_fire(
        _tdir(root, "迁居", "改户口"), root, "迁20260818")
    assert fire, f"应将点火: {reason}"
    assert word not in reason, f"自家任务被误挡: {reason}"


@then("任务判定 {task} 为 {verdict}")
def step_needs_fire_plain(context, task, verdict):
    root = context.tree_root
    fire, reason = eng._task_needs_fire(
        _tdir(root, "社保", "办卡"), root, None)
    if verdict == "未使能":
        assert not fire, f"应未使能: {reason}"
    else:
        assert fire, f"应将点火: {reason}"


@then("lint 报悬账 {doc} {case}")
def step_lint_hold(context, doc, case):
    rep = core.lint.lint_tree(context.tree_root)
    hit = any(doc in e and case in e
              for lst in (rep.errors, rep.warnings) for _w, e in lst)
    assert hit, f"lint 未报 {doc}/{case} 悬账"

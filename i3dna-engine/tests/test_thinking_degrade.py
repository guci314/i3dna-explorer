# -*- coding: utf-8 -*-
"""max_tokens 降档重试（8-19）：首跑思考烧光输出预算＝确定性死，
重试降一档思考（THINKING_LADDER max→high→low），梯内档位才有得降。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")
sys.path.insert(0, os.path.dirname(ENG))

import i3dna_engine as eng  # noqa: E402


def test_降档映射_梯内档位():
    assert eng._degrade_thinking("acp:omp --thinking max acp") \
        == ("acp:omp --thinking high acp", "max", "high")
    assert eng._degrade_thinking("omp -p --no-session --thinking max @{prompt_file}") \
        == ("omp -p --no-session --thinking high @{prompt_file}", "max", "high")
    # 默认档已是 high（8-19 裁定）：high 烧穿也要接得住 → low
    assert eng._degrade_thinking("acp:omp --thinking high acp") \
        == ("acp:omp --thinking low acp", "high", "low")


def test_降档映射_梯尽头返回None():
    assert eng._degrade_thinking("claude -p") is None
    assert eng._degrade_thinking("acp:omp --thinking low acp") is None  # 梯子尽头


def test_降档只换档位不误伤参数():
    e = eng._degrade_thinking("omp --thinking high --no-session -p @{prompt_file}")
    assert e == ("omp --thinking low --no-session -p @{prompt_file}", "high", "low")

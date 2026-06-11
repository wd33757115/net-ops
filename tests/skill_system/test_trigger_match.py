# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""触发词宽松匹配单元测试。"""

from src.skill_system.trigger_match import trigger_matches


def test_write_qingshi_exact():
    assert trigger_matches("写请示", "帮我写请示给领导")


def test_write_qingshi_with_measure_word():
    assert trigger_matches("写请示", "我写一份请示，向信息中心申请采购一台核心交换机")


def test_write_qingshi_direct_trigger():
    assert trigger_matches("写一份请示", "我写一份请示，向信息中心申请采购")


def test_gongwen_substring():
    assert trigger_matches("公文写作", "需要公文写作指导")


def test_no_false_positive():
    assert not trigger_matches("写请示", "交换机端口down了怎么办")


def test_textfsm_ignore_whitespace():
    assert trigger_matches("生成 TextFSM", "生成TEXTFSM解析模板，display fan")


def test_display_fan_trigger():
    assert trigger_matches("display fan", "生成TEXTFSM，<SW>display fan\n Slot 1:")

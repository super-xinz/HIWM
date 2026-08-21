from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShowcaseExample:
    id: str
    name: str
    tagline: str
    description: str
    prompt_suggestions: tuple[str, ...]

    def public_view(self) -> dict:
        value = asdict(self)
        value["prompt_suggestions"] = list(self.prompt_suggestions)
        return value


SHOWCASE_EXAMPLES = (
    ShowcaseExample(
        id="showcase-explorer",
        name="灵感探索者",
        tagline="热情开放，喜欢从可能性出发",
        description="适合体验更有参与感、鼓励联想和保留选择空间的交流方式。",
        prompt_suggestions=(
            "我最近有很多新想法，但不知道先做哪一个。",
            "陪我把一个模糊的灵感慢慢聊清楚。",
        ),
    ),
    ShowcaseExample(
        id="showcase-innovator",
        name="观点开拓者",
        tagline="反应迅速，乐于挑战惯常答案",
        description="适合体验观点碰撞、快速拆题和从多个角度寻找新解法的交流方式。",
        prompt_suggestions=(
            "我有一个看起来不太现实的方案，帮我挑战一下。",
            "同一件事还能从哪些完全不同的角度理解？",
        ),
    ),
    ShowcaseExample(
        id="showcase-strategist",
        name="果断策略者",
        tagline="目标清晰，重视效率与推进",
        description="适合体验先抓重点、明确取舍并把讨论落到下一步行动的交流方式。",
        prompt_suggestions=(
            "这件事卡住很久了，直接帮我找关键矛盾。",
            "我需要今天做决定，帮我快速比较两个方案。",
        ),
    ),
    ShowcaseExample(
        id="showcase-supporter",
        name="温暖协调者",
        tagline="细致体贴，关注关系与感受",
        description="适合体验先接住情绪、照顾沟通氛围，再一起寻找稳妥办法的交流方式。",
        prompt_suggestions=(
            "我和朋友有点误会，不知道该怎么开口。",
            "今天有点委屈，我想先理清自己的感受。",
        ),
    ),
    ShowcaseExample(
        id="showcase-anchor",
        name="稳健守护者",
        tagline="可靠有序，偏好清晰和可执行",
        description="适合体验节奏稳定、信息明确、兼顾现实条件与长期可靠性的交流方式。",
        prompt_suggestions=(
            "我最近事情很多，帮我排一个不容易失控的计划。",
            "这个决定有哪些风险是我应该提前准备的？",
        ),
    ),
)

SHOWCASE_BY_ID = {item.id: item for item in SHOWCASE_EXAMPLES}
DEFAULT_EXAMPLE_ID = "showcase-anchor"

SHOWCASE_PUBLIC_PROFILES = {
    "showcase-explorer": {
        "portrait": {
            "essence": "热情、开放，习惯先看可能性，也善于让交流变得轻松而有参与感。",
            "strengths": ["快速联想不同可能", "主动营造交流氛围", "面对变化及时调整"],
            "core_tension": "想法丰富时容易同时展开多个方向，适合用轻量的优先级帮助落地。",
        },
        "top_traits": [
            {"group": "互动节奏", "name": "互动活跃度", "level": "突出"},
            {"group": "信息处理", "name": "开放程度", "level": "突出"},
            {"group": "互动节奏", "name": "社交温度", "level": "突出"},
            {"group": "行动方式", "name": "适应能力", "level": "突出"},
            {"group": "决策方式", "name": "风险接受度", "level": "突出"},
        ],
        "interaction_preferences": {
            "回复长度": "适中",
            "表达直接度": "适中",
            "共情优先": "是",
            "提问密度": "适中",
        },
        "current_state": {},
    },
    "showcase-innovator": {
        "portrait": {
            "essence": "思路敏捷、表达有力，喜欢通过观点碰撞快速发现问题的新解法。",
            "strengths": ["迅速拆解复杂问题", "从不同角度提出假设", "在不确定中推动尝试"],
            "core_tension": "推进速度较快时可能忽略必要的结构，适合在关键节点补充约束与检查。",
        },
        "top_traits": [
            {"group": "信息处理", "name": "开放程度", "level": "突出"},
            {"group": "自我调节", "name": "自信程度", "level": "突出"},
            {"group": "互动节奏", "name": "表达坚定度", "level": "突出"},
            {"group": "行动方式", "name": "持续投入度", "level": "突出"},
            {"group": "互动节奏", "name": "互动活跃度", "level": "突出"},
        ],
        "interaction_preferences": {
            "回复长度": "适中",
            "表达直接度": "较高",
            "共情优先": "适中",
            "提问密度": "较高",
        },
        "current_state": {},
    },
    "showcase-strategist": {
        "portrait": {
            "essence": "目标感强、判断果断，倾向先抓关键矛盾，再把讨论转成可执行的下一步。",
            "strengths": ["快速识别重点", "清楚表达立场", "在压力下保持推进"],
            "core_tension": "聚焦结果时可能压缩感受与过渡过程，适合在行动前确认相关人的接受度。",
        },
        "top_traits": [
            {"group": "互动节奏", "name": "表达坚定度", "level": "突出"},
            {"group": "信息处理", "name": "开放程度", "level": "突出"},
            {"group": "自我调节", "name": "自信程度", "level": "突出"},
            {"group": "决策方式", "name": "分析决策倾向", "level": "突出"},
            {"group": "行动方式", "name": "持续投入度", "level": "突出"},
        ],
        "interaction_preferences": {
            "回复长度": "简短",
            "表达直接度": "较高",
            "共情优先": "适中",
            "提问密度": "较低",
        },
        "current_state": {},
    },
    "showcase-supporter": {
        "portrait": {
            "essence": "温暖、细致，重视关系中的回应感，通常会先照顾情绪，再寻找稳妥办法。",
            "strengths": ["敏锐觉察他人感受", "维护合作与信任", "耐心把事情安排周全"],
            "core_tension": "照顾他人时可能承担过多责任，适合同时确认自己的边界与真实需要。",
        },
        "top_traits": [
            {"group": "互动节奏", "name": "社交温度", "level": "突出"},
            {"group": "情绪与关系", "name": "共情能力", "level": "突出"},
            {"group": "行动方式", "name": "自律程度", "level": "突出"},
            {"group": "自我调节", "name": "积极预期", "level": "突出"},
            {"group": "行动方式", "name": "结构化偏好", "level": "突出"},
        ],
        "interaction_preferences": {
            "回复长度": "适中",
            "表达直接度": "适中",
            "共情优先": "是",
            "提问密度": "适中",
        },
        "current_state": {},
    },
    "showcase-anchor": {
        "portrait": {
            "essence": "稳健、可靠，偏好清晰的边界和可执行的安排，也会留意长期关系中的责任。",
            "strengths": ["按计划稳定推进", "提前识别现实风险", "在关系中保持耐心与责任感"],
            "core_tension": "信息不足时容易反复确认，适合先明确最低可行步骤，再逐步增加把握。",
        },
        "top_traits": [
            {"group": "行动方式", "name": "自律程度", "level": "突出"},
            {"group": "行动方式", "name": "结构化偏好", "level": "突出"},
            {"group": "互动节奏", "name": "社交温度", "level": "均衡"},
            {"group": "情绪与关系", "name": "共情能力", "level": "均衡"},
            {"group": "信息处理", "name": "思考深度", "level": "均衡"},
        ],
        "interaction_preferences": {
            "回复长度": "适中",
            "表达直接度": "适中",
            "共情优先": "是",
            "提问密度": "较低",
        },
        "current_state": {},
    },
}


def is_showcase_example(user_id: str) -> bool:
    return user_id in SHOWCASE_BY_ID


def public_profile_for_example(user_id: str) -> dict:
    return deepcopy(SHOWCASE_PUBLIC_PROFILES[user_id])

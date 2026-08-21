from service.companion_service.profile_client import public_profile
from service.companion_service.orchestrator import _update_summary
from service.companion_service.prompt_composer import profile_context


def test_public_profile_hides_internal_methodology_and_codes():
    result = public_profile({
        "profile_version": 3,
        "profile": {
            "meta": {"overall_confidence": 0.45, "updated_at": "2026-08-21T12:00:00Z"},
            "mbti_dimensions": {"type_label": "ENFP"},
            "enneagram_profile": {"identity": {"code": "SX/SO｜7w6"}},
            "digital_code_profile": {"code": "6318", "algorithm_version": "digital-code-v1"},
            "birth_analysis": {"bazi_text": "示例八字", "numerology_code": "6318"},
            "portrait": {
                "essence": {
                    "content": (
                        "数字密码 6318、ENFP、九型人格 7w6、SX/SO、7号、完美型、"
                        "偏财格、戊寅 癸亥 丁亥、INFJ型、荣格八维、Ni、I N F J、"
                        "SO优先、1998-12-06、生辰、Type 4、social/self-preservation，"
                        "以及数字学画像2.xlsx的综合摘要"
                    )
                },
            },
            "core_traits": {
                "energy_mode": {
                    "extroversion": {"value": 0.72, "confidence": 0.81},
                },
            },
            "runtime": {
                "interaction_preferences": {
                    "response_length": "short",
                    "internal_summary": "不展示 enneagram 或 numerology",
                },
                "current_state": {"stress_level": {"value": "low", "expires_at": "secret"}},
                "memories": [],
            },
        },
    })

    assert result is not None
    serialized = str(result).lower()
    for hidden in (
        "mbti", "enneagram", "numerology", "数字密码", "数字学", "九型", "八字",
        "6318", "7w6", "7号", "完美型", "偏财格", "戊寅", "xlsx", "infj",
        "荣格", "ni", "i n f j", "so优先", "1998-12-06", "生辰", "type 4",
        "social", "self-preservation",
    ):
        assert hidden.lower() not in serialized
    assert result["top_traits"][0]["name"] == "互动活跃度"
    assert result["top_traits"][0]["level"] == "突出"
    assert "profile_version" not in result
    assert "overall_confidence" not in result
    assert "value" not in result["top_traits"][0]
    assert "confidence" not in result["top_traits"][0]
    assert "内部资料" in result["portrait"]["essence"]
    assert result["interaction_preferences"] == {"回复长度": "简短"}
    assert result["current_state"] == {"压力水平": "较低"}
    assert "memories" not in result


def test_profile_update_summary_uses_public_facing_labels():
    assert _update_summary({
        "profile_patch": [{"field": "core_traits.energy_mode.extroversion"}],
        "runtime_operations": [
            {"operation": "SET_INTERACTION_PREFERENCE"},
            {"operation": "INTERNAL_UNKNOWN_OPERATION"},
        ],
    }) == ["已更新互动活跃度", "已更新沟通偏好", "已更新一项个性化信息"]


def test_model_context_uses_only_neutral_actionable_information():
    context = profile_context({
        "profile_version": 3,
        "profile": {
            "meta": {"overall_confidence": 0.45},
            "mbti_dimensions": {"type_label": "ENFP"},
            "enneagram_profile": {
                "identity": {"code": "SX/SO｜7w6"},
                "interaction_strategy": {
                    "communication": {
                        "entry_point": "先回应关系和感受",
                        "language_style": "温暖、有回应感",
                        "response_pattern": "先感谢与看见，再询问本人需要",
                    },
                    "companionship": {"long_term_support": "鼓励健康给予和接受照顾"},
                },
            },
            "digital_code_profile": {"code": "6318"},
            "birth_analysis": {"bazi_text": "甲木日主"},
            "portrait": {"essence": {"content": "ENFP 与 7w6 的综合摘要"}},
            "core_traits": {
                "energy_mode": {
                    "extroversion": {"value": 0.72, "confidence": 0.81},
                },
            },
            "runtime": {
                "interaction_preferences": {"response_length": "short"},
                "current_state": {"stress_level": {"value": "low"}},
                "memories": [{"summary": "用户主动谈到 MBTI，但不应暴露内部方法"}],
            },
        },
    }, 8_000)

    lowered = context.lower()
    for hidden in (
        "mbti", "enneagram", "numerology", "数字密码", "九型", "八字",
        "enfp", "7w6", "sx/so", "6318", "日主",
    ):
        assert hidden not in lowered
    assert "互动活跃度" in context
    assert "先感谢与看见，再询问本人需要" in context
    assert "画像成熟度" not in context

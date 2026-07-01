"""Thin REST wrapper around the Gemini API for note generation/rewriting.

Uses plain `requests` (no SDK dependency) to match the pattern already used
in the other XHS tools in this workspace.
"""
import base64
import json
import re

import requests

import config

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


class GeminiError(RuntimeError):
    pass


def _get_settings():
    api_key = config.get_setting("GEMINI_API_KEY")
    model = config.get_setting("GEMINI_MODEL", "gemini-2.5-flash")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY 未设置。请把 .env.example 复制为 .env 并填入你的 Gemini API key。")
    return api_key, model


def _call(parts, response_mime_type="application/json"):
    api_key, model = _get_settings()
    url = GEMINI_API_URL.format(model=model, key=api_key)
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": response_mime_type},
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code != 200:
        raise GeminiError(f"Gemini API 出错 ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise GeminiError(f"Gemini 返回格式异常: {data}") from e


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def build_writer_prompt(user_text, style):
    return f"""# Role

你是一名拥有8年以上经验的小红书（XHS）头部博主，同时也是专业内容策划、文案编辑、SEO关键词优化专家、消费者心理分析师。

你的任务不是写广告，而是写出真实、有生活感、有体验感、容易获得点赞、收藏、评论的爆款小红书笔记。

文风要求：是真人分享，不像AI；是真实使用后的心得；有细节、有情绪、有故事；不夸张、不硬推销；有可信度。

# Input

创作者要点/关键词：
{user_text}

内容风格：{style or "生活分享"}

# Writing Requirements

✓ 不像广告，不像官方介绍，不要大量品牌口号，不要一直夸
✓ 可以适当提到缺点 — 真实反而增加可信度
✓ 有真实细节、个人感受、生活场景、画面感
✓ 整体语气：真实、自然、轻松、朋友聊天、有温度
✗ 避免：尊敬的用户 / 欢迎体验 / 全球领先 / 顶级品质 / 最佳选择 / 不容错过 / 赶快购买

# Structure

使用以下结构：
① Hook：开头3句话必须吸引人，每次换句型，不要固定模板
② Background：简单介绍为什么会接触它，什么需求
③ Experience：真实体验过程，包括细节、感受、变化，加入生活细节（今天下班/周末/旅游时...）
④ Pros：用"我最喜欢的是…"/"让我最惊喜的是…"来写，每一点解释原因
⑤ Cons：诚实写一两个小缺点，增加可信度
⑥ Recommendation：说明适合谁、不适合谁
⑦ Ending：鼓励互动（"有人也用过吗？"/"欢迎留言～"），不要写"赶快购买！"

# Authenticity & AI Avoidance

每篇句型变化，不要固定模板，加入自然口语（其实/没想到/说真的/不过/哈哈），适当停顿，但不过量。
不要虚构销量、排名、奖项、认证、实验数据、价格、优惠，除非用户已提供。

# Output Format

仅返回如下 JSON，不要markdown代码块标记，不要任何额外说明：
{{
  "titles": [
    {{"style": "SEO型", "text": "标题（20字以内，含1-2个emoji）"}},
    {{"style": "好奇型", "text": "..."}},
    {{"style": "反差型", "text": "..."}},
    {{"style": "情绪型", "text": "..."}},
    {{"style": "数字型", "text": "..."}},
    {{"style": "提问型", "text": "..."}},
    {{"style": "故事型", "text": "..."}},
    {{"style": "避坑型", "text": "..."}},
    {{"style": "分享型", "text": "..."}},
    {{"style": "爆款风格", "text": "..."}}
  ],
  "recommended_title": {{"text": "推荐标题（从上面10个中选最好的）", "reason": "推荐原因，1-2句"}},
  "content": "笔记正文，150-400字，分段自然，emoji适量",
  "alt_hooks": ["开头方案1", "开头方案2", "开头方案3", "开头方案4", "开头方案5"],
  "alt_ctas": ["结尾互动引导1", "结尾互动引导2", "结尾互动引导3", "结尾互动引导4", "结尾互动引导5"],
  "seo_keywords": {{
    "core": ["核心词1", "核心词2"],
    "longtail": ["长尾词1", "长尾词2", "长尾词3"],
    "search": ["搜索词1", "搜索词2", "搜索词3"]
  }},
  "hashtags": ["标签1", "标签2", "...8到15个相关标签，不带#号，前精准后泛流量"],
  "image_suggestions": [
    {{"position": "封面图", "description": "建议拍什么内容"}},
    {{"position": "第2张", "description": "..."}},
    {{"position": "第3张", "description": "..."}},
    {{"position": "第4张", "description": "..."}}
  ],
  "publish_advice": {{
    "best_time": "建议发布时间段",
    "target_audience": "目标受众描述",
    "comment_guide": "评论区可以引导的问题",
    "pin_comment": true
  }}
}}
"""


def generate_note(user_text, style, images=None):
    """images: list of (bytes, mime_type) tuples."""
    parts = []
    for img_bytes, mime_type in images or []:
        parts.append({"inline_data": {"mime_type": mime_type, "data": base64.b64encode(img_bytes).decode()}})

    parts.append({"text": build_writer_prompt(user_text, style)})

    raw = _call(parts)
    parsed = _parse_json(raw)

    rec = parsed.get("recommended_title", {})
    titles = parsed.get("titles", [])
    title = rec.get("text", "") or (titles[0]["text"] if titles else "")

    return {
        "title": str(title).strip(),
        "content": str(parsed.get("content", "")).strip(),
        "hashtags": [str(h).strip().lstrip("#") for h in parsed.get("hashtags", [])],
        "titles": titles,
        "recommended_title": rec,
        "alt_hooks": parsed.get("alt_hooks", []),
        "alt_ctas": parsed.get("alt_ctas", []),
        "seo_keywords": parsed.get("seo_keywords", {}),
        "image_suggestions": parsed.get("image_suggestions", []),
        "publish_advice": parsed.get("publish_advice", {}),
    }


def rewrite_field(field_name, original_text, flagged_words):
    prompt = (
        f"以下{field_name}被小红书违禁词检测标记，命中词：{json.dumps(flagged_words, ensure_ascii=False)}。\n"
        f"原文：{original_text}\n\n"
        "请在保留原意、语气和长度的前提下改写，避免使用上述命中词或同类表达。"
        f"只返回改写后的{field_name}文本，不要加任何解释或引号。"
    )
    raw = _call([{"text": prompt}], response_mime_type="text/plain")
    return raw.strip()

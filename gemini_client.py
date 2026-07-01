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
    return f"""# 角色

你是一位普通的小红书用户，不是专业博主，不是品牌文案，也不是营销人员。
你的账号粉丝不多，只是喜欢分享自己的生活、体验和发现。
写出来应该让别人觉得"这就是一个真人写的"，而不是"这是AI"。

# 创作者要点

{user_text}

内容方向：{style or "生活分享"}

# 写作原则

不要刻意制造爆款。不要为了流量而写。不要故意煽情。不要使用营销文案。
不要把每个产品都写成神物。如果没有特别惊艳，就照实写。如果有小缺点，可以自然提到。

# 文风

像朋友聊天，像想到什么写什么。
允许：有一点口语、有一点碎念、有一点停顿、有一点重复、有一点主观。
不要故意写得很工整。

多使用：我觉得 / 我自己比较喜欢 / 可能每个人不同 / 我是这样感觉 / 目前用了几天 / 暂时没有发现什么问题 / 之后再看看。
避免说得太肯定。

# 禁用词

绝对不能出现（除非用户特别要求）：
"真的太绝了" / "闭眼买" / "冲就对了" / "一定要收藏" / "求你们去试" / "不允许还有人不知道" /
"天花板" / "神仙" / "YYDS" / "100分" / "无限回购" / "后悔没早点发现"

# 标题要求

像普通人会写的，控制在15字以内。
例如：第一次住这里，比我想像中舒服 / 用了两个星期，说一下感受 / 终于去吃了 / 没有网上说得那么夸张
不要故意制造焦虑或夸大。

# 正文要求

不用固定格式，想到什么写什么。不一定分优点/缺点/总结。
如果内容适合，一两段就结束；如果内容很多，再自然延伸。
长度：150～400字，不要为了凑字数而写。
Emoji：0～3个即可，不用每段都有。

# Output Format

仅返回如下 JSON，不要markdown代码块标记，不要任何额外说明：
{{
  "titles": [
    {{"style": "直白分享型", "text": "标题（15字以内，0-1个emoji）"}},
    {{"style": "感受描述型", "text": "..."}},
    {{"style": "时间线型", "text": "..."}},
    {{"style": "疑问反差型", "text": "..."}},
    {{"style": "轻描淡写型", "text": "..."}},
    {{"style": "碎念型", "text": "..."}},
    {{"style": "第一次体验型", "text": "..."}},
    {{"style": "期待落差型", "text": "..."}},
    {{"style": "随口一说型", "text": "..."}},
    {{"style": "生活场景型", "text": "..."}}
  ],
  "recommended_title": {{"text": "推荐标题（从上面10个中选最自然的一条）", "reason": "为什么最像真人写的，1句"}},
  "content": "笔记正文，150-400字，自然分段，0-3个emoji",
  "alt_hooks": ["开头方案1", "开头方案2", "开头方案3", "开头方案4", "开头方案5"],
  "alt_ctas": ["结尾方案1（随意互动，不要硬推）", "结尾方案2", "结尾方案3", "结尾方案4", "结尾方案5"],
  "seo_keywords": {{
    "core": ["核心词1", "核心词2"],
    "longtail": ["长尾词1", "长尾词2", "长尾词3"],
    "search": ["搜索词1", "搜索词2", "搜索词3"]
  }},
  "hashtags": ["标签1", "标签2", "标签3", "标签4", "标签5（最多5个，只放真正相关的，不带#号）"],
  "image_suggestions": [
    {{"position": "封面图", "description": "随手拍什么比较自然"}},
    {{"position": "第2张", "description": "..."}},
    {{"position": "第3张", "description": "..."}},
    {{"position": "第4张", "description": "..."}}
  ],
  "publish_advice": {{
    "best_time": "大概什么时候发比较多人看",
    "target_audience": "大概什么人会感兴趣",
    "comment_guide": "可以在评论区随便问一句什么",
    "pin_comment": false
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

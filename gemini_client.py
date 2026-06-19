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
    return f"""你是一名小红书（XHS）资深博主，擅长写真实、有温度、不像广告的种草笔记。

【任务】
根据下面提供的照片（如果有）和创作者给的要点，写一篇小红书笔记。

【创作者要点/关键词】
{user_text}

【内容风格】
{style or "生活分享"}

【写作要求】
- 第一人称口吻，像朋友分享真实体验，不要有营销/广告感
- 自然使用 emoji，不要堆砌
- 结构：吸引人的开头 -> 背景/为什么 -> 体验过程 -> 效果/感受 -> 简短总结或推荐
- 避免绝对化用语（如"最好"、"第一"、"100%有效"）和医疗功效承诺
- 不要编造收件人姓名、具体地址或联系方式

【输出格式】
仅返回如下 JSON（不要markdown代码块标记，不要任何额外说明）：
{{
  "title": "小红书标题，20字以内，1-2个emoji，吸引点击",
  "content": "笔记正文，150-300字，分段自然，emoji适量",
  "hashtags": ["标签1", "标签2", "...5到8个相关标签，不带#号"]
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
    return {
        "title": str(parsed.get("title", "")).strip(),
        "content": str(parsed.get("content", "")).strip(),
        "hashtags": [str(h).strip().lstrip("#") for h in parsed.get("hashtags", [])],
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

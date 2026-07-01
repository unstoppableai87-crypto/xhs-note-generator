"""XHS Note Generator - upload photos + a few sentences, get an AI-drafted
小红书 (Xiaohongshu) note (title/content/hashtags), run it through a local
违禁词 (banned-word) check, preview and edit it, then queue it up for manual
posting (XHS has no public posting API, so the final publish step stays
manual by design - this app just gets you a clean, checked draft fast).
"""
import urllib.parse

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import compliance
import config
import cover
import gemini_client
import storage

st.set_page_config(page_title="XHS Note Generator", page_icon="📕", layout="wide")

creator_passcode = config.get_setting("CREATOR_PASSCODE")
customer_passcode = config.get_setting("CUSTOMER_PASSCODE")
if "user_role" not in st.session_state:
    st.session_state.user_role = None  # "admin" or "guest"

if (creator_passcode or customer_passcode) and st.session_state.user_role is None:
    st.title("📕 XHS Note Generator")
    st.subheader("🔒 请输入访问密码")
    entered_passcode = st.text_input("密码", type="password")
    if st.button("进入", type="primary"):
        if creator_passcode and entered_passcode == creator_passcode:
            st.session_state.user_role = "admin"
            st.rerun()
        elif customer_passcode and entered_passcode == customer_passcode:
            st.session_state.user_role = "guest"
            st.rerun()
        else:
            st.error("密码不正确，请重新输入。")
    st.stop()

is_admin = st.session_state.user_role != "guest"

st.title("📕 XHS Note Generator · 小红书笔记生成器")

if "note" not in st.session_state:
    st.session_state.note = None
if "images" not in st.session_state:
    st.session_state.images = []  # list of (filename, bytes)
if "form_key" not in st.session_state:
    st.session_state.form_key = 0
if "just_saved" not in st.session_state:
    st.session_state.just_saved = None

tab_names = ["✍️ 创建笔记", "🖼️ 封面图"]
if is_admin:
    tab_names.append("📋 待发布队列")
tabs = st.tabs(tab_names)
tab_create, tab_cover = tabs[0], tabs[1]
tab_queue = tabs[2] if is_admin else None

# ---------------------------------------------------------------- Create ---
with tab_create:
    if st.session_state.just_saved:
        if is_admin:
            st.success(
                f"✅ 已保存到待发布队列：{st.session_state.just_saved}"
                " — 可以到上方「📋 待发布队列」标签页查看和复制文案。"
            )
        else:
            st.success("🎉 提交成功，谢谢分享！")
        st.session_state.just_saved = None

    st.subheader("1. 上传照片 & 输入要点")
    uploaded = st.file_uploader(
        "上传图片（可多选）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.form_key}",
    )
    user_text = st.text_area(
        "输入几句话 / 关键词",
        placeholder="例如：今天去了一家新开的咖啡店，环境很好，拿铁很香浓，价格也实惠...",
        height=120,
        key=f"user_text_{st.session_state.form_key}",
    )
    style = st.selectbox(
        "内容风格",
        ["生活分享", "美食探店", "美妆护肤", "穿搭", "旅行", "好物推荐", "家居家装"],
        key=f"style_{st.session_state.form_key}",
    )

    if st.button("🚀 生成笔记", type="primary", disabled=not user_text.strip()):
        images = [(f.getvalue(), f.type or "image/jpeg") for f in (uploaded or [])]
        with st.spinner("AI 正在生成中..."):
            try:
                result = gemini_client.generate_note(user_text, style, images)
                st.session_state.note = result
                st.session_state.images = [(f.name, f.getvalue()) for f in (uploaded or [])]
            except gemini_client.GeminiError as e:
                st.error(str(e))

    note = st.session_state.note
    if note:
        st.divider()
        st.subheader("2. 选择标题 & 编辑内容")

        # --- 10-title selector ---
        titles_list = note.get("titles", [])
        rec = note.get("recommended_title", {})
        rec_text = rec.get("text", "")
        rec_reason = rec.get("reason", "")

        if titles_list:
            if rec_text:
                st.info(f"💡 AI推荐：**{rec_text}**{'  — ' + rec_reason if rec_reason else ''}")
            title_labels = [f"[{t['style']}] {t['text']}" for t in titles_list]
            rec_idx = next((i for i, t in enumerate(titles_list) if t["text"] == rec_text), 0)
            selected_idx = st.radio(
                "选择标题版本（10个）",
                range(len(title_labels)),
                format_func=lambda i: title_labels[i],
                index=rec_idx,
                label_visibility="collapsed",
            )
            selected_title_default = titles_list[selected_idx]["text"]
        else:
            selected_idx = 0
            selected_title_default = note.get("title", "")

        col_edit, col_preview = st.columns([1, 1])

        with col_edit:
            title = st.text_input(
                "标题 Title（可直接编辑）",
                value=selected_title_default,
                key=f"title_input_{selected_idx}_{st.session_state.form_key}",
            )
            content = st.text_area("正文 Content", value=note["content"], height=250)
            hashtags_str = st.text_input(
                "话题标签 Hashtags（用逗号分隔）", value=", ".join(note["hashtags"])
            )
            hashtags = [h.strip().lstrip("#") for h in hashtags_str.split(",") if h.strip()]
            note["title"], note["content"], note["hashtags"] = title, content, hashtags

        check = compliance.check_note(title, content, hashtags)
        hits = compliance.total_hits(check)

        with col_preview:
            st.markdown("**📱 小红书预览**")
            with st.container(border=True):
                if st.session_state.images:
                    img_cols = st.columns(min(3, len(st.session_state.images)))
                    for i, (fname, data) in enumerate(st.session_state.images):
                        img_cols[i % len(img_cols)].image(data, use_container_width=True)
                st.markdown(f"### {title}")
                st.write(content)
                st.markdown(" ".join(f"`#{h}`" for h in hashtags))

        # --- Rich extras in expanders ---
        ex1, ex2 = st.columns(2)
        with ex1:
            if note.get("alt_hooks"):
                with st.expander("💡 可选开头（5种 Hook）"):
                    for i, hook in enumerate(note["alt_hooks"], 1):
                        st.markdown(f"**方案{i}：** {hook}")
            if note.get("seo_keywords"):
                with st.expander("🔍 SEO 关键词"):
                    kw = note["seo_keywords"]
                    if kw.get("core"):
                        st.markdown("**核心词：** " + " · ".join(kw["core"]))
                    if kw.get("longtail"):
                        st.markdown("**长尾词：** " + " · ".join(kw["longtail"]))
                    if kw.get("search"):
                        st.markdown("**搜索词：** " + " · ".join(kw["search"]))
            if note.get("image_suggestions"):
                with st.expander("📷 图片建议"):
                    for s in note["image_suggestions"]:
                        st.markdown(f"**{s.get('position','')}：** {s.get('description','')}")
        with ex2:
            if note.get("alt_ctas"):
                with st.expander("💬 可选结尾（5种互动引导）"):
                    for i, cta in enumerate(note["alt_ctas"], 1):
                        st.markdown(f"**方案{i}：** {cta}")
            if note.get("publish_advice"):
                with st.expander("📅 发布建议"):
                    pa = note["publish_advice"]
                    if pa.get("best_time"):
                        st.markdown(f"**⏰ 建议时间：** {pa['best_time']}")
                    if pa.get("target_audience"):
                        st.markdown(f"**👥 目标人群：** {pa['target_audience']}")
                    if pa.get("comment_guide"):
                        st.markdown(f"**💬 评论引导：** {pa['comment_guide']}")
                    pin = pa.get("pin_comment")
                    if pin is not None:
                        st.markdown(f"**📌 置顶评论：** {'建议' if pin else '不需要'}")

        st.divider()
        st.subheader("3. 违禁词检测 Compliance Check")
        if hits == 0:
            st.success("✅ 未检测到违禁词，可以发布")
        else:
            st.error(f"⚠️ 检测到 {hits} 处可能的违禁/风险词，建议修改后再发布")
            for field, field_hits in check.items():
                for h in field_hits:
                    st.write(f"- **{field}**: `{h['word']}` — {h['category']}")

            if st.button("🔄 一键改写违规内容"):
                with st.spinner("AI 正在改写..."):
                    try:
                        if check["title"]:
                            note["title"] = gemini_client.rewrite_field(
                                "标题", title, [h["word"] for h in check["title"]]
                            )
                        if check["content"]:
                            note["content"] = gemini_client.rewrite_field(
                                "正文", content, [h["word"] for h in check["content"]]
                            )
                        if check["hashtags"]:
                            rewritten = gemini_client.rewrite_field(
                                "话题标签（逗号分隔）", ", ".join(hashtags), [h["word"] for h in check["hashtags"]]
                            )
                            note["hashtags"] = [h.strip().lstrip("#") for h in rewritten.split(",") if h.strip()]
                        st.rerun()
                    except gemini_client.GeminiError as e:
                        st.error(str(e))

        st.divider()
        st.subheader("4. 确认发布")
        allow_save = True
        if hits > 0:
            allow_save = st.checkbox("我已检查上述违禁词标记，确认内容可以发布")

        if st.button("✅ 通过审核，加入待发布队列", disabled=not allow_save, type="primary"):
            with st.spinner("正在上传到队列..."):
                try:
                    draft_id = storage.save_draft(
                        title, content, hashtags, st.session_state.images,
                        source="creator" if is_admin else "customer",
                    )
                    st.session_state.just_saved = draft_id
                    st.session_state.note = None
                    st.session_state.images = []
                    st.session_state.form_key += 1
                    st.rerun()
                except storage.StorageError as e:
                    st.error(str(e))

# ------------------------------------------------------------------ Cover --
with tab_cover:
    st.subheader("🖼️ 封面图生成器 · 4图拼版 + 标题")
    st.caption("上传最多4张照片，自动拼成2x2方格，标题以白字黑边样式叠加在图片上。")

    default_title = st.session_state.note["title"] if st.session_state.note else ""
    cover_title = st.text_input("封面标题", value=default_title, key="cover_title_input")
    cover_subtitle = st.text_input(
        "位置/标签（可选，会显示为白底圆角标签）",
        placeholder="例如：Tropicana 218 Macalister",
        key="cover_subtitle_input",
    )
    cover_photos = st.file_uploader(
        "上传照片（建议4张）",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="cover_uploader",
    )
    if cover_photos and len(cover_photos) > 4:
        st.warning("最多使用前4张照片，其余将被忽略。")

    if st.button(
        "🖼️ 生成封面图", type="primary", disabled=not (cover_photos and cover_title.strip())
    ):
        image_bytes = [f.getvalue() for f in cover_photos[:4]]
        st.session_state.cover_png = cover.create_cover(
            image_bytes, cover_title.strip(), subtitle=cover_subtitle.strip() or None
        )

    if st.session_state.get("cover_png"):
        st.image(st.session_state.cover_png, caption="封面预览", width=420)
        st.download_button(
            "⬇️ 下载封面图",
            data=st.session_state.cover_png,
            file_name="cover.png",
            mime="image/png",
        )

# ----------------------------------------------------------------- Queue ---
if is_admin:
    with tab_queue:
        st.subheader("📋 待发布队列")
        if st.button("🔄 刷新队列"):
            st.rerun()
        try:
            drafts = storage.list_drafts()
        except storage.StorageError as e:
            drafts = []
            st.error(str(e))

        if not drafts:
            st.info("暂无草稿，先去「创建笔记」生成一篇，或者等客户提交～")
        for d in drafts:
            source_badge = "👤 客户提交" if d["source"] == "customer" else "✍️ 我创建"
            with st.expander(f"{d['status']} · {source_badge} · {d['title']} · {d['created_at']}"):
                if d["image_urls"]:
                    cols = st.columns(min(3, len(d["image_urls"])))
                    for i, url in enumerate(d["image_urls"]):
                        cols[i % len(cols)].image(url, use_container_width=True)
                st.write(d["content"])
                st.markdown(" ".join(f"`#{h}`" for h in d["hashtags"]))
                st.code(storage.copy_text(d), language=None)

                wa_url = "https://wa.me/?text=" + urllib.parse.quote(storage.copy_text(d))
                st.link_button("📲 发送到 WhatsApp", wa_url)
                st.caption("会打开 WhatsApp 并填好文案，你选择联系人后手动发送（照片需要自己另外附加）。")

                c1, c2 = st.columns(2)
                if c1.button("标记为已发布", key=f"posted_{d['id']}"):
                    storage.update_status(d["id"], storage.POSTED)
                    st.rerun()
                if c2.button("🗑️ 删除", key=f"delete_{d['id']}"):
                    storage.delete_draft(d["id"])
                    st.rerun()

"""Customer-facing intake form.

A guest opens this page (deployed as its OWN Streamlit Cloud app, separate
from app.py), uploads a few photos, writes a few sentences about their
experience, and submits. This auto-generates a draft note via Gemini, runs
it through the banned-word check, and drops it straight into the shared
Google Sheets queue - it shows up in app.py's 待发布队列 tab for the creator
to review/edit/approve. The guest never sees the creator's internal tools.
"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import compliance
import config
import gemini_client
import storage

st.set_page_config(page_title="分享你的体验", page_icon="📸", layout="centered")
st.title("📸 分享你的体验")
st.caption("上传几张照片，写几句话，我们会帮你生成一篇小红书笔记草稿～")

if "customer_submitted" not in st.session_state:
    st.session_state.customer_submitted = False

if st.session_state.customer_submitted:
    st.success("🎉 提交成功，谢谢分享！")
    if st.button("再分享一次"):
        st.session_state.customer_submitted = False
        st.rerun()
else:
    required_passcode = config.get_setting("CUSTOMER_PASSCODE")
    passcode = st.text_input("邀请码", type="password") if required_passcode else None

    photos = st.file_uploader(
        "上传照片", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True
    )
    text = st.text_area(
        "写几句话，分享你的体验",
        height=140,
        placeholder="例如：住了三天两夜，很喜欢这里的游泳池，房东很亲切，客服也很周到...",
    )

    if st.button("✅ 提交", type="primary", disabled=not text.strip()):
        if required_passcode and passcode != required_passcode:
            st.error("邀请码不正确，请确认后重新输入。")
        else:
            with st.spinner("正在生成中，请稍候..."):
                try:
                    images = [(f.getvalue(), f.type or "image/jpeg") for f in (photos or [])]
                    result = gemini_client.generate_note(text, "生活分享", images)

                    check = compliance.check_note(result["title"], result["content"], result["hashtags"])
                    status = storage.NEEDS_REVIEW if compliance.total_hits(check) else storage.PENDING

                    image_files = [(f.name, f.getvalue()) for f in (photos or [])]
                    storage.save_draft(
                        result["title"], result["content"], result["hashtags"],
                        image_files, source="customer", status=status,
                    )

                    st.session_state.customer_submitted = True
                    st.rerun()
                except gemini_client.GeminiError:
                    st.error("生成失败，请稍后再试一次。")
                except storage.StorageError:
                    st.error("提交失败（系统问题），请稍后再试一次。")

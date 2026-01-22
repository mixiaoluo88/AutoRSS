import os
import json
import streamlit as st

from services.store import list_report_files
from utils.reporting import generate_markdown_report
from services.git_helper import commit
from services.config import get_config

st.set_page_config(page_title="历史报告", page_icon="📚", layout="wide")
st.title("📚 历史简报归档")

files = list_report_files(ext=".json")
if not files:
    st.info("暂无历史报告，请先在 ‘运行分析’ 页面生成。")
    st.stop()

selected_file = st.selectbox("选择报告文件", files, format_func=lambda x: os.path.basename(x))
with open(selected_file, "r", encoding="utf-8") as f:
    report = json.load(f)

# 导出/复制区域
with st.expander("📤 导出/复制 Markdown 报告 (适用于公众号/Notion)"):
    md_text = generate_markdown_report(report)
    st.markdown("##### 预览与复制")
    st.code(md_text, language="markdown")

    st.download_button(
        label="📥 下载 .md 文件",
        data=md_text,
        file_name=f"report_{report['meta'].get('date','')}.md",
        mime="text/markdown",
    )

    # 保存为仓库文件并 git 提交
    cfg = get_config()
    if st.button("💾 保存为 Markdown 到仓库并提交"):
        ts = report.get("meta", {}).get("date", "").replace(" ", "_").replace(":","").replace("-","")
        domain = report.get("meta", {}).get("domain", "report")
        md_name = f"{ts}_{domain}.md" if ts else f"{domain}.md"
        md_path = os.path.join(os.path.dirname(selected_file), md_name)
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_text)
            st.success(f"已保存 Markdown: {md_name}")
            if cfg.get("GIT_AUTO_COMMIT", True):
                summary = commit([selected_file, md_path], message=f"chore(report): export md {md_name}")
                st.caption(summary)
        except Exception as e:
            st.error(f"保存失败: {e}")

# 顶部：全局总结
st.markdown("### 📰 本期看点 (Issue Overview)")
st.info(report.get("global_summary", "无总结内容"))

st.divider()

# 关键词筛选与分数过滤
all_keywords = set()
articles = report.get("articles", [])
for art in articles:
    kws = art.get("ai_analysis", {}).get("keywords", [])
    if isinstance(kws, list):
        all_keywords.update(kws)
    elif isinstance(kws, str):
        all_keywords.add(kws)

col_f1, col_f2 = st.columns([3, 1])
with col_f1:
    selected_kws = st.multiselect("🔍 按关键词筛选", sorted(list(all_keywords)))
with col_f2:
    min_score = st.slider("最低分数", 0, 100, 60)

# 过滤
display_list = []
for art in articles:
    ai = art.get("ai_analysis", {})
    score = ai.get("score", 0)
    art_kws = set(ai.get("keywords", []) if isinstance(ai.get("keywords", []), list) else [ai.get("keywords", [])])
    if score < min_score:
        continue
    if selected_kws and not art_kws.intersection(set(selected_kws)):
        continue
    display_list.append(art)

st.caption(f"共显示 {len(display_list)} / {len(articles)} 篇文章")

# 列表渲染
for art in display_list:
    ai = art.get("ai_analysis", {})
    score = ai.get("score", 0)
    score_color = "red" if score >= 9 else ("orange" if score >= 7 else "gray")

    with st.container():
        c1, c2 = st.columns([0.1, 0.9])
        with c1:
            st.markdown(f"<h2 style='text-align: center; color: {score_color};'>{score}</h2>", unsafe_allow_html=True)
            st.caption("Score")
        with c2:
            title_cn = ai.get("title_cn", art["title"]) if art.get("title") else ai.get("title_cn", "")
            link = art.get("link", "#")
            st.markdown(f"### [{title_cn}]({link})")
            if title_cn != art.get("title"):
                st.caption(f"Original: {art.get('title')}")
            st.caption(f"📅 {art.get('pub_date','')} | Source: {art.get('source','')} | 🏷️ {ai.get('category', 'General')}")
            if ai.get("one_sentence"):
                st.info(f"📌 **看点**: {ai.get('one_sentence')}")
            if ai.get("keywords"):
                if isinstance(ai["keywords"], list):
                    st.markdown(" ".join([f"`{k}`" for k in ai["keywords"]]))
                else:
                    st.markdown(f"`{ai['keywords']}`")
            st.write(ai.get("summary", "暂无摘要"))
            if ai.get("reason"):
                st.caption(f"💡 评分依据: {ai.get('reason')}")
        st.divider()

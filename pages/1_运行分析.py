import os
import json
from datetime import datetime
import streamlit as st

import core
from services.store import ensure_dirs, load_prompts, REPORTS_DIR
from services.config import get_config, is_config_ready
from services.git_helper import commit
from utils.reporting import aggregate_history_stats, generate_markdown_report
from utils.ui import metric_card, light_card

ensure_dirs()
st.set_page_config(page_title="运行分析", page_icon="⚡️", layout="wide")

st.title("⚡️ 开始新一期分析")

cfg = get_config()
if not is_config_ready(cfg):
    st.warning("检测到配置不完整，请先在‘提示词与配置’页面设置 st.secrets 或环境变量。")

colm = st.columns(4)
try:
    raw_articles = core.fetch_rss_articles(cfg)
    unique_articles = core.deduplicate_articles(raw_articles, threshold=float(cfg.get("DEDUP_THRESHOLD", 0.65)))
    hist_stats = aggregate_history_stats(limit=50)
    prompts = load_prompts()
    
    metrics_data = {
        "近7天抓取文章数": {"value": len(raw_articles), "emoji": "📰"},
        "去重后文章数": {"value": len(unique_articles), "emoji": "🏅"},
        "历史报告数量": {"value": hist_stats.get("total_reports", 0), "emoji": "📚"},
        "提示词领域数量": {"value": len(prompts.keys()), "emoji": "🪣"},
    }
    
    for i, (k, v) in enumerate(metrics_data.items()):
        with colm[i]:
            metric_card(k, v["value"], emoji=v["emoji"])
except Exception as e:
    st.error(f"统计信息获取失败：{e}")

st.markdown("---")

prompts_data = load_prompts()
domains = list(prompts_data.keys()) or ["Bioinfo"]
col1, col2 = st.columns([2, 1])
with col1:
    selected_domain = st.selectbox("选择分析领域 / 提示词组", domains)
with col2:
    run_btn = st.button("🚀 立即运行", type="primary", use_container_width=True)

if run_btn:
    status_text = st.empty()
    progress_bar = st.progress(0)

    def update_progress(p: float, text: str):
        progress_bar.progress(p)
        status_text.text(text)

    try:
        result = core.run_pipeline(
            selected_domain,
            prompts_data[selected_domain],
            progress_callback=update_progress,
            cfg=cfg,
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_name = f"{ts}_{selected_domain}.json"
        json_path = os.path.join(REPORTS_DIR, json_name)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 生成并保存 Markdown
        md_text = generate_markdown_report(result)
        md_name = f"{ts}_{selected_domain}.md"
        md_path = os.path.join(REPORTS_DIR, md_name)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_text)

        progress_bar.progress(100)
        status_text.text("✅ 分析完成！报告已保存并可在历史页面查看。")
        st.success(f"报告已保存: {json_name}")
        st.json(result.get("meta", {}))

        # Git 自动提交
        auto_commit = bool(cfg.get("GIT_AUTO_COMMIT", True))
        auto_tag = bool(cfg.get("GIT_AUTO_TAG", False))
        if auto_commit:
            tag = f"report-{ts}" if auto_tag else None
            summary = commit([json_path, md_path], message=f"feat(report): {selected_domain} {ts}", tag=tag, cwd=os.getcwd())
            light_card("Git 提交结果", summary)

        st.info("前往左侧页面 ‘历史报告’ 查看详情或导出 Markdown。")
    except Exception as e:
        st.error(f"运行出错: {e}")

try:
    hist = aggregate_history_stats(limit=50)
    cat = hist.get("category_count", {})
    per = hist.get("per_issue_passed", [])
    import altair as alt
    import pandas as pd

    left, right = st.columns(2)
    with left:
        st.subheader("📊 历史类别分布")
        df_cat = pd.DataFrame({"category": list(cat.keys()), "count": list(cat.values())})
        chart_cat = alt.Chart(df_cat).mark_bar(color="#1479FF").encode(x="category", y="count")
        st.altair_chart(chart_cat, use_container_width=True)
    with right:
        st.subheader("📈 每期通过数趋势")
        df_per = pd.DataFrame(per, columns=["date", "passed"]) if per else pd.DataFrame({"date": [], "passed": []})
        chart_line = alt.Chart(df_per).mark_line(color="#1479FF").encode(x="date", y="passed")
        st.altair_chart(chart_line, use_container_width=True)
except Exception as e:
    st.warning(f"历史统计绘制失败：{e}")
import os
import json
import streamlit as st

from services.store import ensure_dirs, load_prompts, save_prompts, PROMPTS_FILE
from services.config import get_config, is_config_ready
from services.git_helper import commit

ensure_dirs()
st.set_page_config(page_title="提示词与配置", page_icon="🛠️", layout="wide")

st.title("🛠️ 提示词配置 (Prompt Engineering) 与配置状态")

# 配置状态
cfg = get_config()
ready = is_config_ready(cfg)
if ready:
    st.success("✅ 配置已就绪（读取自 st.secrets 或环境变量）")
else:
    st.warning("⚠️ 配置尚未完整。请在 .streamlit/secrets.toml 中设置 freshrss/llm/git 等字段，或通过环境变量提供。")

with st.expander("📄 查看当前配置（敏感值不展示全量）", expanded=False):
    safe_cfg = {k: ("***" if "KEY" in k or "PASS" in k else v) for k, v in cfg.items()}
    st.json(safe_cfg)

st.markdown("---")

# secrets 示例提示
st.markdown("#### Secrets 示例 (复制到 .streamlit/secrets.toml)")
secrets_example = """
[freshrss]
host = "http://localhost:8080"
username = "your-user"
password = "your-pass"

[llm]
base_url = "https://api.siliconflow.cn/v1"
model = "Pro/deepseek-ai/DeepSeek-V3.2"
api_key = "sk-..."

[git]
auto_commit = true
auto_tag = false
user_name = "Your Name"
user_email = "you@example.com"
"""
st.code(secrets_example, language="toml")

st.markdown("---")

# 提示词管理
prompts_data = load_prompts()
col_new, col_del = st.columns(2)
with col_new:
    new_domain = st.text_input("新建领域名称")
    if st.button("➕ 添加领域") and new_domain:
        if new_domain not in prompts_data:
            template = list(prompts_data.values())[0] if prompts_data else {"step1": "", "step2": "", "step3": ""}
            prompts_data[new_domain] = template
            save_prompts(prompts_data)
            st.rerun()

selected_domain = st.selectbox("选择要编辑的领域", list(prompts_data.keys()))

if selected_domain:
    current_p = prompts_data[selected_domain]
    with st.form("prompt_form"):
        st.subheader(f"编辑: {selected_domain}")
        st.markdown("#### 步骤 1: 筛选 (Filter)")
        st.caption("输入变量: `{title}`, `{content}`. 要求: 返回 JSON `{\"pass\": true, \"reason\": \"...\"}` 或 `{\"value\": number}`")
        p1 = st.text_area("Step 1 Prompt", current_p.get("step1", ""), height=150)

        st.markdown("#### 步骤 2: 深度分析 (Analysis)")
        st.caption("输入变量: `{title}`, `{content}`. 要求: 返回 JSON 包含 score, summary, keywords 等")
        p2 = st.text_area("Step 2 Prompt", current_p.get("step2", ""), height=200)

        st.markdown("#### 步骤 3: 全局总结 (Overview)")
        st.caption("输入变量: `{context}` (包含所有步骤2选出的文章标题和摘要)")
        p3 = st.text_area("Step 3 Prompt", current_p.get("step3", ""), height=150)

        if st.form_submit_button("💾 保存配置"):
            prompts_data[selected_domain] = {"step1": p1, "step2": p2, "step3": p3}
            save_prompts(prompts_data)
            st.success("配置已更新！")
            cfg = get_config()
            if cfg.get("GIT_AUTO_COMMIT", True):
                summary = commit([PROMPTS_FILE], message=f"chore(prompts): update {selected_domain}")
                st.caption(summary)

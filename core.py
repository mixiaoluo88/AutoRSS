import json
import re
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from bs4 import BeautifulSoup
from freshrss_api import FreshRSSAPI
from openai import OpenAI

from services.config import get_config


def clean_html(html_content: Optional[str]) -> str:
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def get_llm_client(cfg: Dict) -> OpenAI:
    return OpenAI(api_key=cfg["LLM_API_KEY"], base_url=cfg["LLM_BASE_URL"])  # type: ignore


def fetch_rss_articles(cfg: Dict, days: Optional[int] = None, max_count: Optional[int] = None) -> List[Dict]:
    """从 FreshRSS 获取源数据"""
    days = days if days is not None else int(cfg.get("FETCH_DAYS", 7))
    max_count = max_count if max_count is not None else int(cfg.get("FETCH_MAX_COUNT", 100))

    print("📡 连接 FreshRSS...")
    client = FreshRSSAPI(
        host=cfg["FRESHRSS_HOST"],
        username=cfg["FRESHRSS_USER"],
        password=cfg["FRESHRSS_PASS"],
    )

    entries = client.get_unreads()
    candidates: List[Dict] = []
    now_utc = datetime.now(timezone.utc)

    for entry in entries:
        timestamp = getattr(entry, "created_on_time", 0)
        if not timestamp:
            continue

        pub_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if (now_utc - pub_date).days > days:
            continue

        raw_html = getattr(entry, "html", "") or ""
        clean_text = clean_html(raw_html)
        if len(clean_text) < 50:
            continue

        candidates.append(
            {
                "title": entry.title,
                "link": getattr(entry, "url", getattr(entry, "link", "#")),
                "pub_date": pub_date.strftime("%Y-%m-%d %H:%M"),
                "source": getattr(entry, "feed", {}).get("title", "Unknown"),
                "content_text": clean_text,
            }
        )

    candidates.sort(key=lambda x: x["pub_date"], reverse=True)
    return candidates[: max_count or 100]


def safe_json_parse(response_text: str) -> Dict:
    """辅助函数：清理 Markdown 标记并解析 JSON"""
    text = response_text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except Exception:
        return {}


def calculate_jaccard_similarity(text1: str, text2: str) -> float:
    """计算两个文本的 Jaccard 相似度 (基于词集合)"""
    set1 = set(re.split(r"\W+", text1.lower()))
    set2 = set(re.split(r"\W+", text2.lower()))
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union


def deduplicate_articles(articles: List[Dict], threshold: float = 0.6) -> List[Dict]:
    """对文章列表进行去重。threshold: 相似度阈值 (0.0-1.0)，高于此值视为重复。"""
    unique_articles: List[Dict] = []
    print(f"🔄 开始去重，原始数量: {len(articles)}")
    for article in articles:
        is_duplicate = False
        current_content = article["title"] + " " + article["content_text"][:500]

        for existing in unique_articles:
            existing_content = existing["title"] + " " + existing["content_text"][:500]
            similarity = calculate_jaccard_similarity(current_content, existing_content)
            if similarity > threshold:
                is_duplicate = True
                print(
                    f"   ❌ 发现重复 (相似度 {similarity:.2f}): {article['title']} <==> {existing['title']}"
                )
                break

        if not is_duplicate:
            unique_articles.append(article)

    print(f"✅ 去重完成，剩余数量: {len(unique_articles)}")
    return unique_articles


# === 核心三步工作流 ===

def step1_filter_articles(articles: List[Dict], prompt_template: str, client: OpenAI, model: str) -> List[Dict]:
    """步骤1：快速初筛 (Pass/Fail) — 兼容 {"pass": true/false} 或 {"value": number}"""
    filtered_articles: List[Dict] = []

    for article in articles:
        prompt = prompt_template.format(title=article["title"], content=article["content_text"][:1000])
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception as e:
            print(f"Filter call error: {e}")
            continue

        try:
            res = safe_json_parse(resp.choices[0].message.content)  # type: ignore[attr-defined]
        except Exception:
            res = {}

        should_ignore = bool(res.get("ignore", False))
        pass_flag: Optional[bool] = None
        if "pass" in res:
            try:
                pass_flag = bool(res.get("pass"))
            except Exception:
                pass
        if pass_flag is None:
            try:
                pass_flag = float(res.get("value", 0)) > 0
            except Exception:
                pass_flag = None
        if pass_flag is None and "score" in res:
            try:
                pass_flag = float(res.get("score", 0)) > 0
            except Exception:
                pass_flag = False

        if not should_ignore and pass_flag:
            article["filter_data"] = res
            filtered_articles.append(article)
        else:
            print(f"过滤掉: {article['title']} (Reason: {res.get('reason')})")

    return filtered_articles


def _chat_json(client: OpenAI, model: str, prompt: str, temperature: float = 0.3) -> Dict:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        return safe_json_parse(resp.choices[0].message.content)  # type: ignore[attr-defined]
    except Exception as e:
        print(f"Chat json error: {e}")
        return {}


def step2_deep_analyze(articles: List[Dict], prompt_template: str, client: OpenAI, model: str) -> List[Dict]:
    """步骤2：深度分析 (摘要、打分、标签)"""
    analyzed: List[Dict] = []
    for article in articles:
        prompt = prompt_template.format(title=article["title"], content=article["content_text"][:4000])
        ai_data = _chat_json(client, model, prompt, temperature=0.3)
        if ai_data:
            article["ai_analysis"] = ai_data
            analyzed.append(article)
    return analyzed


def step3_global_summary(analyzed_articles: List[Dict], prompt_template: str, client: OpenAI, model: str) -> str:
    """步骤3：全局总结"""
    if not analyzed_articles:
        return "本期无内容。"

    high_value_articles = [a for a in analyzed_articles if a.get("ai_analysis", {}).get("score", 0) >= 6]
    high_value_articles.sort(key=lambda x: x.get("ai_analysis", {}).get("score", 0), reverse=True)

    if not high_value_articles:
        high_value_articles = analyzed_articles[:10]

    context_str = ""
    for idx, item in enumerate(high_value_articles):
        ai = item.get("ai_analysis", {})
        context_str += f"""
        ---
        [文章 {idx+1}]
        标题: {item.get('title')}
        中文标题: {ai.get('title_cn', '')}
        分类: {ai.get('category', 'OTHER')}
        评分: {ai.get('score', 0)}
        一句话亮点: {ai.get('one_sentence', '')}
        核心洞察(Key Insight): {ai.get('key_insight', '无')}
        摘要: {ai.get('summary', '')}
        """

    prompt = prompt_template.format(context=context_str)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return resp.choices[0].message.content  # type: ignore[attr-defined]
    except Exception as e:
        return f"总结失败: {e}"


def run_pipeline(domain_name: str, prompts: Dict[str, str], progress_callback: Optional[Callable[[float, str], None]] = None, cfg: Optional[Dict] = None) -> Dict:
    """执行完整流程的入口函数"""
    cfg = cfg or get_config()
    client = get_llm_client(cfg)
    model = cfg["LLM_MODEL"]

    if progress_callback:
        progress_callback(0.1, "正在从 FreshRSS 拉取数据...")
    raw_articles = fetch_rss_articles(cfg)

    if progress_callback:
        progress_callback(0.2, "正在进行内容去重...")
    unique_articles = deduplicate_articles(raw_articles, threshold=float(cfg.get("DEDUP_THRESHOLD", 0.65)))

    if progress_callback:
        progress_callback(0.3, f"去重后剩余 {len(unique_articles)} 篇，开始步骤1：智能初筛...")
    passed_articles = step1_filter_articles(unique_articles, prompts["step1"], client, model)

    if progress_callback:
        progress_callback(0.6, f"初筛通过 {len(passed_articles)} 篇，开始步骤2：深度分析...")
    analyzed_articles = step2_deep_analyze(passed_articles, prompts["step2"], client, model)

    if progress_callback:
        progress_callback(0.9, "步骤3：生成本期简报...")
    final_summary = step3_global_summary(analyzed_articles, prompts["step3"], client, model)

    report_data = {
        "meta": {
            "schema": 1,
            "domain": domain_name,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_raw": len(raw_articles),
            "total_unique": len(unique_articles),
            "total_passed": len(passed_articles),
        },
        "global_summary": final_summary,
        "articles": analyzed_articles,
    }

    return report_data

import os
import json
from typing import Dict, List

DATA_DIR = "data"
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
MARKDOWN_DIR = REPORTS_DIR  # 保存 md 与 json 同目录


def ensure_dirs() -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    if not os.path.exists(PROMPTS_FILE):
        default_prompts = {
            "Bioinfo": {
                "step1": "判断文章是否有关生物信息学，返回JSON: {\"pass\": true/false, \"reason\": \"...\"}. 标题: {title}, 内容: {content}",
                "step2": "总结并打分，返回JSON: {\"summary\": \"...\", \"score\": 8, \"keywords\": [\"DNA\", \"Tool\"], \"one_sentence\": \"...\"}. 文章: {title}\n{content}",
                "step3": "根据以下文章列表生成简报: {context}",
            }
        }
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_prompts, f, ensure_ascii=False, indent=2)


def load_prompts() -> Dict:
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prompts(data: Dict) -> None:
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_report_files(ext: str = ".json") -> List[str]:
    files = []
    if os.path.isdir(REPORTS_DIR):
        for name in os.listdir(REPORTS_DIR):
            if name.endswith(ext):
                files.append(os.path.join(REPORTS_DIR, name))
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files

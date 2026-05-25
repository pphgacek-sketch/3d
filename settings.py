import os
import json
from dataclasses import dataclass, asdict

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

@dataclass
class AppSettings:
    api_key: str = os.environ.get("OPENAI_API_KEY", "")
    model: str = "gpt-4o"
    backend: str = "cadquery"
    cq_python: str = "python"
    fusion_url: str = "http://localhost:7634"
    fusion_timeout: int = 60
    output_dir: str = os.path.join(os.path.expanduser("~"), "CadAgent_output")
    max_retries: int = 3
    knowledge_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge")
    temperature: float = 0.2
    keep_scripts: bool = True
    auto_open_step: bool = False

def load_settings() -> AppSettings:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            s = AppSettings()
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
            return s
        except Exception:
            pass
    return AppSettings()

def save_settings(s: AppSettings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(s), f, indent=2, ensure_ascii=False)

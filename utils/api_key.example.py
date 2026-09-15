"""Copy to api_key.py and configure the judge through environment variables."""

import os

api_keys = {"gpt-5.4": os.environ["EVAL_JUDGE_API_KEY"]}
model_base_url = {"gpt-5.4": os.environ["EVAL_JUDGE_BASE_URL"]}
model_api_name = {"gpt-5.4": os.environ.get("EVAL_JUDGE_MODEL", "gpt-5.4")}

import google.generativeai as genai
import json
import re
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def analyze_cv(cv_text: str):
    # (Bạn có thể lưu prompt trong file txt nếu muốn tách tiếp)
    prompt_template = open("prompt/prompt.txt", "r", encoding="utf-8").read()
    prompt = prompt_template.format(cv_text=cv_text)

    model = genai.GenerativeModel("gemini-2.0-flash")

    try:
        response = model.generate_content(prompt)
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            raise ValueError("Không tìm thấy JSON hợp lệ trong phản hồi.")
    except Exception as e:
        raise Exception(f"Lỗi khi gọi Gemini API: {e}")

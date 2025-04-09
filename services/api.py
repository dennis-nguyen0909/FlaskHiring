import requests

BASE_API = "https://hiredev-api.shop/nest/api/v1"
BEARER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2N2U3NGM1Y2Y1ODkwNzcwZmE0YjcxODkiLCJ1c2VybmFtZSI6ImR1eTFAZ21haWwuY29tIiwicm9sZSI6eyJyb2xlX3Blcm1pc3Npb24iOltdLCJfaWQiOiI2NzcwYjE5M2I1MGVlY2FjYmI4ZTBjNWQiLCJyb2xlX25hbWUiOiJVU0VSIn0sImlhdCI6MTc0NDE4OTQxMiwiZXhwIjoxNzQ0Nzk0MjEyfQ.jWOZhxcPzr3_qQ_vRyGD1MXAkB2eeGyFp210aURpmmg"  # Đặt trong .env cho bảo mật

def post_to_api(endpoint: str, items: list,token:str,user_id:str):
    url = f"{BASE_API}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    for item in items:
        item["user_id"] = user_id 
        try:
            res = requests.post(url, json=item, headers=headers)
            print(f"[{endpoint}] Status: {res.status_code}")
            print(res.json())
        except Exception as e:
            print(f"[{endpoint}] Lỗi gửi dữ liệu: {e}")

def updateUser(endpoint: str, data: dict, token: str, user_id: str):
    url = f"{BASE_API}/{endpoint}"  # Giả sử API cần /endpoint/<user_id>
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data["id"] = user_id  # Đảm bảo có user_id nếu API yêu cầu

    try:
        res = requests.patch(url, json=data, headers=headers)
        print(f"[{endpoint}] ✅ Cập nhật user - Status: {res.status_code}")
        try:
            print("Response:", res.json())
        except:
            print("Không phải JSON:", res.text)
    except Exception as e:
        print(f"[{endpoint}] ❌ Lỗi cập nhật user: {e}")

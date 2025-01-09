# Sử dụng image Python chính thức làm base image
FROM python:3.12-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Sao chép file requirements.txt vào thư mục làm việc
COPY requirements.txt .

# Cài đặt các thư viện cần thiết
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép tất cả mã nguồn vào container
COPY . .

# Thiết lập biến môi trường để không lưu cache file pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Chạy Flask server
CMD ["flask", "run", "--host=0.0.0.0"]

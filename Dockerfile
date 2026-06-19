FROM ubuntu:22.04
# تثبيت المتطلبات الأساسية
RUN apt-get update && apt-get install -y openjdk-17-jre-headless python3 python3-pip curl wget tar && rm -rf /var/lib/apt/lists/*
# تحميل أداة Bore
RUN wget -qO bore.tar.gz https://github.com/ekzhang/bore/releases/download/v0.5.1/bore-v0.5.1-x86_64-unknown-linux-musl.tar.gz && \
    tar -xzf bore.tar.gz && mv bore /usr/local/bin/ && rm bore.tar.gz
WORKDIR /app
# تثبيت مكتبات البايثون
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
# نسخ باقي الملفات
COPY . .
EXPOSE 7860
# تشغيل لوحة التحكم (وهي راح تتكفل بكلشي)
CMD ["python3", "app.py"]

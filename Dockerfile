FROM ubuntu:22.04
# تثبيت المتطلبات الأساسية
RUN apt-get update && apt-get install -y openjdk-17-jre-headless python3 python3-pip curl wget tar && rm -rf /var/lib/apt/lists/*
# تحميل أداة Playit.gg للآي بي الثابت
RUN curl -SsL https://playit-cloud.github.io/playit/playit-linux-amd64 -o /usr/local/bin/playit && \
    chmod +x /usr/local/bin/playit
WORKDIR /app
# تثبيت مكتبات البايثون
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
# نسخ باقي الملفات
COPY . .
EXPOSE 7860
# تشغيل لوحة التحكم
CMD ["python3", "app.py"]

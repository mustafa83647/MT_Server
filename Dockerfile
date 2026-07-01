# استخدام بيئة أوبونتو خفيفة مع Java 8
FROM openjdk:8-jre-slim
# تحديث النظام وتثبيت الأدوات اللازمة (مثل wget لتحميل الملفات)
RUN apt-get update && apt-get install -y wget unzip curl && rm -rf /var/lib/apt/lists/*
# تحديد مسار العمل داخل الكونتينر
WORKDIR /app
# نسخ ملفات المتطلبات وتثبيتها (Flask وغيرها)
COPY requirements.txt .
RUN apt-get update && apt-get install -y python3 python3-pip
RUN pip3 install --no-cache-dir -r requirements.txt
# نسخ باقي ملفات المشروع (app.py وغيرها)
COPY . .
# فتح البورتات (7860 للـ Flask علمود Hugging Face، و 25565 لماين كرافت)
EXPOSE 7860
EXPOSE 25565
# تشغيل ملف البايثون
CMD ["python3", "app.py"]

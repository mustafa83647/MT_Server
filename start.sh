#!/bin/bash
# مسار الحفظ الدائم (البوكت)
DATA_DIR="/data/minecraft_data"
mkdir -p $DATA_DIR/world $DATA_DIR/config $DATA_DIR/mods $DATA_DIR/logs $DATA_DIR/crash-reports
chmod -R 777 /data
# مسار السيرفر المؤقت (الذاكرة السريعة)
SERVER_DIR="/app/minecraft"
mkdir -p $SERVER_DIR
cd $SERVER_DIR
# 1. ربط المجلدات بالبوكت
for dir in world config mods logs crash-reports; do
    rm -rf ./$dir
    ln -s $DATA_DIR/$dir ./$dir
done
# 2. ربط الملفات المهمة بالبوكت (إنشائها إذا ما موجودة ثم ربطها)
for file in server.properties ops.json banned-players.json banned-ips.json whitelist.json usercache.json; do
    touch $DATA_DIR/$file
    rm -f ./$file
    ln -s $DATA_DIR/$file ./$file
done
# إعدادات أساسية
echo "eula=true" > eula.txt
if ! grep -q "online-mode" server.properties; then
    echo "online-mode=false" >> server.properties
fi
# تحميل وتثبيت Fabric
MC_VERSION="1.20.4"
FABRIC_LOADER="0.15.7"
if [ ! -f "fabric-server-launch.jar" ]; then
    echo "جاري تحميل وتثبيت السيرفر..."
    wget -q -O fabric-installer.jar https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.1/fabric-installer-1.0.1.jar
    java -jar fabric-installer.jar server -mcversion $MC_VERSION -loader $FABRIC_LOADER -downloadMinecraft
    rm fabric-installer.jar
fi
# تشغيل نفق Bore
echo "جاري تشغيل أداة Bore لفتح النفق..."
bore local 25565 --to bore.pub > /app/bore.log 2>&1 &
# تشغيل ماينكرافت
echo "جاري تشغيل سيرفر ماينكرافت بـ 10 كيكا رام..."
java -Xms2G -Xmx10G -jar fabric-server-launch.jar nogui

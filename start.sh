#!/bin/bash
# مسار الحفظ الدائم
DATA_DIR="/data/minecraft_data"
mkdir -p $DATA_DIR/world
mkdir -p $DATA_DIR/config
mkdir -p $DATA_DIR/mods
chmod -R 777 /data
# مسار السيرفر المؤقت
SERVER_DIR="/app/minecraft"
mkdir -p $SERVER_DIR
cd $SERVER_DIR
# ربط كل الملفات المهمة بالحفظ الدائم (حتى ما يضيع أي شي)
rm -rf ./world ./config ./mods ./server.properties ./ops.json ./banned-players.json ./whitelist.json
ln -s $DATA_DIR/world ./world
ln -s $DATA_DIR/config ./config
ln -s $DATA_DIR/mods ./mods
touch $DATA_DIR/server.properties $DATA_DIR/ops.json $DATA_DIR/banned-players.json $DATA_DIR/whitelist.json
ln -s $DATA_DIR/server.properties ./server.properties
ln -s $DATA_DIR/ops.json ./ops.json
ln -s $DATA_DIR/banned-players.json ./banned-players.json
ln -s $DATA_DIR/whitelist.json ./whitelist.json
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

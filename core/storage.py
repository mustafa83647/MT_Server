import os
import shutil
from core.config import DATA_DIR, APP_DIR
class EnterpriseStorageManager:
    def __init__(self, logger):
        self.logger = logger
        self.data_config = os.path.join(DATA_DIR, "config")
        self.app_config = os.path.join(APP_DIR, "config")
    def hydrate_to_ram(self):
        self.logger.log("النظام", "🔄 جاري تفعيل محرك المزامنة الفيزيائية لكسر حماية WorldEdit...", is_safe=True)
        os.makedirs(self.data_config, exist_ok=True)
        if os.path.islink(self.app_config): os.remove(self.app_config)
        elif os.path.exists(self.app_config): shutil.rmtree(self.app_config)
        try:
            shutil.copytree(self.data_config, self.app_config, dirs_exist_ok=True)
            self.logger.log("النظام", "✅ تم بناء الملفات الفيزيائية بنجاح. WorldEdit الآن أعمى عن الـ Bucket!", is_safe=True)
        except Exception as e:
            self.logger.log("النظام", f"❌ خطأ في المزامنة الفيزيائية: {e}", is_safe=True)
    def dehydrate_to_disk(self):
        if not os.path.exists(self.app_config): return
        try:
            shutil.copytree(self.app_config, self.data_config, dirs_exist_ok=True)
            for root, dirs, files in os.walk(self.data_config):
                rel_path = os.path.relpath(root, self.data_config)
                app_root = os.path.join(self.app_config, rel_path)
                for file in files:
                    if not os.path.exists(os.path.join(app_root, file)):
                        os.remove(os.path.join(root, file))
                for d in dirs:
                    if not os.path.exists(os.path.join(app_root, d)):
                        shutil.rmtree(os.path.join(root, d))
        except: pass
    def wake_up_world(self):
        self.logger.log("النظام", "⏳ جاري إيقاظ ملفات العالم من السبات السحابي بأمان...", is_safe=True)
        world_path = os.path.join(DATA_DIR, "world")
        if os.path.exists(world_path):
            for root, dirs, files in os.walk(world_path):
                for file in files:
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'rb') as f: f.read(1)
                    except: pass

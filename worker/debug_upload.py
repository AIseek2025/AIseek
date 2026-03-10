from app.services.storage_service import storage_service
import os
import shutil

test_dir = "/app/outputs/test_hls_debug"
if os.path.exists(test_dir):
    shutil.rmtree(test_dir)
os.makedirs(test_dir, exist_ok=True)

with open(os.path.join(test_dir, "master.m3u8"), "w") as f:
    f.write("#EXTM3U")

print(f"Testing upload_directory from {test_dir}")
try:
    result = storage_service.upload_directory(test_dir, "hls/test_debug_01")
    print(f"Result: {result}")
except Exception as e:
    print(f"Exception: {e}")

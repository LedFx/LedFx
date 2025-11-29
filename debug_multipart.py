"""Debug script to test multipart upload."""
import io
import requests
from PIL import Image

# Create sample image
img = Image.new("RGB", (10, 10), color="red")
img_bytes = io.BytesIO()
img.save(img_bytes, "PNG")
img_data = img_bytes.getvalue()

print(f"Image size: {len(img_data)} bytes")

# Test upload
files = {"file": ("test.png", io.BytesIO(img_data), "image/png")}
data = {"path": "debug_test.png"}

resp = requests.post("http://localhost:8888/api/assets", files=files, data=data, timeout=5)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")

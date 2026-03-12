import requests
import numpy as np
import io

CLIENT_ID     = "sh-8b1fcf79-492b-46fc-8721-185d55b6d2b5"
CLIENT_SECRET = "24VgZm2mFiqwbWjpJLst9WclfRsZRj2s"
TOKEN_URL     = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL   = "https://sh.dataspace.copernicus.eu/api/v1/process"

print("Step 1: Getting token...")
r = requests.post(TOKEN_URL, data={
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
})
token = r.json()["access_token"]
print(f"  OK: {token[:30]}...")

print("\nStep 2: Process request...")
evalscript = """
//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B04", "B08", "B11"], units: "REFLECTANCE" }],
        output: { bands: 3, sampleType: "FLOAT32" }
    };
}
function evaluatePixel(sample) {
    return [sample.B04, sample.B08, sample.B11];
}
"""

payload = {
    "input": {
        "bounds": {
            "bbox": [17.0, 34.5, 19.0, 36.5],
            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
        },
        "data": [{
            "type": "sentinel-2-l2a",
            "dataFilter": {
                "timeRange": {
                    "from": "2024-06-01T00:00:00Z",
                    "to":   "2024-08-31T23:59:59Z"
                },
                "mosaickingOrder": "leastCC",
                "maxCloudCoverage": 20
            }
        }]
    },
    "output": {
        "width":  300,
        "height": 300,
        "responses": [{
            "identifier": "default",
            "format": {"type": "image/tiff"}
        }]
    },
    "evalscript": evalscript
}

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type":  "application/json",
    "Accept":        "image/tiff"
}

r = requests.post(PROCESS_URL, json=payload, headers=headers)
print(f"  Status: {r.status_code}")
print(f"  Size: {len(r.content)} bytes")
print(f"  Content-Type: {r.headers.get('Content-Type')}")

if r.status_code != 200:
    print(f"  Error: {r.text[:300]}")
    exit()

print("\nStep 3: Parsing TIFF...")
import tifffile
arr = tifffile.imread(io.BytesIO(r.content))
print(f"  Shape: {arr.shape}")
print(f"  Dtype: {arr.dtype}")

if arr.ndim == 3:
    red  = round(float(np.nanmean(arr[:,:,0])), 4)
    nir  = round(float(np.nanmean(arr[:,:,1])), 4)
    swir = round(float(np.nanmean(arr[:,:,2])), 4)
elif arr.ndim == 2:
    print("  Got 2D array — only 1 band returned, check evalscript")
    exit()

print(f"  Red:  {red}")
print(f"  NIR:  {nir}")
print(f"  SWIR: {swir}")
print(f"  FDI:  {round(nir - (red + swir), 4)}")
print("\nSUCCESS")
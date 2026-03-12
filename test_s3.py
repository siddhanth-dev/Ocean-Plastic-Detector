import requests
import numpy as np
import io
import tifffile

CLIENT_ID     = "sh-8b1fcf79-492b-46fc-8721-185d55b6d2b5"
CLIENT_SECRET = "24VgZm2mFiqwbWjpJLst9WclfRsZRj2s"
TOKEN_URL     = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL   = "https://sh.dataspace.copernicus.eu/api/v1/process"

def get_token():
    r = requests.post(TOKEN_URL, data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    return r.json()["access_token"]

def test(name, lat, lon, token, delta=2.0):
    bbox = [lon-delta, lat-delta, lon+delta, lat+delta]

    # Sentinel-3 OLCI bands for ocean color
    # Oa08 = 665nm (Red), Oa17 = 865nm (NIR), Oa21 = 1020nm (closest to SWIR)
    evalscript = """
    //VERSION=3
    function setup() {
        return {
            input: [{ bands: ["B08", "B17", "B21"], units: "REFLECTANCE" }],
            output: { bands: 3, sampleType: "FLOAT32" }
        };
    }
    function evaluatePixel(sample) {
        return [sample.B08, sample.B17, sample.B21];
    }
    """

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}
            },
            "data": [{
                "type": "sentinel-3-olci",
                "dataFilter": {
                    "timeRange": {
                        "from": "2024-01-01T00:00:00Z",
                        "to":   "2024-12-31T23:59:59Z"
                    },
                    "mosaickingOrder": "leastCC"
                }
            }]
        },
        "output": {
            "width":  300,
            "height": 300,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
        },
        "evalscript": evalscript
    }

    r = requests.post(PROCESS_URL, json=payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "image/tiff"
    })

    if r.status_code != 200:
        print(f"  {name}: ERROR {r.status_code} — {r.text[:200]}")
        return

    try:
        arr  = tifffile.imread(io.BytesIO(r.content))
        red  = round(float(np.nanmean(arr[:,:,0])), 4)
        nir  = round(float(np.nanmean(arr[:,:,1])), 4)
        swir = round(float(np.nanmean(arr[:,:,2])), 4)
        fdi  = round(nir - (red + swir), 4)
        status = "OK" if red > 0 else "ALL ZEROS"
        print(f"  {name}: Red={red} NIR={nir} SWIR={swir} FDI={fdi} [{status}]")
    except Exception as e:
        print(f"  {name}: parse error — {e}")

token = get_token()
print("Testing Sentinel-3 OLCI:\n")
test("Great Pacific Patch",  35.0, -145.0, token)
test("North Atlantic Patch", 28.0,  -45.0, token)
test("Indian Ocean Patch",  -28.0,   80.0, token)
test("Mediterranean Coast",  35.5,   18.0, token)
test("Bay of Bengal",        13.0,   86.0, token)
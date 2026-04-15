## Ocean Plastic Ledger 🌊

An experimental prototype for tracking ocean plastic hotspots using map-based visualization, basic spectral analysis, and a simple ML model.

This project explores how satellite data and crowd-informed datasets could be used to identify and prioritize marine plastic cleanup efforts. However, it is currently limited by the lack of reliable, publicly accessible satellite data specifically for ocean plastic detection.

---

### 1. Features

- **Hotspot Map**
  - Input vessel latitude, longitude, and search radius
  - View known plastic accumulation zones (major gyres + coastal sinks)
  - See severity, FDI score, estimated density, and source for each zone
  - Rank top 3 cleanup targets by a composite priority score

- **FDI Analyzer**
  - Adjust **Red**, **NIR**, and **SWIR** band sliders
  - Compute **FDI = NIR - (RED + SWIR)** and get a severity band (Low → Critical)
  - Get a simple **ML classification** (“Plastic Detected” / “No Plastic”) with confidence

- **Metrics Overview**
  - Total zones tracked
  - Count of critical zones
  - Average FDI score
  - Total area affected (km²)

---

### 2. Tech Stack

- Frontend: Streamlit
- Mapping: Folium, OpenStreetMap
- Backend / Logic: Python
- ML: scikit-learn (Random Forest)
- Data Processing: NumPy, Pandas

---

### 3. Project Structure

- `app.py` – Main Streamlit app (tabs, layout, wiring)
- `fdi.py` – FDI formula, severity banding, and RandomForest model
- `components/map_view.py` – Map UI, hotspot search, cleanup ranking
- `components/metrics.py` – Top‑level metrics cards
- `data/hotspots.py` – Curated dataset of known accumulation zones + helpers

---

### 4. Installation

1. **Clone the repo**

```bash
git clone <your-repo-url>
cd Ocean-Plastic-Detector
```

2. **Create and activate a virtual environment (recommended)**

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows PowerShell
```

3. **Install dependencies**

Make sure you have `pip` up to date:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Dependencies :

- `streamlit`
- `pandas`
- `numpy`
- `scikit-learn`
- `folium`
- `streamlit-folium`

---

4. **Running the App**

From the project root:

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints in your terminal (usually `http://localhost:8501`).

---

### 5. How It Works (High‑Level)

- A curated dataset (data/hotspots.py) contains known ocean plastic accumulation zones derived from research sources (NOAA, The Ocean Cleanup, etc.)
- The app filters zones using distance calculations based on user input
- A scoring system ranks cleanup priorities using severity, density, and proximity
- The FDI analyzer simulates how spectral bands might indicate floating debris
- A simple ML model provides experimental classification based on input values

---

### 6. Notes & Limitations
This is an educational prototype and not a production-ready system.

Key limitations:

- ❗ No reliable real-time satellite dataset
  There is currently no easily accessible, high-quality public dataset specifically for detecting ocean plastic using satellite imagery.
- ❗ Simulated / approximated data
  Hotspot locations and FDI values are based on research summaries and simplified assumptions, not live data pipelines.
- ❗ Experimental ML model
  The Random Forest classifier is trained on a small synthetic dataset and is not scientifically validated.
- ❗ Not suitable for real-world decision making
  This tool is intended for exploration and demonstration purposes only.
---

### 7. License & Attribution

Add your chosen license here (e.g. MIT) and any additional acknowledgements you want to include for data sources and collaborators.

## Global Plastic Ledger 🌊

Real‑time ocean plastic hotspot tracker built with Streamlit, Folium, and a simple ML model. It lets you:

- **Visualize verified plastic accumulation zones** on an interactive global map
- **Rank nearby cleanup targets** for a vessel’s current position
- **Experiment with satellite band inputs** (Red, NIR, SWIR) using a Floating Debris Index (FDI) and a toy Random Forest classifier

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

### 2. Project Structure

- `app.py` – Main Streamlit app (tabs, layout, wiring)
- `fdi.py` – FDI formula, severity banding, and RandomForest model
- `components/map_view.py` – Map UI, hotspot search, cleanup ranking
- `components/metrics.py` – Top‑level metrics cards
- `data/hotspots.py` – Curated dataset of known accumulation zones + helpers

---

### 3. Installation

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

If you don’t have a `requirements.txt` yet, typical dependencies are:

- `streamlit`
- `pandas`
- `numpy`
- `scikit-learn`
- `folium`
- `streamlit-folium`

---

### 4. Running the App

From the project root:

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints in your terminal (usually `http://localhost:8501`).

---

### 5. How It Works (High‑Level)

- **Hotspots dataset** in `data/hotspots.py` contains real‑world plastic accumulation zones sourced from NOAA, The Ocean Cleanup, Eriksen et al., and other literature (see in‑file comments).
- **Map search** uses a Haversine distance calculation to filter zones within the selected radius of the vessel.
- **Priority score** combines severity weighting, FDI score, density, and distance to rank cleanup targets.
- **FDI + ML tab** lets you interactively see how spectral bands would influence FDI and a toy classifier’s decision.

---

### 6. Notes & Limitations

- This is an **educational / prototyping tool**, not an operational navigation or decision‑support system.
- Coordinates and metrics are based on published ranges and simplified assumptions, not live satellite data.
- The Random Forest model is trained on a tiny synthetic dataset—**do not** treat its predictions as scientific outputs.

---

### 7. License & Attribution

Add your chosen license here (e.g. MIT) and any additional acknowledgements you want to include for data sources and collaborators.

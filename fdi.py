import numpy as np
from sklearn.ensemble import RandomForestClassifier

# ── FDI Formula ───────────────────────────────────────────────────────────────
def calculate_fdi(red, nir, swir):
    """
    Floating Debris Index
    High score = likely plastic

    Correct formula (matches sentinel.py / literature):
        FDI = NIR − [RED + (SWIR − RED) × (λNIR − λRED) / (λSWIR − λRED)]

    The old formula  FDI = NIR − (RED + SWIR)  was wrong — it doesn't
    account for the spectral baseline interpolation between RED and SWIR,
    which is what makes FDI sensitive to floating debris specifically.
    """
    lambda_red  = 665
    lambda_nir  = 842
    lambda_swir = 1610

    baseline = red + (swir - red) * ((lambda_nir - lambda_red) / (lambda_swir - lambda_red))
    return round(float(nir - baseline), 6)


# ── Label from FDI score ──────────────────────────────────────────────────────
def classify_fdi(fdi_score):
    """
    FDI thresholds for floating debris severity.
    Values are in reflectance units (0.0 – 1.0 scale).
    """
    if fdi_score >= 0.06:
        return "Critical", "🔴 Dispatch cleanup vessel immediately"
    elif fdi_score >= 0.04:
        return "High",     "🟠 Schedule cleanup within 48 hours"
    elif fdi_score >= 0.02:
        return "Medium",   "🟡 Monitor and log for follow-up"
    else:
        return "Low",      "🟢 No immediate action needed"


# ── Trained ML Classifier ─────────────────────────────────────────────────────
# Training data: [red, nir, swir] → label (1 = plastic, 0 = not plastic)
# All values are Sentinel-2 surface reflectance (0.0 – 1.0).
X_train = np.array([
    # plastic / floating debris — high NIR, low RED & SWIR
    [0.05, 0.80, 0.10],
    [0.06, 0.75, 0.12],
    [0.07, 0.85, 0.08],
    [0.10, 0.90, 0.05],
    # water — low NIR, moderate RED & SWIR
    [0.30, 0.20, 0.40],
    [0.25, 0.15, 0.35],
    [0.20, 0.25, 0.30],
    # algae — moderate NIR and RED
    [0.15, 0.30, 0.10],
    [0.18, 0.35, 0.12],
    # sea foam — moderate across all bands
    [0.22, 0.28, 0.15],
])
y_train = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]

model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X_train, y_train)


def ml_classify(red, nir, swir):
    """Returns prediction label and confidence (%) from ML model."""
    features   = np.array([[red, nir, swir]])
    prediction = model.predict(features)[0]
    # predict_proba returns [prob_class0, prob_class1]; index with prediction
    confidence = round(model.predict_proba(features)[0][prediction] * 100, 1)
    label      = "Plastic Detected" if prediction == 1 else "No Plastic"
    return label, confidence
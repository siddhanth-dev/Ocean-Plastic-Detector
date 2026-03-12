import numpy as np
from sklearn.ensemble import RandomForestClassifier

# ── FDI Formula ───────────────────────────────────────────────────────────────
def calculate_fdi(red, nir, swir):
    """
    Floating Debris Index
    High score = likely plastic
    Formula: FDI = NIR - (RED + SWIR)
    """
    return round(nir - (red + swir), 4)


# ── Label from FDI score ──────────────────────────────────────────────────────
def classify_fdi(fdi_score):
    if fdi_score >= 0.6:
        return "Critical", "🔴 Dispatch cleanup vessel immediately"
    elif fdi_score >= 0.4:
        return "High", "🟠 Schedule cleanup within 48 hours"
    elif fdi_score >= 0.2:
        return "Medium", "🟡 Monitor and log for follow-up"
    else:
        return "Low", "🟢 No immediate action needed"


# ── Trained ML Classifier ─────────────────────────────────────────────────────
# Sample training data: [red, nir, swir] → label (1=plastic, 0=not plastic)
X_train = np.array([
    [0.05, 0.80, 0.10],  # plastic
    [0.06, 0.75, 0.12],  # plastic
    [0.07, 0.85, 0.08],  # plastic
    [0.10, 0.90, 0.05],  # plastic
    [0.30, 0.20, 0.40],  # water
    [0.25, 0.15, 0.35],  # water
    [0.20, 0.25, 0.30],  # water
    [0.15, 0.30, 0.10],  # algae
    [0.18, 0.35, 0.12],  # algae
    [0.22, 0.28, 0.15],  # sea foam
])
y_train = [1, 1, 1, 1, 0, 0, 0, 0, 0, 0]

model = RandomForestClassifier(n_estimators=10, random_state=42)
model.fit(X_train, y_train)


def ml_classify(red, nir, swir):
    """Returns prediction and confidence from ML model"""
    features = np.array([[red, nir, swir]])
    prediction = model.predict(features)[0]
    confidence = round(model.predict_proba(features)[0][prediction] * 100, 1)
    label = "Plastic Detected" if prediction == 1 else "No Plastic"
    return label, confidence
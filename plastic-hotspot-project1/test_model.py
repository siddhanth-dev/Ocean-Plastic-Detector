from ultralytics import YOLO

print("Loading model...")

from ultralytics import YOLO

print("Loading model...")

model = YOLO("best.pt")

print("Running detection...")

results = model.predict(
    source=r"C:\Users\Mikhil Baby\Ocean-Plastic-Detector\plastic-hotspot-project1\test.jpg",
    conf=0.25,
    save=True
)

print("Detection finished")

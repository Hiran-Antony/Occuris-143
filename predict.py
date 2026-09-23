import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from pathlib import Path
import matplotlib.pyplot as plt

from transformers import SegformerForSemanticSegmentation


# ============================================================
# CONFIG
# ============================================================

DATASET_DIR = Path("dataset")
MODEL_DIR = Path("outputs/occurris_segformer_v1")

OUTPUT_DIR = Path("outputs/predictions")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

NUM_IMAGES = 5


# ============================================================
# LOAD MODEL
# ============================================================

print("Loading trained model...")

model = SegformerForSemanticSegmentation.from_pretrained(
    MODEL_DIR
)

model.to(DEVICE)
model.eval()

print(f"Device: {DEVICE}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")


# ============================================================
# FIND TEST IMAGES
# ============================================================

samples = []

for sensor in ["sentinel", "palsar"]:

    image_dir = DATASET_DIR / "test" / sensor / "image"
    label_dir = DATASET_DIR / "test" / sensor / "label"

    images = sorted([
        p for p in image_dir.iterdir()
        if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]
    ])

    for image_path in images:

        label_path = label_dir / image_path.name

        if label_path.exists():
            samples.append(
                (image_path, label_path, sensor)
            )


print(f"Found {len(samples)} test images.")


# ============================================================
# SELECT IMAGES
# ============================================================

# Select a mixture from both sensors
selected = []

sentinel_samples = [x for x in samples if x[2] == "sentinel"]
palsar_samples = [x for x in samples if x[2] == "palsar"]

selected.extend(sentinel_samples[:3])
selected.extend(palsar_samples[:2])


# ============================================================
# PREDICTION
# ============================================================

for index, (image_path, label_path, sensor) in enumerate(selected):

    print(f"\nProcessing {index + 1}/{len(selected)}")
    print(f"Sensor: {sensor}")
    print(f"Image:  {image_path.name}")

    # Load image
    original = Image.open(image_path).convert("L")

    image = np.array(
        original,
        dtype=np.float32
    ) / 255.0

    # Grayscale -> 3 channels
    image_3ch = np.stack(
        [image, image, image],
        axis=0
    )

    # Same ImageNet normalization used during training
    mean = np.array(
        [0.485, 0.456, 0.406],
        dtype=np.float32
    ).reshape(3, 1, 1)

    std = np.array(
        [0.229, 0.224, 0.225],
        dtype=np.float32
    ).reshape(3, 1, 1)

    image_3ch = (image_3ch - mean) / std

    tensor = torch.tensor(
        image_3ch,
        dtype=torch.float32
    ).unsqueeze(0).to(DEVICE)

    # Ground truth
    ground_truth = np.array(
        Image.open(label_path).convert("L")
    )

    ground_truth = (
        ground_truth >= 128
    ).astype(np.uint8)

    # Prediction
    with torch.no_grad():

        with torch.amp.autocast(
            device_type="cuda",
            enabled=torch.cuda.is_available()
        ):

            output = model(
                pixel_values=tensor
            )

            logits = output.logits

            logits = F.interpolate(
                logits,
                size=ground_truth.shape,
                mode="bilinear",
                align_corners=False
            )

            prediction = torch.argmax(
                logits,
                dim=1
            )[0]

    prediction = prediction.cpu().numpy().astype(np.uint8)

    # ========================================================
    # OVERLAY
    # ========================================================

    overlay = np.stack(
        [image, image, image],
        axis=-1
    )

    # Prediction shown in red
    overlay[prediction == 1] = [
        1.0,
        0.0,
        0.0
    ]

    # ========================================================
    # PLOT
    # ========================================================

    fig, axes = plt.subplots(
        1,
        4,
        figsize=(16, 4)
    )

    axes[0].imshow(
        image,
        cmap="gray"
    )

    axes[0].set_title(
        f"SAR Image\n{sensor}"
    )

    axes[1].imshow(
        ground_truth,
        cmap="gray"
    )

    axes[1].set_title(
        "Ground Truth"
    )

    axes[2].imshow(
        prediction,
        cmap="gray"
    )

    axes[2].set_title(
        "Prediction"
    )

    axes[3].imshow(
        overlay
    )

    axes[3].set_title(
        "Prediction Overlay"
    )

    for ax in axes:
        ax.axis("off")

    plt.tight_layout()

    output_path = (
        OUTPUT_DIR /
        f"{sensor}_{index + 1}.png"
    )

    plt.savefig(
        output_path,
        dpi=150,
        bbox_inches="tight"
    )

    plt.close()

    print(f"Saved: {output_path}")


print("\n========================================")
print("Prediction generation complete.")
print(f"Results saved to: {OUTPUT_DIR}")
print("========================================")
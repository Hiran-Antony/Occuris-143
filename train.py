import os
import random
import time
import numpy as np
from PIL import Image
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

from transformers import SegformerForSemanticSegmentation
from tqdm import tqdm


# ============================================================
# CONFIG
# ============================================================

DATASET_DIR = Path("dataset")

BATCH_SIZE = 8
NUM_EPOCHS = 1
NUM_WORKERS = 0
IMAGE_SIZE = 256

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("=" * 60)
print("OCCURIS - Oil Spill Segmentation")
print("=" * 60)
print(f"Device: {DEVICE}")

if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

print("=" * 60)


# ============================================================
# DATASET
# ============================================================

class OilSpillDataset(Dataset):

    def __init__(self, root_dir):
        self.samples = []

        sensors = ["sentinel", "palsar"]

        for sensor in sensors:

            image_dir = root_dir / sensor / "image"
            label_dir = root_dir / sensor / "label"

            if not image_dir.exists():
                print(f"WARNING: Missing {image_dir}")
                continue

            images = sorted(
                [p for p in image_dir.iterdir()
                 if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".tif", ".tiff"]]
            )

            for image_path in images:

                label_path = label_dir / image_path.name

                if label_path.exists():
                    self.samples.append(
                        (image_path, label_path, sensor)
                    )

        print(f"Loaded {len(self.samples)} image/label pairs from {root_dir}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):

        image_path, label_path, sensor = self.samples[idx]

        # Load image as grayscale
        image = Image.open(image_path).convert("L")

        # Load mask as grayscale
        mask = Image.open(label_path).convert("L")

        # Convert to numpy
        image = np.array(image, dtype=np.float32)
        mask = np.array(mask, dtype=np.uint8)

        # Normalize SAR image to [0, 1]
        image = image / 255.0

        # Simple SAR-compatible augmentation
        if random.random() < 0.5:
            image = np.fliplr(image).copy()
            mask = np.fliplr(mask).copy()

        if random.random() < 0.5:
            image = np.flipud(image).copy()
            mask = np.flipud(mask).copy()

        if random.random() < 0.5:
            k = random.randint(1, 3)
            image = np.rot90(image, k).copy()
            mask = np.rot90(mask, k).copy()

        # Convert grayscale SAR -> 3 channels
        image = np.stack([image, image, image], axis=0)

        # ImageNet normalization used by the pretrained SegFormer backbone
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)

        image = (image - mean) / std

        # Convert mask to binary
        mask = (mask >= 128).astype(np.int64)

        image = torch.tensor(image, dtype=torch.float32)
        mask = torch.tensor(mask, dtype=torch.long)

        return {
            "pixel_values": image,
            "labels": mask
        }


# ============================================================
# DICE LOSS
# ============================================================

def dice_loss(logits, targets):

    probs = torch.softmax(logits, dim=1)

    # Oil class = class 1
    probs = probs[:, 1]

    targets = (targets == 1).float()

    smooth = 1e-6

    intersection = (probs * targets).sum(dim=(1, 2))

    dice = (
        (2 * intersection + smooth)
        /
        (probs.sum(dim=(1, 2)) + targets.sum(dim=(1, 2)) + smooth)
    )

    return 1 - dice.mean()


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(predictions, targets):

    predictions = predictions.flatten()
    targets = targets.flatten()

    tp = ((predictions == 1) & (targets == 1)).sum()
    fp = ((predictions == 1) & (targets == 0)).sum()
    fn = ((predictions == 0) & (targets == 1)).sum()

    tp = tp.item()
    fp = fp.item()
    fn = fn.item()

    iou = tp / (tp + fp + fn + 1e-8)

    dice = (2 * tp) / (2 * tp + fp + fn + 1e-8)

    precision = tp / (tp + fp + 1e-8)

    recall = tp / (tp + fn + 1e-8)

    return iou, dice, precision, recall


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading training dataset...")

train_dataset = OilSpillDataset(
    DATASET_DIR / "train"
)

print("\nLoading test dataset...")

test_dataset = OilSpillDataset(
    DATASET_DIR / "test"
)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=NUM_WORKERS,
    pin_memory=True
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=NUM_WORKERS,
    pin_memory=True
)

print(f"\nTraining images: {len(train_dataset)}")
print(f"Test images:     {len(test_dataset)}")
print(f"Batch size:      {BATCH_SIZE}")
print(f"Batches/epoch:   {len(train_loader)}")


# ============================================================
# MODEL
# ============================================================

print("\nLoading SegFormer-B0...")

model = SegformerForSemanticSegmentation.from_pretrained(
    "nvidia/mit-b0",
    num_labels=2,
    ignore_mismatched_sizes=True
)

model.to(DEVICE)

print("Model loaded.")


# ============================================================
# OPTIMIZER
# ============================================================

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=6e-5,
    weight_decay=0.01
)

# Mixed precision
scaler = torch.amp.GradScaler("cuda", enabled=torch.cuda.is_available())


# ============================================================
# TRAINING
# ============================================================

print("\nStarting training...")
print("=" * 60)

total_start = time.time()

model.train()

for epoch in range(NUM_EPOCHS):

    epoch_start = time.time()

    running_loss = 0.0

    progress = tqdm(
        train_loader,
        desc=f"Epoch {epoch + 2}/5"
    )

    for batch in progress:

        images = batch["pixel_values"].to(
            DEVICE,
            non_blocking=True
        )

        masks = batch["labels"].to(
            DEVICE,
            non_blocking=True
        )

        optimizer.zero_grad(set_to_none=True)

        with torch.amp.autocast(
            device_type="cuda",
            enabled=torch.cuda.is_available()
        ):

            outputs = model(
                pixel_values=images
            )

            logits = outputs.logits

            # Resize predictions to mask size
            logits = F.interpolate(
                logits,
                size=masks.shape[-2:],
                mode="bilinear",
                align_corners=False
            )

            ce_loss = F.cross_entropy(
                logits,
                masks
            )

            d_loss = dice_loss(
                logits,
                masks
            )

            loss = ce_loss + d_loss

        scaler.scale(loss).backward()

        scaler.step(optimizer)

        scaler.update()

        running_loss += loss.item()

        progress.set_postfix(
            loss=f"{loss.item():.4f}"
        )

    epoch_time = time.time() - epoch_start

    avg_loss = running_loss / len(train_loader)

    print("\n")
    print(f"Epoch {epoch + 2} completed")
    print(f"Average loss: {avg_loss:.4f}")
    print(f"Epoch time:   {epoch_time / 60:.2f} minutes")


# ============================================================
# EVALUATION
# ============================================================

print("\nEvaluating on TEST dataset...")
print("=" * 60)

model.eval()

all_predictions = []
all_targets = []

with torch.no_grad():

    for batch in tqdm(test_loader, desc="Testing"):

        images = batch["pixel_values"].to(
            DEVICE,
            non_blocking=True
        )

        masks = batch["labels"].to(
            DEVICE,
            non_blocking=True
        )

        with torch.amp.autocast(
            device_type="cuda",
            enabled=torch.cuda.is_available()
        ):

            outputs = model(
                pixel_values=images
            )

            logits = outputs.logits

            logits = F.interpolate(
                logits,
                size=masks.shape[-2:],
                mode="bilinear",
                align_corners=False
            )

        predictions = torch.argmax(
            logits,
            dim=1
        )

        all_predictions.append(
            predictions.cpu().numpy()
        )

        all_targets.append(
            masks.cpu().numpy()
        )


predictions = np.concatenate(all_predictions)
targets = np.concatenate(all_targets)

iou, dice, precision, recall = calculate_metrics(
    predictions,
    targets
)

print("\n")
print("=" * 60)
print("FINAL 1-EPOCH RESULTS")
print("=" * 60)

print(f"IoU:       {iou:.4f}")
print(f"Dice/F1:   {dice:.4f}")
print(f"Precision: {precision:.4f}")
print(f"Recall:    {recall:.4f}")

total_time = time.time() - total_start

print(f"\nTotal runtime: {total_time / 60:.2f} minutes")

# Save model
os.makedirs("outputs", exist_ok=True)

model.save_pretrained(
    "outputs/occurris_segformer_v1"
)

print("\nModel saved to:")
print("outputs/segformer_oilspill_augmented")

print("=" * 60)
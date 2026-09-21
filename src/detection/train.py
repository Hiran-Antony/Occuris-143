"""
Module 1 — SegFormer-B0 Fine-tuning Script
Run this ONLY if you do NOT have a .pth file yet.
If you already have a trained .pth from Kaggle, skip to infer.py.

Usage:
  python src/detection/train.py

Saves best checkpoint to models/segformer_spill.pth
"""
import sys, time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
import albumentations as A
from albumentations.pytorch import ToTensorV2

from transformers import SegformerForSemanticSegmentation
import torch.nn.functional as F

from config import MODEL_BACKBONE, MODEL_CKPT, MODEL_IMG_SIZE, NUM_LABELS
from detection.dataset import SARSpillDataset

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
EPOCHS = 60
LR     = 6e-5
BATCH  = 1  # only 3 images — use batch size 1 with heavy augmentation


def dice_loss(pred_logits, targets, smooth=1.0):
    """Binary Dice loss for spill class."""
    # pred_logits: (B, C, H, W) — upsample to match target size first
    pred = F.interpolate(pred_logits, size=targets.shape[-2:], mode="bilinear", align_corners=False)
    pred = torch.softmax(pred, dim=1)[:, 1]  # spill probability
    tgt  = (targets == 1).float()
    inter = (pred * tgt).sum(dim=(1, 2))
    union = pred.sum(dim=(1, 2)) + tgt.sum(dim=(1, 2))
    return 1 - (2 * inter + smooth) / (union + smooth)


def compute_iou(pred_mask, gt_mask):
    inter = ((pred_mask == 1) & (gt_mask == 1)).sum().item()
    union = ((pred_mask == 1) | (gt_mask == 1)).sum().item()
    return inter / (union + 1e-6)


def main():
    print(f"Device: {DEVICE}")

    transform = A.Compose([
        A.HorizontalFlip(p=0.5),
        A.VerticalFlip(p=0.3),
        A.RandomRotate90(p=0.5),
        A.RandomBrightnessContrast(p=0.4),
        A.GaussNoise(p=0.3),
        A.ElasticTransform(p=0.2),
    ])

    dataset = SARSpillDataset(transform=transform)
    loader  = DataLoader(dataset, batch_size=BATCH, shuffle=True)

    model = SegformerForSemanticSegmentation.from_pretrained(
        MODEL_BACKBONE,
        num_labels=NUM_LABELS,
        ignore_mismatched_sizes=True,
    ).to(DEVICE)

    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    best_iou = 0.0
    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        for batch in loader:
            pv  = batch["pixel_values"].to(DEVICE)
            lbl = batch["labels"].to(DEVICE)

            outputs = model(pixel_values=pv, labels=lbl)
            ce_loss  = outputs.loss
            d_loss   = dice_loss(outputs.logits, lbl).mean()
            loss     = 0.6 * ce_loss + 0.4 * d_loss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            epoch_loss += loss.item()

        scheduler.step()

        # validation on same 3 images (honest about small dataset)
        if epoch % 10 == 0:
            model.eval()
            ious = []
            val_ds = SARSpillDataset()
            with torch.no_grad():
                for item in val_ds:
                    pv  = item["pixel_values"].unsqueeze(0).to(DEVICE)
                    lbl = item["labels"].numpy()
                    out = model(pixel_values=pv)
                    logits = F.interpolate(out.logits, size=(MODEL_IMG_SIZE, MODEL_IMG_SIZE),
                                           mode="bilinear", align_corners=False)
                    pred = logits.argmax(dim=1).squeeze().cpu().numpy()
                    ious.append(compute_iou(pred, lbl))
            mean_iou = sum(ious) / len(ious)
            print(f"  Epoch {epoch:3d}/{EPOCHS}  loss={epoch_loss/len(loader):.4f}  "
                  f"IoU={mean_iou:.4f}  (train=val, n=3)")
            if mean_iou > best_iou:
                best_iou = mean_iou
                MODEL_CKPT.parent.mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), MODEL_CKPT)
                print(f"    --> Saved best checkpoint  IoU={best_iou:.4f}")

    print(f"\nTraining complete. Best IoU={best_iou:.4f}  Checkpoint: {MODEL_CKPT}")


if __name__ == "__main__":
    main()

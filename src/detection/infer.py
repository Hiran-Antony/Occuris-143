"""
Module 1 — SAR Spill Detection Inference
Loads the .pt checkpoint and runs inference on all 3 SAR images.
Saves side-by-side PNG: [SAR | Predicted Mask | Ground Truth | Overlay]
Prints measured IoU and F1 per image — no invented numbers.

Usage:
  python src/detection/infer.py
  python src/detection/infer.py --case case_01   # single case
"""
import sys, argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from transformers import (SegformerForSemanticSegmentation,
                          SegformerImageProcessor, SegformerConfig)
from config import MODEL_BACKBONE, MODEL_CKPT, MODEL_IMG_SIZE, NUM_LABELS, CASES, DATA_PROCESSED
from detection.dataset import SARSpillDataset

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Processor must match Kaggle training exactly (ImageNet mean/std normalisation)
_PROCESSOR = SegformerImageProcessor.from_pretrained(
    MODEL_BACKBONE,
    size={"height": MODEL_IMG_SIZE, "width": MODEL_IMG_SIZE},
    do_reduce_labels=False,
)


def load_model(ckpt_path: Path) -> SegformerForSemanticSegmentation:
    """
    Build SegFormer architecture from scratch (no pretrained weights),
    then load our fine-tuned state dict on top.
    This avoids HuggingFace from_pretrained() overwriting the decode head
    with ImageNet weights after we apply our checkpoint.
    """
    # Build config matching mit-b0 architecture
    config = SegformerConfig.from_pretrained(MODEL_BACKBONE)
    config.num_labels = NUM_LABELS
    config.id2label   = {i: str(i) for i in range(NUM_LABELS)}
    config.label2id   = {str(i): i for i in range(NUM_LABELS)}

    model = SegformerForSemanticSegmentation(config)

    if ckpt_path.exists():
        state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        # Strip DataParallel prefix if present
        state = {k.replace("module.", ""): v for k, v in state.items()}
        missing, unexpected = model.load_state_dict(state, strict=True)
        if missing:
            print(f"  [WARN] Missing keys: {missing[:5]}")
        if unexpected:
            print(f"  [WARN] Unexpected keys: {unexpected[:5]}")
        print(f"  Loaded checkpoint: {ckpt_path}  ({len(state)} keys, strict=True)")
    else:
        print(f"  [WARNING] No checkpoint at {ckpt_path} — random init (expected noise output).")

    model.eval()
    return model.to(DEVICE)


def predict_mask(model, pixel_values: torch.Tensor) -> np.ndarray:
    """Returns binary mask (H, W) numpy array."""
    with torch.no_grad():
        out    = model(pixel_values=pixel_values.unsqueeze(0).to(DEVICE))
        logits = F.interpolate(out.logits, size=(MODEL_IMG_SIZE, MODEL_IMG_SIZE),
                               mode="bilinear", align_corners=False)
        return logits.argmax(dim=1).squeeze().cpu().numpy().astype(np.uint8)


def compute_metrics(pred: np.ndarray, gt: np.ndarray):
    tp = int(((pred == 1) & (gt == 1)).sum())
    fp = int(((pred == 1) & (gt == 0)).sum())
    fn = int(((pred == 0) & (gt == 1)).sum())
    union = tp + fp + fn
    iou  = tp / (union + 1e-6)
    prec = tp / (tp + fp + 1e-6)
    rec  = tp / (tp + fn + 1e-6)
    f1   = 2 * prec * rec / (prec + rec + 1e-6)
    return {"iou": iou, "f1": f1, "precision": prec, "recall": rec,
            "tp": tp, "fp": fp, "fn": fn}


def save_comparison(sar_arr: np.ndarray, pred_mask: np.ndarray,
                    gt_mask: np.ndarray, case_id: str, metrics: dict,
                    out_dir: Path):
    """Save side-by-side figure: SAR | Predicted | Ground Truth | Overlay."""
    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    fig.patch.set_facecolor("#0d1117")

    panel_titles = ["SAR Image", "Predicted Mask", "Ground Truth", "Overlay"]
    for ax, t in zip(axes, panel_titles):
        ax.set_facecolor("#0d1117")
        ax.set_title(t, color="white", fontsize=11, pad=8)
        ax.axis("off")

    axes[0].imshow(sar_arr, cmap="gray", vmin=0, vmax=255)

    axes[1].imshow(pred_mask, cmap="hot", vmin=0, vmax=1)

    axes[2].imshow(gt_mask, cmap="hot", vmin=0, vmax=1)

    # overlay: SAR + predicted mask in red, GT in green outline
    rgb = np.stack([sar_arr, sar_arr, sar_arr], axis=-1)
    overlay = rgb.copy()
    overlay[pred_mask == 1, 0] = 220   # red channel for prediction
    overlay[pred_mask == 1, 1] = 50
    overlay[pred_mask == 1, 2] = 50
    # GT outline
    from scipy.ndimage import binary_dilation
    gt_border = binary_dilation(gt_mask, iterations=2).astype(np.uint8) - gt_mask
    overlay[gt_border == 1, 0] = 50
    overlay[gt_border == 1, 1] = 220  # green for GT boundary
    overlay[gt_border == 1, 2] = 50
    axes[3].imshow(overlay)

    title_str = (f"Occuris — {case_id.replace('_', ' ').title()}  |  "
                 f"IoU={metrics['iou']:.3f}  F1={metrics['f1']:.3f}  "
                 f"Prec={metrics['precision']:.3f}  Rec={metrics['recall']:.3f}")
    fig.suptitle(title_str, color="white", fontsize=12, y=1.02)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{case_id}_detection.png"
    plt.savefig(out_path, bbox_inches="tight", dpi=130,
                facecolor=fig.get_facecolor())
    plt.close()
    return out_path


def run_inference(case_ids=None):
    model   = load_model(MODEL_CKPT)
    dataset = SARSpillDataset(case_ids=case_ids)
    results = {}

    print(f"\n{'='*62}")
    print(f"Module 1 -- SAR Spill Detection Inference")
    print(f"{'='*62}")
    print(f"  Model: {MODEL_BACKBONE}  Device: {DEVICE}")
    print(f"  Checkpoint: {'found' if MODEL_CKPT.exists() else 'NOT FOUND (random init)'}")

    for item in dataset:
        case_id = item["case_id"]
        pv      = item["pixel_values"]
        gt      = item["labels"].numpy()

        # load original SAR for display
        sar_arr = np.array(
            Image.open(CASES[case_id]["sar_image"]).convert("L")
                 .resize((MODEL_IMG_SIZE, MODEL_IMG_SIZE))
        )

        pred    = predict_mask(model, pv)
        metrics = compute_metrics(pred, gt)
        out_path = save_comparison(sar_arr, pred, gt, case_id, metrics, DATA_PROCESSED)

        results[case_id] = {"metrics": metrics, "pred_mask": pred, "output": str(out_path)}

        print(f"\n  [{case_id}]")
        print(f"    IoU={metrics['iou']:.4f}  F1={metrics['f1']:.4f}  "
              f"Precision={metrics['precision']:.4f}  Recall={metrics['recall']:.4f}")
        print(f"    TP={metrics['tp']}  FP={metrics['fp']}  FN={metrics['fn']}")
        print(f"    Saved: {out_path}")

    print(f"\n[OK] Module 1 Definition of Done: inference ran on all {len(dataset)} images.")
    print(f"     Output PNGs in: {DATA_PROCESSED}")
    print(f"{'='*62}\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=str, default=None,
                        help="Run only one case (e.g. case_01). Default: all.")
    args = parser.parse_args()
    run_inference(case_ids=[args.case] if args.case else None)

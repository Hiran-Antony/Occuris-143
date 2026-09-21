import sys
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset
from transformers import SegformerImageProcessor

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from config import CASES, MODEL_IMG_SIZE, MODEL_BACKBONE

# Processor applies ImageNet normalisation — must match Kaggle training
_PROCESSOR = SegformerImageProcessor.from_pretrained(
    MODEL_BACKBONE,
    size={"height": MODEL_IMG_SIZE, "width": MODEL_IMG_SIZE},
    do_reduce_labels=False,
)


class SARSpillDataset(Dataset):
    """
    Loads SAR PNGs and applies SegformerImageProcessor preprocessing
    (ImageNet mean/std normalisation — matches Kaggle training exactly).
    Mask is binarized at threshold 127.
    """

    def __init__(self, case_ids=None, transform=None, img_size=MODEL_IMG_SIZE):
        self.img_size  = img_size
        self.transform = transform
        self.samples   = []
        ids = case_ids if case_ids else list(CASES.keys())
        for cid in ids:
            c = CASES[cid]
            self.samples.append({
                "case_id":   cid,
                "sar_path":  Path(c["sar_image"]),
                "mask_path": Path(c["sar_mask"]),
            })

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]

        # Open SAR as RGB — PIL repeats the single SAR channel into R/G/B
        # SegformerImageProcessor then applies ImageNet normalisation
        img_rgb = Image.open(s["sar_path"]).convert("RGB")
        processed = _PROCESSOR(images=img_rgb, return_tensors="pt")
        pixel_values = processed["pixel_values"].squeeze(0)  # (3, H, W)

        # Ground-truth mask: resize to model input size, binarise
        mask = np.array(
            Image.open(s["mask_path"]).convert("L").resize(
                (self.img_size, self.img_size), Image.NEAREST
            ),
            dtype=np.int64
        )
        mask = (mask > 127).astype(np.int64)

        # Optional albumentations augmentation (training only)
        if self.transform:
            hwc = (pixel_values.numpy().transpose(1, 2, 0) * 255).astype(np.uint8)
            aug = self.transform(image=hwc, mask=mask.astype(np.uint8))
            pixel_values = torch.tensor(
                aug["image"].transpose(2, 0, 1).astype(np.float32) / 255.0
            )
            mask = aug["mask"].astype(np.int64)

        return {
            "case_id":      s["case_id"],
            "pixel_values": pixel_values,
            "labels":       torch.tensor(mask, dtype=torch.long),
        }

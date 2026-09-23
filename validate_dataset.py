from pathlib import Path
from PIL import Image
import numpy as np

DATASET = Path("dataset")

SETS = [
    ("train", "sentinel"),
    ("train", "palsar"),
    ("test", "sentinel"),
    ("test", "palsar"),
]


def validate_split(split, sensor):

    image_dir = DATASET / split / sensor / "image"
    label_dir = DATASET / split / sensor / "label"

    images = sorted(image_dir.glob("*"))
    labels = sorted(label_dir.glob("*"))

    print("\n" + "=" * 70)
    print(f"{split.upper()} / {sensor.upper()}")
    print("=" * 70)

    print(f"Images : {len(images)}")
    print(f"Labels : {len(labels)}")

    label_map = {p.stem: p for p in labels}

    valid_pairs = 0
    missing_labels = 0
    size_errors = 0
    binary_masks = 0
    non_binary_masks = 0
    empty_masks = 0

    suspicious = []

    for image_path in images:

        label_path = label_map.get(image_path.stem)

        if label_path is None:
            missing_labels += 1
            continue

        image = Image.open(image_path)
        label = Image.open(label_path).convert("L")

        image_array = np.array(image)
        label_array = np.array(label)

        if image.size != label.size:
            size_errors += 1
            continue

        valid_pairs += 1

        unique_values = np.unique(label_array)

        # Expected binary mask
        if np.all(np.isin(unique_values, [0, 255])):
            binary_masks += 1
        else:
            non_binary_masks += 1

            if len(suspicious) < 20:
                suspicious.append(
                    (
                        image_path.name,
                        len(unique_values),
                        unique_values[:20]
                    )
                )

        if np.all(label_array == 0):
            empty_masks += 1

    print("\nRESULTS")
    print("-" * 70)

    print(f"Valid image/label pairs : {valid_pairs}")
    print(f"Missing labels          : {missing_labels}")
    print(f"Size errors             : {size_errors}")

    print(f"\nBinary masks            : {binary_masks}")
    print(f"Non-binary masks        : {non_binary_masks}")
    print(f"Empty masks (no oil)    : {empty_masks}")

    if suspicious:

        print("\nFIRST SUSPICIOUS LABELS")
        print("-" * 70)

        for filename, count, values in suspicious:
            print(
                f"{filename:15} "
                f"unique values = {count:4} | "
                f"first values = {values}"
            )


def main():

    for split, sensor in SETS:
        validate_split(split, sensor)


if __name__ == "__main__":
    main()
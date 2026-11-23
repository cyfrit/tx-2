#!/usr/bin/env python3
"""Train the TX-2 64→32→10 integer digit classifier from official MNIST.

Requires CPU PyTorch, NumPy and SciPy. Example:
    python tools/train_digits.py --cache /tmp/tx2-mnist
Downloaded IDX archives stay in the cache, outside the repository. Inputs are
binary 16×16 ink masks; normalize_mask implements the native program's exact
bounding-box/aspect-preserving 8×8 mapping. No division or scale conversion is
needed between the exported network's two integer layers.
"""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import struct
import urllib.request

import numpy as np
from scipy import ndimage
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "https://storage.googleapis.com/cvdf-datasets/mnist/"
FILES = {
    "train-images-idx3-ubyte.gz": "f68b3c2dcbeaaa9fbdd348bbdeb94873",
    "train-labels-idx1-ubyte.gz": "d53e105ee54ea40749a09fcbcd1e9432",
    "t10k-images-idx3-ubyte.gz": "9fb629c4189551a2d022fa330f9573f3",
    "t10k-labels-idx1-ubyte.gz": "ec29112dd5afa0611ce80d1b7f02629c",
}


def load_mnist(cache):
    """Download checked official archives and validate their IDX headers."""
    cache.mkdir(parents=True, exist_ok=True)
    arrays = []
    for name, checksum in FILES.items():
        path = cache / name
        if not path.exists():
            print(f"Downloading {SOURCE}{name}", flush=True)
            urllib.request.urlretrieve(SOURCE + name, path)
        raw = path.read_bytes()
        if hashlib.md5(raw).hexdigest() != checksum:
            raise ValueError(f"MNIST checksum mismatch: {path}")
        raw = gzip.decompress(raw)
        magic, count = struct.unpack_from(">II", raw)
        if "images" in name:
            rows, cols = struct.unpack_from(">II", raw, 8)
            if magic != 2051 or (rows, cols) != (28, 28):
                raise ValueError(f"Invalid image IDX header: {path}")
            array = np.frombuffer(raw, np.uint8, offset=16).reshape(count, 28, 28)
        else:
            if magic != 2049:
                raise ValueError(f"Invalid label IDX header: {path}")
            array = np.frombuffer(raw, np.uint8, offset=8)
            if len(array) != count:
                raise ValueError(f"Invalid label IDX length: {path}")
        arrays.append(array.copy())
    return arrays


def normalize_masks(masks):
    """Exact native mapping, including binary OR when source cells collide."""
    masks = np.asarray(masks, dtype=bool)
    if masks.ndim != 3 or masks.shape[1:] != (16, 16):
        raise ValueError("Expected a batch of 16×16 ink masks")
    occupied_x = masks.any(axis=1)
    occupied_y = masks.any(axis=2)
    xmin = occupied_x.argmax(axis=1)
    xmax = 15 - occupied_x[:, ::-1].argmax(axis=1)
    ymin = occupied_y.argmax(axis=1)
    ymax = 15 - occupied_y[:, ::-1].argmax(axis=1)
    width = xmax - xmin + 1
    height = ymax - ymin + 1
    span = np.maximum(width, height)
    sample, y, x = np.nonzero(masks)
    col = (2 * (x - xmin[sample]) + span[sample] - width[sample] + 1) * 4 // span[sample]
    row = (2 * (y - ymin[sample]) + span[sample] - height[sample] + 1) * 4 // span[sample]
    features = np.zeros((len(masks), 64), dtype=np.float32)
    features[sample, row * 8 + col] = 1
    return features


def normalize_mask(mask):
    return normalize_masks(np.asarray(mask)[None])[0]


def thin_masks(masks):
    """Zhang-Suen thinning preserves connectivity for one-cell pen strokes."""
    image = np.pad(masks.astype(bool), ((0, 0), (1, 1), (1, 1)))
    for _ in range(12):
        changed = False
        for second in (False, True):
            p = [image[:, :-2, 1:-1], image[:, :-2, 2:], image[:, 1:-1, 2:],
                 image[:, 2:, 2:], image[:, 2:, 1:-1], image[:, 2:, :-2],
                 image[:, 1:-1, :-2], image[:, :-2, :-2]]
            count = sum(q.astype(np.uint8) for q in p)
            transitions = sum((~p[i] & p[(i + 1) % 8]).astype(np.uint8) for i in range(8))
            if second:
                guard = ~(p[0] & p[2] & p[6]) & ~(p[0] & p[4] & p[6])
            else:
                guard = ~(p[0] & p[2] & p[4]) & ~(p[2] & p[4] & p[6])
            remove = image[:, 1:-1, 1:-1] & (count >= 2) & (count <= 6) & (transitions == 1) & guard
            changed |= bool(remove.any())
            image[:, 1:-1, 1:-1] &= ~remove
        if not changed:
            break
    return image[:, 1:-1, 1:-1]


def mnist_features(images, rng, augmented=False, thin_fraction=0.0):
    """Rasterize grayscale digits into binary pen grids before normalization."""
    chunks = []
    for start in range(0, len(images), 1024):
        batch = torch.from_numpy(images[start:start + 1024].astype(np.float32) / 255)[:, None]
        size = len(batch)
        theta = np.zeros((size, 2, 3), np.float32)
        if augmented:
            angle = rng.uniform(-0.22, 0.22, size)
            scale_x = rng.uniform(0.84, 1.15, size)
            scale_y = rng.uniform(0.84, 1.15, size)
            shear = rng.uniform(-0.18, 0.18, size)
            theta[:, 0, 0] = np.cos(angle) * scale_x
            theta[:, 0, 1] = -np.sin(angle) + shear
            theta[:, 1, 0] = np.sin(angle)
            theta[:, 1, 1] = np.cos(angle) * scale_y
            theta[:, :, 2] = rng.uniform(-0.10, 0.10, (size, 2))
            thresholds = rng.uniform(0.18, 0.56, (size, 1, 1))
        else:
            theta[:, 0, 0] = theta[:, 1, 1] = 1
            thresholds = 0.30
        grid = F.affine_grid(torch.from_numpy(theta), (size, 1, 16, 16), align_corners=False)
        gray = F.grid_sample(batch, grid, align_corners=False)[:, 0].numpy()
        masks = gray >= thresholds
        if thin_fraction:
            selected = rng.random(size) < thin_fraction
            masks[selected] = thin_masks(masks[selected])
        chunks.append(normalize_masks(masks))
    return np.concatenate(chunks)


# Coordinates use an upright unit square; each inner list is a separate stroke.
PATHS = [
    [[(.5, .03), (.17, .12), (.05, .45), (.13, .85), (.45, .98), (.78, .89), (.94, .58), (.86, .18), (.5, .03)]],
    [[(.52, .02), (.52, .98)]],
    [[(.08, .17), (.3, .02), (.7, .02), (.93, .22), (.82, .43), (.08, .97), (.96, .97)]],
    [[(.06, .08), (.75, .04), (.96, .22), (.75, .45), (.42, .49), (.77, .52), (.96, .74), (.78, .96), (.1, .95)]],
    [[(.72, .03), (.05, .64), (.99, .64)], [(.73, .12), (.73, .98)]],
    [[(.95, .03), (.12, .03), (.1, .49), (.63, .43), (.92, .59), (.91, .83), (.65, .98), (.1, .93)]],
    [[(.82, .04), (.43, .1), (.12, .48), (.1, .82), (.36, .98), (.76, .95), (.94, .73), (.79, .5), (.45, .47), (.13, .63)]],
    [[(.03, .04), (.98, .04), (.24, .98)]],
    [[(.5, .03), (.12, .14), (.18, .36), (.78, .63), (.92, .84), (.68, .98), (.25, .96), (.07, .79), (.19, .59), (.78, .35), (.87, .14), (.5, .03)]],
    [[(.85, .43), (.58, .52), (.18, .43), (.07, .22), (.27, .03), (.69, .03), (.89, .25), (.85, .67), (.58, .97)]],
]


def synthetic_masks(rng, per_digit):
    """Varied connected mouse/pen paths, including plain vertical 1 and 7."""
    masks, labels = [], []
    for digit, template in enumerate(PATHS):
        for _ in range(per_digit):
            mask = np.zeros((16, 16), bool)
            angle = rng.uniform(-0.17, 0.17)
            width = rng.uniform(6, 12)
            height = rng.uniform(10, 14)
            shear = rng.uniform(-0.12, 0.12)
            matrix = np.array([[math.cos(angle), -math.sin(angle) + shear],
                               [math.sin(angle), math.cos(angle)]])
            for stroke in template:
                points = np.asarray(stroke, dtype=float).copy()
                # Keep the lone vertical 1 narrow rather than adding random kinks.
                if len(points) > 2:
                    points += rng.normal(0, 0.025, points.shape)
                points = ((points - .5) * [width, height]) @ matrix.T + 7.5
                for a, b in zip(points[:-1], points[1:]):
                    steps = max(2, int(np.linalg.norm(b - a) * 8))
                    line = np.rint(np.linspace(a, b, steps)).astype(int).clip(0, 15)
                    mask[line[:, 1], line[:, 0]] = True
            if rng.random() < .12:
                mask = ndimage.binary_dilation(mask, structure=np.ones((2, 2)))
            masks.append(mask)
            labels.append(digit)
    return np.asarray(masks), np.asarray(labels, np.int64)


def quantize(model, scale):
    w1, b1 = model[0].weight.detach().numpy(), model[0].bias.detach().numpy()
    w2, b2 = model[2].weight.detach().numpy(), model[2].bias.detach().numpy()
    return {"w1": np.rint(w1 * scale).astype(np.int64),
            "b1": np.rint(b1 * scale).astype(np.int64),
            "w2": np.rint(w2 * scale).astype(np.int64),
            "b2": np.rint(b2 * scale * scale).astype(np.int64)}


def integer_predict(weights, features):
    h = np.maximum(0, features.astype(np.int64) @ weights["w1"].T + weights["b1"])
    return (h @ weights["w2"].T + weights["b2"]).argmax(axis=1)


def integer_bounds(weights):
    """Conservative bounds for every multiply, prefix sum and layer result."""
    hidden = np.abs(weights["w1"]).sum(axis=1) + np.abs(weights["b1"])
    output = np.abs(weights["w2"]) @ hidden + np.abs(weights["b2"])
    bound = int(max(hidden.max(), output.max(), *(np.abs(v).max() for v in weights.values())))
    if bound >= 1 << 34:
        raise ValueError(f"Integer inference exceeds signed 35-bit range: {bound}")
    return {"hidden_absolute_bound": int(hidden.max()),
            "score_absolute_bound": int(output.max()), "signed_bits": 35}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("/tmp/tx2-mnist"))
    parser.add_argument("--output", type=Path, default=ROOT / "programs/digits-model.json")
    parser.add_argument("--seed", type=int, default=20261123)
    parser.add_argument("--epochs", type=int, default=35)
    parser.add_argument("--variants", type=int, default=5)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.epochs < 1 or args.variants < 1:
        parser.error("epochs and variants must be positive")
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    images, labels, test_images, test_labels = load_mnist(args.cache)
    order = rng.permutation(len(images))
    validation_ids, training_ids = order[:5000], order[5000:]
    print("Preparing 16×16 binary mask variants", flush=True)
    train_x = [mnist_features(images[training_ids], rng)]
    for variant in range(args.variants - 1):
        train_x.append(mnist_features(images[training_ids], rng, augmented=True, thin_fraction=.40))
        print(f"Prepared variant {variant + 2}/{args.variants}", flush=True)
    synthetic, synthetic_y = synthetic_masks(rng, 1200)
    train_x.append(normalize_masks(synthetic))
    train_y = np.concatenate([labels[training_ids]] * args.variants + [synthetic_y])
    train_x = torch.from_numpy(np.concatenate(train_x))
    train_y = torch.from_numpy(train_y.astype(np.int64))
    validation_x = mnist_features(images[validation_ids], rng)
    validation_y = labels[validation_ids]
    model = nn.Sequential(nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 10))
    optimizer = torch.optim.AdamW(model.parameters(), lr=.006, weight_decay=.0001)
    batch_size = 1024
    best_accuracy, best_state = -1, None
    for epoch in range(args.epochs):
        model.train()
        permutation = torch.randperm(len(train_x))
        for indices in permutation.split(batch_size):
            optimizer.zero_grad(set_to_none=True)
            loss = F.cross_entropy(model(train_x[indices]), train_y[indices])
            loss.backward()
            optimizer.step()
        if epoch == 19:
            for group in optimizer.param_groups:
                group["lr"] *= .35
        if epoch == 29:
            for group in optimizer.param_groups:
                group["lr"] *= .35
        model.eval()
        weights = quantize(model, 128)
        accuracy = float(np.mean(integer_predict(weights, validation_x) == validation_y))
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch + 1
        print(f"Epoch {epoch + 1:02d}: quantized validation {accuracy:.2%}", flush=True)
    model.load_state_dict(best_state)
    weights = quantize(model, 128)
    bounds = integer_bounds(weights)
    # The official test split is evaluated only after selecting by validation.
    test_x = mnist_features(test_images, rng)
    test_prediction = integer_predict(weights, test_x)
    test_accuracy = float(np.mean(test_prediction == test_labels))
    varied_x = mnist_features(test_images, rng, augmented=True, thin_fraction=.40)
    varied_accuracy = float(np.mean(integer_predict(weights, varied_x) == test_labels))
    heldout_masks, heldout_labels = synthetic_masks(np.random.default_rng(args.seed + 1), 200)
    pen_accuracy = float(np.mean(integer_predict(weights, normalize_masks(heldout_masks)) == heldout_labels))
    with torch.no_grad():
        float_prediction = model(torch.from_numpy(test_x)).argmax(dim=1).numpy()
    confusion = np.zeros((10, 10), dtype=np.int64)
    np.add.at(confusion, (test_labels, test_prediction), 1)
    result = {name: values.tolist() for name, values in weights.items()}
    result["provenance"] = {
        "dataset": "MNIST official training/test IDX archives",
        "source": SOURCE, "archive_md5": FILES, "seed": args.seed,
        "training_mnist_examples": len(training_ids), "validation_mnist_examples": len(validation_ids),
        "training_variants": args.variants, "training_synthetic_examples": len(synthetic_y),
        "epochs": args.epochs, "selected_epoch": best_epoch,
        "architecture": [64, 32, 10], "activation": "ReLU",
        "input": "row-major binary 16x16 ink mask, y increasing downward",
        "normalization": "crop bbox; span=max(width,height); col=(2*(x-xmin)+span-width+1)*4//span; row=(2*(y-ymin)+span-height+1)*4//span; binary OR into row-major 8x8",
        "rasterization": "28x28 grayscale bilinear-resampled to 16x16; fixed threshold .30 for standard evaluation; training variants use affine jitter, thresholds .18-.56, and 40% connectivity-preserving thinning",
        "integer_inference": "h=max(0,w1*x+b1); score=w2*h+b2; argmax, smallest digit wins ties; no intermediate scaling",
        "quantization": {"weight_scale": 128, "b1_scale": 128, "b2_scale": 16384},
        "synthetic_paths": "randomized connected 16x16 polylines for 0-9, including plain vertical 1, oval 0 and top-bar/diagonal 7",
    }
    result["metrics"] = {
        "validation_quantized_accuracy": best_accuracy,
        "test_examples": len(test_labels), "test_quantized_accuracy": test_accuracy,
        "test_float_accuracy": float(np.mean(float_prediction == test_labels)),
        "test_quantized_confusion_rows_actual_columns_predicted": confusion.tolist(),
        "test_varied_binary_accuracy": varied_accuracy,
        "heldout_synthetic_examples": len(heldout_labels), "heldout_synthetic_accuracy": pen_accuracy,
        "bounds": bounds,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(json.dumps(result["metrics"], indent=2), flush=True)
    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()

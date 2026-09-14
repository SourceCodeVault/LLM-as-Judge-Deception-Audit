#!/usr/bin/env python3
"""
Visualize rule clustering outputs as PNGs.

Uses Pillow only, because matplotlib/scipy are not guaranteed in the local
runtime. The heatmaps show similarity/closeness:
  - Jaccard panel: similarity = 1 - distance = Jaccard
  - fire-rate panel: similarity = 1 - distance = Pearson correlation
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BACKGROUND = (255, 255, 255)
TEXT = (25, 25, 30)
MUTED = (105, 105, 115)
GRID = (220, 220, 225)


@dataclass
class Node:
    name: str
    distance: float
    left: "Node | None" = None
    right: "Node | None" = None
    label: str | None = None


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def read_matrix(path: Path) -> tuple[list[str], list[list[float]]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        labels = header[1:]
        matrix = []
        for row in reader:
            matrix.append([float(value) for value in row[1:]])
    return labels, matrix


def read_linkage(path: Path, labels: list[str]) -> Node:
    nodes = {label: Node(name=label, distance=0.0, label=label) for label in labels}
    last: Node | None = None
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            node = Node(
                name=row["cluster"],
                distance=float(row["distance"]),
                left=nodes[row["left"]],
                right=nodes[row["right"]],
            )
            nodes[node.name] = node
            last = node
    if last is None:
        raise ValueError(f"No linkage rows in {path}")
    return last


def leaf_order(node: Node) -> list[str]:
    if node.label is not None:
        return [node.label]
    assert node.left is not None and node.right is not None
    return leaf_order(node.left) + leaf_order(node.right)


def similarity_color(value: float) -> tuple[int, int, int]:
    # Diverging map: negative red, zero white, positive blue. Jaccard lives in [0, 1].
    value = max(-1.0, min(1.0, value))
    if value >= 0:
        t = value
        return (
            int(255 * (1 - t) + 35 * t),
            int(255 * (1 - t) + 105 * t),
            int(255 * (1 - t) + 210 * t),
        )
    t = -value
    return (
        int(255 * (1 - t) + 210 * t),
        int(255 * (1 - t) + 65 * t),
        int(255 * (1 - t) + 70 * t),
    )


def draw_rotated_label(base: Image.Image, xy: tuple[int, int], text: str, text_font: ImageFont.ImageFont) -> None:
    bbox = text_font.getbbox(text)
    label = Image.new("RGBA", (bbox[2] - bbox[0] + 8, bbox[3] - bbox[1] + 8), (255, 255, 255, 0))
    d = ImageDraw.Draw(label)
    d.text((4, 4), text, fill=TEXT, font=text_font)
    rotated = label.rotate(90, expand=True)
    base.alpha_composite(rotated, xy)


def draw_heatmap(
    labels: list[str],
    matrix: list[list[float]],
    order: list[str],
    title: str,
    out_path: Path,
    width: int = 920,
    height: int = 920,
) -> None:
    label_to_idx = {label: i for i, label in enumerate(labels)}
    ordered_idx = [label_to_idx[label] for label in order]
    img = Image.new("RGBA", (width, height), BACKGROUND + (255,))
    draw = ImageDraw.Draw(img)
    title_font = font(28, bold=True)
    label_font = font(18)
    small_font = font(15)

    left = 115
    top = 155
    cell = min((width - left - 80) // len(order), (height - top - 135) // len(order))
    heat_w = cell * len(order)

    draw.text((30, 24), title, fill=TEXT, font=title_font)
    draw.text((30, 62), "Darker blue = closer / more similar. White = weak or zero similarity. Red = negative correlation.", fill=MUTED, font=small_font)

    for row_pos, i in enumerate(ordered_idx):
        y = top + row_pos * cell
        draw.text((left - 58, y + cell // 2 - 9), labels[i], fill=TEXT, font=label_font)
        for col_pos, j in enumerate(ordered_idx):
            x = left + col_pos * cell
            distance = matrix[i][j]
            similarity = 1.0 - distance
            color = similarity_color(similarity)
            draw.rectangle((x, y, x + cell, y + cell), fill=color, outline=GRID)
            if row_pos == col_pos:
                draw.line((x, y, x + cell, y + cell), fill=(20, 20, 20), width=2)

    for col_pos, i in enumerate(ordered_idx):
        x = left + col_pos * cell + cell // 2 - 9
        draw_rotated_label(img, (x, top - 62), labels[i], label_font)

    # Legend
    legend_x = left
    legend_y = top + heat_w + 40
    legend_w = 360
    for k in range(legend_w):
        sim = -1.0 + 2.0 * k / max(1, legend_w - 1)
        draw.line((legend_x + k, legend_y, legend_x + k, legend_y + 18), fill=similarity_color(sim))
    draw.rectangle((legend_x, legend_y, legend_x + legend_w, legend_y + 18), outline=GRID)
    draw.text((legend_x, legend_y + 24), "-1", fill=MUTED, font=small_font)
    draw.text((legend_x + legend_w // 2 - 8, legend_y + 24), "0", fill=MUTED, font=small_font)
    draw.text((legend_x + legend_w - 16, legend_y + 24), "1", fill=MUTED, font=small_font)
    draw.text((legend_x + legend_w + 18, legend_y), "similarity", fill=MUTED, font=small_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


def draw_dendrogram(root: Node, title: str, out_path: Path, width: int = 920, height: int = 680) -> None:
    order = leaf_order(root)
    leaves = {label: idx for idx, label in enumerate(order)}
    img = Image.new("RGBA", (width, height), BACKGROUND + (255,))
    draw = ImageDraw.Draw(img)
    title_font = font(28, bold=True)
    label_font = font(18)
    small_font = font(15)

    left = 70
    right = width - 55
    top = 90
    bottom = height - 95
    plot_w = right - left
    plot_h = bottom - top
    max_distance = max(root.distance, 1e-9)

    draw.text((30, 24), title, fill=TEXT, font=title_font)
    draw.text((30, 60), "Average-linkage hierarchy. Lower merge distance means tighter cluster.", fill=MUTED, font=small_font)

    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        dist = tick * max_distance
        y = bottom - tick * plot_h
        draw.line((left, y, right, y), fill=(238, 238, 242), width=1)
        draw.text((18, y - 8), f"{dist:.2f}", fill=MUTED, font=small_font)

    def x_for(label: str) -> float:
        if len(order) == 1:
            return (left + right) / 2
        return left + leaves[label] * plot_w / (len(order) - 1)

    def y_for(distance: float) -> float:
        return bottom - distance / max_distance * plot_h

    def draw_node(node: Node) -> tuple[float, float]:
        if node.label is not None:
            x = x_for(node.label)
            y = bottom
            bbox = label_font.getbbox(node.label)
            draw.text((x - (bbox[2] - bbox[0]) / 2, bottom + 18), node.label, fill=TEXT, font=label_font)
            return x, y
        assert node.left is not None and node.right is not None
        lx, ly = draw_node(node.left)
        rx, ry = draw_node(node.right)
        y = y_for(node.distance)
        draw.line((lx, ly, lx, y), fill=(35, 80, 150), width=3)
        draw.line((rx, ry, rx, y), fill=(35, 80, 150), width=3)
        draw.line((lx, y, rx, y), fill=(35, 80, 150), width=3)
        return (lx + rx) / 2, y

    draw_node(root)
    draw.line((left, bottom, right, bottom), fill=GRID, width=1)
    draw.text((20, top - 4), "dist.", fill=MUTED, font=small_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_path)


def combine(paths: list[Path], out_path: Path) -> None:
    images = [Image.open(path).convert("RGB") for path in paths]
    cell_w = max(img.width for img in images)
    cell_h = max(img.height for img in images)
    canvas = Image.new("RGB", (cell_w * 2, cell_h * 2), BACKGROUND)
    for idx, img in enumerate(images):
        x = (idx % 2) * cell_w
        y = (idx // 2) * cell_h
        canvas.paste(img, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    # Reads the cluster CSV outputs and renders dependency-free PNG figures.
    parser.add_argument("--cluster-dir", default="results/clusters")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--out-dir", default="results/plots")
    args = parser.parse_args()

    cluster_dir = Path(args.cluster_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    j_labels, j_matrix = read_matrix(cluster_dir / f"rule_distance_jaccard_{args.suffix}.csv")
    c_labels, c_matrix = read_matrix(cluster_dir / f"rule_distance_fire_rate_corr_{args.suffix}.csv")
    j_root = read_linkage(cluster_dir / f"rule_cluster_linkage_jaccard_{args.suffix}.csv", j_labels)
    c_root = read_linkage(cluster_dir / f"rule_cluster_linkage_fire_rate_corr_{args.suffix}.csv", c_labels)

    j_order = leaf_order(j_root)
    c_order = leaf_order(c_root)

    paths = [
        out_dir / f"heatmap_jaccard_{args.suffix}.png",
        out_dir / f"dendrogram_jaccard_{args.suffix}.png",
        out_dir / f"heatmap_fire_rate_corr_{args.suffix}.png",
        out_dir / f"dendrogram_fire_rate_corr_{args.suffix}.png",
    ]

    draw_heatmap(j_labels, j_matrix, j_order, "Pass-Level Jaccard Closeness", paths[0])
    draw_dendrogram(j_root, "Pass-Level Jaccard Clustering", paths[1])
    draw_heatmap(c_labels, c_matrix, c_order, "Case-Level Fire-Rate Correlation", paths[2])
    draw_dendrogram(c_root, "Case-Level Fire-Rate Clustering", paths[3])
    combined = out_dir / f"rule_cluster_visual_summary_{args.suffix}.png"
    combine(paths, combined)

    print("Wrote:")
    for path in [*paths, combined]:
        print(f"  {path}")


if __name__ == "__main__":
    main()

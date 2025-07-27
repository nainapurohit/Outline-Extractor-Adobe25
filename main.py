
from __future__ import annotations
import pdfplumber
import fitz
from collections import Counter
from time import perf_counter
import itertools
import re
import json
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from pdfplumber.utils import intersects_bbox
import os
from pathlib import Path


def does_it_only_have_symbols_digits(t):
    return int(all(not ch.isalpha() for ch in t))


def does_it_only_have_symbols(t):
    return int(all(not ch.isalnum() for ch in t))


def get_word_count(t):
    return len([w for w in t.split(" ") if w])


def get_character_count(t):
    return len([ch for ch in t.strip() if ch.isalnum()])


def get_font_threshold(size, body_size):
    return int(size > body_size)


def get_symbol_count(t):
    return len([ch for ch in t if not ch.isalnum() and ch != " "])


def build_header_footer_maps(lines):
    text_ctr, coord_ctr = Counter(), Counter()
    for ln in lines:
        alpha_text = ''.join(ch for ch in ln["text"] if not (ch.isnumeric() and ch == ' '))
        if not alpha_text:
            continue
        text_ctr[alpha_text] += 1
        coord_ctr[(round(ln["top"]), round(ln["bottom"]), round(ln["x1"]))] += 1
    return text_ctr, coord_ctr


def is_header_footer(line, pages_total, text_ctr, coord_ctr):
    if pages_total < 3:
        return 0
    page_threshold = (0, 1) if pages_total < 10 else (0, 1, 2)
    alpha_text = ''.join(ch for ch in line["text"] if not (ch.isnumeric() and ch == ' '))
    if not alpha_text:
        return 0
    coords = (round(line["top"]), round(line["bottom"]), round(line["x1"]))
    return int(
        pages_total - text_ctr[alpha_text] in page_threshold
        and pages_total - coord_ctr[coords] in page_threshold
    )


def scan_pdf(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        title = pdf.metadata.get('Title', '')
        pages_total = len(pdf.pages)
        all_lines, all_sizes = [], []
        for p_idx, pg in enumerate(pdf.pages):
            tables = [t for t in pg.find_tables() if len(t.columns) > 1]
            for ln in pg.extract_text_lines(strip=True, return_chars=True):
                if any(intersects_bbox([ln], t.bbox) for t in tables):
                    continue
                ln["page_no"] = p_idx + 1
                all_lines.append(ln)
                all_sizes.append(round(ln["chars"][0]["size"]))
    body_font = Counter(all_sizes).most_common(1)[0][0]
    return pages_total, body_font, all_lines, title


def is_text_bold(line):
    bold_hits = sum(1 for ch in line["chars"]
                    if ch["text"].isalnum()
                    and "bold" in ch["fontname"].lower())
    return int(len(line["chars"]) - 3 < bold_hits <= len(line["chars"]))


def is_potential_heading(line, pages_total, body_font, text_ctr, coord_ctr):
    text = line["text"]
    if is_header_footer(line, pages_total, text_ctr, coord_ctr):
        return 0
    if get_character_count(text) < 3:
        return 0
    if get_symbol_count(text) > 7:
        return 0
    if text.strip().endswith("."):
        return 0
    if (does_it_only_have_symbols(text) or does_it_only_have_symbols_digits(text)):
        return 0
    if line["x0"] > 250:
        return 0
    font_threshold = get_font_threshold(round(line["chars"][0]["size"]), body_font)
    bold = is_text_bold(line)
    words = get_word_count(text)
    if words > 12:
        return 0
    if font_threshold and words < 12:
        return 1
    if font_threshold and bold:
        return 1
    if bold and words < 12:
        return 1
    return 0


def classify_headings_by_style(heading_lines, *, levels=("H1", "H2", "H3", "H4")):
    if not heading_lines:
        return []
    features = np.array([
        [round(line["chars"][0]["size"]), line["x0"]]
        for line in heading_lines
    ])
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    db = DBSCAN(eps=0.5, min_samples=1).fit(scaled_features)
    labels = db.labels_
    unique_labels = set(labels)
    if not unique_labels:
        return []
    styles = []
    for label in unique_labels:
        if label == -1:
            continue
        cluster_indices = np.where(labels == label)[0]
        cluster_features = features[cluster_indices]
        avg_size = np.mean(cluster_features[:, 0])
        avg_x0 = np.mean(cluster_features[:, 1])
        styles.append({
            "label": label,
            "avg_size": avg_size,
            "avg_x0": avg_x0,
            "count": len(cluster_indices)
        })
    ranked_styles = sorted(styles, key=lambda s: (-s["avg_size"], s["avg_x0"]))
    level_map = {style["label"]: levels[i]
                 for i, style in enumerate(ranked_styles) if i < len(levels)}
    for i, line in enumerate(heading_lines):
        label = labels[i]
        line["level"] = level_map.get(label, "OTHER")
    return [line for line in heading_lines if line["level"] in levels]


def merge_adjacent_lines(lines, gap_threshold=10, x_threshold=80):
    lines_sorted = sorted(lines, key=lambda ln: (ln["page_no"], ln["top"]))
    merged = []
    for ln in lines_sorted:
        if not merged:
            merged.append(ln.copy())
            continue
        prev = merged[-1]
        if ln["page_no"] != prev["page_no"]:
            merged.append(ln.copy())
            continue
        if abs(ln["x0"] - prev["x0"]) > x_threshold:
            merged.append(ln.copy())
            continue
        if (abs(ln["top"] - prev["bottom"]) <= gap_threshold
                and ln["chars"][0]["fontname"]
                == prev["chars"][-1]["fontname"]):
            prev["text"] = (prev["text"].rstrip()
                            + " " + ln["text"].lstrip())
            if "chars" in prev and "chars" in ln:
                prev["chars"].extend(ln["chars"])
        else:
            merged.append(ln.copy())
    return merged


def extract_headings(pdf_path):
    pages_total, body_font, all_lines, title = scan_pdf(pdf_path)
    if pages_total > 3:
        page_word_totals = Counter()
        for ln in all_lines:
            page_word_totals[ln["page_no"]] += get_word_count(ln["text"])
        if page_word_totals.get(1):
            avg_other = ((sum(page_word_totals.values())
                          - page_word_totals[1]) / (pages_total - 1))
            if avg_other > 0 and page_word_totals[1] < 0.20 * avg_other:
                all_lines = [ln for ln in all_lines if ln["page_no"] != 1]
    text_ctr, coord_ctr = build_header_footer_maps(all_lines)
    early_candidates = [ln for ln in all_lines
                        if get_word_count(ln["text"]) < 20]
    headings = [ln for ln in early_candidates
                if is_potential_heading(
                    ln, pages_total, body_font, text_ctr, coord_ctr)]
    headings = merge_adjacent_lines(headings)
    classified = classify_headings_by_style(headings)
    return title, classified


def to_outline(title, classified):
    return {
        "title": title.strip(),
        "outline": [
            {"level": ln["level"], "text": ln["text"].rstrip(),
             "page": ln["page_no"]-1}
            for ln in classified
        ],
    }


if __name__ == "__main__":
    INPUT_DIR = Path("input")
    OUTPUT_DIR = Path("output")
    OUTPUT_DIR.mkdir(exist_ok=True)
    total_t0 = perf_counter()
    pdf_files = list(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"[SYSTEM] No PDF documents found in the '{INPUT_DIR}' directory.")
        print("[SYSTEM] Please ensure the 'input' directory exists and contains PDF files.")
    else:
        print(f"[SYSTEM] Found {len(pdf_files)} PDF document(s) for processing.")
        for pdf_path in pdf_files:
            print("-" * 60)
            print(f"[INFO] Initializing process for: {pdf_path.name}")
            file_t0 = perf_counter()
            try:
                doc_title, heads = extract_headings(pdf_path)
                outline = to_outline(doc_title or pdf_path.stem, heads)
                output_filename = pdf_path.stem + ".json"
                output_path = OUTPUT_DIR / output_filename
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(outline, f, indent=2, ensure_ascii=False)
                print(f"[SUCCESS] Output generated: {output_path}")
                print(f"[INFO] Task completed in {perf_counter() - file_t0:.2f} seconds.")
            except Exception as e:
                print(f"[ERROR] Failed to process {pdf_path.name}. Details: {e}")

    print("=" * 60)
    print(f"[SYSTEM] Batch processing has concluded.")
    print(f"[SYSTEM] Total elapsed time: {perf_counter() - total_t0:.2f} seconds.")
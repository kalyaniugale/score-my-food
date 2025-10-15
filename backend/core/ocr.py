# core/ocr.py
from typing import Tuple, Optional, List
from PIL import Image, ImageOps, ImageFilter
import pytesseract
import io
import math

try:
    import cv2  # optional, for better preprocessing
    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False

# Tweak this to your languages (add +de, +es, etc. if you expect them)
LANGS = "eng"

# Characters you expect in ingredient lists
WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789,.-()%/ +"

def _pil_fix_orientation(img: Image.Image) -> Image.Image:
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img

def _pil_preprocess(img: Image.Image) -> Image.Image:
    # Grayscale → slight sharpen → upscale if small → adaptive-ish threshold
    g = img.convert("L")
    if min(g.size) < 900:
        # upscale small images for better OCR
        scale = 1200.0 / min(g.size)
        g = g.resize((int(g.width * scale), int(g.height * scale)), Image.BICUBIC)
    g = g.filter(ImageFilter.UnsharpMask(radius=1.2, percent=150, threshold=3))

    # Simple binarization that works reasonably without OpenCV
    # (we’ll rely on OpenCV’s adaptive threshold if available)
    return g.point(lambda p: 255 if p > 180 else 0)

def _cv2_preprocess(img: Image.Image) -> Image.Image:
    # Convert PIL→OpenCV
    import numpy as np
    arr = np.array(img.convert("RGB"))[:, :, ::-1]  # to BGR
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)

    # Deskew (estimate angle via moments)
    coords = cv2.findNonZero(255 - gray)
    if coords is not None:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        (h, w) = gray.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    # Adaptive threshold + light morphology
    thr = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 31, 11)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel, iterations=1)

    # Upscale a bit if still small
    if min(thr.shape[:2]) < 900:
        scale = 1200.0 / min(thr.shape[:2])
        thr = cv2.resize(thr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Back to PIL
    pil = Image.fromarray(thr)
    return pil

def _run_tesseract(img: Image.Image, psm: int) -> Tuple[str, float]:
    """
    Returns (text, avg_confidence 0..100)
    """
    config = f'--oem 3 --psm {psm} -l {LANGS} -c tessedit_char_whitelist="{WHITELIST}"'
    data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
    # Combine text and compute average confidence (ignore -1)
    words = [w for w in data["text"] if w.strip()]
    confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c >= 0]
    text = " ".join(words)
    avg_conf = sum(confs) / max(len(confs), 1) if confs else 0.0
    return text, avg_conf

def extract_text(img: Image.Image) -> str:
    """
    Best-effort OCR with preprocessing and multiple PSM tries.
    """
    img = _pil_fix_orientation(img)

    proc = _cv2_preprocess(img) if _HAS_CV2 else _pil_preprocess(img)

    # Try a few PSMs commonly good for labels
    # 6: Assume a single uniform block of text
    # 11: Sparse text
    # 4: Single column of text of variable sizes
    psm_candidates: List[int] = [6, 11, 4]

    best_text, best_conf = "", -1.0
    for psm in psm_candidates:
        t, conf = _run_tesseract(proc, psm)
        if conf > best_conf:
            best_conf, best_text = conf, t

    # Fallback to vanilla image_to_string if everything fails short
    if len(best_text.strip()) < 10:
        fallback = pytesseract.image_to_string(proc, config=f'-l {LANGS} --oem 3 --psm 6')
        if len(fallback.strip()) > len(best_text.strip()):
            best_text = fallback

    # Normalize whitespace and common OCR quirks for ingredients
    cleaned = (
        best_text.replace("•", ",")
                 .replace(";", ",")
                 .replace("|", "I")
                 .replace("”", '"')
                 .replace("“", '"')
                 .replace("‘", "'")
                 .replace("’", "'")
    )
    # Collapse multiple spaces/newlines
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()

r"""ref_match — score a render against a reference image, and say WHERE it is wrong.

The problem this solves: for 13 passes the only test of "does the model match the design sheet?"
was a human looking at a picture. That is one slow round trip per change, and it produced three
mis-diagnoses (see ../RETROSPECTIVE.md). This turns the question into numbers an agent can iterate
against on its own.

Runs INSIDE Blender (uses bpy to decode PNG/JPG; numpy for the maths). No PIL needed.

    import sys; sys.path.append(r"...\agentic\tools")
    import ref_match
    ref_match.report(ref=r"...\refs\front_sheet.png",
                     render=r"...\renders\pass14_front.png",
                     frame_width_m=347.0, horizon=0.72,
                     debug_png=r"...\renders\pass14_match.png")

What it measures — the SKYLINE PROFILE: for every image column, the topmost point of the building.
That is the silhouette, which is what a tower's identity actually is. Clouds are rejected because
the profile is traced upward from the ground, so only geometry connected to the ground counts.

Outputs: apex position, RMS/max profile error in metres, per-band left/right edges and widths, and
a band table saying which part of the silhouette is off and by how much.
"""

import numpy as np

try:
    import bpy
except ImportError:  # allows --help / import outside Blender
    bpy = None


# ---------------------------------------------------------------- image io ---

def load_rgba(path):
    """Decode an image to a top-down (H, W, 4) float array in [0, 1]."""
    if bpy is None:
        raise RuntimeError("ref_match must run inside Blender (bpy decodes the image)")
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        buf = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        return buf.reshape(h, w, 4)[::-1].copy()  # Blender stores bottom-up
    finally:
        bpy.data.images.remove(img)


def _resample(arr, width, height):
    """Nearest-neighbour resample to (height, width) — no scipy/PIL dependency."""
    h, w = arr.shape[:2]
    yi = (np.linspace(0, h - 1, height)).astype(np.int32)
    xi = (np.linspace(0, w - 1, width)).astype(np.int32)
    return arr[yi][:, xi]


# ------------------------------------------------------------- silhouette ---

def skyline(rgba, horizon=0.72, tol=0.13, margin=0.04, max_gap=2):
    """Topmost building row per column, as a fraction of image height (NaN where none).

    Sky is estimated per row from the left/right margins, which are sky in an architectural
    elevation framing. A pixel differing from its row's sky colour by more than `tol` is
    "not sky". The profile is then traced UPWARD from the horizon so only geometry connected
    to the ground is counted — clouds and lens flare are ignored.

    `tol` is the one setting that matters and it is image-dependent: a heavily clouded sky needs
    a higher value or the cloud edges read as building. Defaults (0.13 / gap 2) were calibrated on
    a dusk render with broken cloud — they put the apex within ~2 m of truth at 88 % coverage,
    where the old 0.055 tracked cloud all the way to the frame edge. Tune per project with
    `calibrate()` and record the value in PROJECT.md.
    """
    h, w = rgba.shape[:2]
    rgb = rgba[:, :, :3]
    m = max(2, int(w * margin))
    sky = np.median(np.concatenate([rgb[:, :m], rgb[:, -m:]], axis=1), axis=1)  # (h, 3)
    diff = np.abs(rgb - sky[:, None, :]).max(axis=2)                            # (h, w)
    solid = diff > tol

    hrow = min(h - 1, max(1, int(h * horizon)))
    prof = np.full(w, np.nan, dtype=np.float64)
    for x in range(w):
        col = solid[:, x]
        if not col[hrow]:                      # nothing standing at the horizon in this column
            up = np.nonzero(col[:hrow])[0]
            if up.size == 0:
                continue
            y = up[-1]                         # fall back to the lowest solid run above horizon
        else:
            y = hrow
        gap = 0
        top = y
        while y > 0:
            y -= 1
            if col[y]:
                top, gap = y, 0
            else:
                gap += 1
                if gap > max_gap:
                    break
        prof[x] = top / h
    return prof


def bands(prof, n=8, horizon=0.72):
    """Left edge, right edge and width per horizontal band, in normalised units."""
    w = prof.size
    xs = np.arange(w) / w
    out = []
    for i in range(n):
        lo, hi = horizon * i / n, horizon * (i + 1) / n     # band in v (0 = top of frame)
        sel = np.isfinite(prof) & (prof >= lo) & (prof < hi)
        if not sel.any():
            out.append((lo, hi, np.nan, np.nan, 0.0))
            continue
        x = xs[sel]
        out.append((lo, hi, float(x.min()), float(x.max()), float(x.max() - x.min())))
    return out


# ---------------------------------------------------------------- compare ---

def calibrate(image, apex_uv, horizon=0.72, width=512,
              tols=(0.055, 0.09, 0.13, 0.18, 0.25, 0.33), gaps=(2, 6), min_coverage=0.75):
    """Find the tol/max_gap that best locates a KNOWN landmark, e.g. the tower tip.

    apex_uv is the true apex as (u, v) with v measured from the TOP of the frame
    (a Blender ndc y of 0.961 is v = 0.039). Returns the best (tol, gap, error, coverage) and
    prints the sweep so the choice is auditable.
    """
    img = _resample(load_rgba(image), width, width)
    best, rows = None, []
    for tol in tols:
        for gap in gaps:
            prof = skyline(img, horizon, tol, max_gap=gap)
            if not np.isfinite(prof).any():
                continue
            u = float(np.nanargmin(prof)) / prof.size
            v = float(np.nanmin(prof))
            cov = float(np.isfinite(prof).mean())
            err = float(np.hypot(u - apex_uv[0], v - apex_uv[1]))
            rows.append((tol, gap, u, v, cov, err))
            if cov >= min_coverage and (best is None or err < best[5]):
                best = (tol, gap, u, v, cov, err)
    for tol, gap, u, v, cov, err in rows:
        mark = " <-- best" if best and (tol, gap) == (best[0], best[1]) else ""
        print(f"tol {tol:.3f} gap {gap}: apex ({u:.3f}, {v:.3f}) coverage {cov:.2f} err {err:.4f}{mark}")
    return best


def compare(ref, render, horizon=0.72, tol=0.13, width=512, n_bands=8, frame_width_m=None):
    a = _resample(load_rgba(ref), width, width)
    b = _resample(load_rgba(render), width, width)
    pa, pb = skyline(a, horizon, tol), skyline(b, horizon, tol)

    both = np.isfinite(pa) & np.isfinite(pb)
    d = pb[both] - pa[both]                      # + = render's skyline sits LOWER than the reference
    apex = lambda p: (float(np.nanargmin(p)) / p.size, float(np.nanmin(p)))

    res = {
        "columns_compared": int(both.sum()),
        "coverage": float(both.sum() / max(1, np.isfinite(pa).sum())),
        "apex_ref": apex(pa), "apex_render": apex(pb),
        "rms": float(np.sqrt((d ** 2).mean())) if d.size else float("nan"),
        "max": float(np.abs(d).max()) if d.size else float("nan"),
        "bias": float(d.mean()) if d.size else float("nan"),
        "bands_ref": bands(pa, n_bands, horizon),
        "bands_render": bands(pb, n_bands, horizon),
        "scale_m": frame_width_m,
    }
    if frame_width_m:
        res["rms_m"] = res["rms"] * frame_width_m
        res["max_m"] = res["max"] * frame_width_m
    return res, pa, pb


def report(ref, render, horizon=0.72, tol=0.13, frame_width_m=None, debug_png=None, n_bands=8):
    res, pa, pb = compare(ref, render, horizon, tol, frame_width_m=frame_width_m, n_bands=n_bands)
    u = f" ({{:.1f}} m)" if frame_width_m else ""
    ax, ay = res["apex_ref"]; bx, by = res["apex_render"]
    print(f"ref    : {ref}")
    print(f"render : {render}")
    print(f"coverage {res['coverage']*100:5.1f}%  columns {res['columns_compared']}")
    print(f"apex   ref (u={ax:.3f}, v={ay:.3f})   render (u={bx:.3f}, v={by:.3f})   "
          f"du={bx-ax:+.3f} dv={by-ay:+.3f}"
          + (f"  = {(bx-ax)*frame_width_m:+.1f} m, {(by-ay)*frame_width_m:+.1f} m" if frame_width_m else ""))
    print(f"skyline RMS {res['rms']:.4f}" + (f" = {res['rms_m']:.1f} m" if frame_width_m else "")
          + f"   max {res['max']:.4f}" + (f" = {res['max_m']:.1f} m" if frame_width_m else "")
          + f"   bias {res['bias']:+.4f}")
    print(f"{'band (v)':>14} {'ref L..R':>18} {'render L..R':>18} {'dW':>8}")
    for (lo, hi, l1, r1, w1), (_, _, l2, r2, w2) in zip(res["bands_ref"], res["bands_render"]):
        f = lambda v: "  --  " if not np.isfinite(v) else f"{v:.3f}"
        dw = (w2 - w1) * (frame_width_m or 1)
        print(f"{lo:.2f}-{hi:.2f} {f(l1)}..{f(r1)}   {f(l2)}..{f(r2)}   {dw:+7.1f}"
              + ("m" if frame_width_m else ""))
    if debug_png:
        _write_overlay(debug_png, pa, pb)
        print(f"overlay -> {debug_png}")
    return res


def _write_overlay(path, pa, pb, size=512):
    """Reference profile in red, render in green, agreement in yellow."""
    img = np.zeros((size, size, 4), dtype=np.float32)
    img[:, :, 3] = 1.0
    for prof, ch in ((pa, 0), (pb, 1)):
        for x in range(min(size, prof.size)):
            if np.isfinite(prof[x]):
                y = int(np.clip(prof[x] * size, 0, size - 1))
                img[max(0, y - 1):y + 2, x, ch] = 1.0
    out = bpy.data.images.new("ref_match_overlay", size, size, alpha=True)
    out.pixels.foreach_set(img[::-1].ravel())
    out.filepath_raw = path
    out.file_format = 'PNG'
    out.save()
    bpy.data.images.remove(out)

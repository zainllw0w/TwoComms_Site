"""Realistic SVG garment artwork for the custom print configurator stage.

Every garment (hoodie / tshirt / longsleeve / customer garment) is drawn
parametrically in a 420x520 viewBox. Colors are driven by CSS variables that
the configurator JS sets from the chosen product color:

    --cp-g-hi / --cp-g-base / --cp-g-lo / --cp-g-deep   fabric ramp
    --cp-g-line                                          seam / stitch color
    --cp-g-inner-hi / --cp-g-inner-lo                    hood lining
    --cp-g-cord                                          drawcord color

Each view exports ``metrics`` so that print placement boxes can be computed
physically (mm -> svg units) and stay glued to the artwork.
"""

from __future__ import annotations

VIEW_BOX = "0 0 420 520"
CX = 210.0


def _f(value: float) -> str:
    """Compact float formatting for path data."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _mirror_path(d: str) -> str:
    """Mirror a path's x coordinates around the vertical center axis."""
    out = []
    token = ""
    coords: list[str] = []
    is_x = True

    def flush_token():
        nonlocal token, is_x
        if not token:
            return
        if is_x:
            coords.append(_f(420.0 - float(token)))
        else:
            coords.append(token)
        is_x = not is_x
        token = ""

    for ch in d:
        if ch.upper() in "MCLQSHVZAT":
            flush_token()
            if ch.upper() == "H":
                raise ValueError("H not supported in mirror")
            if ch.upper() == "V":
                raise ValueError("V not supported in mirror")
            coords.append(ch)
            is_x = True
        elif ch in " ,":
            flush_token()
        elif ch == "-" and token:
            flush_token()
            token = "-"
        else:
            token += ch
    flush_token()
    return " ".join(coords)


# ── Shared defs ──────────────────────────────────────────────────────


def _defs(uid: str) -> str:
    return f"""
<defs>
  <linearGradient id='{uid}-body' x1='0' y1='0' x2='0' y2='1'>
    <stop offset='0' style='stop-color:var(--cp-g-hi, #5e5a64)'/>
    <stop offset='0.42' style='stop-color:var(--cp-g-base, #49454e)'/>
    <stop offset='1' style='stop-color:var(--cp-g-lo, #34313a)'/>
  </linearGradient>
  <linearGradient id='{uid}-sleeve' x1='0' y1='0' x2='0' y2='1'>
    <stop offset='0' style='stop-color:var(--cp-g-base, #49454e)'/>
    <stop offset='0.55' style='stop-color:var(--cp-g-lo, #34313a)'/>
    <stop offset='1' style='stop-color:var(--cp-g-deep, #26232c)'/>
  </linearGradient>
  <linearGradient id='{uid}-hood' x1='0' y1='0' x2='0' y2='1'>
    <stop offset='0' style='stop-color:var(--cp-g-hi, #5e5a64)'/>
    <stop offset='1' style='stop-color:var(--cp-g-base, #49454e)'/>
  </linearGradient>
  <linearGradient id='{uid}-rib' x1='0' y1='0' x2='0' y2='1'>
    <stop offset='0' style='stop-color:var(--cp-g-lo, #34313a)'/>
    <stop offset='1' style='stop-color:var(--cp-g-deep, #26232c)'/>
  </linearGradient>
  <linearGradient id='{uid}-inner' x1='0' y1='0' x2='0' y2='1'>
    <stop offset='0' style='stop-color:var(--cp-g-inner-hi, #1d1b22)'/>
    <stop offset='1' style='stop-color:var(--cp-g-inner-lo, #0e0d12)'/>
  </linearGradient>
  <radialGradient id='{uid}-metal' cx='0.35' cy='0.3' r='0.9'>
    <stop offset='0' stop-color='#f4f4f6'/>
    <stop offset='0.45' stop-color='#b9bcc4'/>
    <stop offset='0.8' stop-color='#787c86'/>
    <stop offset='1' stop-color='#54575f'/>
  </radialGradient>
  <linearGradient id='{uid}-sheen' x1='0' y1='0' x2='1' y2='1'>
    <stop offset='0' stop-color='rgba(255,255,255,0.16)'/>
    <stop offset='0.45' stop-color='rgba(255,255,255,0.05)'/>
    <stop offset='1' stop-color='rgba(255,255,255,0)'/>
  </linearGradient>
  <filter id='{uid}-soft' x='-30%' y='-30%' width='160%' height='160%'>
    <feGaussianBlur stdDeviation='5'/>
  </filter>
  <filter id='{uid}-soft2' x='-40%' y='-40%' width='180%' height='180%'>
    <feGaussianBlur stdDeviation='2.4'/>
  </filter>
</defs>"""


def _seam(d: str, width: float = 1.6, dash: str = "", opacity: float = 0.55) -> str:
    dash_attr = f" stroke-dasharray='{dash}'" if dash else ""
    return (
        f"<path d='{d}' fill='none' style='stroke:var(--cp-g-line, rgba(255,255,255,0.35))' "
        f"stroke-width='{width}' stroke-linecap='round' stroke-linejoin='round' "
        f"opacity='{opacity}'{dash_attr}/>"
    )


def _stitch(d: str, opacity: float = 0.5) -> str:
    return _seam(d, width=1.3, dash="5 4", opacity=opacity)


def _fold(d: str, uid: str, opacity: float = 0.14, light: bool = False) -> str:
    color = "rgba(255,255,255,0.5)" if light else "rgba(8,7,12,0.85)"
    return f"<path d='{d}' fill='{color}' opacity='{opacity}' filter='url(#{uid}-soft)'/>"


def _rib_hatch(x1: float, x2: float, y1: float, y2: float, step: float = 7.0, skew: float = 0.0) -> str:
    lines = []
    x = x1 + step / 2
    while x < x2:
        lines.append(f"M{_f(x)} {_f(y1 + 2)} L{_f(x + skew)} {_f(y2 - 2)}")
        x += step
    return (
        f"<path d='{' '.join(lines)}' fill='none' stroke='rgba(10,9,14,0.35)' "
        f"stroke-width='1.4' opacity='0.5'/>"
    )


def _cuff_hatch(cx_: float, cy_: float, w: float, h: float, angle: float, step: float = 6.0) -> str:
    lines = []
    n = int(w // step)
    x0 = -w / 2 + step / 2
    for i in range(n):
        x = x0 + i * step
        lines.append(f"M{_f(x)} {_f(-h / 2 + 2)} L{_f(x)} {_f(h / 2 - 2)}")
    return (
        f"<g transform='translate({_f(cx_)} {_f(cy_)}) rotate({_f(angle)})'>"
        f"<path d='{' '.join(lines)}' fill='none' stroke='rgba(10,9,14,0.35)' stroke-width='1.3' opacity='0.5'/>"
        f"</g>"
    )


# ── Hoodie ───────────────────────────────────────────────────────────


def hoodie_front(oversize: bool = False) -> dict:
    uid = "cpsgHF" + ("o" if oversize else "r")
    if oversize:
        bw = 224.0          # svg body width
        body_l, body_r = CX - bw / 2, CX + bw / 2
        sh_y = 158.0        # shoulder tip y
        sh_drop = 14.0      # dropped shoulder
        hem_top, hem_bot = 466.0, 492.0
        slv_out, slv_elbow, slv_cuff_y = 58.0, 64.0, 380.0
        pocket = (140.0, 280.0, 334.0, 442.0)
        collar_y = 150.0
        body_mm = 660.0
    else:
        bw = 204.0
        body_l, body_r = CX - bw / 2, CX + bw / 2
        sh_y = 150.0
        sh_drop = 6.0
        hem_top, hem_bot = 462.0, 488.0
        slv_out, slv_elbow, slv_cuff_y = 74.0, 78.0, 370.0
        pocket = (150.0, 270.0, 332.0, 438.0)
        collar_y = 140.0
        body_mm = 600.0

    pk_l, pk_r, pk_top, pk_bot = pocket
    neck_l, neck_r = CX - 48, CX + 48

    # Torso silhouette (slight waist shaping, rounded hem corners)
    torso = (
        f"M{_f(neck_l)} {_f(collar_y - 8)} "
        f"C{_f(neck_l - 26)} {_f(collar_y - 4)} {_f(body_l + 22)} {_f(sh_y - 12)} {_f(body_l + 4)} {_f(sh_y)} "
        f"C{_f(body_l - 2)} {_f(sh_y + 40)} {_f(body_l - 1)} {_f(260)} {_f(body_l + 3)} {_f(330)} "
        f"C{_f(body_l + 5)} {_f(395)} {_f(body_l + 6)} {_f(435)} {_f(body_l + 8)} {_f(hem_top)} "
        f"L{_f(body_r - 8)} {_f(hem_top)} "
        f"C{_f(body_r - 6)} {_f(435)} {_f(body_r - 5)} {_f(395)} {_f(body_r - 3)} {_f(330)} "
        f"C{_f(body_r + 1)} {_f(260)} {_f(body_r + 2)} {_f(sh_y + 40)} {_f(body_r - 4)} {_f(sh_y)} "
        f"C{_f(body_r - 22)} {_f(sh_y - 12)} {_f(neck_r + 26)} {_f(collar_y - 4)} {_f(neck_r)} {_f(collar_y - 8)} "
        f"C{_f(CX + 30)} {_f(collar_y + 6)} {_f(CX - 30)} {_f(collar_y + 6)} {_f(neck_l)} {_f(collar_y - 8)} Z"
    )

    # Left sleeve (outer silhouette), mirrored for right
    armpit_x, armpit_y = body_l + 14, sh_y + 64
    cuff_out_x, cuff_in_x = slv_out + 8, armpit_x + 6
    sleeve_l = (
        f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} "
        f"C{_f(slv_out + 14)} {_f(sh_y + 26)} {_f(slv_elbow - 6)} {_f(250)} {_f(slv_elbow - 2)} {_f(300)} "
        f"C{_f(slv_elbow)} {_f(330)} {_f(cuff_out_x - 4)} {_f(slv_cuff_y - 16)} {_f(cuff_out_x)} {_f(slv_cuff_y)} "
        f"L{_f(cuff_in_x + 26)} {_f(slv_cuff_y - 4)} "
        f"C{_f(cuff_in_x + 16)} {_f(320)} {_f(armpit_x - 2)} {_f(270)} {_f(armpit_x)} {_f(armpit_y)} "
        f"C{_f(armpit_x + 4)} {_f(sh_y + 26)} {_f(body_l + 2 + sh_drop)} {_f(sh_y + 4)} {_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} Z"
    )
    sleeve_r = _mirror_path(sleeve_l)

    # Cuff ribs
    cuff_w, cuff_h = (cuff_in_x + 30) - (cuff_out_x - 2), 22.0
    cuff_cx = (cuff_out_x + cuff_in_x + 28) / 2
    cuff_cy = slv_cuff_y + 8
    cuff_angle = 8.0
    cuff_l = (
        f"<g transform='translate({_f(cuff_cx)} {_f(cuff_cy)}) rotate({_f(cuff_angle)})'>"
        f"<rect x='{_f(-cuff_w / 2)}' y='{_f(-cuff_h / 2)}' width='{_f(cuff_w)}' height='{_f(cuff_h)}' rx='9' fill='url(#{uid}-rib)'/>"
        f"</g>"
        + _cuff_hatch(cuff_cx, cuff_cy, cuff_w, cuff_h, cuff_angle)
    )
    cuff_r = (
        f"<g transform='translate({_f(420 - cuff_cx)} {_f(cuff_cy)}) rotate({_f(-cuff_angle)})'>"
        f"<rect x='{_f(-cuff_w / 2)}' y='{_f(-cuff_h / 2)}' width='{_f(cuff_w)}' height='{_f(cuff_h)}' rx='9' fill='url(#{uid}-rib)'/>"
        f"</g>"
        + _cuff_hatch(420 - cuff_cx, cuff_cy, cuff_w, cuff_h, -cuff_angle)
    )

    # Hood: back dome + draped front panels + dark lining opening
    hood_dome = (
        f"M{_f(neck_l - 6)} {_f(collar_y - 6)} "
        f"C{_f(CX - 60)} {_f(74)} {_f(CX + 60)} {_f(74)} {_f(neck_r + 6)} {_f(collar_y - 6)} "
        f"C{_f(CX + 38)} {_f(collar_y + 10)} {_f(CX - 38)} {_f(collar_y + 10)} {_f(neck_l - 6)} {_f(collar_y - 6)} Z"
    )
    hood_opening = (
        f"M{_f(neck_l + 8)} {_f(collar_y - 10)} "
        f"C{_f(CX - 32)} {_f(96)} {_f(CX + 32)} {_f(96)} {_f(neck_r - 8)} {_f(collar_y - 10)} "
        f"C{_f(CX + 28)} {_f(collar_y + 2)} {_f(CX - 28)} {_f(collar_y + 2)} {_f(neck_l + 8)} {_f(collar_y - 10)} Z"
    )
    drape_l = (
        f"M{_f(neck_l - 6)} {_f(collar_y - 6)} "
        f"C{_f(neck_l - 14)} {_f(collar_y + 18)} {_f(neck_l - 4)} {_f(collar_y + 40)} {_f(CX - 10)} {_f(collar_y + 52)} "
        f"L{_f(CX)} {_f(collar_y + 44)} "
        f"C{_f(CX - 24)} {_f(collar_y + 30)} {_f(neck_l + 16)} {_f(collar_y + 14)} {_f(neck_l + 8)} {_f(collar_y - 10)} "
        f"C{_f(neck_l + 2)} {_f(collar_y - 8)} {_f(neck_l - 2)} {_f(collar_y - 7)} {_f(neck_l - 6)} {_f(collar_y - 6)} Z"
    )
    drape_r = _mirror_path(drape_l)

    cord_x1, cord_x2 = CX - 17, CX + 17
    cord_y0 = collar_y + 46
    cords_standard = (
        f"<g class='cp-stage-svg__cords cp-stage-svg__cords--standard'>"
        f"<path d='M{_f(cord_x1)} {_f(cord_y0)} C{_f(cord_x1 - 5)} {_f(cord_y0 + 26)} {_f(cord_x1 + 3)} {_f(cord_y0 + 44)} {_f(cord_x1 - 2)} {_f(cord_y0 + 64)}' "
        f"fill='none' style='stroke:var(--cp-g-cord, #2c2931)' stroke-width='4.6' stroke-linecap='round'/>"
        f"<path d='M{_f(cord_x2)} {_f(cord_y0)} C{_f(cord_x2 + 5)} {_f(cord_y0 + 26)} {_f(cord_x2 - 3)} {_f(cord_y0 + 44)} {_f(cord_x2 + 2)} {_f(cord_y0 + 64)}' "
        f"fill='none' style='stroke:var(--cp-g-cord, #2c2931)' stroke-width='4.6' stroke-linecap='round'/>"
        f"</g>"
    )
    cords_lacing = (
        f"<g class='cp-stage-svg__cords cp-stage-svg__cords--lacing'>"
        f"<circle cx='{_f(cord_x1)}' cy='{_f(cord_y0 - 2)}' r='6.2' fill='url(#{uid}-metal)' stroke='rgba(20,20,26,0.65)' stroke-width='1.2'/>"
        f"<circle cx='{_f(cord_x1)}' cy='{_f(cord_y0 - 2)}' r='2.6' style='fill:var(--cp-g-inner-lo, #0e0d12)'/>"
        f"<circle cx='{_f(cord_x2)}' cy='{_f(cord_y0 - 2)}' r='6.2' fill='url(#{uid}-metal)' stroke='rgba(20,20,26,0.65)' stroke-width='1.2'/>"
        f"<circle cx='{_f(cord_x2)}' cy='{_f(cord_y0 - 2)}' r='2.6' style='fill:var(--cp-g-inner-lo, #0e0d12)'/>"
        f"<path d='M{_f(cord_x1)} {_f(cord_y0 + 3)} C{_f(cord_x1 - 7)} {_f(cord_y0 + 30)} {_f(cord_x1 + 4)} {_f(cord_y0 + 52)} {_f(cord_x1 - 3)} {_f(cord_y0 + 76)}' "
        f"fill='none' style='stroke:var(--cp-g-cord-lace, #d8d3c8)' stroke-width='4.2' stroke-linecap='round'/>"
        f"<path d='M{_f(cord_x2)} {_f(cord_y0 + 3)} C{_f(cord_x2 + 7)} {_f(cord_y0 + 30)} {_f(cord_x2 - 4)} {_f(cord_y0 + 52)} {_f(cord_x2 + 3)} {_f(cord_y0 + 76)}' "
        f"fill='none' style='stroke:var(--cp-g-cord-lace, #d8d3c8)' stroke-width='4.2' stroke-linecap='round'/>"
        f"<rect x='{_f(cord_x1 - 5.4)}' y='{_f(cord_y0 + 72)}' width='6' height='12' rx='2.4' fill='url(#{uid}-metal)' transform='rotate(-8 {_f(cord_x1 - 2)} {_f(cord_y0 + 78)})'/>"
        f"<rect x='{_f(cord_x2 - 0.6)}' y='{_f(cord_y0 + 72)}' width='6' height='12' rx='2.4' fill='url(#{uid}-metal)' transform='rotate(8 {_f(cord_x2 + 2)} {_f(cord_y0 + 78)})'/>"
        f"</g>"
    )

    pocket_path = (
        f"M{_f(pk_l + 16)} {_f(pk_top)} L{_f(pk_r - 16)} {_f(pk_top)} "
        f"C{_f(pk_r - 10)} {_f(pk_top)} {_f(pk_r - 8)} {_f(pk_top + 4)} {_f(pk_r - 7)} {_f(pk_top + 10)} "
        f"L{_f(pk_r)} {_f(pk_bot - 12)} C{_f(pk_r + 1)} {_f(pk_bot - 4)} {_f(pk_r - 5)} {_f(pk_bot)} {_f(pk_r - 12)} {_f(pk_bot)} "
        f"L{_f(pk_l + 12)} {_f(pk_bot)} C{_f(pk_l + 5)} {_f(pk_bot)} {_f(pk_l - 1)} {_f(pk_bot - 4)} {_f(pk_l)} {_f(pk_bot - 12)} "
        f"L{_f(pk_l + 7)} {_f(pk_top + 10)} C{_f(pk_l + 8)} {_f(pk_top + 4)} {_f(pk_l + 10)} {_f(pk_top)} {_f(pk_l + 16)} {_f(pk_top)} Z"
    )

    hem_rib = (
        f"<rect x='{_f(body_l + 8)}' y='{_f(hem_top)}' width='{_f(bw - 16)}' height='{_f(hem_bot - hem_top)}' rx='10' fill='url(#{uid}-rib)'/>"
        + _rib_hatch(body_l + 14, body_r - 14, hem_top, hem_bot)
    )

    parts = [
        f"<path d='{sleeve_l}' fill='url(#{uid}-sleeve)'/>",
        f"<path d='{sleeve_r}' fill='url(#{uid}-sleeve)'/>",
        cuff_l,
        cuff_r,
        f"<path d='{torso}' fill='url(#{uid}-body)'/>",
        # soft folds on torso
        _fold(f"M{_f(body_l + 16)} {_f(armpit_y + 4)} C{_f(body_l + 30)} {_f(armpit_y + 40)} {_f(body_l + 26)} {_f(300)} {_f(body_l + 18)} {_f(340)} L{_f(body_l + 10)} {_f(330)} C{_f(body_l + 14)} {_f(286)} {_f(body_l + 12)} {_f(240)} {_f(body_l + 8)} {_f(armpit_y + 8)} Z", uid),
        _fold(_mirror_path(f"M{_f(body_l + 16)} {_f(armpit_y + 4)} C{_f(body_l + 30)} {_f(armpit_y + 40)} {_f(body_l + 26)} {_f(300)} {_f(body_l + 18)} {_f(340)} L{_f(body_l + 10)} {_f(330)} C{_f(body_l + 14)} {_f(286)} {_f(body_l + 12)} {_f(240)} {_f(body_l + 8)} {_f(armpit_y + 8)} Z"), uid),
        _fold(f"M{_f(CX - 56)} {_f(hem_top - 50)} C{_f(CX - 40)} {_f(hem_top - 38)} {_f(CX - 20)} {_f(hem_top - 36)} {_f(CX)} {_f(hem_top - 38)} L{_f(CX)} {_f(hem_top - 28)} C{_f(CX - 26)} {_f(hem_top - 26)} {_f(CX - 46)} {_f(hem_top - 30)} {_f(CX - 60)} {_f(hem_top - 40)} Z", uid, opacity=0.06),
        # sheen
        f"<path d='M{_f(neck_l)} {_f(collar_y + 10)} L{_f(CX + 6)} {_f(collar_y + 4)} L{_f(body_l + 50)} {_f(hem_top - 10)} L{_f(body_l + 14)} {_f(hem_top - 10)} Z' fill='url(#{uid}-sheen)' opacity='0.5'/>",
        # pocket
        f"<path d='{pocket_path}' fill='url(#{uid}-body)' filter='url(#{uid}-soft2)'/>",
        f"<path d='{pocket_path}' fill='rgba(255,255,255,0.045)'/>",
        _stitch(pocket_path, opacity=0.55),
        _seam(f"M{_f(pk_l + 16)} {_f(pk_top + 3)} L{_f(pk_l + 4)} {_f(pk_top + 56)}", width=1.6, opacity=0.4),
        _seam(f"M{_f(pk_r - 16)} {_f(pk_top + 3)} L{_f(pk_r - 4)} {_f(pk_top + 56)}", width=1.6, opacity=0.4),
        # hem rib
        hem_rib,
        _stitch(f"M{_f(body_l + 12)} {_f(hem_top + 3)} L{_f(body_r - 12)} {_f(hem_top + 3)}", opacity=0.4),
        # shoulder + armhole seams
        _seam(f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} C{_f(armpit_x + 6)} {_f(sh_y + 24)} {_f(armpit_x + 2)} {_f(sh_y + 44)} {_f(armpit_x)} {_f(armpit_y)}", opacity=0.45),
        _seam(_mirror_path(f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} C{_f(armpit_x + 6)} {_f(sh_y + 24)} {_f(armpit_x + 2)} {_f(sh_y + 44)} {_f(armpit_x)} {_f(armpit_y)}"), opacity=0.45),
        # hood
        f"<path d='{hood_dome}' fill='url(#{uid}-hood)'/>",
        f"<path d='{hood_opening}' fill='url(#{uid}-inner)'/>",
        f"<path d='{drape_l}' fill='url(#{uid}-hood)'/>",
        f"<path d='{drape_r}' fill='url(#{uid}-hood)'/>",
        _seam(f"M{_f(neck_l - 6)} {_f(collar_y - 6)} C{_f(neck_l - 14)} {_f(collar_y + 18)} {_f(neck_l - 4)} {_f(collar_y + 40)} {_f(CX - 10)} {_f(collar_y + 52)}", opacity=0.4),
        _seam(_mirror_path(f"M{_f(neck_l - 6)} {_f(collar_y - 6)} C{_f(neck_l - 14)} {_f(collar_y + 18)} {_f(neck_l - 4)} {_f(collar_y + 40)} {_f(CX - 10)} {_f(collar_y + 52)}"), opacity=0.4),
        _stitch(f"M{_f(neck_l + 4)} {_f(collar_y - 16)} C{_f(CX - 30)} {_f(92)} {_f(CX + 30)} {_f(92)} {_f(neck_r - 4)} {_f(collar_y - 16)}", opacity=0.42),
        cords_standard,
        cords_lacing,
    ]

    svg = _defs(uid) + "<g class='cp-stage-svg__garment'>" + "".join(parts) + "</g>"
    return {
        "svg": svg,
        "metrics": {
            "body_width_svg": bw,
            "body_width_mm": body_mm,
            "collar_y_svg": collar_y + 44,  # bottom of hood drape = top usable print line
            "sleeve_left": {"cx": (slv_elbow + armpit_x) / 2 - 2, "cy": 268.0, "angle": 9.0},
            "sleeve_right": {"cx": 420 - ((slv_elbow + armpit_x) / 2 - 2), "cy": 268.0, "angle": -9.0},
            "sleeve_len": {"y_top": sh_y + 10, "y_bot": slv_cuff_y - 8},
        },
    }


def hoodie_back(oversize: bool = False) -> dict:
    uid = "cpsgHB" + ("o" if oversize else "r")
    base = hoodie_front(oversize)
    if oversize:
        bw, body_l, body_r = 224.0, CX - 112, CX + 112
        sh_y, sh_drop = 158.0, 14.0
        hem_top, hem_bot = 466.0, 492.0
        slv_out, slv_elbow, slv_cuff_y = 58.0, 64.0, 380.0
        collar_y = 142.0
        body_mm = 660.0
    else:
        bw, body_l, body_r = 204.0, CX - 102, CX + 102
        sh_y, sh_drop = 150.0, 6.0
        hem_top, hem_bot = 462.0, 488.0
        slv_out, slv_elbow, slv_cuff_y = 74.0, 78.0, 370.0
        collar_y = 142.0
        body_mm = 600.0

    neck_l, neck_r = CX - 48, CX + 48
    armpit_x, armpit_y = body_l + 14, sh_y + 64
    cuff_out_x, cuff_in_x = slv_out + 8, armpit_x + 6

    torso = (
        f"M{_f(neck_l)} {_f(collar_y - 14)} "
        f"C{_f(neck_l - 26)} {_f(collar_y - 10)} {_f(body_l + 22)} {_f(sh_y - 12)} {_f(body_l + 4)} {_f(sh_y)} "
        f"C{_f(body_l - 2)} {_f(sh_y + 40)} {_f(body_l - 1)} {_f(260)} {_f(body_l + 3)} {_f(330)} "
        f"C{_f(body_l + 5)} {_f(395)} {_f(body_l + 6)} {_f(435)} {_f(body_l + 8)} {_f(hem_top)} "
        f"L{_f(body_r - 8)} {_f(hem_top)} "
        f"C{_f(body_r - 6)} {_f(435)} {_f(body_r - 5)} {_f(395)} {_f(body_r - 3)} {_f(330)} "
        f"C{_f(body_r + 1)} {_f(260)} {_f(body_r + 2)} {_f(sh_y + 40)} {_f(body_r - 4)} {_f(sh_y)} "
        f"C{_f(body_r - 22)} {_f(sh_y - 12)} {_f(neck_r + 26)} {_f(collar_y - 10)} {_f(neck_r)} {_f(collar_y - 14)} "
        f"C{_f(CX + 28)} {_f(collar_y - 4)} {_f(CX - 28)} {_f(collar_y - 4)} {_f(neck_l)} {_f(collar_y - 14)} Z"
    )
    sleeve_tpl = (
        f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} "
        f"C{_f(slv_out + 14)} {_f(sh_y + 26)} {_f(slv_elbow - 6)} {_f(250)} {_f(slv_elbow - 2)} {_f(300)} "
        f"C{_f(slv_elbow)} {_f(330)} {_f(cuff_out_x - 4)} {_f(slv_cuff_y - 16)} {_f(cuff_out_x)} {_f(slv_cuff_y)} "
        f"L{_f(cuff_in_x + 26)} {_f(slv_cuff_y - 4)} "
        f"C{_f(cuff_in_x + 16)} {_f(320)} {_f(armpit_x - 2)} {_f(270)} {_f(armpit_x)} {_f(armpit_y)} "
        f"C{_f(armpit_x + 4)} {_f(sh_y + 26)} {_f(body_l + 2 + sh_drop)} {_f(sh_y + 4)} {_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} Z"
    )
    cuff_w, cuff_h = (cuff_in_x + 30) - (cuff_out_x - 2), 22.0
    cuff_cx = (cuff_out_x + cuff_in_x + 28) / 2
    cuff_cy = slv_cuff_y + 8

    # Hood hanging over the back
    hood = (
        f"M{_f(CX - 48)} {_f(collar_y - 18)} "
        f"C{_f(CX - 54)} {_f(98)} {_f(CX + 54)} {_f(98)} {_f(CX + 48)} {_f(collar_y - 18)} "
        f"L{_f(CX + 53)} {_f(collar_y + 30)} "
        f"C{_f(CX + 53)} {_f(collar_y + 68)} {_f(CX - 53)} {_f(collar_y + 68)} {_f(CX - 53)} {_f(collar_y + 30)} Z"
    )

    parts = [
        f"<path d='{sleeve_tpl}' fill='url(#{uid}-sleeve)'/>",
        f"<path d='{_mirror_path(sleeve_tpl)}' fill='url(#{uid}-sleeve)'/>",
        f"<g transform='translate({_f(cuff_cx)} {_f(cuff_cy)}) rotate(8)'>"
        f"<rect x='{_f(-cuff_w / 2)}' y='-11' width='{_f(cuff_w)}' height='22' rx='9' fill='url(#{uid}-rib)'/></g>"
        + _cuff_hatch(cuff_cx, cuff_cy, cuff_w, cuff_h, 8.0),
        f"<g transform='translate({_f(420 - cuff_cx)} {_f(cuff_cy)}) rotate(-8)'>"
        f"<rect x='{_f(-cuff_w / 2)}' y='-11' width='{_f(cuff_w)}' height='22' rx='9' fill='url(#{uid}-rib)'/></g>"
        + _cuff_hatch(420 - cuff_cx, cuff_cy, cuff_w, cuff_h, -8.0),
        f"<path d='{torso}' fill='url(#{uid}-body)'/>",
        _fold(f"M{_f(body_l + 16)} {_f(armpit_y + 4)} C{_f(body_l + 30)} {_f(armpit_y + 40)} {_f(body_l + 26)} {_f(300)} {_f(body_l + 18)} {_f(340)} L{_f(body_l + 10)} {_f(330)} C{_f(body_l + 14)} {_f(286)} {_f(body_l + 12)} {_f(240)} {_f(body_l + 8)} {_f(armpit_y + 8)} Z", uid),
        _fold(_mirror_path(f"M{_f(body_l + 16)} {_f(armpit_y + 4)} C{_f(body_l + 30)} {_f(armpit_y + 40)} {_f(body_l + 26)} {_f(300)} {_f(body_l + 18)} {_f(340)} L{_f(body_l + 10)} {_f(330)} C{_f(body_l + 14)} {_f(286)} {_f(body_l + 12)} {_f(240)} {_f(body_l + 8)} {_f(armpit_y + 8)} Z"), uid),
        f"<path d='M{_f(neck_l + 8)} {_f(collar_y + 70)} L{_f(CX + 10)} {_f(collar_y + 64)} L{_f(body_l + 54)} {_f(hem_top - 16)} L{_f(body_l + 18)} {_f(hem_top - 16)} Z' fill='url(#{uid}-sheen)' opacity='0.45'/>",
        f"<rect x='{_f(body_l + 8)}' y='{_f(hem_top)}' width='{_f(bw - 16)}' height='{_f(hem_bot - hem_top)}' rx='10' fill='url(#{uid}-rib)'/>"
        + _rib_hatch(body_l + 14, body_r - 14, hem_top, hem_bot),
        _stitch(f"M{_f(body_l + 12)} {_f(hem_top + 3)} L{_f(body_r - 12)} {_f(hem_top + 3)}", opacity=0.4),
        _seam(f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} C{_f(armpit_x + 6)} {_f(sh_y + 24)} {_f(armpit_x + 2)} {_f(sh_y + 44)} {_f(armpit_x)} {_f(armpit_y)}", opacity=0.45),
        _seam(_mirror_path(f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} C{_f(armpit_x + 6)} {_f(sh_y + 24)} {_f(armpit_x + 2)} {_f(sh_y + 44)} {_f(armpit_x)} {_f(armpit_y)}"), opacity=0.45),
        # hood
        f"<path d='{hood}' fill='url(#{uid}-hood)'/>",
        f"<path d='{hood}' fill='rgba(255,255,255,0.05)'/>",
        _fold(f"M{_f(CX - 53)} {_f(collar_y + 26)} C{_f(CX - 28)} {_f(collar_y + 40)} {_f(CX + 28)} {_f(collar_y + 40)} {_f(CX + 53)} {_f(collar_y + 26)} L{_f(CX + 53)} {_f(collar_y + 36)} C{_f(CX + 28)} {_f(collar_y + 52)} {_f(CX - 28)} {_f(collar_y + 52)} {_f(CX - 53)} {_f(collar_y + 36)} Z", uid, opacity=0.2),
        _seam(f"M{_f(CX)} {_f(98)} L{_f(CX)} {_f(collar_y + 30)}", opacity=0.4),
        _stitch(f"M{_f(CX - 50)} {_f(collar_y + 34)} C{_f(CX - 26)} {_f(collar_y + 48)} {_f(CX + 26)} {_f(collar_y + 48)} {_f(CX + 50)} {_f(collar_y + 34)}", opacity=0.45),
    ]

    svg = _defs(uid) + "<g class='cp-stage-svg__garment'>" + "".join(parts) + "</g>"
    metrics = dict(base["metrics"])
    metrics["collar_y_svg"] = collar_y + 66  # below hanging hood
    return {"svg": svg, "metrics": metrics}


# ── Tee / Longsleeve ─────────────────────────────────────────────────


def tee_front(oversize: bool = False, long_sleeves: bool = False, generic: bool = False) -> dict:
    uid = "cpsgT" + ("o" if oversize else "r") + ("l" if long_sleeves else "") + ("g" if generic else "")
    if oversize:
        bw = 208.0
        sh_y, sh_drop = 156.0, 16.0
        hem_y = 460.0
        slv_end_y = 282.0
        slv_out = 70.0
        collar_y = 128.0
        body_mm = 600.0
    else:
        bw = 188.0
        sh_y, sh_drop = 150.0, 4.0
        hem_y = 466.0
        slv_end_y = 258.0
        slv_out = 88.0
        collar_y = 126.0
        body_mm = 520.0

    body_l, body_r = CX - bw / 2, CX + bw / 2
    neck_l, neck_r = CX - 42, CX + 42

    torso = (
        f"M{_f(neck_l)} {_f(collar_y)} "
        f"C{_f(neck_l - 24)} {_f(collar_y + 2)} {_f(body_l + 20)} {_f(sh_y - 12)} {_f(body_l + 4)} {_f(sh_y)} "
        f"C{_f(body_l - 2)} {_f(sh_y + 50)} {_f(body_l)} {_f(280)} {_f(body_l + 4)} {_f(350)} "
        f"C{_f(body_l + 6)} {_f(405)} {_f(body_l + 7)} {_f(438)} {_f(body_l + 9)} {_f(hem_y)} "
        f"L{_f(body_r - 9)} {_f(hem_y)} "
        f"C{_f(body_r - 7)} {_f(438)} {_f(body_r - 6)} {_f(405)} {_f(body_r - 4)} {_f(350)} "
        f"C{_f(body_r)} {_f(280)} {_f(body_r + 2)} {_f(sh_y + 50)} {_f(body_r - 4)} {_f(sh_y)} "
        f"C{_f(body_r - 20)} {_f(sh_y - 12)} {_f(neck_r + 24)} {_f(collar_y + 2)} {_f(neck_r)} {_f(collar_y)} "
        f"C{_f(CX + 26)} {_f(collar_y + 15)} {_f(CX - 26)} {_f(collar_y + 15)} {_f(neck_l)} {_f(collar_y)} Z"
    )

    armpit_x, armpit_y = body_l + 12, sh_y + 56
    if long_sleeves:
        slv_cuff_y = 384.0
        slv_elbow = slv_out - 6
        sleeve_tpl = (
            f"M{_f(body_l + 8 + sh_drop)} {_f(sh_y - 2)} "
            f"C{_f(slv_out + 10)} {_f(sh_y + 22)} {_f(slv_elbow + 4)} {_f(252)} {_f(slv_elbow + 8)} {_f(300)} "
            f"C{_f(slv_elbow + 12)} {_f(332)} {_f(slv_out + 18)} {_f(slv_cuff_y - 16)} {_f(slv_out + 22)} {_f(slv_cuff_y)} "
            f"L{_f(armpit_x + 28)} {_f(slv_cuff_y - 4)} "
            f"C{_f(armpit_x + 18)} {_f(322)} {_f(armpit_x)} {_f(272)} {_f(armpit_x + 2)} {_f(armpit_y)} "
            f"C{_f(armpit_x + 6)} {_f(sh_y + 24)} {_f(body_l + 4 + sh_drop)} {_f(sh_y + 4)} {_f(body_l + 8 + sh_drop)} {_f(sh_y - 2)} Z"
        )
        cuff_w = (armpit_x + 32) - (slv_out + 14)
        cuff_cx = (slv_out + 18 + armpit_x + 28) / 2
        cuff_cy = slv_cuff_y + 7
        cuffs = (
            f"<g transform='translate({_f(cuff_cx)} {_f(cuff_cy)}) rotate(7)'>"
            f"<rect x='{_f(-cuff_w / 2)}' y='-10' width='{_f(cuff_w)}' height='20' rx='8' fill='url(#{uid}-rib)'/></g>"
            + _cuff_hatch(cuff_cx, cuff_cy, cuff_w, 20, 7.0)
            + f"<g transform='translate({_f(420 - cuff_cx)} {_f(cuff_cy)}) rotate(-7)'>"
            f"<rect x='{_f(-cuff_w / 2)}' y='-10' width='{_f(cuff_w)}' height='20' rx='8' fill='url(#{uid}-rib)'/></g>"
            + _cuff_hatch(420 - cuff_cx, cuff_cy, cuff_w, 20, -7.0)
        )
        sleeve_metrics = {"cx": (slv_elbow + armpit_x) / 2 + 2, "cy": 272.0, "angle": 8.0}
        sleeve_len = {"y_top": sh_y + 12, "y_bot": slv_cuff_y - 10}
    else:
        sleeve_tpl = (
            f"M{_f(body_l + 8 + sh_drop)} {_f(sh_y - 2)} "
            f"C{_f(slv_out + 16)} {_f(sh_y + 18)} {_f(slv_out + 2)} {_f(sh_y + 56)} {_f(slv_out)} {_f(slv_end_y)} "
            f"L{_f(armpit_x + 22)} {_f(slv_end_y + 8)} "
            f"C{_f(armpit_x + 8)} {_f(slv_end_y - 22)} {_f(armpit_x + 2)} {_f(sh_y + 50)} {_f(armpit_x + 2)} {_f(armpit_y)} "
            f"C{_f(armpit_x + 6)} {_f(sh_y + 24)} {_f(body_l + 4 + sh_drop)} {_f(sh_y + 4)} {_f(body_l + 8 + sh_drop)} {_f(sh_y - 2)} Z"
        )
        cuffs = (
            _stitch(f"M{_f(slv_out + 3)} {_f(slv_end_y - 5)} L{_f(armpit_x + 22)} {_f(slv_end_y + 3)}", opacity=0.5)
            + _stitch(_mirror_path(f"M{_f(slv_out + 3)} {_f(slv_end_y - 5)} L{_f(armpit_x + 22)} {_f(slv_end_y + 3)}"), opacity=0.5)
        )
        sleeve_metrics = {"cx": (slv_out + armpit_x + 16) / 2, "cy": (sh_y + slv_end_y) / 2 + 8, "angle": 12.0}
        sleeve_len = {"y_top": sh_y + 12, "y_bot": slv_end_y + 4}

    collar = (
        f"<path d='M{_f(neck_l - 4)} {_f(collar_y - 1)} "
        f"C{_f(CX - 28)} {_f(collar_y - 14)} {_f(CX + 28)} {_f(collar_y - 14)} {_f(neck_r + 4)} {_f(collar_y - 1)} "
        f"C{_f(CX + 28)} {_f(collar_y + 18)} {_f(CX - 28)} {_f(collar_y + 18)} {_f(neck_l - 4)} {_f(collar_y - 1)} Z' "
        f"fill='url(#{uid}-rib)'/>"
        f"<path d='M{_f(neck_l + 4)} {_f(collar_y)} "
        f"C{_f(CX - 24)} {_f(collar_y - 9)} {_f(CX + 24)} {_f(collar_y - 9)} {_f(neck_r - 4)} {_f(collar_y)} "
        f"C{_f(CX + 24)} {_f(collar_y + 12)} {_f(CX - 24)} {_f(collar_y + 12)} {_f(neck_l + 4)} {_f(collar_y)} Z' "
        f"fill='url(#{uid}-inner)'/>"
        + _stitch(f"M{_f(neck_l)} {_f(collar_y + 5)} C{_f(CX - 20)} {_f(collar_y + 17)} {_f(CX + 20)} {_f(collar_y + 17)} {_f(neck_r)} {_f(collar_y + 5)}", opacity=0.45)
    )

    fold_tpl = (
        f"M{_f(body_l + 14)} {_f(armpit_y + 10)} C{_f(body_l + 26)} {_f(armpit_y + 50)} {_f(body_l + 22)} {_f(320)} {_f(body_l + 16)} {_f(356)} "
        f"L{_f(body_l + 9)} {_f(348)} C{_f(body_l + 12)} {_f(300)} {_f(body_l + 11)} {_f(252)} {_f(body_l + 7)} {_f(armpit_y + 14)} Z"
    )

    parts = [
        f"<path d='{sleeve_tpl}' fill='url(#{uid}-sleeve)'/>",
        f"<path d='{_mirror_path(sleeve_tpl)}' fill='url(#{uid}-sleeve)'/>",
        cuffs,
        f"<path d='{torso}' fill='url(#{uid}-body)'/>",
        _fold(fold_tpl, uid),
        _fold(_mirror_path(fold_tpl), uid),
        _fold(f"M{_f(CX - 50)} {_f(hem_y - 56)} C{_f(CX - 34)} {_f(hem_y - 44)} {_f(CX - 14)} {_f(hem_y - 42)} {_f(CX + 4)} {_f(hem_y - 44)} L{_f(CX + 4)} {_f(hem_y - 34)} C{_f(CX - 22)} {_f(hem_y - 32)} {_f(CX - 42)} {_f(hem_y - 36)} {_f(CX - 54)} {_f(hem_y - 46)} Z", uid, opacity=0.06),
        f"<path d='M{_f(neck_l)} {_f(collar_y + 24)} L{_f(CX + 4)} {_f(collar_y + 18)} L{_f(body_l + 48)} {_f(hem_y - 14)} L{_f(body_l + 14)} {_f(hem_y - 14)} Z' fill='url(#{uid}-sheen)' opacity='0.5'/>",
        # hem + side seams
        _stitch(f"M{_f(body_l + 11)} {_f(hem_y - 9)} L{_f(body_r - 11)} {_f(hem_y - 9)}", opacity=0.5),
        _seam(f"M{_f(body_l + 5)} {_f(armpit_y + 16)} C{_f(body_l + 2)} {_f(280)} {_f(body_l + 6)} {_f(380)} {_f(body_l + 9)} {_f(hem_y - 4)}", opacity=0.35),
        _seam(_mirror_path(f"M{_f(body_l + 5)} {_f(armpit_y + 16)} C{_f(body_l + 2)} {_f(280)} {_f(body_l + 6)} {_f(380)} {_f(body_l + 9)} {_f(hem_y - 4)}"), opacity=0.35),
        # armhole seams
        _seam(f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} C{_f(armpit_x + 8)} {_f(sh_y + 22)} {_f(armpit_x + 4)} {_f(sh_y + 46)} {_f(armpit_x + 2)} {_f(armpit_y)}", opacity=0.45),
        _seam(_mirror_path(f"M{_f(body_l + 6 + sh_drop)} {_f(sh_y - 8)} C{_f(armpit_x + 8)} {_f(sh_y + 22)} {_f(armpit_x + 4)} {_f(sh_y + 46)} {_f(armpit_x + 2)} {_f(armpit_y)}"), opacity=0.45),
        # shoulder seams
        _seam(f"M{_f(neck_l - 2)} {_f(collar_y + 2)} L{_f(body_l + 10 + sh_drop)} {_f(sh_y - 6)}", opacity=0.4),
        _seam(_mirror_path(f"M{_f(neck_l - 2)} {_f(collar_y + 2)} L{_f(body_l + 10 + sh_drop)} {_f(sh_y - 6)}"), opacity=0.4),
        collar,
    ]
    if generic:
        parts.append(
            f"<path d='M{_f(body_l - 10)} {_f(sh_y - 24)} C{_f(body_l - 18)} {_f(300)} {_f(body_l - 12)} {_f(420)} {_f(body_l - 6)} {_f(hem_y + 18)} "
            f"L{_f(body_r + 6)} {_f(hem_y + 18)} C{_f(body_r + 12)} {_f(420)} {_f(body_r + 18)} {_f(300)} {_f(body_r + 10)} {_f(sh_y - 24)}' "
            f"fill='none' stroke='rgba(242,211,155,0.4)' stroke-width='1.6' stroke-dasharray='7 7' opacity='0.8'/>"
        )

    svg = _defs(uid) + "<g class='cp-stage-svg__garment'>" + "".join(parts) + "</g>"
    return {
        "svg": svg,
        "metrics": {
            "body_width_svg": bw,
            "body_width_mm": body_mm,
            "collar_y_svg": collar_y + 22,
            "sleeve_left": dict(sleeve_metrics),
            "sleeve_right": {**sleeve_metrics, "cx": 420 - sleeve_metrics["cx"], "angle": -sleeve_metrics["angle"]},
            "sleeve_len": sleeve_len,
        },
    }


def tee_back(oversize: bool = False, long_sleeves: bool = False, generic: bool = False) -> dict:
    front = tee_front(oversize=oversize, long_sleeves=long_sleeves, generic=generic)
    uid = "cpsgTB" + ("o" if oversize else "r") + ("l" if long_sleeves else "") + ("g" if generic else "")
    # Back = same construction, higher neckline, no deep collar opening.
    svg = front["svg"]
    src_uid = "cpsgT" + ("o" if oversize else "r") + ("l" if long_sleeves else "") + ("g" if generic else "")
    svg = svg.replace(src_uid, uid)

    collar_y = 128.0 if oversize else 126.0
    neck_l, neck_r = CX - 42, CX + 42
    # Replace the front collar group with a flat back neckband.
    import re as _re

    back_collar = (
        f"<path d='M{_f(neck_l - 4)} {_f(collar_y - 1)} "
        f"C{_f(CX - 28)} {_f(collar_y - 13)} {_f(CX + 28)} {_f(collar_y - 13)} {_f(neck_r + 4)} {_f(collar_y - 1)} "
        f"C{_f(CX + 28)} {_f(collar_y + 10)} {_f(CX - 28)} {_f(collar_y + 10)} {_f(neck_l - 4)} {_f(collar_y - 1)} Z' "
        f"fill='url(#{uid}-rib)'/>"
        + _stitch(f"M{_f(neck_l)} {_f(collar_y + 3)} C{_f(CX - 22)} {_f(collar_y + 12)} {_f(CX + 22)} {_f(collar_y + 12)} {_f(neck_r)} {_f(collar_y + 3)}", opacity=0.45)
    )
    # The collar block is the segment between fill='url(#uid-rib)' collar path and the final stitch — rebuild via marker
    marker_start = svg.find(f"<path d='M{_f(neck_l - 4)} {_f(collar_y - 1)}")
    if marker_start != -1:
        svg = svg[:marker_start] + back_collar + "</g>"
    metrics = dict(front["metrics"])
    metrics["collar_y_svg"] = collar_y + 12
    return {"svg": svg, "metrics": metrics}


# ── Public API ───────────────────────────────────────────────────────


def build_stage_art() -> dict:
    return {
        "hoodie": {
            "regular": {"front": hoodie_front(False), "back": hoodie_back(False)},
            "oversize": {"front": hoodie_front(True), "back": hoodie_back(True)},
        },
        "tshirt": {
            "regular": {"front": tee_front(False), "back": tee_back(False)},
            "oversize": {"front": tee_front(True), "back": tee_back(True)},
        },
        "longsleeve": {
            "default": {"front": tee_front(False, long_sleeves=True), "back": tee_back(False, long_sleeves=True)},
        },
        "customer_garment": {
            "default": {
                "front": tee_front(False, long_sleeves=True, generic=True),
                "back": tee_back(False, long_sleeves=True, generic=True),
            },
        },
    }

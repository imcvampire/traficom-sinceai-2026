"""RR Article 21, Table 21-4 pfd limits (`data/ref/rr21_pfd_limits.json`) as evaluable functions of δ."""

import hashlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from ific.config import settings

# Space-station classes per Table 21-4 service, from the BR IFIC Preface, Section IV, Table 3 "Class of
# Station" (edition of October 2026). ED, EK and ER (telecommand, tracking, telemetering) are space operation
# functions (RR No. 1.23). Classes with no Table 21-4 entry (EA amateur, EE/EY standard frequency and time)
# are left out, so their groups are `not_applicable`.
SERVICE_CLASSES: dict[str, tuple[str, ...]] = {
    "fss": ("EC",),
    "bss": ("EB", "EV"),
    "mss": ("EI", "EG", "EJ", "EU", "E5", "E6"),
    "rdss": ("EF",),
    "rnss": ("EN", "EO", "EQ"),
    "metsat": ("EM",),
    "eess": ("EW", "E3", "E4"),
    "sr": ("EH", "E1", "E2"),
    "so": ("ET", "ED", "EK", "ER"),
    "iss": ("ES",),
}
SERVICE_LABEL = {
    "fss": "FSS",
    "bss": "BSS",
    "mss": "MSS",
    "rdss": "RDSS",
    "rnss": "RNSS",
    "metsat": "MetSat",
    "eess": "EESS",
    "sr": "Space research",
    "so": "Space operation",
    "iss": "ISS",
}
KNOWN_CLASSES = frozenset(c for cs in SERVICE_CLASSES.values() for c in cs) | {"EA", "EE", "EY"}
CLASS_CITE = "BR IFIC Preface, Section IV, Table 3 (edition of October 2026)"
ORBITS = ("gso", "ngso", "any")
NGSO_CLASSES = ("heo", "non_heo")
HEO_APOGEE_KM = 18_000.0
HEO_INCL_DEG = (35.0, 145.0)


class LimitsError(ValueError):
    pass


class NotEvaluable(Exception):
    """The limit exists but cannot be evaluated for these inputs (reason in the message)."""


@dataclass(frozen=True)
class XSegment:
    n_gt: int
    n_le: int
    num: float
    den: float
    n_off: float


@dataclass(frozen=True)
class Limit:
    id: str
    f_lo_hz: float
    f_hi_hz: float
    services: tuple[str, ...]
    orbit: str
    ngso_class: str | None
    ref_bw_hz: float
    encoded: bool
    reason: str | None
    kind: str | None
    delta: tuple[float, ...]
    base: tuple[float, ...]
    x_coeff: tuple[float, ...]
    x: tuple[XSegment, ...]
    x_beyond: str | None
    n_sats_max: int | None
    footnotes: tuple[str, ...]
    cite: str
    note: str | None

    @property
    def stn_cls(self) -> frozenset[str]:
        return frozenset(c for s in self.services for c in SERVICE_CLASSES[s])

    def x_db(self, n_sats: int | None) -> float:
        """Footnote 21.16.6 X(N) in dB; `NotEvaluable` outside the encoded N range."""
        if not self.x:
            return 0.0
        if n_sats is None:
            raise NotEvaluable("number of satellites N not notified (21.16.6)")
        for s in self.x:
            if s.n_gt < n_sats <= s.n_le:
                return s.num / s.den * (n_sats + s.n_off)
        raise NotEvaluable(self.x_beyond or f"N = {n_sats} is outside the encoded range")

    def at(self, delta_deg: np.ndarray | float, n_sats: int | None = None) -> np.ndarray | float:
        """Limit in dB(W/m²) in `ref_bw_hz` at angle of arrival δ (degrees, clipped to 0–90)."""
        if not self.encoded:
            raise NotEvaluable(self.reason or "row not encoded")
        if self.n_sats_max is not None and n_sats is not None and n_sats > self.n_sats_max:
            raise NotEvaluable(
                f"the limit applies to systems of at most {self.n_sats_max} satellites; this one has "
                f"{n_sats} ({', '.join(self.footnotes)})"
            )
        x = self.x_db(n_sats)
        values = np.asarray(self.base) - np.asarray(self.x_coeff) * x
        out = np.interp(np.clip(delta_deg, 0.0, 90.0), self.delta, values)
        return float(out) if np.ndim(out) == 0 else out


@dataclass(frozen=True)
class Limits:
    raw: dict[str, Any]
    rows: tuple[Limit, ...]
    sha256: str
    review_status: str
    cite: str


def _row(r: dict[str, Any]) -> Limit:
    rid = r.get("id") or "?"

    def fail(msg: str) -> LimitsError:
        return LimitsError(f"{rid}: {msg}")

    lo, hi = float(r["f_lo_mhz"]), float(r["f_hi_mhz"])
    if not lo < hi:
        raise fail("f_lo_mhz must be below f_hi_mhz")
    if float(r["ref_bw_hz"]) <= 0:
        raise fail("ref_bw_hz must be positive")
    if r["orbit"] not in ORBITS:
        raise fail(f"unknown orbit {r['orbit']!r}")
    if r.get("ngso_class") not in (None, *NGSO_CLASSES):
        raise fail(f"unknown ngso_class {r['ngso_class']!r}")
    unknown = [s for s in r["services"] if s not in SERVICE_CLASSES]
    if unknown or not r["services"]:
        raise fail(f"unknown services {unknown}")
    encoded = bool(r["encoded"])
    if not encoded and not r.get("reason"):
        raise fail("a row with encoded: false needs a reason")
    lim = r.get("limit")
    delta: tuple[float, ...] = ()
    base: tuple[float, ...] = ()
    coeff: tuple[float, ...] = ()
    xs: tuple[XSegment, ...] = ()
    kind = None
    if lim is not None:
        kind = lim["kind"]
        if kind == "piecewise":
            pts = [(float(d), float(v), 0.0) for d, v in lim["points"]]
        elif kind == "ngso_n":
            pts = [(float(d), float(v), float(c)) for d, v, c in lim["points"]]
            xs = tuple(XSegment(**s) for s in lim["x"])
            for s in xs:
                if s.den == 0 or s.n_gt >= s.n_le:
                    raise fail("bad X segment")
        else:
            raise fail(f"unknown limit kind {kind!r}")
        delta = tuple(p[0] for p in pts)
        if len(delta) < 2 or delta[0] != 0 or delta[-1] != 90:
            raise fail("δ points must start at 0 and end at 90")
        if any(b <= a for a, b in zip(delta, delta[1:], strict=False)):
            raise fail("δ points must be strictly increasing")
        base, coeff = tuple(p[1] for p in pts), tuple(p[2] for p in pts)
    elif encoded:
        raise fail("an encoded row needs a limit")
    return Limit(
        id=rid,
        f_lo_hz=lo * 1e6,
        f_hi_hz=hi * 1e6,
        services=tuple(r["services"]),
        orbit=r["orbit"],
        ngso_class=r.get("ngso_class"),
        ref_bw_hz=float(r["ref_bw_hz"]),
        encoded=encoded,
        reason=r.get("reason"),
        kind=kind,
        delta=delta,
        base=base,
        x_coeff=coeff,
        x=xs,
        x_beyond=(lim or {}).get("x_beyond"),
        n_sats_max=r.get("n_sats_max"),
        footnotes=tuple(r.get("footnotes", ())),
        cite=r["cite"],
        note=r.get("note"),
    )


def parse(raw: dict[str, Any], sha256: str = "") -> Limits:
    rows = tuple(_row(r) for r in raw["rows"])
    ids = [r.id for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise LimitsError(f"duplicate row ids {sorted(dup)}")
    return Limits(raw, rows, sha256, raw["review"]["status"], raw["cite"])


@cache
def load_limits(path: Path | None = None) -> Limits:
    path = path or settings.data_dir / "ref" / "rr21_pfd_limits.json"
    data = path.read_bytes()
    return parse(json.loads(data), hashlib.sha256(data).hexdigest())

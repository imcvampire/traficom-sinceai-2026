"""The method description served by `GET /api/risk/model`; wording is quoted from the doc's sources."""

from typing import Any

from ific.riia import MODEL_VERSION, antenna, curves, emission
from ific.riia.assess import ASSUMPTIONS
from ific.riia.receivers import load_classes

TAC = "FCC TAC, A Quick Introduction to Risk-Informed Interference Assessment, v1.00 (2015)"
DE_VRIES_2018 = (
    "J. P. de Vries, Modeling Interference Risk: Propagation and Other Uncertainties, ISART (2018)"
)

METHOD_STEPS = [
    {
        "step": 1,
        "source_wording": "Make an inventory of all significant harmful interference hazard modes",
        "what": (
            "Every hazard mode for each notice and Finnish receiver class, "
            "including the modes not yet quantified."
        ),
        "cite": TAC,
    },
    {
        "step": 2,
        "source_wording": "Define a consequence metric to characterize the severity of hazards",
        "what": (
            "I/N in dB for active services; spectral pfd minus the RA.769 "
            "threshold, in dB, for radio astronomy."
        ),
        "cite": TAC,
    },
    {
        "step": 3,
        "source_wording": "Assess the likelihood and consequence of each hazard mode",
        "what": (
            "Seeded Monte Carlo over the receiver population, time and uncertain "
            "parameters, after a Tier 1 screen."
        ),
        "cite": TAC,
    },
    {
        "step": 4,
        "source_wording": "Aggregate results",
        "what": (
            "All hazard curves of a notice on one likelihood–consequence chart "
            "against the ITU-R criterion points."
        ),
        "cite": DE_VRIES_2018,
    },
]

REFERENCES = [
    {
        "title": TAC,
        "url": "https://transition.fcc.gov/bureaus/oet/tac/tacdocs/meeting4115/Intro-to-RIA-v100.pdf",
        "supports": (
            "Steps, likelihood in a population, quantitative scales, risk curves "
            "per mode, risk-informed not risk-based"
        ),
    },
    {
        "title": "J. P. de Vries, Risk-informed interference assessment, CSMAC handout (2015)",
        "url": "https://www.ntia.gov/sites/default/files/publications/15-05-12_csmac_risk_hand-out_0.pdf",
        "supports": "Risk triplet, I/N as consequence metric, Monte Carlo likelihood–consequence profiles",
    },
    {
        "title": DE_VRIES_2018,
        "url": "https://its.ntia.gov/media/66520/devries_isart2018.pdf",
        "supports": (
            "Aggregate step, protection criteria as acceptability test, sample size by time %, sensitivity"
        ),
    },
    {
        "title": "Silicon Flatirons Center, Risk Assessment in Spectrum Policy (2015)",
        "url": "https://siliconflatirons.org/documents/publications/report/201512RiskAssessmentReport.pdf",
        "supports": "Tiered analysis: deterministic screen first",
    },
    {
        "title": (
            "Voicu et al., Risk-Informed Interference Assessment for Shared Spectrum Bands (arXiv:1706.02479)"
        ),
        "url": "https://arxiv.org/abs/1706.02479",
        "supports": "Likelihood as a CCDF; curves that cross",
    },
]


def describe(outcome_sensitive: list[str]) -> dict[str, Any]:
    cf = load_classes()
    classes = []
    for raw in cf.raw["classes"]:
        cls = cf.classes[raw["id"]]
        classes.append(
            {
                "id": cls.id,
                "label": cls.label,
                "keywords": [" + ".join(r["keywords"]) for r in cf.rules if r["class"] == cls.id],
                "pattern": cls.pattern,
                "gain_dbi": cls.gain_dbi,
                "nf_db": cls.nf_db,
                "bw_hz": cls.bw_hz,
                "criteria": [vars(c) for c in cls.criteria],
                "distributions": [vars(d) for d in cls.distributions.values()],
            }
        )
    inputs = [
        {
            "name": "Assignment bands, power, beam gain",
            "source": "data",
            "cite": "space.grp, space.emiss, space.s_beam",
        },
        {"name": "GSO position and tolerance", "source": "data", "cite": "space.geo"},
        {"name": "Non-GSO orbits", "source": "data", "cite": "space.orbit"},
        {"name": "Notified pfd", "source": "data", "cite": "space.c_pfd"},
        {
            "name": "Finnish protected bands",
            "source": "data",
            "cite": "ref.m4_allocation (Services_in_Finland)",
        },
        {
            "name": "Protection criteria, patterns, receiver characteristics",
            "source": "itu-r",
            "cite": "data/ref/receiver_classes.json (review " + cf.raw["review"]["status"] + ")",
        },
        *({"name": f"Pattern {k}", "source": "itu-r", "cite": v} for k, v in antenna.PATTERN_CITES.items()),
        {"name": "Out-of-band mask", "source": "itu-r", "cite": emission.OOB_CITE},
        {"name": "Spurious limit", "source": "rr", "cite": emission.SPURIOUS_CITE},
        {"name": "Comment windows", "source": "rr", "cite": "data/ref/rr_comment_windows.json"},
        {
            "name": "Thermal noise, geometry, link budget",
            "source": "physics",
            "cite": "k·T0; spherical Earth",
        },
        *({"name": k, "source": "assumption", "cite": v} for k, v in ASSUMPTIONS.items()),
    ]
    return {
        "model_version": MODEL_VERSION,
        "receiver_source": "generic-m4",
        "curve_grid_db": {
            "start": curves.GRID_START_DB,
            "stop": curves.GRID_STOP_DB,
            "step": curves.GRID_STEP_DB,
        },
        "method_steps": METHOD_STEPS,
        "references": REFERENCES,
        "receiver_classes": classes,
        "inputs": inputs,
        "outcome_sensitive": sorted(outcome_sensitive),
        "doc_path": "docs/interference-risk-assessment.md",
    }

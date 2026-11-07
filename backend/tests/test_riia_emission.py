import numpy as np
import pytest

from ific.riia import emission as e


def test_sm1541_mask() -> None:
    assert e.oob_attenuation_db(np.array([0.0, 50.0, 200.0])) == pytest.approx([0.0, 12.04, 27.96], abs=0.01)


def test_appendix3_spurious() -> None:
    assert e.spurious_attenuation_db(10.0) == 53.0
    assert e.spurious_attenuation_db(30.0) == 60.0


def test_unwanted_switches_domain_at_200_percent() -> None:
    att = e.unwanted_attenuation_db(np.array([1e6, 2e6, 3e6]), 1e6, 10.0)
    assert att == pytest.approx([19.08, 27.96, 53.0], abs=0.01)


def test_acir() -> None:
    assert float(e.acir_db(30.0, 30.0)) == pytest.approx(26.99, abs=0.01)
    assert float(e.acir_db(80.0, 30.0)) == pytest.approx(30.0, abs=0.01)

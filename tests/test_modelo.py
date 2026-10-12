"""Comprobaciones físicas básicas: ejecutar con `pytest`."""
import numpy as np
import pytest

from motor0d import HCCI, MEC, MEP, MOTORES, Geometria, Opciones, ciclo, volumen
from motor0d.modelo import integral_lw, quemado, tau_ign

GEO = Geometria()


def test_volumen_pms_pmi():
    rc = 12.0
    V, _ = volumen(GEO, rc, np.array([0.0, 180.0, -180.0]))
    Vc = GEO.Vd / (rc - 1)
    assert V[0] == pytest.approx(Vc)
    assert V[1] == pytest.approx(Vc + GEO.Vd)
    assert V[1] / V[0] == pytest.approx(rc)


def test_derivada_volumen():
    th = np.linspace(-170, 170, 341)
    V, dV = volumen(GEO, 10.0, th)
    assert np.allclose(np.gradient(V, th)[5:-5], dV[5:-5], rtol=1e-3, atol=1e-9)


@pytest.mark.parametrize("mot", MOTORES, ids=lambda m: m.nombre)
def test_fraccion_quemada_completa(mot):
    cb = mot.comb if mot.comb.soc is not None else mot.comb_si
    xb, _ = quemado(np.array([-180.0, 180.0]), cb)
    assert xb[0] == pytest.approx(0.0)
    assert xb[1] == pytest.approx(1.0, abs=1e-3)


def test_ciclo_arrastrado_adiabatico_sin_trabajo():
    """Sin combustión ni pérdidas, compresión y expansión deben cancelarse."""
    mot = MEP.con(eta_comb=0.0)
    r = ciclo(mot, 1.0, 2500, opc=Opciones(woschni=False))
    assert abs(r.imep_g) < 0.01e5


def test_tendencias_clasicas():
    r_mep = ciclo(MEP, 0.4, 2500)
    r_mec = ciclo(MEC, 0.4, 2500)
    r_hcci = ciclo(HCCI, 0.4, 2500)
    assert r_mec.eta_i > r_mep.eta_i          # sin bombeo y rc alta
    assert r_hcci.eta_i > r_mep.eta_i
    assert r_hcci.nox < 0.05 * r_mep.nox      # combustión pobre y fría
    assert r_mep.pmep > r_mec.pmep            # mariposa


def test_tau_disminuye_con_T_y_p():
    assert tau_ign(30e5, 1000, 0.4, 0.21) < tau_ign(30e5, 950, 0.4, 0.21)
    assert tau_ign(40e5, 1000, 0.4, 0.21) < tau_ign(30e5, 1000, 0.4, 0.21)


def test_integral_lw_monotona():
    th = np.linspace(-60, 20, 161)
    I = integral_lw(th, np.full_like(th, 40e5), np.full_like(th, 1000.0), 2500, 0.4, 0.19)
    assert np.all(np.diff(I) > 0)


def test_control_ca50_alcanza_objetivo():
    r = ciclo(HCCI, 0.4, 2500)
    assert r.modo == "HCCI"
    assert r.ca50 == pytest.approx(HCCI.ca50_obj, abs=0.5)


def test_hcci_fallo_en_lazo_abierto_frio():
    r = ciclo(HCCI.con(ca50_obj=None, T_ivc=360), 0.4, 2500)
    assert r.fallo and r.imep_n < 0

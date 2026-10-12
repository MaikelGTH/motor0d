"""Modelo 0D monozona de ciclo cerrado (IVC = EVO = PMI).

Ecuación de energía (gas ideal, gamma(T), sin intercambio de masa):

    dp/dθ = (γ-1)/V · (dQc/dθ - dQw/dθ) - γ · p/V · dV/dθ
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import pi
from typing import Optional

import numpy as np
from scipy.integrate import solve_ivp

from .config import Ambiente, Combustion, Geometria, Motor, Opciones

AMB = Ambiente()
GEO = Geometria()
OPC = Opciones()


# --------------------------------------------------------------------------
# Geometría y ley de combustión
# --------------------------------------------------------------------------
def volumen(geo: Geometria, rc: float, th):
    """Biela-manivela exacto, θ = 0 en PMS. Devuelve V [m3] y dV/dθ [m3/deg]."""
    t = np.deg2rad(th)
    a = geo.S / 2
    R = geo.L / a
    Vc = geo.Vd / (rc - 1)
    raiz = np.sqrt(R**2 - np.sin(t) ** 2)
    V = Vc + geo.Ap * a * (R + 1 - np.cos(t) - raiz)
    dV = geo.Ap * a * np.sin(t) * (1 + np.cos(t) / raiz) * pi / 180
    return V, dV


def wiebe(th, soc, dur, a, m):
    z = np.maximum((np.asarray(th) - soc) / dur, 0.0)
    xb = 1 - np.exp(-a * z ** (m + 1))
    dxb = a * (m + 1) / dur * z**m * np.exp(-a * z ** (m + 1))   # [1/deg]
    return xb, dxb


def quemado(th, cb: Combustion):
    if cb.tipo == "wiebe":
        return wiebe(th, cb.soc, cb.dur, cb.a, cb.m)
    # Watson: fase premezclada (beta) + fase de difusión
    x1, d1 = wiebe(th, cb.soc, cb.dur, cb.a, cb.m)
    x2, d2 = wiebe(th, cb.soc, cb.dur2, cb.a, cb.m2)
    return cb.beta * x1 + (1 - cb.beta) * x2, cb.beta * d1 + (1 - cb.beta) * d2


def gamma_T(T):
    """γ(T) lineal para mezclas aire-combustible/productos (300-3000 K)."""
    return 1.392 - 8.13e-5 * T


# --------------------------------------------------------------------------
# Estrategia de carga y llenado
# --------------------------------------------------------------------------
def estrategia_carga(mot: Motor, carga: float, amb: Ambiente = AMB):
    """carga = masa de combustible / masa máxima (lambda_pc sin mariposa).

    Devuelve (p_admisión, lambda, ley de combustión, modo).
    """
    cb, modo = mot.comb, mot.nombre
    if mot.ctrl == "cantidad":                 # mariposa, lambda fija
        return carga * amb.p, 1.0, cb, modo
    if mot.ctrl == "calidad":                  # sin mariposa, lambda variable
        cb = replace(cb, beta=0.10 + 0.35 * (1 - carga), dur2=30 + 30 * carga)
        return amb.p, mot.lambda_pc / carga, cb, modo
    # HCCI: pobre sin mariposa hasta lambda_min; por encima, chispa a lambda = 1
    if carga <= 1 / mot.lambda_min:
        return amb.p, 1 / carga, cb, "HCCI"
    return carga * amb.p, 1.0, mot.comb_si, "SI"


def rend_vol(mot: Motor, n: float) -> float:
    """Curva SUPUESTA (no calculada): parábola centrada en el régimen de sintonía."""
    return max(mot.etav_max * (1 - 0.35 * ((n - mot.n_etav) / mot.n_etav) ** 2), 0.55)


# --------------------------------------------------------------------------
# Autoignición: Livengood-Wu con la correlación de He et al. (2005)
# --------------------------------------------------------------------------
def tau_ign(p, T, phi, x_o2):
    """Retraso de autoignición [ms] para iso-octano (He et al., Combust. Flame 2005).

    τ = 1.3e-4 · p^-1.05 · φ^-0.77 · χO2^-1.41 · exp(33700 / (Ru·T)),
    p en atm, χO2 en % molar, Ru = 1.987 cal/mol·K. Validada en ~943-1027 K, 9-23 atm,
    φ 0.25-1: fuera de ese rango es extrapolación.
    """
    p_atm = p / 101325.0
    return 1.3e-4 * p_atm**-1.05 * phi**-0.77 * (100 * x_o2)**-1.41 * np.exp(33700 / (1.987 * T))


def integral_lw(th, p, T, n, phi, x_o2):
    """Integral de Livengood-Wu acumulada: I(θ) = ∫ dt / τ. Autoignición en I = 1."""
    dt_ms = 1000.0 / (6.0 * n)                 # ms por grado
    f = 1.0 / tau_ign(p, T, phi, x_o2)
    I = np.concatenate(([0.0], np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(th)))) * dt_ms
    return I


# --------------------------------------------------------------------------
# Integración del ciclo
# --------------------------------------------------------------------------
def _integrar(geo, mot, cb, Qtot, m, p0, V0, n, th, opc):
    Sp = 2 * geo.S * n / 60
    soc = cb.soc if cb is not None else np.inf

    def dpdth(t, y):
        p = y[0]
        V, dV = volumen(geo, mot.rc, t)
        dxb = quemado(t, cb)[1] if cb is not None else 0.0
        T = p * V / (m * AMB.R)
        g = gamma_T(T)
        dQw = 0.0
        if opc.woschni:                         # Woschni (1967)
            pmot = p0 * (V0 / V) ** mot.g
            C2 = 3.24e-3 if t >= soc else 0.0
            w = max(2.28 * Sp + C2 * geo.Vd * mot.T_ivc / (p0 * V0) * (p - pmot), 0.1)
            h = 3.26 * geo.B**-0.2 * (p / 1e3) ** 0.8 * T**-0.55 * w**0.8
            A = 2 * geo.Ap + 4 * V / geo.B
            dQw = h * A * (T - opc.T_pared) / (6 * n)     # [J/deg]
        return [(g - 1) / V * (Qtot * dxb - dQw) - g * p / V * dV]

    sol = solve_ivp(dpdth, (th[0], th[-1]), [p0], t_eval=th, max_step=0.5,
                    rtol=1e-6, atol=1.0)
    return sol.y[0]


def soc_livengood_wu(mot, lam, p0, n, geo=GEO, amb=AMB, opc=OPC):
    """Inicio de combustión por autoignición [deg], o None si no autoinflama.

    Se integra la compresión sin combustión (con pérdidas) y se busca I(θ) = 1.
    Hasta el encendido no hay liberación de calor, así que la traza arrastrada
    coincide exactamente con la del ciclo real.
    """
    th = np.arange(-180.0, opc.fin_lw + 1e-9, opc.dth)
    V, _ = volumen(geo, mot.rc, th)
    m = p0 * V[0] / (amb.R * mot.T_ivc)
    p = _integrar(geo, mot, None, 0.0, m, p0, V[0], n, th, opc)
    T = p * V / (m * amb.R)
    I = integral_lw(th, p, T, n, 1 / lam, mot.x_o2)
    if I[-1] < 1.0:
        return None
    k = int(np.argmax(I >= 1.0))
    return float(np.interp(1.0, I[k - 1:k + 1], th[k - 1:k + 1]))


def controlar_ca50(mot, cb, lam, p0, n, geo=GEO, amb=AMB, opc=OPC,
                   T_lim=(330.0, 560.0), tol=0.25):
    """T_IVC [K] que lleva el CA50 al objetivo (bisección; el SOC baja al subir T_IVC).

    Representa el control real del HCCI: residuales internos (NVO) o EGR caliente.
    Si el objetivo no es alcanzable dentro de T_lim, devuelve el extremo.
    """
    z50 = (np.log(2) / cb.a) ** (1 / (cb.m + 1))
    soc_obj = mot.ca50_obj - cb.dur * z50

    def soc(Ti):
        s = soc_livengood_wu(mot.con(T_ivc=Ti), lam, p0, n, geo, amb, opc)
        return np.inf if s is None else s

    lo, hi = T_lim
    if soc(hi) > soc_obj:
        return hi
    if soc(lo) < soc_obj:
        return lo
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if soc(mid) > soc_obj else (lo, mid)
    return 0.5 * (lo + hi)


@dataclass
class Resultado:
    motor: str
    modo: str
    carga: float
    n: float
    lam: float
    th: np.ndarray
    V: np.ndarray
    p: np.ndarray
    T: np.ndarray
    Tb: np.ndarray
    hrr: np.ndarray
    T_ivc: float
    soc: Optional[float]
    ca50: Optional[float]
    fallo: bool
    imep_g: float
    pmep: float
    imep_n: float
    eta_i: float
    pmax: float
    dpmax: float
    Tmax: float
    nox: float


def ciclo(mot: Motor, carga: float, n: float, *, geo: Geometria = GEO,
          amb: Ambiente = AMB, opc: Opciones = OPC) -> Resultado:
    p_in, lam, cb, modo = estrategia_carga(mot, carga, amb)
    th = np.arange(-180.0, 180.0 + 1e-9, opc.dth)
    V, _ = volumen(geo, mot.rc, th)
    p0 = rend_vol(mot, n) * p_in              # presión en IVC
    if modo == "SI":                           # HCCI en modo chispa: sin residuales calientes
        mot = mot.con(T_ivc=mot.T_ivc_si)

    # --- Autoignición: control en lazo cerrado de CA50 actuando sobre T_IVC
    if cb.soc is None and mot.ca50_obj is not None:
        mot = mot.con(T_ivc=controlar_ca50(mot, cb, lam, p0, n, geo, amb, opc))

    m = p0 * V[0] / (amb.R * mot.T_ivc)       # masa atrapada
    mf = m / (lam * mot.AFR_st)
    Qtot = mot.eta_comb * mf * mot.LHV

    # --- Inicio de combustión: impuesto o por autoignición (Livengood-Wu)
    fallo = False
    if cb.soc is None:
        soc = soc_livengood_wu(mot, lam, p0, n, geo, amb, opc)
        if soc is None:                        # no autoinflama: ciclo arrastrado
            fallo, cb, Qtot = True, None, 0.0
        else:
            cb = replace(cb, soc=soc)

    p = _integrar(geo, mot, cb, Qtot, m, p0, V[0], n, th, opc)
    T = p * V / (m * amb.R)

    if cb is not None:
        xb, dxb = quemado(th, cb)
        ca50 = float(np.interp(0.5, xb, th))
    else:
        xb, dxb, ca50 = np.zeros_like(th), np.zeros_like(th), None

    W = np.trapezoid(p, V)                     # trabajo bruto de ciclo cerrado [J]
    pmep = amb.p_esc - p_in                    # bombeo simplificado
    imep_g = W / geo.Vd

    # --- T de quemados estimada y NOx (índice cualitativo, no ppm)
    # En difusión la llama arde a lambda local ~1 aunque la global sea pobre.
    lam_fl = 1.0 if mot.llama == "difusion" else lam
    Tu = mot.T_ivc * (p / p0) ** ((mot.g - 1) / mot.g)
    Tb = Tu + mot.eta_comb * mot.LHV / ((1 + lam_fl * mot.AFR_st) * 1450)  # sin disociación
    Tb = np.where(xb >= 0.01, Tb, np.nan)
    x_o2b = max(0.21 * (lam_fl - 1) / lam_fl, 0.01)       # suelo ~ O2 por disociación
    tasa = (lam_fl / lam) * xb * np.exp(-38370 / np.nan_to_num(Tb, nan=1.0)) * np.sqrt(x_o2b)
    nox = float(np.trapezoid(tasa, th) / (6 * n))

    return Resultado(
        motor=mot.nombre, modo="fallo" if fallo else modo, carga=carga, n=n, lam=lam,
        th=th, V=V, p=p, T=T, Tb=Tb, hrr=Qtot * dxb,
        T_ivc=mot.T_ivc, soc=None if cb is None else cb.soc, ca50=ca50, fallo=fallo,
        imep_g=imep_g, pmep=pmep, imep_n=imep_g - pmep,
        eta_i=(W - pmep * geo.Vd) / (mf * mot.LHV),
        pmax=float(p.max()), dpmax=float(np.diff(p).max() / opc.dth),
        Tmax=float(T.max()), nox=nox,
    )


def par_efectivo(r: Resultado, geo: Geometria = GEO):
    """Par [Nm] y potencia [CV] con FMEP de Chen-Flynn (coeficientes ORIENTATIVOS)."""
    cm = 2 * geo.S * r.n / 60
    fmep = (0.25 + 0.005 * r.pmax / 1e5 + 0.06 * cm + 0.0009 * cm**2) * 1e5
    par = (r.imep_n - fmep) * geo.Vd * geo.n_cil / (4 * pi)   # 4T
    return par, par * 2 * pi * r.n / 60 / 735.5

"""Parámetros de geometría, ambiente y de cada motor.

Todos los motores comparten geometría (2,0 L, 4 cilindros) para que la
comparativa aísle el efecto del ciclo de combustión.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import pi
from typing import Optional


@dataclass(frozen=True)
class Ambiente:
    p: float = 1.013e5          # [Pa]
    T: float = 298.0            # [K]
    R: float = 287.0            # [J/kgK]
    p_esc: float = 1.05 * 1.013e5  # contrapresión de escape [Pa]


@dataclass(frozen=True)
class Geometria:
    B: float = 0.086            # diámetro [m]
    S: float = 0.086            # carrera [m]
    L: float = 0.145            # longitud de biela [m]
    n_cil: int = 4

    @property
    def Ap(self) -> float:
        return pi * self.B**2 / 4

    @property
    def Vd(self) -> float:      # cilindrada unitaria [m3]
        return self.Ap * self.S


@dataclass(frozen=True)
class Combustion:
    """Ley de liberación de calor (Wiebe simple o doble).

    soc = None indica que el inicio lo calcula Livengood-Wu (autoignición).
    """
    tipo: str = "wiebe"         # "wiebe" | "doble"
    soc: Optional[float] = -20.0  # inicio de combustión [deg]
    dur: float = 50.0           # duración [deg]
    a: float = 5.0
    m: float = 2.0
    beta: float = 0.0           # fracción premezclada (solo "doble")
    dur2: float = 50.0          # duración fase de difusión
    m2: float = 0.9


@dataclass(frozen=True)
class Motor:
    nombre: str
    color: str
    rc: float                   # relación de compresión
    g: float                    # gamma de compresión de la carga fresca
    T_ivc: float                # temperatura en cierre de admisión [K]
    LHV: float                  # poder calorífico inferior [J/kg]
    AFR_st: float               # dosado estequiométrico
    eta_comb: float             # rendimiento de combustión
    ctrl: str                   # "cantidad" | "calidad" | "hcci"
    llama: str                  # "premezcla" | "difusion"
    lambda_pc: float            # lambda a plena carga
    comb: Combustion
    n_max: float                # régimen máximo [rpm]
    n_etav: float               # régimen de pico de rendimiento volumétrico [rpm]
    etav_max: float
    lambda_min: float = 1.0     # solo HCCI: límite de ringing
    comb_si: Optional[Combustion] = None  # solo HCCI: modo chispa a alta carga
    x_o2: float = 0.21          # fracción molar de O2 en la carga (dilución/EGR)
    T_ivc_si: float = 330.0     # solo HCCI: T_IVC en modo chispa (sin residuales calientes)
    ca50_obj: Optional[float] = None  # solo HCCI: CA50 objetivo [deg]; None = lazo abierto

    def con(self, **cambios) -> "Motor":
        """Copia con parámetros modificados (útil para barridos)."""
        return replace(self, **cambios)


MEP = Motor(
    nombre="MEP", color="#2a78d6",
    rc=10.5, g=1.32, T_ivc=320, LHV=43.0e6, AFR_st=14.7, eta_comb=0.97,
    ctrl="cantidad", llama="premezcla", lambda_pc=1.0,
    comb=Combustion("wiebe", soc=-22, dur=50, a=5, m=2),
    n_max=6500, n_etav=4500, etav_max=0.92,
)

MEC = Motor(
    nombre="MEC", color="#eb6834",
    rc=17.5, g=1.35, T_ivc=330, LHV=42.6e6, AFR_st=14.5, eta_comb=0.98,
    ctrl="calidad", llama="difusion", lambda_pc=1.35,   # límite de humos
    comb=Combustion("doble", soc=-6, dur=8, a=5, m=2, beta=0.15, dur2=55, m2=0.9),
    n_max=4500, n_etav=2200, etav_max=0.90,
)

HCCI = Motor(
    nombre="HCCI", color="#1baf7a",
    rc=15.0, g=1.36,
    T_ivc=440,                  # valor inicial; con ca50_obj lo fija el control
    LHV=43.0e6, AFR_st=14.7, eta_comb=0.95,
    ctrl="hcci", llama="premezcla", lambda_pc=1.0, lambda_min=2.0,
    comb=Combustion("wiebe", soc=None, dur=12, a=5, m=2),     # soc por Livengood-Wu
    comb_si=Combustion("wiebe", soc=-8, dur=55, a=5, m=2),    # avance limitado por picado
    n_max=6500, n_etav=4000, etav_max=0.88,
    x_o2=0.19,                  # dilución por residuales
    ca50_obj=6.0,               # control de fase: CA50 ~ 6 deg tras PMS
)

MOTORES = (MEP, MEC, HCCI)


@dataclass(frozen=True)
class Opciones:
    woschni: bool = True
    T_pared: float = 450.0      # [K]
    dth: float = 0.5            # paso de salida [deg]
    fin_lw: float = 30.0        # ángulo límite para declarar fallo de encendido [deg]

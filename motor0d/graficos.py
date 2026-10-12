"""Figuras. Paleta categórica validada (azul / naranja / aqua) para los tres
motores; escala secuencial de un solo tono para series ordenadas (rpm)."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
REJILLA = "#e4e3df"
SECUENCIAL = ("#9fd9c0", "#1baf7a", "#0b6b49")   # aqua claro -> oscuro

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE, "axes.edgecolor": REJILLA,
    "axes.labelcolor": TEXTO_2, "axes.titlecolor": TEXTO, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "xtick.color": TEXTO_2, "ytick.color": TEXTO_2, "text.color": TEXTO,
    "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 1.8, "legend.frameon": False, "font.size": 9.5,
    "figure.dpi": 110,
})


def _fig(nf, nc, titulo, tam):
    fig, ax = plt.subplots(nf, nc, figsize=tam, constrained_layout=True)
    fig.suptitle(titulo, x=0.01, ha="left", fontsize=12.5, fontweight="bold")
    return fig, np.atleast_1d(ax).ravel()


def ciclo_referencia(ref, motores, carga, n):
    fig, ax = _fig(2, 2, f"Ciclo de referencia · carga {carga:.0%}, {n:.0f} rpm", (11, 7.2))
    for r, mot in zip(ref, motores):
        lab = f"{mot.nombre}" + (f" (CA50 {r.ca50:+.0f}°)" if r.ca50 is not None else "")
        ax[0].loglog(r.V * 1e6, r.p / 1e5, color=mot.color, label=lab)
        ax[1].plot(r.th, r.p / 1e5, color=mot.color)
        ax[2].plot(r.th, r.hrr, color=mot.color)
        ax[3].plot(r.th, r.T, color=mot.color, label=f"{mot.nombre} media")
        ax[3].plot(r.th, r.Tb, color=mot.color, ls="--", lw=1.2)
    ax[0].set(title="Diagrama p–V (log–log)", xlabel="V [cm³]", ylabel="p [bar]")
    ax[0].legend()
    ax[1].set(title="Presión en cámara", xlabel="θ [°]", ylabel="p [bar]", xlim=(-60, 90))
    ax[2].set(title="Tasa de liberación de calor", xlabel="θ [°]",
              ylabel="dQ/dθ [J/°]", xlim=(-40, 90))
    ax[3].axhline(1800, color=TEXTO_2, ls=":", lw=1)
    ax[3].text(-38, 1830, "NO térmico relevante (~1800 K)", ha="left", va="bottom",
               color=TEXTO_2, fontsize=8.5)
    ax[3].set(title="T media (—) y T de quemados estimada (- -)", xlabel="θ [°]",
              ylabel="T [K]", xlim=(-40, 90))
    return fig


def barrido_carga(cargas, datos, motores, n, carga_hcci):
    fig, ax = _fig(2, 2, f"Barrido de carga · {n:.0f} rpm", (11, 7.2))
    claves = [("lam", "λ [-]", "Dosado relativo", 1.0, False),
              ("imep_n", "IMEP neta [bar]", "IMEP neta", 1e-5, False),
              ("eta_i", "η ind. [%]", "Rendimiento indicado", 100.0, False),
              ("nox", "Índice NOx [-] (MEP a plena carga = 1)", "Índice de NOx (cualitativo)",
               1.0, True)]
    for a, (k, ylab, tit, esc, log) in zip(ax, claves):
        for mot in motores:
            y = np.array([getattr(r, k) for r in datos[mot.nombre]]) * esc
            a.plot(np.array(cargas) * 100, y, color=mot.color, label=mot.nombre)
        a.axvline(carga_hcci * 100, color=TEXTO_2, ls="--", lw=1)
        a.set(title=tit, xlabel="Carga [%]", ylabel=ylab)
        if log:
            a.set_yscale("log")
    ax[0].text(carga_hcci * 100 + 1.5, ax[0].get_ylim()[1] * 0.92,
               "fin ventana HCCI →\nmodo chispa", color=TEXTO_2, fontsize=8.5, va="top")
    ax[0].legend(loc="upper right")
    return fig


def plena_carga(rpm, par, pot, motores):
    fig, ax = _fig(1, 2, "Plena carga (2,0 L atmosférico; HCCI en modo chispa, picado no modelado)",
                   (11, 4.0))
    for mot in motores:
        ax[0].plot(rpm, par[mot.nombre], color=mot.color, label=mot.nombre)
        ax[1].plot(rpm, pot[mot.nombre], color=mot.color, label=mot.nombre)
    ax[0].set(title="Par efectivo", xlabel="n [rpm]", ylabel="Par [Nm]")
    ax[1].set(title="Potencia efectiva", xlabel="n [rpm]", ylabel="Potencia [CV]")
    ax[1].legend(loc="upper left")
    return fig


def control_hcci(T_ivc, ca50_lazo_abierto, cargas, T_req, rpms, carga_ref, ca50_obj):
    fig, ax = _fig(1, 2, "Control de la autoignición HCCI (Livengood-Wu)", (11, 4.2))
    for col, n in zip(SECUENCIAL, rpms):
        ax[0].plot(T_ivc, ca50_lazo_abierto[n], color=col, label=f"{n:.0f} rpm")
        ax[1].plot(np.array(cargas) * 100, T_req[n], color=col, marker="o", ms=4,
                   label=f"{n:.0f} rpm")
    ax[0].axhline(ca50_obj, color=TEXTO_2, ls=":", lw=1)
    ax[0].text(T_ivc[-1], ca50_obj + 0.6, f"objetivo CA50 = {ca50_obj:+.0f}°",
               ha="right", va="bottom", color=TEXTO_2, fontsize=8.5)
    ax[0].set(title=f"Lazo abierto: fase vs T en IVC (carga {carga_ref:.0%})",
              xlabel="T en IVC [K]", ylabel="CA50 [° tras PMS]")
    ax[0].text(0.02, 0.04, "Hueco a la izquierda de cada curva = fallo de encendido",
               transform=ax[0].transAxes, color=TEXTO_2, fontsize=8.5)
    ax[0].legend(loc="upper right")
    ax[1].set(title=f"Lazo cerrado: T en IVC necesaria para CA50 = {ca50_obj:+.0f}°",
              xlabel="Carga [%]", ylabel="T en IVC [K]")
    ax[1].legend(loc="upper right")
    return fig

"""Ejecuta la comparativa completa y guarda figuras y tabla en figs/ y resultados/.

    python main.py            # todo
    python main.py --rapido   # menos puntos (para probar)
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from motor0d import HCCI, MOTORES, ciclo, par_efectivo
from motor0d import graficos
from motor0d.modelo import soc_livengood_wu, rend_vol, estrategia_carga, wiebe

RAIZ = Path(__file__).parent
FIGS, RES = RAIZ / "figs", RAIZ / "resultados"


def tabla_referencia(ref, carga, n):
    filas = [f"Punto de referencia: carga {carga:.0%}, {n:.0f} rpm\n",
             "| Motor | Modo | λ | T IVC [K] | CA50 [°] | IMEP neta [bar] | η ind. [%] "
             "| p máx [bar] | dp/dθ máx [bar/°] | T máx [K] | NOx (rel.) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    nox_mep = ref[0].nox
    for r in ref:
        ca50 = f"{r.ca50:+.1f}" if r.ca50 is not None else "–"
        filas.append(f"| {r.motor} | {r.modo} | {r.lam:.2f} | {r.T_ivc:.0f} | {ca50} | "
                     f"{r.imep_n/1e5:.2f} | {r.eta_i*100:.1f} | {r.pmax/1e5:.1f} | "
                     f"{r.dpmax/1e5:.2f} | {r.Tmax:.0f} | {r.nox/nox_mep:.3f} |")
    return "\n".join(filas)


def main(rapido: bool = False):
    FIGS.mkdir(exist_ok=True)
    RES.mkdir(exist_ok=True)
    carga_ref, n_ref = 0.40, 2500
    paso = 0.10 if rapido else 0.05
    cargas = np.round(np.arange(0.15, 1.0 + 1e-9, paso), 3)
    rpm = np.arange(1000, 6500 + 1, 500 if rapido else 250)

    # 1. Ciclo de referencia
    ref = [ciclo(m, carga_ref, n_ref) for m in MOTORES]
    tabla = tabla_referencia(ref, carga_ref, n_ref)
    print(tabla)
    (RES / "tabla_referencia.md").write_text(tabla + "\n", encoding="utf-8")
    graficos.ciclo_referencia(ref, MOTORES, carga_ref, n_ref).savefig(
        FIGS / "ciclo_referencia.png", dpi=160)

    # 2. Barrido de carga
    datos = {m.nombre: [ciclo(m, c, n_ref) for c in cargas] for m in MOTORES}
    nox_ref = ciclo(MOTORES[0], 1.0, n_ref).nox
    for lista in datos.values():
        for r in lista:
            r.nox /= nox_ref
    graficos.barrido_carga(cargas, datos, MOTORES, n_ref, 1 / HCCI.lambda_min).savefig(
        FIGS / "barrido_carga.png", dpi=160)

    # 3. Plena carga
    par, pot = {}, {}
    for m in MOTORES:
        res = [par_efectivo(ciclo(m, 1.0, n)) if n <= m.n_max else (np.nan, np.nan)
               for n in rpm]
        par[m.nombre], pot[m.nombre] = map(np.array, zip(*res))
    graficos.plena_carga(rpm, par, pot, MOTORES).savefig(FIGS / "plena_carga.png", dpi=160)

    # 4. Control HCCI
    rpms = (1500, 2500, 4000)
    T_ivc = np.arange(400, 520 + 1e-9, 5 if rapido else 2.5)
    cb = HCCI.comb
    z50 = (np.log(2) / cb.a) ** (1 / (cb.m + 1))
    p_in, lam, _, _ = estrategia_carga(HCCI, carga_ref)
    ca50_la = {}
    for n in rpms:
        p0 = rend_vol(HCCI, n) * p_in
        socs = [soc_livengood_wu(HCCI.con(T_ivc=T), lam, p0, n) for T in T_ivc]
        ca50_la[n] = np.array([np.nan if s is None else s + cb.dur * z50 for s in socs])
    cargas_h = [c for c in cargas if c <= 1 / HCCI.lambda_min + 1e-9]
    T_req = {n: [ciclo(HCCI, c, n).T_ivc for c in cargas_h] for n in rpms}
    graficos.control_hcci(T_ivc, ca50_la, cargas_h, T_req, rpms, carga_ref,
                          HCCI.ca50_obj).savefig(FIGS / "control_hcci.png", dpi=160)
    print(f"\nFiguras en {FIGS}/ y tabla en {RES}/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rapido", action="store_true")
    main(ap.parse_args().rapido)

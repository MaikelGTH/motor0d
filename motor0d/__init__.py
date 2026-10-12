"""motor0d: modelo 0D de ciclo cerrado para comparar MEP, MEC y HCCI."""
from .config import HCCI, MEC, MEP, MOTORES, Ambiente, Combustion, Geometria, Motor, Opciones
from .modelo import ciclo, integral_lw, par_efectivo, tau_ign, volumen

__all__ = [
    "MEP", "MEC", "HCCI", "MOTORES", "Ambiente", "Combustion", "Geometria", "Motor",
    "Opciones", "ciclo", "par_efectivo", "volumen", "tau_ign", "integral_lw",
]

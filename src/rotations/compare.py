"""comparar_rotaciones: compare a farmer's rotation with alternatives built from local data.

    from src.rotations.compare import comparar_rotaciones
    out = comparar_rotaciones("Celaya", "maíz", estado="Guanajuato", prioridades=["agua", "suelo"])

The result is a JSON-serializable dict; every number is computed by code (SIAP, NASA POWER, FAO-56, IPCC
coefficients), so a language model only has to phrase it.
"""

import json

from . import candidates, cards, catalog, places, scoring
from .indicators import RESIDUE, evaluate

DISCLAIMER = ("Esta comparación usa datos públicos (SIAP, NASA) y supuestos de literatura. Sirve para explorar "
              "opciones, no reemplaza tu experiencia ni la de un técnico o extensionista de tu zona.")


def comparar_rotaciones(lugar, rotacion_actual, estado=None, agua="temporal", prioridades=(), residuo="dejar",
                        tiene_animales=False, mes_siembra=None, pendiente="ligera", propuestas=(), n_alternativas=3):
    """Compare `rotacion_actual` with up to `n_alternativas` alternatives (plus any `propuestas`).

    lugar: municipality or SIAP district name; estado: state name to disambiguate.
    rotacion_actual / propuestas: text like "maíz - frijol" or "maíz/garbanzo", or lists of {"pv":..., "oi":...}.
    agua: "temporal" or "riego". prioridades: subset of scoring.PRIORITIES.
    residuo: what happens to stover, one of indicators.RESIDUE. pendiente: "plana", "ligera" or "fuerte".
    """
    if agua not in ("temporal", "riego"):
        raise ValueError("agua debe ser 'temporal' o 'riego'")
    if residuo not in RESIDUE:
        raise ValueError(f"residuo debe ser uno de {sorted(RESIDUE)}")
    prioridades = [p for p in prioridades if p in scoring.PRIORITIES]
    place = places.place(lugar, estado, water=agua, sowing_month=mes_siembra)
    current = candidates.assign_cycles(place, candidates.parse_rotation(rotacion_actual))

    options = [("actual", current)]
    options += [("propuesta", candidates.assign_cycles(place, candidates.parse_rotation(p))) for p in propuestas]
    generated = candidates.generate(place, current, has_animals=tiene_animales)

    evaluated = []
    for template, rotation in options + generated:
        e = evaluate(place, rotation, residuo)
        score = scoring.scores(e["values"], agua, pendiente)
        evaluated.append({"template": template, "rotation": rotation, "evaluation": e, "score": score,
                          "weighted": scoring.weighted(score, prioridades)})

    baseline = evaluated[0]
    fixed = [x for x in evaluated if x["template"] in ("actual", "propuesta")]
    pool = sorted((x for x in evaluated if x["template"] not in ("actual", "propuesta")
                   and x["weighted"] is not None and not x["evaluation"]["gaps"]),
                  key=lambda x: -x["weighted"])
    chosen, used, shown = [], set(), {c for y in current for c in y.values()}
    for strict in (True, False):                    # best per template first, so the options differ in kind,
        for x in pool:                              # and first those that bring a crop not shown yet
            new = {c for y in x["rotation"] for c in y.values()} - shown
            if x in chosen or x["template"] in used or len(chosen) >= n_alternativas or (strict and not new):
                continue
            chosen.append(x)
            used.add(x["template"])
            shown |= new
    for x in pool:
        if len(chosen) >= n_alternativas:
            break
        if x not in chosen:
            chosen.append(x)

    rotations = []
    for x in fixed + chosen:
        e = x["evaluation"]
        diff = None if x is baseline else scoring.paired_difference(e["income_by_year"], baseline["evaluation"]["income_by_year"])
        rotations.append({
            "id": x["template"] if x["template"] != "propuesta" else f"propuesta_{len(rotations)}",
            "nombre": f"{cards.TEMPLATE_NAMES[x['template']]}: {' – '.join(catalog.name(c) for c in cards.crop_names(x['rotation']))}",
            "secuencia": candidates.describe(x["rotation"]),
            "rotacion": x["rotation"],
            "puntaje_prioridades": None if x["weighted"] is None else round(x["weighted"]),
            "indicadores": cards.indicator_rows(e, x["score"], agua),
            "vs_actual_ingreso": diff,
            "tarjeta": cards.card(place, x["template"], x["rotation"], e, baseline, diff, residuo),
        })

    return {
        "lugar": {"municipio": place.municipality, "distrito": place.ddr_name, "estado": place.state, "agua": agua,
                  "notas": place.notes},
        "tu_lugar": cards.place_summary(place, baseline["evaluation"]),
        "prioridades": [scoring.PRIORITY_LABELS[p] for p in prioridades],
        "rotaciones": rotations,
        "cultivos_de_nicho": {
            "nota": ("Se siembran poco en tu distrito, así que no se proponen solos; puedes pedir compararlos. Su "
                     "rendimiento viene de las pocas parcelas donde se dan y su mercado es chico."),
            "cultivos": candidates.niche_crops(place, current)},
        "no_evaluadas": [{"secuencia": candidates.describe(x["rotation"]), "motivo": "; ".join(x["evaluation"]["gaps"])}
                         for x in evaluated if x["evaluation"]["gaps"] and x["template"] not in ("actual", "propuesta")],
        "como_leer": ("Cada indicador tiene un puntaje de 0 a 100 en una escala fija (100 = mejor) y un nivel de "
                      "evidencia: alta = datos observados en tu distrito; media = modelo o datos del estado; "
                      "baja = supuestos de literatura; regla = criterio agronómico general."),
        "vacios_generales": cards.GENERAL_GAPS,
        "aviso": DISCLAIMER,
    }


def to_json(result):
    return json.dumps(result, ensure_ascii=False, indent=1, default=float)

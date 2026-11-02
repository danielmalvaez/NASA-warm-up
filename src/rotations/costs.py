"""Production costs per hectare: the farmer's own figure first, then a sourced reference table.

Open cost data for Mexico are scarce. FIRA's Agrocostos system estimates costs by crop, state and cycle, but
only some summaries are public; the reference table (tables/costs.csv) holds the ones we could source, all
irrigated autumn-winter crops in Sinaloa. Every other crop needs the farmer's figure, and without it the
tool reports break-even costs (the most a hectare can cost before it loses money) instead of profit.
No cost is ever estimated or borrowed from another state.
"""

from functools import lru_cache

import numpy as np
import pandas as pd

from . import catalog


@lru_cache(maxsize=1)
def reference():
    return pd.read_csv(catalog.DATA / "costs.csv")


def cost_for(place, crop, cycle):
    """{'valor', 'fuente', 'evidencia', ...} for one season, or None when no cost is known."""
    if crop in place.costs:
        return {"valor": float(place.costs[crop]), "fuente": "tu dato", "evidencia": "alta", "url": None,
                "temporada": None}
    t = reference()
    hit = t[(t["crop"] == crop) & (t["cycle"] == cycle) & (t["water"] == place.water)
            & (t["state"].map(catalog.plain) == catalog.plain(place.state))]
    if hit.empty:
        return None
    row = hit.iloc[0]
    return {"valor": float(row.cost_mxn_ha), "fuente": row.source, "evidencia": row.evidencia, "url": row.url,
            "temporada": row.season, "nota": row.nota}


def own_yield_factor(place, crop, per_sown):
    """Ratio of the farmer's normal-year yield to the district's median production per sown ha (0.2-5)."""
    if crop not in place.own_yield:
        return None
    median = float(per_sown[per_sown.index > per_sown.index.max() - 10].median())
    if not np.isfinite(median) or median <= 0:
        return None
    return float(np.clip(place.own_yield[crop] / median, 0.2, 5.0))

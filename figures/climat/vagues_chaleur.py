"""Détection des vagues de chaleur selon Météo-France (rapport TRACC, partie 2, encart C).

Sur une série journalière de Tmoy = (Tn + Tx)/2, seuils pris sur la période de référence : S1 = Q99,5,
S2 = Q97,5, S3 = Q95. Un épisode démarre sur un jour au-dessus de S1 et s'étend avant et après tant que
Tmoy ne passe pas sous S3 et ne reste pas plus de deux jours consécutifs sous S2 ; les jours de bord sous
S2 sont retirés. Épisodes d'au moins 3 jours.
"""
import numpy as np
import pandas as pd


def _etend(t, i, pas, s2, s3):
    j, sous = i, 0
    while 0 <= j + pas < len(t):
        v = t[j + pas]
        if v < s3:
            break
        sous = sous + 1 if v < s2 else 0
        if sous > 2:
            break
        j += pas
    while t[j] < s2:  # bord sous S2 retiré
        j -= pas
    return j


def episodes(serie, ref=(1976, 2005)):
    """Liste de (début, fin) en dates, et seuils (S1, S2, S3)."""
    r = serie.loc[str(ref[0]):str(ref[1])]
    s1, s2, s3 = r.quantile([0.995, 0.975, 0.95])
    t = serie.to_numpy()
    out, i = [], 0
    while i < len(t):
        if t[i] > s1:
            a, b = _etend(t, i, -1, s2, s3), _etend(t, i, 1, s2, s3)
            if out and a <= out[-1][1] + 1:
                out[-1] = (out[-1][0], max(b, out[-1][1]))
            else:
                out.append((a, b))
            i = b + 1
        else:
            i += 1
    out = [(a, b) for a, b in out if b - a + 1 >= 3]
    return [(serie.index[a], serie.index[b]) for a, b in out], (s1, s2, s3)


def jours_par_an(serie, ref=(1976, 2005)):
    ev, seuils = episodes(serie, ref)
    jours = pd.Series(0, index=range(serie.index.year.min(), serie.index.year.max() + 1))
    for a, b in ev:
        for d in pd.date_range(a, b):
            jours[d.year] += 1
    return jours, ev, seuils

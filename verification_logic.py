import re
from datetime import date, timedelta
from pathlib import Path

try:
    from PIL import Image
    import pytesseract
    OCR_DISPONIBLE = True
except ImportError:
    OCR_DISPONIBLE = False


# ── Jours fériés belges ─────────────────────────────────────────────────────

def paques(annee: int) -> date:
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois, jour = divmod(h + l - 7 * m + 114, 31)
    return date(annee, mois, jour + 1)


def jours_feries_belgique(annee: int) -> dict:
    p = paques(annee)
    return {
        date(annee, 1, 1):   "Jour de l'An",
        p + timedelta(1):    "Lundi de Pâques",
        date(annee, 5, 1):   "Fête du Travail",
        p + timedelta(39):   "Ascension",
        p + timedelta(50):   "Lundi de Pentecôte",
        date(annee, 7, 21):  "Fête Nationale",
        date(annee, 8, 15):  "Assomption",
        date(annee, 11, 1):  "Toussaint",
        date(annee, 11, 11): "Armistice",
        date(annee, 12, 25): "Noël",
    }


def feries_du_mois(mois: int, annee: int) -> dict:
    return {d: n for d, n in jours_feries_belgique(annee).items() if d.month == mois}


def ponts_rc(mois: int, annee: int) -> list:
    feries = jours_feries_belgique(annee)
    ponts = []
    for f_date, f_nom in feries.items():
        if f_date.weekday() == 1:
            pont = f_date - timedelta(1)
            if pont.month == mois:
                ponts.append((pont, f"Pont — {f_nom} le mardi {f_date.strftime('%d/%m')}"))
        elif f_date.weekday() == 3:
            pont = f_date + timedelta(1)
            if pont.month == mois:
                ponts.append((pont, f"Pont — {f_nom} le jeudi {f_date.strftime('%d/%m')}"))
    return sorted(ponts)


def occurrences_jour_semaine(mois: int, annee: int, weekday: int) -> list:
    jours = []
    d = date(annee, mois, 1)
    while d.month == mois:
        if d.weekday() == weekday:
            jours.append(d)
        d += timedelta(1)
    return jours


def jours_ouvrables_pool(mois: int, annee: int, regime: str,
                          jour_ct: int, nb_ct_fiche: int) -> tuple:
    feries   = set(jours_feries_belgique(annee).keys())
    rc_dates = {d for d, _ in ponts_rc(mois, annee)}
    jours_off = feries | rc_dates

    if regime == "plein":
        jours = [date(annee, mois, 1) + timedelta(i)
                 for i in range(31)
                 if (d := date(annee, mois, 1) + timedelta(i)).month == mois
                 and d.weekday() <= 4 and d not in jours_off]
        # rebuild properly
        jours = []
        d = date(annee, mois, 1)
        while d.month == mois:
            if d.weekday() <= 4 and d not in jours_off:
                jours.append(d)
            d += timedelta(1)
        return len(jours), jours

    if regime == "4_5":
        ct_dates = set(occurrences_jour_semaine(mois, annee, jour_ct))
    else:
        toutes = occurrences_jour_semaine(mois, annee, jour_ct)
        ct_dates = set(toutes[:nb_ct_fiche])

    jours_off_ct = jours_off | ct_dates
    jours = []
    d = date(annee, mois, 1)
    while d.month == mois:
        if d.weekday() <= 4 and d not in jours_off_ct:
            jours.append(d)
        d += timedelta(1)
    return len(jours), jours


def jours_semaine_total(mois: int, annee: int) -> int:
    count = 0
    d = date(annee, mois, 1)
    while d.month == mois:
        if d.weekday() <= 4:
            count += 1
        d += timedelta(1)
    return count


# ── Lecture fiche ───────────────────────────────────────────────────────────

def _ocr_image(contenu: bytes) -> str:
    import io
    img = Image.open(io.BytesIO(contenu)).convert("L")
    return pytesseract.image_to_string(img, lang="fra")


def extraire_texte(fichiers: list) -> str:
    """
    fichiers : liste de dicts {"nom": str, "contenu": bytes}
    """
    import io
    import pdfplumber
    textes = []
    for f in fichiers:
        ext = Path(f["nom"]).suffix.lower()
        if ext == ".pdf":
            with pdfplumber.open(io.BytesIO(f["contenu"])) as pdf:
                t = "\n".join(p.extract_text() or "" for p in pdf.pages)
            textes.append(t)
        else:
            if not OCR_DISPONIBLE:
                raise RuntimeError("OCR non disponible sur ce serveur.")
            textes.append(_ocr_image(f["contenu"]))
    return "\n".join(textes)


def parser_fiche(texte: str) -> dict:
    data: dict = {
        "periode_debut": None, "periode_fin": None,
        "mois": None, "annee": None,
        "salaire_horaire": None,
        "texte_brut": texte,
        "1010_jours": 0, "1010_heures": 0.0, "1010_montant": 0.0,
        "1280_jours": 0, "1280_montant": 0.0,
        "1350_jours": 0, "1350_montant": 0.0,
        "0570_jours": 0, "0991_jours": 0,
        "1990_montant": 0.0,
        "1712_montant": 0.0, "1712_nb_fiche": None,
        "3101_montant": 0.0, "3102_montant": 0.0,
        "1561_montant": 0.0, "1561_heures": 0.0,
        "9570_jours": 0,
        "0720_jours": 0,
        "0420_jours": 0,
        "jours_sans_salaire": [],
    }

    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*au\s*(\d{2}/\d{2}/\d{4})", texte)
    if m:
        data["periode_debut"] = m.group(1)
        data["periode_fin"]   = m.group(2)
        _, mo, an = m.group(1).split("/")
        data["mois"]  = int(mo)
        data["annee"] = int(an)

    m2 = re.search(r"[Ss]alaire\s*horaire\s*de\s*base\s*[:\s€\xa0]*([0-9]+[.,][0-9]+)", texte)
    if m2:
        data["salaire_horaire"] = float(m2.group(1).replace(",", "."))

    def _code(code, avec_jours=True):
        if avec_jours:
            mx = re.search(rf"{code}\s+\S+\s+(\d+)\s+([\d,]+)\s+([\d.,]+)", texte)
            if mx:
                return int(mx.group(1)), float(mx.group(2).replace(",", ".")), \
                       float(mx.group(3).replace(".", "").replace(",", "."))
        mx2 = re.search(rf"{code}\s+\S+\s+([\d.,]+)\s*$", texte, re.MULTILINE)
        if mx2:
            return 0, 0.0, float(mx2.group(1).replace(".", "").replace(",", "."))
        return 0, 0.0, 0.0

    j, h, mn = _code("1010")
    data["1010_jours"], data["1010_heures"], data["1010_montant"] = j, h, mn

    j, _, mn = _code("1280")
    data["1280_jours"], data["1280_montant"] = j, mn

    j, _, mn = _code("1350")
    data["1350_jours"], data["1350_montant"] = j, mn

    mx = re.search(r"0570\s+\S+\s+(\d+)\s+([\d,]+)", texte)
    if mx:
        data["0570_jours"] = int(mx.group(1))

    # Code 0720/9720 — chômage temporaire / intempérie
    # Résumé page 1 (code 0720)
    mx = re.search(r"0720\s+\S+\s+(\d+)\s+([\d,]+)", texte)
    if mx:
        data["0720_jours"] = int(mx.group(1))
    else:
        # Calendrier : code 9720 (comme 9991=crédit-temps, 9570=grève)
        data["0720_jours"] = len(re.findall(r"[lmjv]\s*:\s*\d{2}\s+9720", texte))

    # Code 0420/9420 — repos compensatoire
    mx = re.search(r"0420\s+\S+\s+(\d+)\s+([\d,]+)", texte)
    if mx:
        data["0420_jours"] = int(mx.group(1))
    else:
        data["0420_jours"] = len(re.findall(r"[lmjv]\s*:\s*\d{2}\s+9420", texte))

    # Jours sans salaire — ligne calendrier weekday sans code 4 chiffres
    # Robuste : accepte n'importe quel nombre d'espaces autour du ":"
    jours_sans = []
    for ligne in texte.split("\n"):
        ligne_s = ligne.strip()
        # Matcher : lettre + espaces + : + espaces + 2 chiffres + éventuels espaces + RIEN d'autre
        m_cal = re.match(r"^([lmjv])\s*:\s*(\d{2})\s*$", ligne_s)
        if m_cal:
            lettre = m_cal.group(1)
            num    = m_cal.group(2)
            noms   = {"l": "Lundi", "m": "Mardi/Mercredi", "j": "Jeudi", "v": "Vendredi"}
            jours_sans.append(f"{noms.get(lettre, lettre)} {num}")
            continue
        # Format alternatif : lettre + : + chiffres + suite SANS code 4 chiffres
        m_cal2 = re.match(r"^([lmjv])\s*:\s*(\d{2})\s+(.+)$", ligne_s)
        if m_cal2:
            reste = m_cal2.group(3)
            # Si aucun code 4 chiffres dans le reste → jour sans salaire
            if not re.search(r"\b\d{4}\b", reste):
                lettre = m_cal2.group(1)
                num    = m_cal2.group(2)
                noms   = {"l": "Lundi", "m": "Mardi/Mercredi", "j": "Jeudi", "v": "Vendredi"}
                jours_sans.append(f"{noms.get(lettre, lettre)} {num}")
    data["jours_sans_salaire"] = jours_sans

    mx = re.search(r"0991\s+\S+\s+(\d+)\s+([\d,]+)", texte)
    if mx:
        data["0991_jours"] = int(mx.group(1))

    _, _, mn = _code("1990", avec_jours=False)
    data["1990_montant"] = mn

    _, _, mn = _code("1712", avec_jours=False)
    data["1712_montant"] = mn

    mx = re.search(r"nbrdeprimestravailpenible\s+([\d,]+)", texte)
    if mx:
        data["1712_nb_fiche"] = int(float(mx.group(1).replace(",", ".")))

    _, _, mn = _code("3101", avec_jours=False)
    data["3101_montant"] = mn

    _, _, mn = _code("3102", avec_jours=False)
    data["3102_montant"] = mn

    mx = re.search(r"1561\s+\S+\s+(?:\d+\s+)?([\d,]+)\s+([\d.,]+)\s*$", texte, re.MULTILINE)
    if mx:
        data["1561_heures"]  = float(mx.group(1).replace(",", "."))
        data["1561_montant"] = float(mx.group(2).replace(".", "").replace(",", "."))

    data["9570_jours"] = len(re.findall(r"9570", texte))

    return data


# ── Vérifications ───────────────────────────────────────────────────────────

NOM_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

TAUX_PRIME_CHEF = 20.31
TAUX_PENIBLE    = 28.44
MONTANT_CARWASH = 15.00
TAUX_INTERNET   = 1.00


def verifier(data: dict, config: dict) -> list:
    """
    Retourne une liste de résultats :
    [{"titre": str, "lignes": [{"texte": str, "statut": "ok"|"erreur"|"info"|""}]}]
    """
    regime      = config["regime"]
    jour_ct     = config["jour_ct"]
    nb_ct_fiche = data.get("0991_jours", 0)
    mois        = data["mois"]
    annee       = data["annee"]
    taux        = data.get("salaire_horaire") or 0.0

    sections = []

    def section(titre, lignes):
        sections.append({"titre": titre, "lignes": lignes})

    def ok(txt):    return {"texte": txt, "statut": "ok"}
    def err(txt):   return {"texte": txt, "statut": "erreur"}
    def info(txt):  return {"texte": txt, "statut": "info"}
    def neutre(txt):return {"texte": txt, "statut": ""}

    # ── Infos générales ──
    lignes = [
        info(f"Période : {data['periode_debut']} → {data['periode_fin']}"),
        info(f"Mois : {mois:02d}/{annee}"),
        info(f"Salaire horaire : €{taux:.4f}"),
        info(f"Régime : {_desc_regime(regime, jour_ct, nb_ct_fiche)}"),
    ]
    section("Informations", lignes)

    # ── Jours fériés ──
    feries = feries_du_mois(mois, annee)
    ponts  = ponts_rc(mois, annee)
    lignes = []
    for d, nom in sorted(feries.items()):
        lignes.append(neutre(f"{NOM_JOURS[d.weekday()]} {d.strftime('%d/%m/%Y')} — {nom}"))
    if ponts:
        for d, desc in ponts:
            lignes.append(neutre(f"{NOM_JOURS[d.weekday()]} {d.strftime('%d/%m/%Y')} — {desc}"))

    feries_eff = {d: n for d, n in feries.items()
                  if not (regime != "plein" and d.weekday() == jour_ct)}
    nb_attendu = len(feries_eff)
    nb_fiche   = data["1350_jours"]
    lignes.append(neutre(""))
    lignes.append(neutre(f"Fériés attendus ce mois : {nb_attendu}"))
    lignes.append(neutre(f"Fériés sur la fiche (1350) : {nb_fiche}"))
    if nb_fiche == nb_attendu:
        lignes.append(ok("✔  Nombre de jours fériés correct"))
    else:
        diff = nb_attendu - nb_fiche
        lignes.append(err(f"✘  Écart : {abs(diff)} jour(s) {'manquant(s)' if diff>0 else 'en trop'}"))
    section("Jours fériés belges", lignes)

    # ── Jours travaillés ──
    nb_pool, _ = jours_ouvrables_pool(mois, annee, regime, jour_ct, nb_ct_fiche)
    j1010 = data["1010_jours"]
    j1280 = data["1280_jours"]
    j0570 = data["0570_jours"]
    j0720 = data.get("0720_jours", 0)
    j0420 = data.get("0420_jours", 0)
    total  = j1010 + j1280 + j0570 + j0720 + j0420
    lignes = [
        neutre(f"Jours crédit-temps (0991) : {nb_ct_fiche} j") if regime != "plein" else neutre(""),
        neutre(f"Pool à justifier : {nb_pool} j"),
        neutre(""),
        neutre(f"Travaillé            (1010) : {j1010} j"),
        neutre(f"Congés sectoriels    (1280) : {j1280} j"),
        neutre(f"Grève                (0570) : {j0570} j"),
    ]
    if j0720:
        lignes.append(neutre(f"Chômage temporaire   (0720) : {j0720} j"))
    if j0420:
        lignes.append(neutre(f"Repos compensatoire  (0420) : {j0420} j"))
    lignes += [
        neutre(""),
        neutre(f"Total justifié              : {total} j"),
        neutre(f"Pool attendu                : {nb_pool} j"),
    ]
    lignes = [l for l in lignes if l["texte"] is not None]
    if total == nb_pool:
        lignes.append(ok("✔  Nombre de jours travaillés correct"))
    else:
        diff = nb_pool - total
        lignes.append(err(f"✘  Écart : {abs(diff)} jour(s) {'non justifié(s)' if diff>0 else 'en trop'}"))
    section("Jours travaillés", lignes)

    # ── Jours sans salaire ──
    jours_sans = data.get("jours_sans_salaire", [])
    if jours_sans:
        lignes = [err(f"✘  Aucun salaire enregistré — {j}") for j in jours_sans]
        lignes.append(neutre("→ Vérifiez ces journées avec votre employeur"))
        section("⚠  Jours sans salaire détectés", lignes)

    # ── Paie jours travaillés ──
    h      = data["1010_heures"]
    mn_fiche = data["1010_montant"]
    mn_calc  = round(h * taux, 2)
    lignes = [
        neutre(f"Heures travaillées : {h:.2f} h"),
        neutre(f"Taux horaire       : €{taux:.4f}"),
        neutre(f"Montant calculé    : €{mn_calc:.2f}"),
        neutre(f"Montant fiche      : €{mn_fiche:.2f}"),
    ]
    if abs(mn_fiche - mn_calc) <= 0.15:
        lignes.append(ok("✔  Montant des heures travaillées correct"))
    else:
        lignes.append(err(f"✘  Écart de €{abs(mn_fiche - mn_calc):.2f}"))
    section("Paie jours travaillés (1010)", lignes)

    # ── Prime chef d'équipe ──
    fonction = config["fonction"]
    if fonction in ("brigadier", "chef_equipe"):
        if fonction == "brigadier":
            nb_j = j1010
            desc = f"Brigadier : {nb_j} j travaillés"
        else:
            nb_j = config.get("jours_brigadier", 0)
            desc = f"Chef d'équipe : {nb_j} j en fonction brigadier"
        mn_att = round(nb_j * TAUX_PRIME_CHEF, 2)
        mn_f   = data["1990_montant"]
        lignes = [
            neutre(desc),
            neutre(f"Taux : €{TAUX_PRIME_CHEF:.2f}/j"),
            neutre(f"Montant attendu      : €{mn_att:.2f}"),
            neutre(f"Montant fiche (1990) : €{mn_f:.2f}"),
        ]
        if abs(mn_f - mn_att) <= 0.15:
            lignes.append(ok("✔  Prime chef d'équipe correcte"))
        else:
            lignes.append(err(f"✘  Écart de €{abs(mn_f - mn_att):.2f}"))
        section("Prime chef d'équipe (1990)", lignes)

    # ── Prime pénible ──
    if config.get("penible"):
        nb_p   = config.get("nb_penible", 0)
        mn_att = round(nb_p * TAUX_PENIBLE, 2)
        mn_f   = data["1712_montant"]
        nb_p2  = data.get("1712_nb_fiche")
        lignes = [neutre(f"Nombre de primes saisi : {nb_p}")]
        if nb_p2 is not None:
            lignes.append(neutre(f"Nombre page 2 fiche    : {nb_p2}"))
            if nb_p != nb_p2:
                lignes.append(err(f"✘  Écart sur le nombre : {nb_p} ≠ {nb_p2}"))
            else:
                lignes.append(ok("✔  Nombre cohérent avec la fiche"))
        lignes += [
            neutre(f"Montant attendu       : {nb_p} × €{TAUX_PENIBLE:.2f} = €{mn_att:.2f}"),
            neutre(f"Montant fiche (1712)  : €{mn_f:.2f}"),
        ]
        if abs(mn_f - mn_att) <= 0.05:
            lignes.append(ok("✔  Prime travail pénible correcte"))
        else:
            lignes.append(err(f"✘  Écart de €{abs(mn_f - mn_att):.2f}"))
        section("Prime travail pénible (1712)", lignes)

    # ── Car-wash ──
    mn_f = data["3101_montant"]
    lignes = [
        neutre(f"Montant attendu      : €{MONTANT_CARWASH:.2f}"),
        neutre(f"Montant fiche (3101) : €{mn_f:.2f}"),
    ]
    if abs(mn_f - MONTANT_CARWASH) <= 0.01:
        lignes.append(ok("✔  Prime car-wash correcte"))
    elif mn_f == 0:
        lignes.append(err("✘  Prime car-wash absente de la fiche"))
    else:
        lignes.append(err(f"✘  Montant incorrect (écart €{abs(mn_f - MONTANT_CARWASH):.2f})"))
    section("Prime car-wash (3101)", lignes)

    # ── Heures supplémentaires ──
    if config.get("heures_sup"):
        h_sam   = config.get("h_sam", 0.0)
        h_dim   = config.get("h_dim", 0.0)
        autres  = config.get("autres_sup", [])
        mn_sam  = round(h_sam * taux * 1.5, 2)
        mn_dim  = round(h_dim * taux * 2.0, 2)
        h_aut   = sum(h for _, h in autres)
        mn_aut  = round(h_aut * taux * 1.5, 2)
        total_h = round(h_sam + h_dim + h_aut, 2)
        mn_att  = round(mn_sam + mn_dim + mn_aut, 2)
        mn_f    = data["1561_montant"]
        lignes  = [
            neutre(f"Samedi   : {h_sam:.2f}h × {taux:.4f} × 150% = €{mn_sam:.2f}"),
            neutre(f"Dimanche : {h_dim:.2f}h × {taux:.4f} × 200% = €{mn_dim:.2f}"),
        ]
        for d_txt, h in autres:
            lignes.append(neutre(f"{d_txt:8s} : {h:.2f}h × {taux:.4f} × 150% = €{round(h*taux*1.5,2):.2f}"))
        lignes += [
            neutre(f"Total heures : {total_h:.2f} h"),
            neutre(f"Montant attendu      : €{mn_att:.2f}"),
            neutre(f"Montant fiche (1561) : €{mn_f:.2f}"),
        ]
        if total_h == 0:
            lignes.append(neutre("Aucune heure supplémentaire saisie — vérification ignorée."))
        elif mn_f == 0:
            lignes.append(err("✘  Code 1561 absent alors que des heures sup sont déclarées"))
        elif abs(mn_f - mn_att) <= 0.05:
            lignes.append(ok("✔  Heures supplémentaires correctes"))
        else:
            lignes.append(err(f"✘  Écart de €{abs(mn_f - mn_att):.2f}"))
        section("Heures supplémentaires (1561)", lignes)

    # ── Prime internet ──
    total_sem     = jours_semaine_total(mois, annee)
    greve_nr      = data.get("9570_jours", 0)
    eligibles     = total_sem - greve_nr
    mn_att        = round(eligibles * TAUX_INTERNET, 2)
    mn_f          = data["3102_montant"]
    lignes = [
        neutre(f"Jours lun→ven        : {total_sem} j"),
        neutre(f"Grève non reconnue   : {greve_nr} j"),
        neutre(f"Jours éligibles      : {eligibles} j"),
        neutre(f"Montant attendu      : {eligibles} × €{TAUX_INTERNET:.2f} = €{mn_att:.2f}"),
        neutre(f"Montant fiche (3102) : €{mn_f:.2f}"),
    ]
    if abs(mn_f - mn_att) <= 0.05:
        lignes.append(ok("✔  Prime internet correcte"))
    else:
        lignes.append(err(f"✘  Écart de €{abs(mn_f - mn_att):.2f}"))
    section("Prime internet (3102)", lignes)

    return sections


def _desc_regime(regime, jour_ct, nb_ct):
    NOM = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    if regime == "plein":
        return "Temps plein (lun→ven)"
    elif regime == "4_5":
        return f"Crédit-temps 4/5 — {NOM[jour_ct]} off chaque semaine"
    else:
        return f"Crédit-temps 3j/3 semaines — {NOM[jour_ct]} ({nb_ct} j ce mois)"


def resume_erreurs(sections: list) -> list:
    return [l["texte"] for s in sections
            for l in s["lignes"] if l["statut"] == "erreur"]

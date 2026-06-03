import streamlit as st
from verification_logic import (
    extraire_texte, parser_fiche, verifier, resume_erreurs, NOM_JOURS
)

st.set_page_config(
    page_title="Vérification fiche de salaire",
    page_icon="📋",
    layout="centered",
)

# Suppression des données en mémoire dès la fin de session
import gc

# ── Mot de passe ─────────────────────────────────────────────────────────────

def verif_mdp():
    if st.session_state.get("auth"):
        return True
    st.title("📋 Vérification fiche de salaire")
    st.markdown("### Connexion requise")
    mdp = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter", use_container_width=True):
        if mdp == st.secrets.get("password", ""):
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    return False

if not verif_mdp():
    st.stop()

# ── Interface principale ──────────────────────────────────────────────────────

st.title("📋 Vérification fiche de salaire")
st.caption("Belgique — Carrières du Tournaisis")
st.info("🔒 Aucune donnée n'est conservée sur le serveur. Votre fiche est analysée en mémoire et immédiatement supprimée.", icon="🔒")

# ── Upload fichiers ──
st.header("1. Fiche de salaire")
fichiers = st.file_uploader(
    "Déposez votre PDF ou vos photos (plusieurs fichiers acceptés)",
    type=["pdf", "jpg", "jpeg", "png", "bmp", "tiff", "webp"],
    accept_multiple_files=True,
    help="Pour une fiche en 2 pages, ajoutez les 2 photos dans l'ordre."
)

# ── Configuration ──
st.header("2. Votre situation")

col1, col2 = st.columns(2)

with col1:
    regime = st.radio("Régime de travail", [
        "Crédit-temps 4/5",
        "Crédit-temps 3j/3 semaines",
        "Temps plein",
    ], index=0)
    regime_map = {
        "Crédit-temps 4/5":          "4_5",
        "Crédit-temps 3j/3 semaines": "3_3",
        "Temps plein":                "plein",
    }
    regime_code = regime_map[regime]

    if regime_code != "plein":
        jour_ct_nom = st.selectbox("Jour de crédit-temps",
                                   ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"],
                                   index=4)
        jour_ct = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"].index(jour_ct_nom)
    else:
        jour_ct = 4

with col2:
    fonction = st.selectbox("Fonction", ["Brigadier", "Chef d'équipe", "Chauffeur", "Pelliste"])
    fonction_code = {"Brigadier": "brigadier", "Chef d'équipe": "chef_equipe",
                     "Chauffeur": "chauffeur",  "Pelliste": "pelliste"}[fonction]

    jours_brig = 0
    if fonction_code == "chef_equipe":
        jours_brig = st.number_input("Jours en fonction brigadier", min_value=0, value=0, step=1)

# ── Options ──
st.header("3. Options")

col3, col4 = st.columns(2)

with col3:
    penible = st.checkbox("Primes travail pénible ?")
    nb_penible = 0
    if penible:
        nb_penible = st.number_input("Nombre de primes pénible", min_value=0, value=0, step=1)

with col4:
    heures_sup = st.checkbox("Heures supplémentaires ?")

autres_sup = []
if heures_sup:
    c1, c2 = st.columns(2)
    with c1:
        h_sam = st.number_input("Heures samedi (×150%)", min_value=0.0, value=0.0, step=0.25)
    with c2:
        h_dim = st.number_input("Heures dimanche (×200%)", min_value=0.0, value=0.0, step=0.25)

    st.markdown("**Autres heures sup (×150%) :**")
    nb_autres = st.number_input("Nombre d'entrées à ajouter", min_value=0, max_value=10,
                                 value=0, step=1, key="nb_autres")
    for i in range(int(nb_autres)):
        ca, cb = st.columns(2)
        with ca:
            d_txt = st.text_input(f"Date {i+1} (ex: 17/05)", key=f"date_sup_{i}")
        with cb:
            h_val = st.number_input(f"Heures {i+1}", min_value=0.0, value=0.0,
                                     step=0.25, key=f"h_sup_{i}")
        if h_val > 0:
            autres_sup.append((d_txt, h_val))
else:
    h_sam = h_dim = 0.0

# ── Analyse ──
st.divider()
if st.button("🔍 Analyser la fiche", use_container_width=True, type="primary"):
    if not fichiers:
        st.warning("Veuillez d'abord déposer votre fiche (PDF ou photo).")
        st.stop()

    with st.spinner("Lecture en cours..."):
        try:
            fichiers_data = [{"nom": f.name, "contenu": f.read()} for f in fichiers]
            texte = extraire_texte(fichiers_data)
            data  = parser_fiche(texte)
            # Suppression immédiate des données brutes de la mémoire
            del fichiers_data, texte
            gc.collect()
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")
            st.stop()

    if not data["mois"]:
        st.error("Impossible de détecter la période sur la fiche. Vérifiez la qualité du document.")
        st.stop()

    config = {
        "regime":        regime_code,
        "jour_ct":       jour_ct,
        "fonction":      fonction_code,
        "jours_brigadier": int(jours_brig),
        "penible":       penible,
        "nb_penible":    int(nb_penible),
        "heures_sup":    heures_sup,
        "h_sam":         h_sam,
        "h_dim":         h_dim,
        "autres_sup":    autres_sup,
    }

    sections = verifier(data, config)
    erreurs  = resume_erreurs(sections)

    # ── Résultats ──
    st.header("4. Résultats")

    for sec in sections:
        with st.expander(sec["titre"], expanded=True):
            for l in sec["lignes"]:
                if not l["texte"]:
                    continue
                if l["statut"] == "ok":
                    st.success(l["texte"])
                elif l["statut"] == "erreur":
                    st.error(l["texte"])
                elif l["statut"] == "info":
                    st.info(l["texte"])
                else:
                    st.write(l["texte"])

    # ── Récapitulatif ──
    st.divider()
    st.header("📊 Récapitulatif")
    if erreurs:
        st.error(f"**{len(erreurs)} anomalie(s) détectée(s) :**")
        for i, e in enumerate(erreurs, 1):
            st.error(f"{i}. {e}")
    else:
        st.success("✔  Aucune anomalie détectée — fiche correcte.")

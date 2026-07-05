"""
frontend_app.py
================
Frontend Streamlit della client application per l'ontologia "Cucina Toscana
e Territorio". Consuma le funzioni definite in backend_app.py (che a sua
volta interroga/aggiorna GraphDB tramite SPARQLWrapper).

Avvio:
    streamlit run frontend_app.py

L'interfaccia è organizzata in pagine (sidebar):
  - Esplora Piatti
  - Dettaglio Piatto
  - Esplora Ingredienti
  - Esplora Bevande
  - Menu e Territorio
  - Inserimento Dati (form di scrittura)
  - SPARQL Playground (query libere in sola lettura)
"""

import streamlit as st
import pandas as pd

import backend_app as be

st.set_page_config(page_title="Cucina Toscana - Client SPARQL", layout="wide")

st.title("🍝 Cucina Toscana e Territorio")
st.caption("Client GraphDB (SPARQLWrapper + Streamlit) per l'ontologia della cucina toscana")

PAGINE = [
    "Esplora Piatti",
    "Dettaglio Piatto",
    "Esplora Ingredienti",
    "Esplora Bevande",
    "Menu e Territorio",
    "Inserimento Dati",
    "SPARQL Playground",
]

pagina = st.sidebar.radio("Naviga", PAGINE)

with st.sidebar.expander("⚙️ Connessione GraphDB"):
    st.write("Query endpoint:", be.QUERY_ENDPOINT)
    st.write("Update endpoint:", be.UPDATE_ENDPOINT)
    st.info("Modifica gli endpoint direttamente in backend_app.py")


def _df(rows, cols=None):
    if not rows:
        st.info("Nessun risultato.")
        return None
    df = pd.DataFrame(rows)
    if cols:
        cols_present = [c for c in cols if c in df.columns]
        df = df[cols_present]
    st.dataframe(df, use_container_width=True)
    return df


def _safe(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"Errore durante l'interrogazione di GraphDB: {e}")
        return []


# --------------------------------------------------------------------------
# PAGINA: ESPLORA PIATTI
# --------------------------------------------------------------------------
if pagina == "Esplora Piatti":
    st.header("Esplora Piatti")

    col1, col2, col3 = st.columns(3)
    with col1:
        tipo = st.selectbox("Tipo", ["Tutti", "PiattoFinito", "PiattoComponibile"])
    with col2:
        portata = st.selectbox("Portata", ["Tutte"] + be.PORTATE)
    with col3:
        stagione = st.selectbox("Stagione", ["Tutte", "Primavera", "Estate", "Autunno", "Inverno"])

    tipo_f = None if tipo == "Tutti" else tipo
    portata_f = None if portata == "Tutte" else portata
    stagione_f = None if stagione == "Tutte" else stagione

    rows = _safe(be.get_piatti, portata=portata_f, stagione=stagione_f, tipo=tipo_f)
    _df(rows, cols=["piatto", "portata", "stagione", "colore"])


# --------------------------------------------------------------------------
# PAGINA: DETTAGLIO PIATTO
# --------------------------------------------------------------------------
elif pagina == "Dettaglio Piatto":
    st.header("Dettaglio Piatto")

    tutti_piatti = _safe(be.get_piatti)
    nomi = sorted({r["piatto"] for r in tutti_piatti}) if tutti_piatti else []

    scelta = st.selectbox("Seleziona un piatto", ["-"] + nomi)
    manuale = st.text_input("...oppure digita il nome esatto dell'individuo")

    piatto = manuale.strip() if manuale.strip() else (scelta if scelta != "-" else None)

    if piatto:
        dettagli = _safe(be.get_piatto_dettagli, piatto)
        st.subheader(f"🍽️ {piatto}")

        c1, c2 = st.columns(2)
        with c1:
            st.write("**Portata:**", ", ".join(dettagli.get("portata", [])) or "—")
            st.write("**Stagione:**", ", ".join(dettagli.get("stagione", [])) or "—")
            st.write("**Colore:**", ", ".join(dettagli.get("colore", [])) or "—")
            st.write("**Temperatura di servizio (°C):**", ", ".join(dettagli.get("temperatura", [])) or "—")
        with c2:
            st.write("**Menu di appartenenza:**")
            for m in dettagli.get("menu", []) or ["—"]:
                st.write("- ", m)

        st.write("**Ingredienti:**")
        ingr = dettagli.get("ingredienti", [])
        if ingr:
            st.write(", ".join(ingr))
        else:
            st.info("Nessun ingrediente registrato.")

        st.write("**Bevande abbinate:**")
        bev = dettagli.get("bevande_abbinate", [])
        if bev:
            st.write(", ".join(bev))
        else:
            st.info("Nessuna bevanda abbinata.")


# --------------------------------------------------------------------------
# PAGINA: ESPLORA INGREDIENTI
# --------------------------------------------------------------------------
elif pagina == "Esplora Ingredienti":
    st.header("Esplora Ingredienti")

    col1, col2 = st.columns(2)
    with col1:
        tipo = st.selectbox("Tipo", ["Tutti", "IngredienteSemplice", "IngredienteComposto"])
    with col2:
        stagione = st.selectbox("Stagione", ["Tutte", "Primavera", "Estate", "Autunno", "Inverno"])

    tipo_f = None if tipo == "Tutti" else tipo
    stagione_f = None if stagione == "Tutte" else stagione

    rows = _safe(be.get_ingredienti, tipo=tipo_f, stagione=stagione_f)
    df = _df(rows, cols=["ingrediente", "stagione", "tipicoDi"])

    st.divider()
    st.subheader("Composizione di un ingrediente composto")
    nomi = sorted({r["ingrediente"] for r in rows}) if rows else []
    scelto = st.selectbox("Ingrediente composto", ["-"] + nomi, key="ingr_composto")
    if scelto != "-":
        comp = _safe(be.get_composizione_ingrediente, scelto)
        _df(comp, cols=["componente"])


# --------------------------------------------------------------------------
# PAGINA: ESPLORA BEVANDE
# --------------------------------------------------------------------------
elif pagina == "Esplora Bevande":
    st.header("Esplora Bevande")

    col1, col2 = st.columns(2)
    with col1:
        sottoclasse = st.selectbox("Categoria", ["Tutte"] + be.CLASSI_BEVANDA[1:])
    with col2:
        solo_super = st.checkbox("Solo Superalcoliche (gradazione > 17°, Regola SWRL 1)")

    sotto_f = None if sottoclasse == "Tutte" else sottoclasse
    rows = _safe(be.get_bevande, sottoclasse=sotto_f, solo_superalcoliche=solo_super)
    _df(rows, cols=["bevanda", "tipologia", "gradazioneAlcolica"])

    st.divider()
    st.subheader("Alimenti abbinati a una bevanda")
    nomi = sorted({r["bevanda"] for r in rows}) if rows else []
    scelta = st.selectbox("Bevanda", ["-"] + nomi, key="bevanda_abbinamenti")
    if scelta != "-":
        abbinati = _safe(be.get_alimenti_abbinati, scelta)
        _df(abbinati, cols=["alimento"])


# --------------------------------------------------------------------------
# PAGINA: MENU E TERRITORIO
# --------------------------------------------------------------------------
elif pagina == "Menu e Territorio":
    st.header("Menu e Territorio")

    tab1, tab2, tab3 = st.tabs(["Tutti i Menu", "Menu Completi (inferiti)", "Prodotti per Zona"])

    with tab1:
        menu_rows = _safe(be.get_menu_list)
        nomi = sorted({r["menu"] for r in menu_rows}) if menu_rows else []
        _df(menu_rows, cols=["menu"])

        scelto = st.selectbox("Vedi dettaglio menu", ["-"] + nomi, key="menu_dettaglio")
        if scelto != "-":
            dett = _safe(be.get_menu_dettagli, scelto)
            st.write("**Prodotti inclusi:**", ", ".join(dett.get("prodotti", [])) or "—")
            st.write("**Territorio rappresentato:**", ", ".join(dett.get("territorio", [])) or "—")

    with tab2:
        st.caption(
            "Richiede che il reasoning (regole OWL / SWRL) sia attivo sul "
            "repository GraphDB, altrimenti la classe inferita MenuCompleto "
            "risulterà vuota."
        )
        completi = _safe(be.get_menu_completi)
        _df(completi, cols=["menu"])

    with tab3:
        zone_rows = _safe(be.get_zone)
        nomi_zone = sorted({r["zona"] for r in zone_rows}) if zone_rows else []
        zona = st.selectbox("Seleziona zona", ["-"] + nomi_zone)
        if zona != "-":
            prodotti = _safe(be.get_prodotti_tipici, zona)
            _df(prodotti, cols=["prodotto"])


# --------------------------------------------------------------------------
# PAGINA: INSERIMENTO DATI
# --------------------------------------------------------------------------
elif pagina == "Inserimento Dati":
    st.header("Inserimento Dati")
    st.caption("Le operazioni qui eseguono INSERT DATA direttamente sul repository GraphDB.")

    tab_ing, tab_piatto, tab_bevanda, tab_menu, tab_link = st.tabs(
        ["Nuovo Ingrediente", "Nuovo Piatto", "Nuova Bevanda", "Nuovo Menu", "Collega Elementi"]
    )

    # --- Nuovo Ingrediente ---
    with tab_ing:
        with st.form("form_ingrediente"):
            nome = st.text_input("Nome individuo (senza spazi, es. PomodoroSanMarzano)")
            tipo = st.selectbox("Tipo", ["IngredienteSemplice", "IngredienteComposto"])
            stagione = st.selectbox("Stagione", ["", "Primavera", "Estate", "Autunno", "Inverno"])
            tipico_di = st.text_input("Tipico di (nome Zona, opzionale)")
            componenti = st.text_input("Componenti (se composto, nomi separati da virgola)")
            submit = st.form_submit_button("Crea Ingrediente")
            if submit:
                if not nome:
                    st.error("Il nome è obbligatorio.")
                else:
                    comp_list = [c.strip() for c in componenti.split(",") if c.strip()]
                    ok = be.insert_ingrediente(
                        nome=nome,
                        tipo=tipo,
                        stagione=stagione or None,
                        tipico_di=tipico_di.strip() or None,
                        componenti=comp_list or None,
                    )
                    if ok:
                        st.success(f"Ingrediente '{nome}' creato con successo.")

    # --- Nuovo Piatto ---
    with tab_piatto:
        with st.form("form_piatto"):
            nome = st.text_input("Nome individuo (es. RibollitaToscana)")
            tipo = st.selectbox("Tipo", ["PiattoFinito", "PiattoComponibile"])
            portata = st.selectbox("Portata", [""] + be.PORTATE)
            colore = st.text_input("Colore (opzionale)")
            temperatura = st.text_input("Temperatura di servizio in °C (opzionale, intero)")
            ingredienti = st.text_input("Ingredienti (nomi separati da virgola)")
            submit = st.form_submit_button("Crea Piatto")
            if submit:
                if not nome:
                    st.error("Il nome è obbligatorio.")
                else:
                    ingr_list = [i.strip() for i in ingredienti.split(",") if i.strip()]
                    temp_val = int(temperatura) if temperatura.strip().isdigit() else None
                    ok = be.insert_piatto(
                        nome=nome,
                        tipo=tipo,
                        portata=portata or None,
                        colore=colore or None,
                        temperatura=temp_val,
                        ingredienti=ingr_list or None,
                    )
                    if ok:
                        st.success(f"Piatto '{nome}' creato con successo.")

    # --- Nuova Bevanda ---
    with tab_bevanda:
        with st.form("form_bevanda"):
            nome = st.text_input("Nome individuo (es. ChiantiClassicoDOCG)")
            sottoclasse = st.selectbox("Categoria", be.CLASSI_BEVANDA)
            tipologia = st.text_input("Tipologia (es. Vino Rosso, opzionale)")
            gradazione = st.text_input("Gradazione alcolica % (opzionale, es. 13.5)")
            temperatura = st.text_input("Temperatura di servizio in °C (opzionale, intero)")
            submit = st.form_submit_button("Crea Bevanda")
            if submit:
                if not nome:
                    st.error("Il nome è obbligatorio.")
                else:
                    try:
                        grad_val = float(gradazione) if gradazione.strip() else None
                    except ValueError:
                        grad_val = None
                        st.warning("Gradazione non valida, ignorata.")
                    temp_val = int(temperatura) if temperatura.strip().isdigit() else None
                    ok = be.insert_bevanda(
                        nome=nome,
                        sottoclasse=sottoclasse,
                        tipologia=tipologia or None,
                        gradazione_alcolica=grad_val,
                        temperatura=temp_val,
                    )
                    if ok:
                        st.success(f"Bevanda '{nome}' creata con successo.")
                        if grad_val and grad_val > 17:
                            st.info(
                                "Gradazione > 17°: se il reasoning SWRL è attivo, "
                                "sarà classificata automaticamente come BevandaSuperalcolica."
                            )

    # --- Nuovo Menu ---
    with tab_menu:
        with st.form("form_menu"):
            nome = st.text_input("Nome individuo (es. MenuAretino)")
            prodotti = st.text_input("Prodotti inclusi (nomi separati da virgola, opzionale)")
            submit = st.form_submit_button("Crea Menu")
            if submit:
                if not nome:
                    st.error("Il nome è obbligatorio.")
                else:
                    prod_list = [p.strip() for p in prodotti.split(",") if p.strip()]
                    ok = be.insert_menu(nome=nome, prodotti=prod_list or None)
                    if ok:
                        st.success(f"Menu '{nome}' creato con successo.")

    # --- Collega Elementi già esistenti ---
    with tab_link:
        st.subheader("Aggiungi un ingrediente a un piatto esistente")
        with st.form("form_link_ingrediente"):
            piatto = st.text_input("Nome del piatto")
            ingrediente = st.text_input("Nome dell'ingrediente")
            submit = st.form_submit_button("Collega")
            if submit and piatto and ingrediente:
                if be.aggiungi_ingrediente_a_piatto(piatto, ingrediente):
                    st.success(f"'{ingrediente}' aggiunto a '{piatto}'.")

        st.subheader("Aggiungi un prodotto a un menu esistente")
        with st.form("form_link_menu"):
            prodotto = st.text_input("Nome del prodotto (piatto o bevanda)")
            menu = st.text_input("Nome del menu")
            submit = st.form_submit_button("Collega al menu")
            if submit and prodotto and menu:
                if be.aggiungi_prodotto_a_menu(prodotto, menu):
                    st.success(f"'{prodotto}' aggiunto al menu '{menu}'.")

        st.subheader("Abbina un alimento a una bevanda")
        with st.form("form_link_abbinamento"):
            alimento = st.text_input("Nome dell'alimento")
            bevanda = st.text_input("Nome della bevanda")
            submit = st.form_submit_button("Crea abbinamento")
            if submit and alimento and bevanda:
                if be.aggiungi_abbinamento(alimento, bevanda):
                    st.success(f"Abbinamento creato: '{alimento}' ↔ '{bevanda}'.")

        st.subheader("Imposta 'tipico di' per un prodotto")
        with st.form("form_link_tipico"):
            prodotto2 = st.text_input("Nome del prodotto", key="prodotto_tipico")
            zona = st.text_input("Nome della zona")
            submit = st.form_submit_button("Imposta tipicità")
            if submit and prodotto2 and zona:
                if be.imposta_tipicoDi(prodotto2, zona):
                    st.success(f"'{prodotto2}' impostato come tipico di '{zona}'.")

        st.divider()
        st.subheader("🗑️ Elimina un individuo")
        with st.form("form_delete"):
            individuo = st.text_input("Nome individuo da eliminare")
            conferma = st.checkbox("Confermo di voler eliminare tutte le triple relative a questo individuo")
            submit = st.form_submit_button("Elimina")
            if submit:
                if not individuo:
                    st.error("Specificare il nome dell'individuo.")
                elif not conferma:
                    st.warning("Conferma richiesta per procedere.")
                else:
                    if be.elimina_individuo(individuo):
                        st.success(f"Individuo '{individuo}' eliminato.")


# --------------------------------------------------------------------------
# PAGINA: SPARQL PLAYGROUND
# --------------------------------------------------------------------------
elif pagina == "SPARQL Playground":
    st.header("SPARQL Playground")
    st.caption(
        "Digita una query SELECT completa (inclusi i PREFIX necessari). "
        "Utile per interrogazioni ad-hoc non coperte dalle altre pagine."
    )

    esempio = f"""PREFIX : <{be.BASE_NS}>
SELECT ?piatto ?portata WHERE {{
    ?piatto a :PiattoFinito ;
            :appartieneAllaPortata ?portata .
}}
LIMIT 20"""

    query_text = st.text_area("Query SPARQL", value=esempio, height=220)
    if st.button("Esegui query"):
        rows = _safe(be.run_raw_select, query_text)
        _df(rows)
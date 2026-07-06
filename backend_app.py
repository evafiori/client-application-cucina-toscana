"""
backend_app.py
================
Backend della client application per l'ontologia "Cucina Toscana e Territorio".

Espone un insieme di funzioni Python (basate su SPARQLWrapper) che il frontend
Streamlit (frontend_app.py) usa per interrogare e aggiornare il triplestore
GraphDB in cui è caricata l'ontologia allegata (Progetto_WebSem_EE.ttl).

Configurazione
--------------
Modificare le costanti QUERY_ENDPOINT / UPDATE_ENDPOINT con l'indirizzo del
proprio repository GraphDB, tipicamente:

    QUERY_ENDPOINT  = "http://localhost:7200/repositories/CucinaToscana"
    UPDATE_ENDPOINT = "http://localhost:7200/repositories/CucinaToscana/statements"

Se il repository ha il reasoning attivo (es. profilo OWL-Horst / RDFS-Plus,
oppure un plugin che valuta le regole SWRL come "OWL-Horst-Optimized" +
SWRL rules caricate come regole custom), le classi/proprietà inferite
(es. :BevandaSuperalcolica, :MenuCompleto, la propagazione di :stagione e
:tipicoDi, :rappresentaIlTerritorio) saranno visibili direttamente nei
risultati delle SELECT, senza bisogno di simularle qui in Python.
"""

from SPARQLWrapper import SPARQLWrapper, JSON, POST, GET, BASIC
from typing import List, Dict, Optional, Any

# --------------------------------------------------------------------------
# CONFIGURAZIONE ENDPOINT GRAPHDB
# --------------------------------------------------------------------------

QUERY_ENDPOINT = "http://localhost:7200/repositories/CucinaToscana"
UPDATE_ENDPOINT = "http://localhost:7200/repositories/CucinaToscana/statements"

# Se il repository richiede autenticazione, impostare qui username/password
# (lasciare None se non richiesta).
GRAPHDB_USER: Optional[str] = None
GRAPHDB_PASSWORD: Optional[str] = None

# --------------------------------------------------------------------------
# NAMESPACE E PREFISSI
# --------------------------------------------------------------------------

BASE_NS = "http://www.semanticweb.org/edoardo/ontologies/2026/5/Progetto-WebSem-EE/"

PREFIXES = f"""
PREFIX : <{BASE_NS}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""

# Classi principali dell'ontologia, utili per popolare menu a tendina nel frontend
CLASSI_PIATTO = ["Piatto", "PiattoFinito", "PiattoComponibile"]
CLASSI_INGREDIENTE = ["Ingrediente", "IngredienteSemplice", "IngredienteComposto"]
CLASSI_BEVANDA = [
    "Bevanda",
    "BevandaDaPasto",
    "BevandaDaFinePasto",
    "BevandaServitaFredda",
    "BevandaSuperalcolica",
]
CLASSI_ZONA = ["Zona", "Localita", "Provincia"]
PORTATE = ["Antipasto", "Primo", "Secondo", "Contorno", "Dessert"]


# --------------------------------------------------------------------------
# WRAPPER SPARQL DI BASSO LIVELLO
# --------------------------------------------------------------------------

def _make_wrapper(endpoint: str, method) -> SPARQLWrapper:
    sparql = SPARQLWrapper(endpoint)
    sparql.setMethod(method)
    sparql.setReturnFormat(JSON)
    if GRAPHDB_USER and GRAPHDB_PASSWORD:
        sparql.setHTTPAuth(BASIC)
        sparql.setCredentials(GRAPHDB_USER, GRAPHDB_PASSWORD)
    return sparql


def local_name(uri: str) -> str:
    """Estrae la parte finale (local name) di un URI, per una visualizzazione leggibile."""
    if uri is None:
        return ""
    if "#" in uri:
        return uri.rsplit("#", 1)[-1]
    return uri.rstrip("/").rsplit("/", 1)[-1]


def run_select(query: str) -> List[Dict[str, Any]]:
    """
    Esegue una query SPARQL SELECT (con PREFIXES già inclusi) e restituisce
    una lista di dizionari {variabile: valore_semplificato}.
    I valori che sono URI del namespace dell'ontologia vengono ridotti al
    local name; gli altri URI e i literal restano come stringhe.
    """
    sparql = _make_wrapper(QUERY_ENDPOINT, GET)
    sparql.setQuery(PREFIXES + query)
    results = sparql.query().convert()

    rows = []
    for binding in results["results"]["bindings"]:
        row = {}
        for var, val in binding.items():
            value = val["value"]
            if val["type"] == "uri":
                row[var] = local_name(value) if value.startswith(BASE_NS) else value
                row[var + "_uri"] = value
            else:
                row[var] = value
        rows.append(row)
    return rows


def run_update(update_query: str) -> bool:
    """
    Esegue una query SPARQL UPDATE (INSERT DATA / DELETE / INSERT-WHERE, ecc.)
    con i PREFIXES già inclusi. Restituisce True se l'operazione va a buon fine.
    """
    sparql = _make_wrapper(UPDATE_ENDPOINT, POST)
    sparql.setQuery(PREFIXES + update_query)
    sparql.query()
    return True


def run_raw_select(full_query: str) -> List[Dict[str, Any]]:
    """
    Come run_select, ma per query "libere" digitate dall'utente nel frontend
    (playground SPARQL): non aggiunge i PREFIXES automaticamente, si assume
    che la query li includa già se necessario.
    """
    sparql = _make_wrapper(QUERY_ENDPOINT, GET)
    sparql.setQuery(full_query)
    results = sparql.query().convert()
    rows = []
    for binding in results["results"]["bindings"]:
        row = {var: val["value"] for var, val in binding.items()}
        rows.append(row)
    return rows


def _run_full_select_simplificata(full_query: str) -> List[Dict[str, Any]]:
    """
    Come run_raw_select, ma con la stessa semplificazione dei valori usata da
    run_select (URI del namespace locale ridotti al local name). Pensata per
    query che includono già tutti i propri PREFIX (es. le query federate
    verso DBpedia/Wikidata), quindi NON aggiunge i PREFIXES globali per
    evitare dichiarazioni duplicate o in conflitto.
    """
    sparql = _make_wrapper(QUERY_ENDPOINT, GET)
    sparql.setQuery(full_query)
    results = sparql.query().convert()
    rows = []
    for binding in results["results"]["bindings"]:
        row = {}
        for var, val in binding.items():
            value = val["value"]
            if val["type"] == "uri":
                row[var] = local_name(value) if value.startswith(BASE_NS) else value
                row[var + "_uri"] = value
            else:
                row[var] = value
        rows.append(row)
    return rows


def _esc(s: str) -> str:
    """Escape minimo per inserire stringhe letterali in query SPARQL."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


# --------------------------------------------------------------------------
# QUERY DI LETTURA - PIATTI
# --------------------------------------------------------------------------

def get_piatti(portata: Optional[str] = None,
               stagione: Optional[str] = None,
               tipo: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco dei piatti, con eventuale filtro su portata,
    stagione (tramite la propagazione data dalla Regola 3) e tipo
    (PiattoFinito / PiattoComponibile).
    """
    classe = tipo if tipo in ("PiattoFinito", "PiattoComponibile") else "Piatto"
    filtri = []
    if portata:
        filtri.append(f'?piatto :appartieneAllaPortata :{portata} .')
    if stagione:
        filtri.append(f'?piatto :stagione "{_esc(stagione)}" .')

    query = f"""
    SELECT DISTINCT ?piatto ?portata ?stagione ?colore WHERE {{
        ?piatto a :{classe} .
        OPTIONAL {{ ?piatto :appartieneAllaPortata ?portata . }}
        OPTIONAL {{ ?piatto :stagione ?stagione . }}
        OPTIONAL {{ ?piatto :colore ?colore . }}
        {' '.join(filtri)}
    }}
    ORDER BY ?piatto
    """
    return run_select(query)


def get_piatto_dettagli(piatto: str) -> Dict[str, Any]:
    """
    Restituisce il dettaglio completo di un piatto: portata, stagione,
    colore, temperatura di servizio, ingredienti (anche indiretti, grazie
    alla transitività di :compostoDaIngrediente se il reasoner è attivo),
    bevande abbinate e menu a cui appartiene.
    """
    query = f"""
    SELECT ?proprieta ?valore WHERE {{
        {{ :{piatto} :appartieneAllaPortata ?valore . BIND("portata" AS ?proprieta) }}
        UNION
        {{ :{piatto} :stagione ?valore . BIND("stagione" AS ?proprieta) }}
        UNION
        {{ :{piatto} :colore ?valore . BIND("colore" AS ?proprieta) }}
        UNION
        {{ :{piatto} :temperaturaServizio ?valore . BIND("temperatura" AS ?proprieta) }}
        UNION
        {{ :{piatto} :compostoDaIngrediente ?valore . BIND("ingrediente" AS ?proprieta) }}
        UNION
        {{ :{piatto} :abbinatoABevanda ?valore . BIND("bevanda_abbinata" AS ?proprieta) }}
        UNION
        {{ :{piatto} :componeMenu ?valore . BIND("menu" AS ?proprieta) }}
    }}
    """
    rows = run_select(query)
    dettagli: Dict[str, Any] = {
        "nome": piatto,
        "portata": [],
        "stagione": [],
        "colore": [],
        "temperatura": [],
        "ingredienti": [],
        "bevande_abbinate": [],
        "menu": [],
    }
    mapping = {
        "portata": "portata",
        "stagione": "stagione",
        "colore": "colore",
        "temperatura": "temperatura",
        "ingrediente": "ingredienti",
        "bevanda_abbinata": "bevande_abbinate",
        "menu": "menu",
    }
    for r in rows:
        key = mapping[r["proprieta"]]
        dettagli[key].append(r["valore"])
    return dettagli


# --------------------------------------------------------------------------
# QUERY DI LETTURA - INGREDIENTI
# --------------------------------------------------------------------------

def get_ingredienti(tipo: Optional[str] = None,
                     stagione: Optional[str] = None) -> List[Dict[str, Any]]:
    classe = tipo if tipo in ("IngredienteSemplice", "IngredienteComposto") else "Ingrediente"
    filtro = f'?ingrediente :stagione "{_esc(stagione)}" .' if stagione else ""
    query = f"""
    SELECT DISTINCT ?ingrediente ?stagione ?tipicoDi WHERE {{
        ?ingrediente a :{classe} .
        OPTIONAL {{ ?ingrediente :stagione ?stagione . }}
        OPTIONAL {{ ?ingrediente :tipicoDi ?tipicoDi . }}
        {filtro}
    }}
    ORDER BY ?ingrediente
    """
    return run_select(query)


def get_composizione_ingrediente(ingrediente: str) -> List[Dict[str, Any]]:
    """Sotto-ingredienti che compongono un IngredienteComposto."""
    query = f"""
    SELECT ?componente WHERE {{
        :{ingrediente} :compostoDaIngrediente ?componente .
    }}
    """
    return run_select(query)


# --------------------------------------------------------------------------
# QUERY DI LETTURA - BEVANDE
# --------------------------------------------------------------------------

def get_bevande(tipologia: Optional[str] = None,
                 solo_superalcoliche: bool = False,
                 sottoclasse: Optional[str] = None) -> List[Dict[str, Any]]:
    classe = "BevandaSuperalcolica" if solo_superalcoliche else (
        sottoclasse if sottoclasse in CLASSI_BEVANDA else "Bevanda"
    )
    filtro = f'?bevanda :tipologia "{_esc(tipologia)}" .' if tipologia else ""
    query = f"""
    SELECT DISTINCT ?bevanda ?tipologia ?gradazioneAlcolica WHERE {{
        ?bevanda a :{classe} .
        OPTIONAL {{ ?bevanda :tipologia ?tipologia . }}
        OPTIONAL {{ ?bevanda :gradazioneAlcolica ?gradazioneAlcolica . }}
        {filtro}
    }}
    ORDER BY ?bevanda
    """
    return run_select(query)


def get_alimenti_abbinati(bevanda: str) -> List[Dict[str, Any]]:
    """Alimenti (piatti) abbinati a una data bevanda (proprietà inversa abbinatoAdAlimento)."""
    query = f"""
    SELECT ?alimento WHERE {{
        :{bevanda} :abbinatoAdAlimento ?alimento .
    }}
    """
    return run_select(query)


# --------------------------------------------------------------------------
# QUERY DI LETTURA - MENU E TERRITORIO
# --------------------------------------------------------------------------

def get_menu_list() -> List[Dict[str, Any]]:
    query = """
    SELECT DISTINCT ?menu WHERE {
        ?menu a :Menu .
    }
    ORDER BY ?menu
    """
    return run_select(query)


def get_menu_completi() -> List[Dict[str, Any]]:
    """
    Menu classificati come :MenuCompleto (classe definita per equivalenza
    logica: richiede il reasoning attivo sul repository GraphDB).
    """
    query = """
    SELECT DISTINCT ?menu WHERE {
        ?menu a :MenuCompleto .
    }
    ORDER BY ?menu
    """
    return run_select(query)


def get_menu_dettagli(menu: str) -> Dict[str, Any]:
    query = f"""
    SELECT ?proprieta ?valore WHERE {{
        {{ :{menu} :comprendeProdotto ?valore . BIND("prodotto" AS ?proprieta) }}
        UNION
        {{ :{menu} :rappresentaIlTerritorio ?valore . BIND("territorio" AS ?proprieta) }}
    }}
    """
    rows = run_select(query)
    dettagli: Dict[str, Any] = {"nome": menu, "prodotti": [], "territorio": []}
    for r in rows:
        if r["proprieta"] == "prodotto":
            dettagli["prodotti"].append(r["valore"])
        else:
            dettagli["territorio"].append(r["valore"])
    return dettagli


def get_zone() -> List[Dict[str, Any]]:
    query = """
    SELECT DISTINCT ?zona WHERE {
        ?zona a :Zona .
    }
    ORDER BY ?zona
    """
    return run_select(query)


def get_prodotti_tipici(zona: str) -> List[Dict[str, Any]]:
    """
    Prodotti tipici di una zona, includendo anche quelli tipici per
    propagazione (Regola: compostoDaIngrediente + tipicoDi -> tipicoDi),
    se il reasoning è attivo.
    """
    query = f"""
    SELECT DISTINCT ?prodotto WHERE {{
        ?prodotto :tipicoDi :{zona} .
    }}
    ORDER BY ?prodotto
    """
    return run_select(query)


# --------------------------------------------------------------------------
# QUERY GENERICHE DI ESPLORAZIONE (utili per la UI)
# --------------------------------------------------------------------------

def get_individui_di_classe(classe: str) -> List[Dict[str, Any]]:
    query = f"""
    SELECT DISTINCT ?individuo WHERE {{
        ?individuo a :{classe} .
    }}
    ORDER BY ?individuo
    """
    return run_select(query)


def get_tutte_le_proprieta(individuo: str) -> List[Dict[str, Any]]:
    """Tutte le triple (predicato, valore) uscenti da un individuo, per un dettaglio generico."""
    query = f"""
    SELECT ?predicato ?valore WHERE {{
        :{individuo} ?predicato ?valore .
    }}
    """
    return run_select(query)


# --------------------------------------------------------------------------
# OPERAZIONI DI SCRITTURA (INSERT / DELETE)
# --------------------------------------------------------------------------

def insert_ingrediente(nome: str,
                        tipo: str = "IngredienteSemplice",
                        stagione: Optional[str] = None,
                        tipico_di: Optional[str] = None,
                        componenti: Optional[List[str]] = None) -> bool:
    """
    Crea un nuovo Ingrediente (Semplice o Composto).
    Se tipo == "IngredienteComposto", 'componenti' è la lista degli
    IngredienteSemplice/PiattoComponibile che lo costituiscono.
    """
    assert tipo in ("IngredienteSemplice", "IngredienteComposto")
    triple = [f":{nome} rdf:type owl:NamedIndividual , :{tipo} ."]
    if stagione:
        triple.append(f':{nome} :stagione "{_esc(stagione)}" .')
    if tipico_di:
        triple.append(f":{nome} :tipicoDi :{tipico_di} .")
    if componenti:
        for c in componenti:
            triple.append(f":{nome} :compostoDaIngrediente :{c} .")

    update = "INSERT DATA { " + " ".join(triple) + " }"
    return run_update(update)


def insert_piatto(nome: str,
                   tipo: str = "PiattoFinito",
                   portata: Optional[str] = None,
                   colore: Optional[str] = None,
                   temperatura: Optional[int] = None,
                   ingredienti: Optional[List[str]] = None) -> bool:
    """Crea un nuovo Piatto (Finito o Componibile)."""
    assert tipo in ("PiattoFinito", "PiattoComponibile")
    triple = [f":{nome} rdf:type owl:NamedIndividual , :{tipo} ."]
    if portata:
        triple.append(f":{nome} :appartieneAllaPortata :{portata} .")
    if colore:
        triple.append(f':{nome} :colore "{_esc(colore)}" .')
    if temperatura is not None:
        triple.append(f':{nome} :temperaturaServizio "{temperatura}"^^xsd:integer .')
    if ingredienti:
        for ing in ingredienti:
            triple.append(f":{nome} :compostoDaIngrediente :{ing} .")

    update = "INSERT DATA { " + " ".join(triple) + " }"
    return run_update(update)


def insert_bevanda(nome: str,
                    sottoclasse: str = "Bevanda",
                    tipologia: Optional[str] = None,
                    gradazione_alcolica: Optional[float] = None,
                    temperatura: Optional[int] = None) -> bool:
    """
    Crea una nuova Bevanda. Se gradazione_alcolica > 17, la Regola 1 SWRL
    la classificherà automaticamente come :BevandaSuperalcolica (previo
    reasoning attivo sul repository).
    """
    assert sottoclasse in CLASSI_BEVANDA
    triple = [f":{nome} rdf:type owl:NamedIndividual , :{sottoclasse} ."]
    if tipologia:
        triple.append(f':{nome} :tipologia "{_esc(tipologia)}" .')
    if gradazione_alcolica is not None:
        triple.append(f':{nome} :gradazioneAlcolica "{gradazione_alcolica}"^^xsd:decimal .')
    if temperatura is not None:
        triple.append(f':{nome} :temperaturaServizio "{temperatura}"^^xsd:integer .')

    update = "INSERT DATA { " + " ".join(triple) + " }"
    return run_update(update)


def insert_menu(nome: str, prodotti: Optional[List[str]] = None) -> bool:
    triple = [f":{nome} rdf:type owl:NamedIndividual , :Menu ."]
    if prodotti:
        for p in prodotti:
            triple.append(f":{nome} :comprendeProdotto :{p} .")
    update = "INSERT DATA { " + " ".join(triple) + " }"
    return run_update(update)


def aggiungi_ingrediente_a_piatto(piatto: str, ingrediente: str) -> bool:
    update = f"INSERT DATA {{ :{piatto} :compostoDaIngrediente :{ingrediente} . }}"
    return run_update(update)


def aggiungi_prodotto_a_menu(prodotto: str, menu: str) -> bool:
    update = f"INSERT DATA {{ :{prodotto} :componeMenu :{menu} . }}"
    return run_update(update)


def aggiungi_abbinamento(alimento: str, bevanda: str) -> bool:
    update = f"INSERT DATA {{ :{alimento} :abbinatoABevanda :{bevanda} . }}"
    return run_update(update)


def imposta_tipicoDi(prodotto: str, zona: str) -> bool:
    update = f"INSERT DATA {{ :{prodotto} :tipicoDi :{zona} . }}"
    return run_update(update)


def elimina_individuo(nome: str) -> bool:
    """
    Elimina un individuo e tutte le triple in cui compare come soggetto o
    come oggetto (rimozione completa dal grafo).
    """
    update = f"""
    DELETE WHERE {{ :{nome} ?p ?o . }} ;
    DELETE WHERE {{ ?s ?p2 :{nome} . }}
    """
    return run_update(update)


def elimina_tripla(soggetto: str, predicato: str, oggetto: str, oggetto_e_letterale: bool = False) -> bool:
    """Elimina una singola tripla, utile ad es. per rimuovere un ingrediente da un piatto."""
    obj = f'"{_esc(oggetto)}"' if oggetto_e_letterale else f":{oggetto}"
    update = f"DELETE DATA {{ :{soggetto} :{predicato} {obj} . }}"
    return run_update(update)


# --------------------------------------------------------------------------
# QUERY FEDERATE VERSO DBPEDIA (arricchimento dati esterni)
# --------------------------------------------------------------------------
#
# Le tre funzioni seguenti eseguono query SPARQL 1.1 federate (clausola
# SERVICE) che vengono valutate interamente da GraphDB: la parte locale
# seleziona i piatti/ingredienti dell'ontologia, la parte SERVICE delega
# l'interrogazione a https://dbpedia.org/sparql per recuperare descrizioni,
# immagini, link a Wikipedia e luoghi di origine.
#
# NOTA: ogni query include già tutti i propri PREFIX, quindi viene eseguita
# tramite _run_full_select_simplificata (che non prepende i PREFIXES globali,
# per evitare dichiarazioni duplicate). Richiede che GraphDB abbia accesso
# di rete in uscita verso dbpedia.org.

def get_descrizione_piatti_dbpedia() -> List[Dict[str, Any]]:
    """
    Query federata 1: per ciascun Piatto locale (e relative sottoclassi),
    cerca su DBpedia una risorsa di tipo dbo:Food originaria della Toscana
    (dbo:region dbr:Tuscany) il cui URI contenga il nome del piatto, e ne
    recupera la descrizione/abstract in italiano.
    """
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX : <{BASE_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbo: <http://dbpedia.org/ontology/>
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX dbc: <http://dbpedia.org/resource/Category:>
    PREFIX dbr: <http://dbpedia.org/resource/>

    SELECT DISTINCT ?piattoLocale ?risorsaDBpedia ?descrizione WHERE {{
        ?piattoLocale a/rdfs:subClassOf* :Piatto .

        BIND(STRAFTER(STR(?piattoLocale), "Progetto-WebSem-EE/") AS ?nomeFrammento)

        SERVICE <https://dbpedia.org/sparql> {{
            ?risorsaDBpedia rdf:type dbo:Food ;
                            dbo:region dbr:Tuscany .

            FILTER(REGEX(STR(?risorsaDBpedia), ?nomeFrammento, "i"))

            OPTIONAL {{
                ?risorsaDBpedia dbo:description | dbo:abstract | rdfs:comment ?descrizione .
                FILTER(LANG(?descrizione) = "it")
            }}
        }}
    }}
    """
    return _run_full_select_simplificata(query)


def get_media_piatti_ingredienti_dbpedia() -> List[Dict[str, Any]]:
    """
    Query federata 2: per ciascun Piatto locale e i suoi ingredienti
    (individuati tramite qualunque proprietà il cui nome contenga
    "ingrediente"/"Ingredient"), ricostruisce l'URI DBpedia corrispondente
    e ne recupera, se disponibili, immagine (dbo:thumbnail) e link alla
    voce Wikipedia (foaf:isPrimaryTopicOf), sia per il piatto sia per
    l'ingrediente.
    """
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX : <{BASE_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbo: <http://dbpedia.org/ontology/>
    PREFIX foaf: <http://xmlns.com/foaf/0.1/>

    SELECT DISTINCT
        ?piattoLocale ?risorsaDBpediaPiatto ?urlImmaginePiatto ?linkWikipediaPiatto
        ?ingredienteLocale ?risorsaDBpediaIngrediente ?urlImmagineIngrediente ?linkWikipediaIngrediente
    WHERE {{
        ?piattoLocale a/rdfs:subClassOf* :Piatto .

        ?piattoLocale ?proprietaIngrediente ?ingredienteLocale .
        FILTER(CONTAINS(STR(?proprietaIngrediente), "ingrediente") || CONTAINS(STR(?proprietaIngrediente), "Ingredient"))

        BIND(STRAFTER(STR(?piattoLocale), "Progetto-WebSem-EE/") AS ?nomePiattoFrammento)
        BIND(STRAFTER(STR(?ingredienteLocale), "Progetto-WebSem-EE/") AS ?nomeIngredienteFrammento)

        BIND(URI(CONCAT("http://dbpedia.org/resource/", ?nomePiattoFrammento)) AS ?risorsaDBpediaPiatto)
        BIND(URI(CONCAT("http://dbpedia.org/resource/", ?nomeIngredienteFrammento)) AS ?risorsaDBpediaIngrediente)

        SERVICE <https://dbpedia.org/sparql> {{
            OPTIONAL {{
                ?risorsaDBpediaPiatto rdf:type dbo:Food .
                OPTIONAL {{ ?risorsaDBpediaPiatto dbo:thumbnail ?urlImmaginePiatto }}
                OPTIONAL {{ ?risorsaDBpediaPiatto foaf:isPrimaryTopicOf ?linkWikipediaPiatto }}
            }}
            OPTIONAL {{
                OPTIONAL {{ ?risorsaDBpediaIngrediente dbo:thumbnail ?urlImmagineIngrediente }}
                OPTIONAL {{ ?risorsaDBpediaIngrediente foaf:isPrimaryTopicOf ?linkWikipediaIngrediente }}
            }}
        }}
    }}
    """
    return _run_full_select_simplificata(query)


def get_origine_geografica_piatti_dbpedia() -> List[Dict[str, Any]]:
    """
    Query federata 3: per ciascun Piatto locale, cerca su DBpedia una
    risorsa dbo:Food il cui URI corrisponda (case-insensitive) al nome del
    piatto, e ne recupera il luogo/regione/paese di origine (dbo:region o
    dbo:country) con l'etichetta in italiano.
    """
    query = f"""
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX : <{BASE_NS}>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dbo: <http://dbpedia.org/ontology/>

    SELECT DISTINCT ?piattoLocale ?risorsaDBpedia ?luogoOrigine ?nomeLuogo WHERE {{
        ?piattoLocale a/rdfs:subClassOf* :Piatto .

        BIND(STRAFTER(STR(?piattoLocale), "Progetto-WebSem-EE/") AS ?nomeFrammento)

        SERVICE <https://dbpedia.org/sparql> {{
            ?risorsaDBpedia rdf:type dbo:Food .

            ?risorsaDBpedia dbo:region | dbo:country ?luogoOrigine .

            ?luogoOrigine rdfs:label ?nomeLuogo .
            FILTER(LANG(?nomeLuogo) = "it")

            FILTER(REGEX(STR(?risorsaDBpedia), ?nomeFrammento, "i"))
        }}
    }}
    """
    return _run_full_select_simplificata(query)


# --------------------------------------------------------------------------
# TEST RAPIDO DA RIGA DI COMANDO
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print("Test di connessione al repository GraphDB:", QUERY_ENDPOINT)
    try:
        piatti = get_piatti()
        print(f"Trovati {len(piatti)} piatti.")
        for p in piatti[:5]:
            print(" -", p.get("piatto"))
    except Exception as e:
        print("Errore nella connessione:", e)
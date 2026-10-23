# F24 Downloader

Applicazione desktop gratuita e indipendente per raccogliere le quietanze F24
dal Cassetto fiscale dell'Agenzia delle Entrate sul proprio computer.

**Versione 0.2.0a13 - versione di prova (alpha). Non ancora verificata
integralmente sul portale reale.** Il progetto non è affiliato, approvato o
supportato dall'Agenzia delle Entrate.

Codice sorgente: [ghedy/F24_Downloader](https://github.com/ghedy/F24_Downloader).
Per problemi usare [le segnalazioni del repository](https://github.com/ghedy/F24_Downloader/issues),
senza allegare dati fiscali o credenziali. Per vulnerabilità seguire [SECURITY.md](SECURITY.md).

## Funzioni

- Interfaccia desktop ispirata all'organizzazione visiva di AsterQuadra:
  navigazione laterale, pannelli chiari, accenti blu.
- Accesso nel browser visibile con **SPID Sielte** o **CIE**.
  CNS, Fisconline/Entratel e gli altri gestori SPID restano in grigio e non
  selezionabili finché i relativi percorsi non saranno sistemati e collaudati.
- Compilazione facoltativa di username e password per SPID Sielte e CIE:
  il secondo fattore resta a carico dell'utente. Come nel programma originale,
  Sielte conferma l'OTP inserito nel browser e clicca Autorizza; CIE clicca Prosegui
  nella schermata finale.
- Rubrica locale delle utenze già autorizzate, periodo su uno o più anni,
  cartella di destinazione e pausa tra i download.
- Controllo dell'utenza disponibile, del valore selezionato e del ritorno al portale
  dopo la conferma. Il selettore non viene riaperto per dedurre l'utenza attiva.
- PDF separati per utenza e anno, rinomina per data/importo quando riconosciuti,
  duplicati riconosciuti per file identico o contenuto F24 invariato e PDF non riconosciuti conservati come
  `F24_da_verificare_...`.
- Avanzamento, contatori, registro in memoria e interruzione.
- Credenziali ricordate solo su richiesta, cifrate con Windows DPAPI.
  Nessuna telemetria applicativa, persistenza di cookie o diagnostica delle pagine.

Il controllo duplicati confronta prima i byte del PDF, poi il contenuto di tutte
le pagine dei documenti F24 riconosciuti, incluse le immagini incorporate.
Ignora soltanto data e ora di generazione nella riga del portale
`Utente / Data / Ore`. Protocolli, contribuente, data del versamento, importi
e tributi restano nel confronto: data e importo uguali da soli non bastano.
I documenti non riconosciuti o senza testo mantengono il solo controllo binario.
Il flag di riordino permette di eliminare anche le copie già presenti nella
cartella, conservando un documento per contenuto.

Un modello F24 non sostituisce una quietanza. Se il portale rifiuta la quietanza
oppure il download Q scade, viene tentato una volta il formato P dello stesso
documento; i modelli ottenuti sono identificati nel nome e nel riepilogo.

## Requisiti e avvio su Windows

Python 3.12 o successivo; sviluppo verificato con Python 3.14 e Windows.
Connessione Internet, utenza AdE valida e relative autorizzazioni.

Da una copia dei sorgenti:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install firefox
.\.venv\Scripts\python.exe main.py
```

In alternativa, dopo l'installazione delle dipendenze, eseguire `avvia.bat`.

Non serve creare manualmente un file con le credenziali.
Al primo avvio non ci sono utenze né una cartella di download già selezionata.
Configura le utenze nella sezione **Utenze** e scegli la cartella nella schermata
**Scarica quietanze**. Questi dati vengono ricordati solo nella configurazione locale,
esclusa da Git. Copia eventualmente `config/config.example.json` in
`config/config.json` per predisporre le sole impostazioni locali.

## Uso su un altro computer

Le password ricordate sono protette per l'account Windows che le ha salvate.
Copiando l'intera cartella su un altro PC, `config/credentials.bin` può quindi
risultare illeggibile. All'avvio il programma conserva l'archivio cifrato con
nome `credentials.bin.non-utilizzabile-…`, mantiene rubrica e impostazioni e
chiede di reinserire le credenziali. Non tenta di trasferire o decifrare le
password con un altro account. Il file conservato resta escluso dal rilascio.

Inserisci nuovamente le credenziali sul nuovo PC e, se desideri, seleziona
**Ricorda le credenziali in questo account Windows**. Controlla anche che la
cartella di destinazione dei PDF sia disponibile sul computer corrente.
L'installazione di dipendenze e Firefox va eseguita anche sul nuovo PC;
non copiare l'ambiente `.venv` da un altro computer.

Se compare un errore di permessi, usa una cartella personale scrivibile,
per esempio Documenti. Se `config.json` è danneggiato, conservane una copia e
ripristinalo da `config/config.example.json`; in questo caso le utenze vanno
riconfigurate. Gli archivi di credenziali con errori di lettura o di accesso
non vengono automaticamente spostati.

## Uso

1. Seleziona SPID Sielte o CIE e l'utenza. In **Utenze** inserisci descrizione
   e **codice fiscale / partita IVA** visibile sul portale, mantenendo gli zeri
   iniziali. Il programma legge le descrizioni del selettore AdE e invia il
   codice interno della posizione corrispondente, senza richiedertelo.
   Se più posizioni corrispondono allo stesso identificativo, si ferma senza
   scegliere arbitrariamente. I vecchi codici interni già salvati restano utilizzabili.
   La rubrica non conferisce deleghe.
   Con **Profilo personale - nessun cambio utenza** il programma salta la
   pagina Cambia utenza e passa direttamente al Cassetto fiscale.
2. Imposta **Anni dal / al**, date e cartella. Per un solo anno inserisci lo stesso
   valore nei due campi; per più anni scegli un intervallo. Anni e date sono
   allineati in due colonne vicine, separate dal trattino corto.
3. Avvia il download e completa il secondo fattore nel browser o nell'app.
   Per Sielte e CIE le conferme successive vengono gestite automaticamente.
   Dopo il cambio utenza il programma segue i collegamenti **Vai al servizio**
   del Cassetto fiscale, **Vai a Consultazioni** e **Versamenti**, poi effettua
   il click sul selettore F24 dell'anno e infine applica il periodo.
   Per ogni anno successivo riparte dalla pagina principale del Cassetto,
   torna a Versamenti e seleziona il collegamento relativo a quell'anno.
   Questo percorso funziona anche dopo una stampa P che non mostra i selettori.
   L'accesso e il cambio utenza si eseguono una sola volta.
4. Controlla contatori e registro; verifica i PDF segnalati come non riconosciuti.
5. Apri la cartella dei risultati.

Il selettore degli anni può essere un carosello: il programma usa le frecce
**Anni successivi** e, quando serve, **Anni precedenti** per portare in vista
l'anno richiesto. Attende la fine dell'animazione e riconosce quando il carosello
ricomincia dall'inizio, senza continuare a scorrere all'infinito.
Un errore del carosello bloccato viene segnalato come tale.

Gli anni senza il collegamento F24 vengono indicati come saltati, senza
bloccare la ricerca. Il messaggio **NESSUNA OCCORRENZA trovata per la selezione
effettuata** indica invece che l'anno è selezionabile ma non ci sono risultati
nel periodo richiesto: viene registrato e si continua con l'anno successivo.

Se il portale risponde **La delega richiesta non è stampabile nel formato
QUIETANZA**, il programma prova lo stesso documento con `stampa=P`.
Il file ottenuto viene segnalato come **modello F24**, con prefisso
`F24_modello_` nel nome e conteggio nel riepilogo; non sostituisce una quietanza.
Anche una quietanza non ricevuta entro il tempo previsto attiva un singolo
tentativo P. Gli errori di sessione riconosciuti attivano prima il ripristino
e una nuova selezione di anno e periodo, poi il tentativo dello stesso formato.
Un documento viene conteggiato fra gli errori solo se nessun tentativo riesce.
Il riordino mantiene il prefisso dei modelli e riconosce i loro duplicati.

Il messaggio **Problemi di collegamento col CICS: ABEND - IUWX** viene
riconosciuto prima di interpretare un elenco o un anno come mancante.
Il programma apre **Ripristina il cassetto fiscale**, torna a Versamenti e
ripete la selezione di anno e periodo. Ogni fase ha un massimo di tre tentativi;
se il ripristino non riesce, si interrompe lasciando il browser consultabile.

Le frecce dell'anno finale restano utilizzabili anche quando coincide con
quello iniziale: scegliendo un anno finale precedente, l'anno iniziale si
allinea automaticamente. Entrambi sono limitati fra il 2000 e l'anno corrente.

Le date delimitano il periodo complessivo: dal 15/03/2023 al 10/02/2025 significa
15/03–31/12 per il 2023, tutto il 2024 e 01/01–10/02 per il 2025.
Ogni anno ha la propria cartella sotto l'utenza. I contatori riassumono l'intera
sessione e il registro indica l'anno in lavorazione.

La disponibilità e la scrittura della destinazione vengono controllate prima
di aprire il browser. Per un'unità di rete non raggiungibile, ricollegarla oppure
scegliere una cartella accessibile con Sfoglia. La destinazione valida scelta
viene ricordata all'avvio del download.

**Interrompi** attende la richiesta in corso, normalmente fino a 60 secondi.
Anche la chiusura della finestra attende il rilascio del browser.
In caso di errore il browser resta aperto per leggere il messaggio del portale;
il registro indica la fase dell'interruzione. Premi **Chiudi browser** per terminare
la sessione. La presenza dell'utenza desiderata deve essere confermata anche nel collaudo reale.
I PDF già salvati restano disponibili. L'interruzione durante la raccolta
dell'elenco avviene prima dello scaricamento.

## Riordino e rinomina della cartella

- **Rinomina e rimuovi duplicati da tutta la cartella**: se selezionato, esegue
  il riordino dei PDF già presenti al termine del download.
- **Riordina e rinomina solo la cartella**: esegue la stessa operazione
  localmente, senza aprire il browser e senza autenticazione AdE.

Seleziona utenza, anni e cartella base; controlla il percorso nella riga
**Destinazione**. L'operazione riguarda tutti i PDF direttamente nelle cartelle
utenza/anno selezionate, indipendentemente dalle date del periodo.
I duplicati vengono confrontati separatamente in ciascuna cartella annuale.
Le cartelle annuali assenti vengono saltate; altri anni, utenze e sottocartelle
restano esclusi.

Le copie uguali vengono eliminate direttamente dopo il confronto del
contenuto. Rimane una copia per ciascuna quietanza distinta. Il controllo
conserva i documenti con differenze nei dati del versamento.
I PDF riconosciuti vengono rinominati come
`F24_AAAAMMGG_PROGRESSIVO_IMPORTOeuro.pdf`; i nomi già corretti restano validi.
I PDF non riconosciuti conservano il loro nome; solo le loro copie binarie
identiche possono essere eliminate.
Il registro riporta rinominati, duplicati eliminati, invariati ed errori.
Il flag è inizialmente disattivato; il pulsante locale può essere usato in
qualsiasi momento in cui non sia in corso un'altra operazione.

## Credenziali e migrazione

All'avvio, le vecchie credenziali presenti in `config/config.json` vengono
cifrate in `config/credentials.bin`, verificate e successivamente rimosse dal
JSON. In caso di errore l'avvio si ferma e non elimina le credenziali originali.
La migrazione logica non garantisce la cancellazione forense di vecchie copie,
backup o precedenti versioni del file.

L'archivio cifrato richiede l'account Windows che lo ha creato: non trasferirlo
come metodo per condividere credenziali. I PDF e la rubrica utenze sono dati
locali non cifrati dall'applicazione. Proteggi il computer e i backup.
Il comando **Dimentica tutte le credenziali salvate** elimina l'archivio locale.

## Verifiche di sviluppo

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python tools/check_repository.py --staged
```

I test usano esclusivamente dati sintetici e non accedono ad AdE.
Il controllo del repository verifica i file effettivamente aggiunti a Git e
l'assenza dei valori privati della configurazione locale, inclusa la destinazione
dei PDF. La configurazione di esempio resta vuota. I controlli GitHub Actions
eseguono la stessa verifica senza generare archivi.

## Sviluppo e pubblicazione con Git

La rubrica utenze, le password, il percorso personale dei download e i PDF
restano sul computer. `.gitignore` ammette esplicitamente i sorgenti pubblici
e lascia esclusi configurazione reale, archivi cifrati, documenti, anteprime,
backup e altri file locali. `config/config.example.json` contiene solo campi
vuoti e la pausa tra download, senza dati personali né una destinazione.

Per aggiornare i file da pubblicare, usare Git dalla cartella del progetto:

```powershell
git add .
python tools/check_repository.py --staged
git diff --cached --stat
```

Dopo la verifica si può creare il commit e pubblicare gli aggiornamenti sul
repository GitHub. Non aggiungere forzatamente i file ignorati e non caricare
l'intera cartella tramite trascinamento nel sito: usare i file gestiti da Git.
Lo strumento di controllo non crea archivi e non invia dati in rete.

## Limiti e pubblicazione

I selettori e le rotte del portale provengono dal programma iniziale e devono
essere verificati con una sessione autorizzata. In particolare, vanno provati
il valore attivo dopo cambio utenza, le pagine vuote e l'eventuale paginazione.
La paginazione con collegamento successivo viene seguita; quella numerica
riconoscibile ma non gestita blocca la ricerca. Non è garantito il
riconoscimento di ogni possibile impaginazione del portale.

Non vengono aggirati MFA, CAPTCHA, blocchi di accesso o limiti del servizio.
La pausa minima di due secondi è una precauzione tecnica, non una soglia
approvata da AdE.

Prima di pubblicare seguire [la lista di rilascio](docs/RELEASE_CHECKLIST.md)
e leggere [la valutazione preliminare](docs/PUBBLICAZIONE.md).
La licenza MIT riguarda il nostro codice e non autorizza l'accesso al portale,
il riuso di marchi o la diffusione di documenti fiscali.

## Struttura

`main.py` avvia la GUI; `src/ui/` contiene l'interfaccia;
`src/service.py` coordina accesso, utenza e download; `src/models.py` valida i
parametri; `src/security.py` protegge i segreti;
`config/` gestisce le impostazioni; `tests/` contiene test locali.

I moduli precedenti non più utilizzati sono conservati solo nella cartella
locale `_legacy/`, esclusa da Git e dai pacchetti di rilascio.

Licenza: [MIT](LICENSE). La licenza consente anche riusi commerciali del codice;
questa distribuzione rimane gratuita.

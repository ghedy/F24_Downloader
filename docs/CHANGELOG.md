# Modifiche

## 0.2.0a14

- Pacchetto Windows x64 con Python e Firefox inclusi e installer per utente.
- Configurazione dell'installazione in LocalAppData, separata dal programma.
- Icona applicativa, licenze incluse e verifica offline dell'eseguibile.
- Accessi attivi sempre limitati a CIE e SPID Sielte.

## 0.2.0a13

- Font definiti in punti positivi per evitare l'avviso QFont::setPointSize(-1)
  quando i controlli Qt riutilizzano il font di selettori e calendari.
- Primo avvio senza rubrica e senza destinazione precompilata. Le preferenze
  già salvate sul computer continuano a essere caricate dalla configurazione locale.
- Esempio pubblico senza output_dir; esclusioni Git basate sui file ammessi,
  estese a configurazioni, credenziali, backup, documenti e dati locali.
- Controllo del contenuto Git effettivamente in stage, inclusi valori privati
  e percorso dei download, eseguito anche nella CI. Nessun archivio generato.
- Icone SVG incluse esplicitamente nei dati del pacchetto Python e archivi
  cifrati di recupero esclusi dai dati di distribuzione.
- Verifiche di regressione su calendari, font e impostazioni vuote; test Git
  con soli dati sintetici per impedire inclusioni accidentali di dati privati.

## 0.2.0a12

- Rubrica basata su codice fiscale o partita IVA: confronto dell'identificativo
  con la descrizione dell'opzione AdE e invio del valore interno associato.
  Conservati zeri iniziali e compatibilità con i codici interni già registrati.
- Nessuna selezione automatica con più corrispondenze, corrispondenze parziali
  o opzioni disabilitate; interruzione con messaggio leggibile.
- Profilo personale: salto esplicito della fase Cambio utenza nel servizio;
  verificato il passaggio diretto da accesso a Cassetto fiscale.
- Solo SPID Sielte e CIE attivi: gli altri metodi restano visibili in grigio,
  disabilitati nell'interfaccia e bloccati prima di aprire il browser.
- Campi anno e data allineati in una griglia compatta; pulsanti sul bordo
  destro allineati e separatori con trattino corto. Scelta utenza più leggibile
  con descrizione e identificativo fiscale. Nelle finestre più piccole il
  contenuto scorre senza sovrapporre i campi.
- Test locali Firefox con dati sintetici per associazione etichetta/valore,
  codice fiscale, partita IVA con zero iniziale, vecchie rubriche e casi ambigui.
  Da riprovare sul portale reale. Nessun archivio di rilascio rigenerato.

## 0.2.0a11

- Tentativo stampa=P anche dopo timeout della quietanza Q, con un solo errore
  conteggiato se falliscono entrambi i formati. Migliorato il riconoscimento
  dei messaggi di quietanza non stampabile con accenti, apostrofi ed entità HTML.
- Prima del cambio anno, ritorno alla pagina principale del Cassetto e nuova
  apertura di Versamenti, anche se la pagina di stampa è priva di menu.
- Riconosciuti CICS ABEND - IUWX e il messaggio di ripristino riportato dal
  portale. Apertura del collegamento di ripristino verificato e ripetizione
  di anno e periodo; recupero anche durante i download Q o P.
- Tentativi di recupero limitati; errori di sessione persistenti distinti
  dagli anni senza selettore. Interruzione rispettata prima del ripiego P.
- Corrette le frecce dell'anno finale: nessun minimo dinamico che le blocchi
  sull'anno iniziale; se necessario, allineamento dell'anno iniziale.
  Frecce disegnate esplicitamente e pulsanti più larghi per facilitare i clic.
- Prove Firefox con pagine locali: 2025–2026 dopo Q→P, CICS sulla selezione
  anno, sul filtro e durante Q/P, errori persistenti, link di ripristino
  esterno rifiutato e PDF P senza intestazione attachment. Verificati anche
  i clic effettivi sulle frecce dell'interfaccia. Da riprovare sul portale reale.

## 0.2.0a10

- Corretto il blocco di avvio quando le credenziali DPAPI copiate da un altro
  computer/account Windows non sono decifrabili.
- Conservazione dell'archivio cifrato originale con suffisso non-utilizzabile,
  mantenimento di rubrica e impostazioni e avvio con avviso per reinserire
  le credenziali. Nessuna modifica al formato di protezione DPAPI.
- Distinti errori di permessi, configurazione JSON non valida e altri errori
  di avvio, senza mostrare messaggi grezzi contenenti dati privati.
- Letture ordinarie della configurazione prive di effetti collaterali;
  recupero applicato esclusivamente dall'avvio dell'applicazione.
- Verifiche con archivio di altro account simulato, archivio danneggiato,
  cartella non accessibile, salvataggio sul nuovo account e ripristino dopo
  fallimento del recupero. Da confermare con la copia sul secondo PC.

## 0.2.0a9

- Ritorno a Versamenti tramite l'indirizzo del servizio: il menu con
  data-toggle=collapse non può più bloccare il passaggio all'anno successivo.
- Ripresa del selettore anche dopo una pagina di errore priva di menu.
- Tentativo stampa=P soltanto dopo il rifiuto esplicito della quietanza.
  Riconosciuto sia come pagina HTML sia come allegato non PDF.
- Modelli F24 identificati dal prefisso F24_modello e segnalati nel registro
  e nel riepilogo. Confronto duplicati e riordino mantengono tale distinzione.
- Prove locali Firefox sull'intervallo 2020–2026, anno senza selettore,
  periodo vuoto, menu che intercetta il click e passaggio Q rifiutato → P.
  Il comportamento sul portale reale resta da riprovare.

## 0.2.0a8

- Corretto il click sugli anni presenti in pannelli nascosti del carosello.
- Ricerca dell'anno tramite i controlli Anni successivi e Anni precedenti;
  attesa della fine della transizione prima di leggere o cliccare i collegamenti.
- Controllo della visibilità anche per elementi traslati fuori da contenitori
  con overflow nascosto.
- Riconosciuto il giro completo tramite pannelli attivi e anni visibili,
  con limite degli scorrimenti e supporto all'interruzione.
- Scelta del collegamento visibile corretto anche se esistono copie nascoste
  dello stesso href.
- Distinti anno assente e carosello non funzionante: un controllo che non
  scorre produce un errore leggibile, non un falso anno saltato.
- 93 test locali superati, inclusi Firefox con carosello simulato, anno 2020
  nascosto, ricomincio dall'inizio, freccia precedente, animazioni e annullamento.
  Da riprovare sul portale AdE reale.

## 0.2.0a7

- Corretto il percorso F24: dopo Versamenti viene cliccato il collegamento
  Ric=F24&Anno dell'anno richiesto, prima di applicare le date. La ricerca del
  periodo resta nella sezione F24 dello stesso anno.
- Aggiunti anno iniziale e finale nell'interfaccia. Il periodo complessivo viene
  diviso alle soglie dell'anno, con un solo login e cambio utenza.
- Ogni anno usa il proprio selettore e la propria cartella. Gli anni privi del
  selettore vengono segnalati e saltati.
- Riconosciuto NESSUNA OCCORRENZA come risultato vuoto, senza interrompere gli
  anni successivi. Il riepilogo distingue anni assenti e periodi senza risultati.
- Riordino e rinomina estesi alle sole cartelle annuali selezionate, con confronto
  duplicati separato per anno.
- Verificati con Firefox e pagine locali: selezione 2025 prima delle date,
  periodo vuoto, anno assente e percorso continuo 2023–2025 con 2024 assente.
  Il comportamento sul portale reale resta da riprovare.

## 0.2.0a6

- Aggiunto il flag per riordinare tutta la cartella utenza/anno dopo lo scaricamento.
- Aggiunto il pulsante Riordina e rinomina solo la cartella, senza login.
- Il riordino confronta il contenuto dei PDF, elimina direttamente le copie
  verificate e rinomina i documenti riconosciuti nel formato standard.
- Conservati i nomi già corretti; PDF non riconosciuti, file non PDF, altre
  sottocartelle e documenti con dati differenti restano distinti.
- Aggiunti contatori del riordino, interruzione e controlli contro sovrascritture.
- 75 test superati. Applicata su autorizzazione dell'autore la pulizia delle prove:
  6 PDF esaminati, 4 copie duplicate eliminate, 2 quietanze conservate con nomi
  già corretti, nessun errore.

## 0.2.0a5

- Corretto il mancato riconoscimento delle quietanze scaricate più volte.
  La verifica in sola lettura sui quattro PDF della prova ha rilevato due coppie:
  in ciascuna cambiava la sola riga Utente / Data / Ore.
- Aggiunto il confronto del contenuto di tutte le pagine F24, escludendo
  soltanto data e ora di generazione in quell'intestazione.
- Conservate le differenze di protocollo, contribuente, versamento, importi,
  tributi, pagine successive e immagini incorporate.
- Mantenuto il confronto binario per PDF non riconosciuti o privi di testo.
- Aggiunta una cache in memoria per non estrarre ripetutamente lo stesso
  documento durante la sessione.
- Nessuna rimozione delle copie già archiviate. I download successivi possono
  riconoscere anche i file creati dalle versioni precedenti.
- 66 test locali superati, compresa la ripetizione dello scaricamento con
  Firefox e PDF rigenerati: 0 salvati, 2 duplicati, 0 errori.

## 0.2.0a4

- Individuato il FileNotFoundError precedente all'apertura del Cassetto:
  creazione della destinazione su un'unità non disponibile.
- Verifica di disponibilità e scrittura della cartella prima dell'accesso AdE,
  con messaggio che permette di correggere la destinazione senza rifare il login.
- Destinazione e pausa valide vengono ricordate quando si avvia il download.
- Ingresso attraverso i collegamenti forniti dall'autore: Vai al servizio del
  Cassetto fiscale, Vai a Consultazioni, Versamenti; successiva ricerca per periodo.
- Usato l'indirizzo /CassHomeWeb/ del collegamento effettivo, al posto del
  precedente ingresso diretto /CassHomeWeb/home.
- Gestita anche l'apertura del servizio in una nuova scheda; il download usa
  la pagina corretta. Il recupero sessione ripercorre Consultazioni e Versamenti.
- Aggiunte prove con Firefox e pagine sintetiche per entrambi i tipi di apertura,
  oltre ai controlli di destinazione prima del login. 56 test locali superati;
  da riprovare sul portale reale.

## 0.2.0a3

- Corretto il blocco dopo la conferma utenza: il programma non riapre più il
  selettore per confrontarne il valore iniziale con la scelta appena inviata.
- Mantenuti il controllo delle opzioni autorizzate, la selezione del codice
  richiesto e la conferma del ritorno alla home del portale.
- Aggiunte le fasi nel registro. Gli errori di navigazione indicano la fase
  senza includere URL completi o dati dei form.
- In caso di errore Firefox resta aperto per leggere la pagina del portale;
  il pulsante Chiudi browser termina la sessione e permette una nuova prova.
- 50 test locali superati, compresa la regressione con un selettore che
  riparte dal profilo personale se riaperto e il mantenimento della finestra
  applicativa in caso di errore.
- Il log della prova reale ha confermato che il blocco precedente avveniva
  nel secondo controllo del selettore. Lo scaricamento reale resta da riprovare.

## 0.2.0a2

- Ripristinata la selezione del metodo OTP MySielteID quando richiesta dalla pagina.
- Ripristinato il pulsante Prosegui dopo l'inserimento completo dell'OTP Sielte.
- Ripristinati Autorizza finale Sielte e Prosegui finale CIE.
- Il codice OTP non viene letto nell'applicazione né registrato: nella pagina
  viene verificato solo che contenga sei cifre.
- Ripristinate l'attesa di stabilizzazione dopo il login e l'attesa di propagazione
  del cambio utenza.
- Ripristinato il recupero della sessione del Cassetto fiscale fino a tre tentativi,
  limitato ai messaggi espliciti di ripristino.
- Gestiti i redirect Firefox con NS_BINDING_ABORTED.
- Mantenuti il controllo dell'utenza attiva e la distinzione fra modello e quietanza.
- Aggiornati testi dell'interfaccia e istruzioni.
- 46 test locali superati, comprese le conferme del login con Firefox e pagine
  simulate. Il login su AdE con una vera identità digitale resta da riprovare.

## 0.2.0a1

Prima interfaccia desktop e preparazione locale del progetto.
Le conferme finali del login erano state rese manuali durante la riorganizzazione:
questa modifica interrompeva l'automatismo del programma originale.

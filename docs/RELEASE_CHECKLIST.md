# Verifica prima del rilascio

Repository pubblico: [ghedy/F24_Downloader](https://github.com/ghedy/F24_Downloader).
Versione iniziale: 0.2.0a13 (alpha). Pacchetto Windows: 0.2.0a14. Le voci non spuntate indicano verifiche
ancora da completare o ripetere prima di versioni successive.

## Verifiche automatiche

- [x] Eseguiti 162 test su una copia pulita dei soli file Git (0.2.0a13).
- [x] Dipendenze installate in un ambiente virtuale nuovo per il pacchetto Windows a14.
- [x] Firefox installato e incluso nel pacchetto; download PDF sintetico verificato nell’eseguibile.
- [x] Verificati 53 file con `python tools/check_repository.py --staged`; dati locali esclusi.
- [ ] Esaminare `git diff --cached --stat` e verificare che i dati locali siano ignorati.
- [ ] Riesaminare dipendenze, relative licenze e attribuzioni.

## Collaudo autorizzato sul portale

- [ ] SPID Sielte: credenziali, MFA e consenso.
- [ ] CIE: percorso credenziali/app nel browser.
- [ ] CNS e Fisconline/Entratel: mantenuti disabilitati fino al collaudo dei relativi percorsi.
- [ ] Altri gestori SPID: mantenuti disabilitati fino al collaudo del percorso tramite portale.
- [ ] Profilo personale e almeno un'utenza collegata.
- [ ] Utenza non autorizzata: blocco prima del download.
- [ ] Dopo la conferma, verificare sul portale e sui documenti scaricati l'utenza
      effettiva. Il valore iniziale del selettore riaperto non è una prova.
- [ ] Periodo con quietanze, periodo vuoto, più pagine.
- [ ] Confronto tra numero totale sul portale e documenti elaborati.
- [ ] PDF quietanza autentico, quietanza mancante e PDF non riconosciuto.
- [ ] Riavvio della stessa ricerca: stessa quietanza saltata anche se cambiano data/ora di stampa.
- [ ] Interruzione durante MFA, raccolta elenco e download.
- [ ] Chiusura della finestra durante un'operazione.
- [ ] Errore dopo il cambio utenza: fase nel registro e browser aperto fino al comando di chiusura.
- [ ] Migrazione della vecchia configurazione e rimozione dei segreti dal JSON.
- [ ] Credenziali ricordate, nuovo avvio e comando per dimenticarle.

## Decisione di pubblicazione

- [ ] Chiarire le condizioni applicabili di AdE e del gestore di identità.
- [ ] Valutare eventuale risposta scritta AdE o revisione legale.
- [ ] Confermare disponibilità del nome e titolarità/licenza del codice.
- [ ] Confermare che la licenza MIT, che consente anche riusi commerciali, sia voluta.
- [x] Segnalazioni private di sicurezza abilitate nel repository GitHub.
- [ ] Controllare che esempi, immagini e documentazione usino dati sintetici.
- [ ] Se esiste già una cronologia Git, controllarla: .gitignore non rimuove
      segreti già presenti nella cronologia. Revocare quelli eventualmente esposti.
- [x] Pubblicazione autorizzata dall'autore.

## Preparazione GitHub

La cartella di lavoro contiene documenti e configurazione privata, che
restano locali. Git include solo i sorgenti ammessi: la configurazione reale,
le credenziali e la destinazione dei PDF non fanno parte dei file pubblicati.
La configurazione di esempio è senza utenze, password e percorso dei download.

Prima del commit eseguire `git add .`, `python tools/check_repository.py --staged`
e controllare `git diff --cached --stat`. La CI ripete la verifica della lista
dei file e dell'esempio pubblico. Non caricare l'intera cartella con il browser
e non forzare l'aggiunta di file ignorati.

Sono inclusi CI Windows, test, README, MIT, SECURITY e modello issue.
Nessun archivio è necessario per la pubblicazione tramite Git.
Il repository remoto è ghedy/F24_Downloader; gli aggiornamenti passano dai soli file gestiti da Git.


## Riordino cartella

- [ ] Flag disattivato: nessuna rimozione delle copie preesistenti.
- [ ] Flag attivato: riordino della cartella dopo lo scaricamento.
- [ ] Pulsante locale: nessuna richiesta di login o browser.
- [ ] Nomi arbitrari: confronto per contenuto e rinomina dei PDF riconosciuti.
- [ ] Copie rigenerate: una sola quietanza conservata.
- [ ] Stessa data e importo ma protocollo diverso: conservazione di entrambe.
- [ ] Seconda esecuzione del riordino: nessuna ulteriore modifica.
- [ ] Altre sottocartelle e file non PDF esclusi dal riordino.

## Più anni e selezione anno

- [ ] Singolo anno 2025: click sul collegamento Ric=F24&Anno=2025 prima delle date.
- [ ] Più anni: un solo login, un selettore per anno e cartelle separate.
- [ ] Primo e ultimo anno con date parziali; anni intermedi completi.
- [ ] Anno senza selettore: saltato, con prosecuzione sul successivo.
- [ ] NESSUNA OCCORRENZA: risultato vuoto senza errore.
- [ ] Totali cumulativi, riepilogo degli anni saltati e duplicati per anno.
- [ ] Riordino limitato alle cartelle annuali selezionate.

## Carosello degli anni

- [ ] Anno richiesto già visibile: click senza scorrimento.
- [ ] Anno 2020 in un pannello nascosto: scorrimento e click del collegamento.
- [ ] Anno assente: arresto dopo un giro completo, poi anno successivo.
- [ ] Freccia successiva non disponibile: utilizzo di Anni precedenti.
- [ ] Attesa delle animazioni e gestione dei collegamenti duplicati nascosti.
- [ ] Carosello bloccato: errore leggibile senza falso anno assente.
- [ ] Interruzione richiesta durante lo scorrimento.


## Ritorno a Versamenti e formato P

- [ ] Intervallo 2020–2026: ritorno al selettore a ogni cambio anno.
- [ ] Menu Versamenti con data-toggle=collapse: apertura della pagina del servizio.
- [ ] Quietanza rifiutata esplicitamente: tentativo dello stesso documento con stampa=P.
- [ ] Modello salvato: prefisso F24_modello, segnalazione nel registro e nel riepilogo.
- [ ] Modello già presente: duplicato riconosciuto anche dopo il riordino.
- [ ] Timeout Q: singolo tentativo P; un solo errore per documento se falliscono entrambi.
- [ ] Pagina di stampa priva di menu: ritorno alla pagina principale e a Versamenti per l'anno seguente.


## Trasferimento su un altro PC

- [ ] Copia con archivio DPAPI del primo PC: avviso, mantenimento utenze e impostazioni, apertura UI.
- [ ] Archivio cifrato originale conservato come credentials.bin.non-utilizzabile, escluso dal rilascio.
- [ ] Reinserimento e memorizzazione sul nuovo PC; riavvio senza ulteriori avvisi.
- [ ] Sul PC originale: credenziali ancora disponibili senza creare copie aggiuntive.
- [ ] Permessi insufficienti e JSON non valido: messaggi distinti, nessuna perdita di file.
- [ ] Cartella di destinazione verificata sul computer corrente prima dell'accesso.


## CICS e selettore anno finale

- [ ] CICS ABEND - IUWX dopo il click anno o il filtro: ripristino dal collegamento e nuova selezione.
- [ ] Errore CICS durante Q o P: ripristino e tentativo dello stesso documento/formato.
- [ ] Errore persistente: limite dei tentativi e browser aperto per verifica.
- [ ] Interruzione dopo timeout Q: nessun ulteriore tentativo P.
- [ ] Frecce dell'anno finale: incremento, decremento e allineamento dell'anno iniziale.
- [ ] PDF P scaricati e rinominati distintamente dalle quietanze; riepilogo corretto.


## Identificativo fiscale, profilo personale e campi periodo

- [ ] Partita IVA nella descrizione AdE: scelta del relativo codice interno.
- [ ] Codice fiscale e vecchi codici interni: scelta confermata senza riaprire il menu.
- [ ] Zeri iniziali conservati; nessuna corrispondenza parziale o opzione disabilitata selezionata.
- [ ] Più posizioni associate allo stesso codice fiscale/partita IVA: interruzione senza invio del form.
- [ ] Profilo personale: nessuna apertura della pagina Cambia utenza, prosecuzione al Cassetto.
- [ ] Solo Sielte e CIE attivi; altri metodi grigi e non selezionabili.
- [ ] Anni e date compatti, pulsanti allineati e separatori con trattino corto.

## Pacchetto Windows 0.2.0a14

- Suite applicativa: 164 test superati; i due nuovi test sul runtime incluso
  e i controlli mirati di avvio/configurazione sono superati separatamente.
- Eseguibile verificato senza cache browser esterna: rubrica iniziale vuota,
  soli CIE/Sielte, DPAPI, interfaccia e icone, Firefox incluso, download e
  lettura di un PDF sintetico. Nessun accesso al portale reale durante il controllo.
- Installer per utente con preferenze in LocalAppData, separate dal programma.
- Pacchetto non firmato digitalmente, indicato nelle istruzioni di installazione.

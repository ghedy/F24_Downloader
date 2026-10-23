# Pubblicazione: valutazione preliminare al 18 ottobre 2026

Questo documento riassume verifiche e punti aperti. Non costituisce un
parere legale né un'autorizzazione dell'Agenzia delle Entrate.

## Risposta pratica

È possibile preparare e distribuire gratuitamente un programma proprio,
ma la gratuità non dimostra che ogni modalità di automazione del portale
sia consentita. Non è stata individuata nelle fonti consultate
un'autorizzazione generale all'automazione del download delle quietanze.
L'assenza di un divieto trovato non equivale a un permesso.

Distinguere la licenza del codice dalle condizioni di utilizzo di AdE e del
gestore SPID/CIE. Occorre leggere le condizioni concretamente applicabili
all'account e al servizio utilizzato, comprese quelle accettate in area riservata.
Il programma non effettua questa verifica contrattuale per l'utente.

Le FAQ AdE confermano accesso con identità digitale e servizi secondo
abilitazioni; per le società sono previsti gestori/operatori incaricati.
La guida per rappresentanti e persone di fiducia descrive accessi abilitati.
La disponibilità di un'utenza nel portale non sostituisce la verifica delle
autorizzazioni necessarie e delle finalità del trattamento.

Fonti ufficiali consultate:

- [FAQ servizi telematici AdE](https://telematici.agenziaentrate.gov.it/Main/FAQ.jsp)
- [Guida AdE per rappresentanti e persone di fiducia](https://www1.agenziaentrate.gov.it/web_app_entrate/accesso_servizi_online.html)
- [GDPR, testo ufficiale](https://eur-lex.europa.eu/eli/reg/2016/679/oj/?locale=it),
  in particolare principi dell'art. 5 e sicurezza dell'art. 32.

I documenti fiscali possono contenere dati personali. La distribuzione di un
programma locale e il trattamento di documenti dei clienti sono situazioni
diverse; ruoli e obblighi privacy dipendono da chi tratta concretamente i dati.
La sola esclusione dei file da Git non esaurisce tali obblighi.

## Nome

Nome consigliato: **F24 Downloader**; repository suggerito: `f24-downloader`.
Corregge il refuso di `F24_Downlader` / `F24_Dowloader` ed è descrittivo della funzione.
Non è stata eseguita una ricerca di anteriorità UIBM/EUIPO:
non è una certificazione della disponibilità del nome.

Non usare loghi ufficiali, sigilli o dichiarazioni di approvazione da parte di AdE.
Nell'interfaccia e nel README compare l'indicazione di progetto indipendente.

## Prima della distribuzione pubblica

1. Verificare condizioni del servizio applicabili e del gestore di identità.
2. Per ridurre l'incertezza, chiedere tramite i canali ufficiali AdE se un
   programma locale con accesso dell'utente, MFA manuale, lettura delle sole
   quietanze autorizzate e download sequenziale sia ammesso, e se esistano
   interfacce dedicate o limiti da rispettare. Non è stato inviato alcun messaggio.
3. Se la risposta non chiarisce gli aspetti contrattuali, sottoporre il flusso
   concreto a un professionista legale prima del rilascio pubblico.
4. Verificare nome, titolarità del codice, licenze delle dipendenze e attribuzioni.
5. Collaudare il portale con un'utenza autorizzata senza pubblicare dati reali.

La licenza MIT predisposta è una scelta tecnica iniziale per la distribuzione
gratuita e aperta del nostro codice. Consente anche riutilizzo e vendita da
parte di terzi: verificare che questa libertà corrisponda all'intento del titolare.

## Quesito pronto per l'assistenza AdE

Desidero distribuire gratuitamente il codice di un'applicazione desktop
indipendente che, sul computer dell'utente, apre un browser visibile e permette
l'accesso personale ai servizi AdE. Il secondo fattore viene completato dall'utente; per Sielte e CIE
il programma conferma automaticamente i pulsanti successivi, come nel flusso originale. L'applicazione consulta esclusivamente utenze già autorizzate e
scarica in sequenza le quietanze F24 di un periodo scelto, senza inviare
documenti allo sviluppatore né aggirare controlli di accesso.

Questa modalità è compatibile con le condizioni applicabili al Cassetto fiscale?
Sono previste autorizzazioni, interfacce dedicate, limiti di frequenza o ulteriori
condizioni per la distribuzione di tale software?

Desidero verificare i requisiti applicabili alla distribuzione e all'utilizzo
del programma.

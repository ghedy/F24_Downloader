# F24 Downloader per Windows

Versione di prova 0.2.0a14. Programma gratuito e indipendente, non affiliato
all'Agenzia delle Entrate. Accessi attualmente attivi: CIE e SPID Sielte.
Gli altri gestori non sono ancora disponibili. Il secondo fattore viene
sempre completato personalmente dall'utente nel browser o nell'app.

## Installazione

Windows 10 (1809 o successivo) / Windows 11, processore x64.
Scarica F24-Downloader-0.2.0a14-windows-x64-setup.exe ed eseguilo.
L'installazione avviene per il tuo utente, senza richiedere privilegi amministrativi.
Python e il Firefox usato dal programma sono inclusi: non vanno installati a parte.
Il pacchetto non ha una firma digitale; Windows potrebbe mostrare un avviso.
Verifica provenienza, versione e checksum prima dell'esecuzione.

Al primo avvio scegli la cartella dei PDF e configura soltanto le utenze
per cui disponi di autorizzazione. Non sono incluse utenze, password o
cartelle personali dell'autore. Il profilo personale non richiede cambio utenza.

## Dati e aggiornamenti

Preferenze e rubrica dell'installazione sono salvate in:
%LOCALAPPDATA%\F24Downloader\config.json
Le credenziali, solo se scegli di ricordarle, sono cifrate con Windows DPAPI in
credentials.bin nella stessa cartella, per il tuo account Windows.
Non trasferire questo file ad altri computer. I PDF rimangono nella cartella scelta.
Aggiornamenti e disinstallazione conservano questi dati personali.
Per eliminare anche la configurazione, chiudi il programma e rimuovi
manualmente la cartella %LOCALAPPDATA%\F24Downloader.

La copia avviata dai sorgenti mantiene la propria configurazione in config/:
non viene importata automaticamente nell'installazione.

## Limiti e riferimenti

Il servizio AdE può cambiare: controlla documenti e riepilogo di fine scaricamento.
Un modello F24 (formato P) non sostituisce una quietanza: viene indicato separatamente.
Il programma non include telemetria applicativa; accede ai portali AdE e al
gestore di identità durante l'autenticazione.

Codice, istruzioni e segnalazioni: https://github.com/ghedy/F24_Downloader
Sito: https://quadra.acortina.it/
Licenza MIT. Licenze dei componenti inclusi: _internal/third-party.

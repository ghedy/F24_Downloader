# Sicurezza

Non allegare password, PIN, OTP, cookie, configurazioni private, schermate
autenticate, codici fiscali o quietanze a issue e pull request.

Per descrivere un problema usa dati sintetici e indica solo versione,
metodo di accesso, fase dell'errore e messaggio applicativo privo di dati personali.

In caso di vulnerabilità non pubblicare dettagli sfruttabili in una issue
pubblica. Usare le [segnalazioni private di sicurezza di GitHub](https://github.com/ghedy/F24_Downloader/security/advisories/new),
abilitate per questo repository. Non includere credenziali reali, OTP o documenti
fiscali neppure nella segnalazione privata: descrivere il problema con dati sintetici.

Le credenziali sono protette con Windows DPAPI. Questa protezione non difende
da software che opera già con i permessi dell'account Windows dell'utente.
I PDF e la rubrica sono memorizzati localmente senza cifratura applicativa.
Le dipendenze devono essere riesaminate prima di ogni rilascio.

Il progetto non richiede credenziali agli sviluppatori e non raccoglie
telemetria applicativa. Le comunicazioni necessarie al servizio avvengono con
AdE e il gestore dell'identità digitale.


Le credenziali non decifrabili all'avvio vengono conservate cifrate come
`config/credentials.bin.non-utilizzabile-…`; l'applicazione prosegue richiedendo
nuove credenziali. Può accadere dopo il trasferimento del programma a un altro
computer/account Windows oppure per un archivio danneggiato. La rubrica e le
impostazioni restano disponibili. Anche questi archivi conservati sono privati:
non allegarli a segnalazioni e non pubblicarli.

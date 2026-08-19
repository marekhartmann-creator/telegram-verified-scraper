# Projekt: Apify Actor — Telegram Channel Scraper (verified)

**Vlastník:** Marek Hartmann
**Založené:** 19. 8. 2026
**Stav:** v0.6 — repo na GitHube, CI zelené, 46 testov, 8/8 živých stavov, Actor overený end-to-end pod Apify SDK; zostáva build a publikovanie na Apify
**Repo:** https://github.com/marekhartmann-creator/telegram-verified-scraper (publikované 19. 8. 2026)
**Časový rozpočet:** 2–4 dni
**Peňažný rozpočet:** 0 € (podmienka: žiadna investícia pred prvým príjmom)

---

## 1. Cieľ

Publikovať na Apify Store platený Actor, ktorý sťahuje príspevky z verejných
Telegram kanálov, a zarobiť na ňom cez revenue share 80/20. Nie cvičenie —
príjmový kanál a zároveň verejný dôkaz kvality do portfólia.

## 2. Prečo práve Telegram (trhové dáta, overené 19. 8. 2026 cez api.apify.com/v2)

Segment má preukázateľný obrat a jedného veľkého nespokojného hráča:

| Actor | používatelia | noví/30d | behy/30d | hodnotenie |
|---|---|---|---|---|
| tri_angle/telegram-scraper | 4 254 | 164 | 47 391 | **2,21** (16) |
| lofomachines/telegram-keyword-search-scraper | 840 | **245** | 8 070 | 5,0 (1) |
| webfinity/telegram-channel-content-media-v2 | 942 | 58 | 1 772 | 5,0 (7) |
| truefetch/telegram-channel-message | 754 | 92 | 5 195 | 4,47 (3) |
| automation-lab/telegram-scraper | 604 | 91 | 2 779 | 5,0 (2) |

**Korekcia pôvodného predpokladu.** Vstupný prieskum hovoril o „diere bez
dominantného konkurenta" a o hodnotení incumbenta 1,42. Overenie ukázalo:

* hodnotenie incumbenta **stúplo na 2,21** a 30. 7. 2026 nasadili novú verziu —
  Actor sa opravuje, nie je opustený;
* **lofomachines získava viac nových používateľov mesačne než incumbent**
  (245 vs 164) a existuje od februára 2026. Dopyt, ktorý incumbentovi uteká,
  už má kam ísť.

Diera teda nie je prázdna. Vstupujeme ako ~6. hráč do segmentu, kde traja majú
hodnotenie 5,0. To je vedomé rozhodnutie, nie prehliadnutie.

## 3. Reprodukované zlyhanie (to, na čom staviame)

Overené 19. 8. 2026:

1. **Neexistujúci kanál nevracia chybu.** `t.me/s/<preklep>` vráti HTTP 200 a
   normálnu stránku bez akéhokoľvek kanálového markupu. Naivný scraper napočíta
   0 príspevkov, ohlási úspech a vyfakturuje. → Toto je hlavný vektor tichého
   zlyhania a je reprodukovateľný na počkanie.
2. **ID príspevkov nie sú súvislé.** `?before=100` na georgenews vrátilo ID
   80, 85, 95–97, 99 — diery po zmazaných a servisných správach. Stránkovanie
   počítané aritmeticky (`min_id − veľkosť_stránky`) preskočí reálne príspevky.
3. Pôvodná sťažnosť („georgenews nevracia výsledky") **nie je dnes
   reprodukovateľná** — kanál sa načíta normálne. Buď to opravili, alebo
   používateľ zadal zlý vstup (čo je presne prípad č. 1).

## 4. Rozsah

**IN:** verejné kanály — príspevky, views, reakcie, media URL, forwardy,
odpovede, edity, hashtagy, mentions, link preview; filter podľa dátumu a
kľúčových slov.

**OUT (natrvalo, nie „zatiaľ"):** členovia kanálov, používateľské profily,
telefónne čísla, akékoľvek osobné údaje. Dôvod: GDPR + Telegram ToS + Marek je
v EU. Napísané aj do listingu ako predajný argument pre EU firmy.

**OUT (v1, kandidát na v2):** globálne vyhľadávanie naprieč Telegramom podľa
kľúčového slova — ťažšia úloha a už ju drží lofomachines.

## 5. Architektúra

Štyri vrstvy, pričom hodnotu nesie 1. a 4., nie 2.:

1. **Preflight (`tg/preflight.py`)** — klasifikuje handle do 7 stavov ešte
   predtým, než sa uverí akémukoľvek počtu príspevkov. Primárny signál: či `/s/`
   stránka vôbec vyrenderovala `.tgme_channel_info` + `.tgme_channel_history`.
   Ak nie, rozhoduje sa z obyčajnej `t.me/<handle>` stránky.
2. **Zber (`tg/fetch.py`, `tg/parse.py`)** — httpx + selectolax proti
   server-renderovanému preview. **Zámerne bez prehliadača:** headless Chrome by
   znásobil pamäť, a teda účet zákazníka, na stránkach, ktoré sú statické HTML.
   Stránkovanie výhradne cez Telegramov vlastný `data-before` odkaz, nikdy
   aritmetikou nad ID.
3. **Orchestrácia (`tg/scraper.py`)** — normalizácia handle, stránkovanie,
   filtre, streamovanie dávok do datasetu počas behu.
4. **Verifikácia (`tg/verify.py`)** — rozhoduje verdikt `OK` /
   `EMPTY_VERIFIED` / `PARTIAL` / `FAILED`. Kľúčové pravidlo: nula príspevkov je
   platný výsledok **iba** ak stav je `PUBLIC_PREVIEWABLE`, aspoň jedna stránka
   sa načítala a metadáta kanála neprotirečia (kanál hlásiaci 1 204 fotiek s
   nulou príspevkov = zlyhanie načítania, nie prázdny kanál).

`failOnUnreadableChannel=true` (default) → beh skončí ako FAILED s dôvodom.

Toto je priamy prenos Marekovho read-back/verify vzoru z browser automation do
scrapingu — rovnaká myšlienka, iný cieľ.

## 6. Cenotvorba

* Actor start: **$0** — konkurencia si účtuje $0,005–0,01 za štart, takže
  neúspešný beh ich stojí peniaze. Nulový štart je marketingový argument aj
  technický záväzok.
* Za overený príspevok: **$0,002** ($2 / 1 000 výsledkov — presne stred pásma,
  ktoré Apify uvádza ako bežné, $1–10 / 1 000).
* Neúčtuje sa nič, čo neprešlo verifikáciou → sľub „prázdny beh je zadarmo"
  vychádza z architektúry, nie z dobrej vôle.

Konkurencia za výsledok: webfinity $0,01 · tri_angle $0,005 · lofomachines
$0,0025 · automation-lab $0,001 · truefetch $0,00035.

## 7. Očakávaný výnos (triezvo)

Jeden používateľ s denným behom nad ~200 príspevkami ≈ **$12/mes hrubého**,
z toho ~$9,60 Marekovi. Zisk teda závisí od počtu **opakujúcich sa** používateľov.

* 1. mesiac: $5–25
* 3. mesiac (pri 3–4 dobrých recenziách): $60–200
* 6. mesiac pri dobrom ranku: $200–600
* Najčastejší scenár na Apify: $0–15 mesačne donekonečna

Benchmark: lofomachines má 8 070 behov/30 dní pri $0,0025 za výsledok — pri
odhade 50–200 výsledkov na beh je to rádovo $1 000–4 000 hrubého mesačne, za pol
roka od nuly. (Počet výsledkov na beh Apify verejne neukazuje — rád veličiny je
podložený, presné číslo nie.)

**Skutočná bariéra nie je technika, ale prvé tri recenzie a nájditeľnosť.**

## 8. Stav a build log

**19. 8. 2026**

* Overené trhové dáta cez per-actor endpointy (nie store-search súhrny).
* Reprodukované tiché zlyhanie na neexistujúcom handle + nesúvislé ID.
* Postavené: `errors.py`, `preflight.py`, `parse.py`, `fetch.py`, `verify.py`,
  `scraper.py`, `main.py`, Apify obal (actor.json, input_schema, dataset_schema,
  pay_per_event, Dockerfile), README ako listing.
* **36 pytest testov, zelené.** Vrátane priamej reprodukcie incumbentovho bugu:
  `test_unknown_handle_fails_loudly_instead_of_returning_empty`.
* Limit prostredia: cloudový kontajner nemá sieťový prístup na `t.me`. v0.1 bola
  preto postavená proti ručne napísaným fixtures.

**19. 8. 2026 — v0.2, živá verifikácia (Windows, Python 3.14, cez Bridge Runtime)**

* 38 testov zelených aj na Windowse.
* Živý beh proti reálnemu Telegramu: `durov` 25 príspevkov (ID 503–543, 2 diery),
  `telegram` 25 (1 diera), `georgenews` 25 (2 diery, 3 media), `durov_russia`
  25 (6 dier). Views, dátumy, ID a stránkovanie sedia.
* **Dve chyby, ktoré by fixtures nikdy neodhalili:**
  1. Reakcie sa parsovali na `.tgme_reactions_reaction`; Telegram v skutočnosti
     renderuje `span.tgme_reaction` v troch tvaroch — `<i class="emoji"><b>😁</b></i>171`,
     custom `<tg-emoji emoji-id="…">55.2K`, a platený `tgme_reaction_paid`
     s ikonou hviezdy. Prepísané, počet sa berie ako textový uzol za emoji.
     Predtým: `reakcie=0` na príspevku so 79 500 reakciami.
  2. Klasifikátor označil neexistujúci handle ako `NOT_A_CHANNEL` namiesto
     `NOT_FOUND`. Verdikt bol správne FAILED, ale správa bola zavádzajúca.
     Skutočný podpis neexistujúceho handle (overený naživo): žiadny
     `.tgme_page_title`, žiadny `.tgme_page_extra`, `og:image` =
     `telegram.org/img/t_logo*.png` a veta "If you have Telegram, you can
     contact @X right away." Fixtures prepísané na reálny markup.
* Doplnené: `sys.stdout.reconfigure` v smoke teste (Windows konzola je cp1250 a
  padala na emoji).
* **Poučenie do listingu:** práve tieto dve chyby sú presne trieda chýb, ktorú
  incumbent nezachytí — parser tichého vráti 0 reakcií a zle pomenovaný stav.
  Verifikačná vrstva ich odhalila okamžite, lebo verdikt nesedel s obsahom.

**19. 8. 2026 — v0.4, druhé kolo živej verifikácie**

* Preverených 19 reálnych handle-ov, aby som našiel vzorky stavov, ktoré som
  dovtedy len odhadoval. Výsledok: **klasifikátor mal vážnu chybu.**
  * `rt_russian` (386 tisíc odberateľov) dostal verdikt **NOT_FOUND** — teda
    "skontroluj si preklep" na kanáli, ktorý existuje. Príčina: Telegram tam
    posiela rovnakú kostru stránky ako pri neexistujúcom handle, líši sa jedna
    veta: *"you can **view posts by** @X"* (kanál existuje, preview nedáme)
    oproti *"you can **contact** @X"* (nič tu nie je).
  * `mdk` vracia rovno marketingovú stránku Telegramu bez `.tgme_page` —
    handle je zablokovaný, nie neexistujúci. Nový podpis → `RESTRICTED`.
  * `zerohedge` hovorí "view and join", ale má počet odberateľov → počítadlá
    teraz prebíjajú boilerplate.
  * Ironicky: bola to presne tá chyba, proti ktorej je celý produkt postavený,
    len o krok vedľa — namiesto tichého prázdna nahlas nesprávny dôvod.
* `scripts/smoke.py` je odteraz **živá regresná sada**: 8 handle-ov s očakávaným
  stavom, pri nezhode končí exit kódom 1. Aktuálne **8/8**.
* Overené naživo: PUBLIC_PREVIEWABLE, NOT_FOUND, EXISTS_NO_PREVIEW (dva rôzne
  tvary), NOT_A_CHANNEL (skupina), RESTRICTED. Neoverené: PRIVATE, UNREACHABLE.
* Pridaná **paralelizácia kanálov** (`maxConcurrency`, default 5). Telegram
  round-tripy trvajú ~4-10 s na kanál; sériovo by zákazník platil compute za
  čakanie.
* **Dve chyby nájdené až prvým skutočným spustením Actora:**
  1. `Dockerfile` mal `CMD python3 -m src.main` — to modul len naimportuje a
     skončí. Actor by na Apify naštartoval a hneď dobehol bez práce. Správne
     je `-m src`.
  2. `create_proxy_configuration` vyhodí výnimku, keď nie je heslo k Apify
     Proxy (lokálny beh, plán bez proxy) a zabije celý beh. Teraz je proxy
     voliteľná — pri chybe sa loguje varovanie a ide sa priamo.
* Pridané: GitHub Actions CI (pytest na 3.11-3.13), `.gitattributes` (LF),
  ukážkový `storage/.../INPUT.json`, prvý git commit (40 súborov).

**19. 8. 2026 — v0.6, prvý skutočný beh Actora**

Spustené pod reálnym Apify SDK (4.0.1) v lokálnom režime. Toto odhalilo veci,
ktoré ani testy, ani živý scraping nemohli:

* `Dockerfile` mal `CMD python3 -m src.main` → modul sa naimportuje a proces
  skončí. Na Apify by Actor „úspešne" dobehol za sekundu a neurobil nič.
  Opravené na `-m src`.
* `create_proxy_configuration` padne, keď nie je heslo k Apify Proxy. Zabíjalo
  to celý beh. Proxy je teraz voliteľná.
* `RUN_SUMMARY` sa ukladal bez `content_type`, čiže bez prípony `.json` a
  neotvoriteľný v Console. Opravené.
* `textHtml` zdvojnásobuje veľkosť každej položky → nový prepínač `includeHtml`,
  default vypnutý.

**Overenie sľubu produktu end-to-end:**

| beh | vstup | výsledok |
|---|---|---|
| 1 | `durov`, `telegram` | exit **0**, 50 overených príspevkov, 2/2 kanály |
| 2 | `durov`, `georgnews_typo_xx` | exit **1**, beh FAILED s dôvodom |

Druhý riadok je celý produkt: incumbent by na tom istom vstupe ohlásil úspech,
vrátil neúplný dataset a vyfakturoval.

**19. 8. 2026 — v0.7, nasadené na Apify**

* Actor vytvorený z verejného GitHub repa (bez OAuth, cez „Another Git provider"
  — verejné repo nepotrebuje deployment key).
* **Build 0.0.1: Succeeded** za 15 s, $0,003.
* **Prvý ostrý beh na Apify: Succeeded, 101 výsledkov, 18 s, $0,002.** Dataset
  view „Posts" sedí, reakcie sa parsujú (80 200 / 227 700), views aj ID sedia.
* Vyplnené Display information: názov `Telegram Channel Scraper - Verified Posts`
  (kľúčové slová dopredu kvôli vyhľadávaniu v Store), popis do 300 znakov,
  kategórie Social media / Automation / Developer tools.
* Apify si vyžiadal **output schema** pred publikovaním. Doplnené:
  `.actor/dataset_schema.json` s plnou definíciou polí (predtým prázdne `fields`)
  a `.actor/key_value_store_schema.json` pre `RUN_SUMMARY`.
* Pri tom padlo rozhodnutie: **verifikačné reporty už nejdú do datasetu.**
  Dataset je odteraz čisto jeden riadok = jeden príspevok (a jediné, za čo sa
  platí); reporty žijú v key-value store. Export je tým pádom čistý.

## 9. Čo ďalej (poradie)

1. ~~Živý smoke test~~ — hotové 19. 8. 2026, dve chyby nájdené a opravené.
2. ~~Doplniť živé prípady~~ — hotové, chýba už len vzorka súkromného kanála
   (`PRIVATE`); jeho fixture je stále odhad, nie zachytený markup.
3. **Blokované na Marekovi:** `gh auth login` (GitHub CLI je nainštalovaný, ale
   neprihlásený) → vytvoriť repo a pushnúť. Commit je pripravený.
4. Prepojiť repo s Apify, build.
5. Nastaviť pay-per-event v Apify Console podľa `.actor/pay_per_event.json`.
6. Publikovať, doplniť listing (README) a screenshot výstupu.
7. Prvé recenzie: požiadať o feedback v Apify Discorde a v jednom OSINT/Telegram
   komunitnom vlákne — bez toho Actor nikto nenájde.

## 10. Riziká

* **Telegram zmení markup** → parser prestane fungovať. Zmiernenie: každé pole
  je voliteľné, žiadny crash; ale tiché prázdno by bolo fatálne pre celý sľub
  produktu — preto verifikačná vrstva kontroluje aj to, či hlavička vôbec
  vyrenderovala.
* **Rate limiting / blokovanie IP** pri veľkých behoch → Apify proxy je v inpute,
  ale netestované pod záťažou.
* **Segment sa zaplní skôr, než získa recenzie.** Toto je hlavné biznis riziko,
  nie technické.

## 11. Obmedzenia prostredia

* **Bridge Runtime beží pod účtom `SYSTEM`** (`C:\WINDOWS\system32\config\systemprofile`),
  nie pod Marekovým používateľom. Nevidí teda jeho `gh auth login` ani Git
  Credential Manager — testy, scraping a lokálne behy cez Bridge fungujú, ale
  `git push`, `gh` a čokoľvek autentifikované musí spustiť Marek sám.
  Riešiteľné prehodením služby na jeho účet alebo vlastným `GH_TOKEN` pre Bridge.
* Cloudový kontajner Cowork session nemá sieťový prístup na `t.me`, preto všetka
  živá verifikácia prebieha cez Bridge na Marekovom PC.

## 12. Publikovanie

* Repo: pushnuté 19. 8. 2026, 39 súborov, 2 commity, `main`.
* GitHub Actions `tests`: **success** (pytest na Python 3.11/3.12/3.13, Linux) —
  prvé potvrdenie, že kód beží aj mimo Windows/3.14, kde bol vyvíjaný.


## 13. Publikovane (19. 8. 2026)

**https://apify.com/marekhartmann/telegram-channel-scraper** - verejne na Apify Store,
zadarmo pocas early access (pay per usage), bez monetizacie.

Cesta od "checklist je zeleny" k publikovanemu Actorovi odhalila styri veci:

1. **Output schema** - Apify vyzaduje pole `output` v `.actor/actor.json`; dataset view
   schema mu nestaci. Ich validator navyse vyzaduje `type` v kazdej polozke, hoci
   minimalny priklad v ich dokumentacii ho neuvadza.
2. **Key-value store schema** musi mat `actorKeyValueStoreSchemaVersion`.
3. **`?clean=true` v output sablone** rozbilo kartu Output - Apify si parametre v URL
   typuje a `true` precitala ako text. Beh pritom presiel; dataset bol v poriadku, len
   sa zakaznikovi nezobrazil. Tichá chyba v konfiguracii produktu, ktory je proti tichym
   chybam postaveny.
4. **Deployment key dialog** blokoval buildy - Apify pyta SSH kluc do GitHub repa. Repo
   je verejne a HTTPS klonovanie funguje, takze "Don't add".

Stav po dokonceni: build **0.0.7** (`latest`), posledny beh Succeeded, 100 vysledkov,
11 s, $0.001. Karta Output sa vykresluje spravne pod pohladom "Verified posts".

**Ochrana proti driftu Telegramu:** tyzdenny GitHub Actions workflow `live-smoke`
(pondelok 6:17 UTC) prebehne `scripts/smoke.py` proti zivemu t.me a spadne, ked sa
ktorykolvek z osmich handle-ov zacne klasifikovat inak. Unit testy dokazuju, ze parser
sedi na markup zachyteny 19. 8. 2026; toto dokazuje, ze Telegram ten markup este ma.

**Predvoleny vstup** je zamerne dvojkanalovy (`durov`, `telegram`): Apify denne
autotestuje publikovany Actor a po troch behoch bez neprazdneho datasetu ho oznaci
"under maintenance". Actor je pritom navrhnuty tak, aby pri necitatelnom kanale zlyhal -
jeden kanal by tu kontrolu zhodil prave vtedy, keby sa Actor zachoval spravne.

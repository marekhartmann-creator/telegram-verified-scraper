# Projekt: Apify Actor — Telegram Channel Scraper (verified)

**Vlastník:** Marek Hartmann
**Založené:** 19. 8. 2026
**Stav:** v0.2 — jadro postavené, otestované a živo overené proti Telegramu; nenasadené do Apify Store
**Repo (plán):** github.com/marekhartmann-creator/telegram-verified-scraper
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

## 9. Čo ďalej (poradie)

1. ~~Živý smoke test~~ — hotové 19. 8. 2026, dve chyby nájdené a opravené.
2. Doplniť živé prípady, ktoré zatiaľ nemám vzorku: súkromný kanál, obmedzený
   (age-gated) kanál, skupina. Fixtures pre ne sú odhad, nie zachytený markup.
3. Push do GitHubu, prepojiť s Apify, build.
4. Nastaviť pay-per-event v Apify Console podľa `.actor/pay_per_event.json`.
5. Publikovať, doplniť listing (README) a screenshot výstupu.
6. Prvé recenzie: požiadať o feedback v Apify Discorde a v jednom OSINT/Telegram
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

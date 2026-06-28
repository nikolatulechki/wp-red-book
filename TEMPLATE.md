# Template for creating missing Red Book → bg.wikipedia articles

A deterministic recipe for turning a Red Book entry + its Wikidata item into a
new bg.wikipedia article stub. One row of `tracking.csv` → one `.mw` page.

## 1. The three sources and what each gives you

| Source | What to take from it |
|---|---|
| **Red Book entry** (`redbook_url`, e-ecodb.bas.bg) | All the prose: morphology, habitat, distribution, threats, conservation. This is the **primary content** and the citeable source. |
| **Wikidata item** (`wikidata_qid`) | Latin name (`P225`), parent taxon (`P171`) → family, taxon rank (`P105`), image (`P18`), Commons category (`P935`), IUCN status (`P141`), bg aliases (other Bulgarian names). Drives the Taxobox automatically. |
| **`tracking.csv` row** | `bg_name` (= page title), `taxon`, `redbook_status` (→ `status_bg`), `redbook_vol` (→ `vol1`/`vol2` in the URL). |

**Key fact:** the bg `{{Taxobox}}` is Wikidata-driven. As long as the page is
linked to its Wikidata item, you do **not** hand-fill kingdom/family/genus/
binomial — the box reads them from the QID. You only set the Bulgarian Red Book
status.

## 2. Red Book entry structure → wiki section mapping

Every e-ecodb entry follows the same skeleton. Map it like this:

| Red Book section | Goes into wiki section |
|---|---|
| Latin name + author, `Сем./Семейство` | Lead sentence + Taxobox (from Wikidata) |
| `Природозащитен статут` (CR/EN/VU/RE/EX) | `status_bg=` + lead sentence |
| `Морфология и биология` | `== Описание ==` (+ phenology, pollination, reproduction) |
| `Местообитания и популации` | `== Местообитания ==` / `== Численост ==` |
| `Разпространение в България` | `== Разпространение ==` (Bulgaria) |
| `Общо разпространение` | `== Разпространение ==` (world) |
| `Отрицателно действащи фактори` | `== Заплахи ==` or merged into conservation |
| `Предприети / Необходими мерки за защита` | `== Природозащитен статут ==` / `== Мерки за защита ==` |
| `Литература`, `Автор` | not copied (covered by the Red Book `<ref>`) |

## 3. Status codes

Set `status_bg` to the Red Book code straight from `redbook_status`:

| Code | Bulgarian | Use in lead as |
|---|---|---|
| `CR` | Критично застрашен | критично [[застрашен вид]] |
| `EN` | Застрашен | [[застрашен вид]] |
| `VU` | Уязвим | [[уязвим вид]] |
| `RE` | Регионално изчезнал | регионално изчезнал вид |
| `EX` | Изчезнал | изчезнал вид — also add `status_bg_extinct = <year>` |

## 4. Reusable wikitext skeleton — PLANTS & FUNGI (vol1)

Placeholders in `«…»`. Delete sections the Red Book entry has no data for.

```wikitext
{{Taxobox
| status_bg     = «CR|EN|VU|RE|EX»
| status_bg_ref = <ref name="ЧК">{{Червена книга | title = {{PAGENAME}} | redbooklink = «redbook_url» | downloaded = «21 юни 2026 г.»}}</ref>
}}

'''«Българско име»''' (''«Latin name»'') е «жизнена форма, напр. многогодишно тревисто» [[растение]] от семейство [[«Семейство на български»]]. В [[България]] е «критично [[застрашен вид]]», включен в [[Червена книга на България|Червената книга на България]]«, и в [[Закон за биологичното разнообразие|Закона за биологичното разнообразие]]».<ref name="ЧК"/>

== Описание ==
«Морфология и биология от ЧК: стъбло, листа, цветове, плод, семена; цъфтеж/плодоносене; опрашване; размножаване.»<ref name="ЧК"/>

== Разпространение и местообитания ==
«Разпространение в България + общо разпространение + тип местообитание и популации от ЧК.»<ref name="ЧК"/>

== Природозащитен статут ==
«Отрицателно действащи фактори + предприети/необходими мерки за защита от ЧК.»<ref name="ЧК"/>

== Източници ==
<references />

{{Нормативен контрол}}

[[Категория:«Най-дълбоката таксономична категория, напр. род»]]
«[[Категория:Флора на България]]  ← само ако видът е български ендемит; иначе пропусни този ред»
```

For the categories follow §6a: the taxonomic line (deepest level only) is
mandatory; add a geographic line (`Флора на България`) **only** if the species
is endemic to Bulgaria, otherwise add no geographic category at all. For
**fungi**, swap the lead to `…е вид [[гъба]] от семейство [[Family]]` and use a
гъба-type taxonomic category instead of Флора.

## 5. Reusable wikitext skeleton — ANIMALS (vol2)

Animal entries are richer; use more sections.

```wikitext
{{Taxobox
| status_bg     = «CR|EN|VU|RE|EX»
| status_bg_ref = <ref name="ЧК">{{Червена книга | title = {{PAGENAME}} | redbooklink = «redbook_url» | downloaded = «21 юни 2026 г.»}}</ref>
«| status_bg_extinct = «година»  ← само при EX»
}}

'''«Българско име»''' (''«Latin name»'') е [[вид (биология)|вид]] «риба/птица/влечуго/бозайник» от семейство [[«Семейство»]] (''«Latin family»'').<ref name="ЧК"/>

== Описание ==
«Външен вид, размери, тегло от ЧК (раздели Морфология/Биология/Близки видове).»<ref name="ЧК"/>

== Разпространение и местообитание ==
«Общо разпространение + разпространение и численост в България + местообитания от ЧК.»<ref name="ЧК"/>

== Начин на живот и хранене ==
«Хранене, поведение от ЧК (Биология).»<ref name="ЧК"/>

== Размножаване ==
«Размножаване от ЧК.»<ref name="ЧК"/>

== Численост и природозащитен статут ==
«Численост, отрицателни фактори, предприети/необходими мерки от ЧК.»<ref name="ЧК"/>

== Източници ==
<references />

{{Нормативен контрол}}

[[Категория:«Най-дълбоката таксономична категория, напр. род или семейство»]]
«[[Категория:Фауна на България]]  ← само ако видът е български ендемит; иначе пропусни този ред»
```

For the categories follow §6a (taxonomic always; geographic only for Bulgarian
endemics).

## 6. Conventions distilled from existing articles (follow these exactly)

- **`{{Червена книга}}` params** are always `title = {{PAGENAME}}`,
  `redbooklink = <redbook_url>`, `downloaded = <date in Bulgarian>`. Reuse it
  with `<ref name="ЧК">…</ref>` then `<ref name="ЧК"/>` so the Red Book is cited
  once.
- **Lead name**: bold Bulgarian name, Latin in italics in parentheses. If
  Wikidata bg-aliases or the Red Book give synonyms (e.g. „Урумов лопен“), add
  them as `'''… или …'''`.
- **Family link**: use the Bulgarian family name (e.g. `[[Бобови]]`,
  `[[Карамфилови]]`, `[[Щъркелови]]`). Derive it from Wikidata `P171`
  (parent taxon → its family) or the Red Book `Сем.` line.
- **Units**: keep ranges with spaced en-dash and Latin units as in the Red Book
  — `40 – 100 cm`, `0,8 – 0,9 mm`, decimal **comma**. Months `Цв. VI–VIII` →
  spell out „цъфти юни – август“.
- **Citation templates**: prefer Bulgarian `{{Цитат уеб}}` / `{{Цитат книга}}`
  for new refs; `{{IUCN|…}}` for the IUCN assessment if `P141`/`P627` exist.
- **Image**: only add `[[Файл:…|мини|...]]` if Wikidata `P18` has one; otherwise
  leave it to the Taxobox.
- **Footer order**: `== Източници ==` → optional `== Външни препратки ==` →
  `{{Нормативен контрол}}` → categories last.
- **Sanity check**: confirm the page is linked to its `wikidata_qid` (otherwise
  the Taxobox renders empty). 23 taxa in `tracking.csv` have no QID — those need
  the Taxobox filled manually or a Wikidata item created first.

## 6a. Category rules (reviewer feedback — follow exactly)

Every article gets a **taxonomic** category line. It gets a **geographic**
category line **only** if the species is endemic to Bulgaria — otherwise it has
just the one taxonomic line.

### Taxonomic category — deepest level only

> **Phase B: add no categories at all.** Writers leave out every category (both
> taxonomic and geographic). Categories are applied in a separate **batch** pass
> later. The rules below are for that batch pass, not for article writing.

Place the article in the **single most specific** taxonomic category that
exists, and **never** also add a broader ancestor. The parent is already
reachable through the category tree, so listing both is redundant.

- Prefer the **genus** category (e.g. `[[Категория:Млечка]]`,
  `[[Категория:Гълъбки]]`); fall back to **family** only if no genus category
  exists.
- ❌ Do **not** add the broad kingdom/group category on top, e.g. having both
  `[[Категория:Гълъбки]]` **and** `[[Категория:Гъби]]` is wrong — keep only
  `[[Категория:Гълъбки]]`.

### Geographic category — България only if endemic to bulgaria

Decide from the Red Book "Общо разпространение" (world distribution):

| Distribution | Category |
|---|---|
| **Endemic to Bulgaria** (occurs only in BG) | `[[Категория:Флора на България]]` / `[[Категория:Фауна на България]]` |
| **Occurs outside Bulgaria too** (the common case) | add nothing |

Rationale: a country category for a widespread species would force dozens of
parallel "Фауна на …" categories, so widespread species get **no** geographic
category at all. Use the BG country category **only** for true endemics.

> Note: this **replaces** the older "always add Фауна/Флора на България" rule
> and the separate "Ендемична флора на България" addition used in earlier
> articles.

## 7. Filled mini-example (Алепска млечка, `EN`, no WP article yet)

Using `tracking.csv` id 8 (`Euphorbia aleppica`, `Q12230481`, vol1) + its
Red Book entry:

```wikitext
{{Taxobox
| status_bg     = EN
| status_bg_ref = <ref name="ЧК">{{Червена книга | title = {{PAGENAME}} | redbooklink = http://e-ecodb.bas.bg/rdb/bg/vol1/Eupalepp.html | downloaded = 21 юни 2026 г.}}</ref>
}}

'''Алепска млечка''' (''Euphorbia aleppica'') е тревисто [[растение]] от семейство [[Млечкови]]. В [[България]] е [[застрашен вид]], включен в [[Червена книга на България|Червената книга на България]] и в [[Закон за биологичното разнообразие|Закона за биологичното разнообразие]].<ref name="ЧК"/>

== Описание ==
…<ref name="ЧК"/>

== Разпространение и местообитания ==
…<ref name="ЧК"/>

== Природозащитен статут ==
…<ref name="ЧК"/>

== Източници ==
<references />

{{Нормативен контрол}}

[[Категория:Млечка]]
```

(No geographic category: the species ranges across SE Europe, the Mediterranean,
Crimea and SW Asia, so it is **not** a Bulgarian endemic — see §6a. The only
category is `Категория:Млечка`, which is already the deepest taxonomic level.)

## 8. Linking the article to Wikidata (so the Taxobox fills in)

The bg `{{Taxobox}}` only auto-populates (kingdom/family/genus/binomial/image)
if the article is **connected to its Wikidata item**. Publishing via
`scripts/publish_api.py` creates the **bgwiki page only** — it does **not**
touch Wikidata. The connection is a **sitelink on the Wikidata item**: the item's `bgwiki` slot must point to the new article title.
This is a separate write against `wikidata.org` using the QID already stored in
`tracking.csv` (`wikidata_qid`).

### Order of operations (important)

1. **Publish the article first** (`publish_api.py`). Wikidata refuses a sitelink to a page that does
   not yet exist, so the wiki page must be live before step 2.
2. **Set the sitelink on the item** `Qxxxx` → `{ site: "bgwiki", title: "<bg_name>" }`.
3. **Purge / null-edit** the new page so the Taxobox re-reads the now-connected
   item (until linked, the box renders empty/partial).
4. **Log the publication** on
   [Потребител:BOTulechki/Видове от Червената Книга](https://bg.wikipedia.org/wiki/Потребител:BOTulechki/Видове_от_Червената_Книга)
   (`wiki/bot/bot-pages/`) — append a bullet at the **end** of
   `== Създадени статии ==` in creation order (do not sort alphabetically) and push.

### How (use the `wikidata-pybot` library)

Tooling lives at `~/Projects/wiki/wikidata-pybot/` (Pywikibot wrapper). It has no
`set_sitelink` helper yet, so either:

- **Option A — call Pywikibot directly** via the library's repo/login helpers:

```python
from wikidata_pybot import get_repo, get_item, delay

repo = get_repo()                      # maxlag/retry defaults already applied
item = get_item(repo, "Q12230481")
item.setSitelink(
    {"site": "bgwiki", "title": "Алепска млечка"},
    summary="bot: add bgwiki sitelink (Red Book article)",
)
delay(1)
```

- **Option B — add a reusable `set_sitelink` primitive** to the library
  (`entities.py`, export from `__init__.py`) wrapping the same call. Preferred
  for batching hundreds of links. Underlying API action: `wbsetsitelink`.

### Batch-run caveats

- **Auth**: needs `PYWIKIBOT_DIR` + `user-config.py`/`user-password.py` with a
  **Wikidata** bot password — a *different* credential from the bgwiki bot
  password used for `git push`.
- **Already-linked items**: the 395 existing articles already have a `bgwiki`
  sitelink; skip those. Setting a sitelink that conflicts with an existing one
  raises an error. Only the ~657 missing rows have an empty slot.
- **The 23 QID-less taxa** (`wikidata_qid` empty): no item to link — reconcile or
  create the item first (also `wikidata-pybot`), then push + link.
- **Rate-limit / maxlag**: `delay(1)` between writes; do not kill on the first
  long `Sleeping` (it is WDQS maxlag backoff, not a hang).

### Pipeline step

Add a new resumable script, e.g. `scripts/link_wikidata_sitelinks.py`, that only
processes rows where the article now exists but the item lacks a `bgwiki`
sitelink, checkpointing into a new tracking column (e.g. `wd_linked`).

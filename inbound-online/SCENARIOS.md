# Online — Expected Behavior

This document defines Online's expected call-routing behavior, traced from the
legacy source's own outlet addresses and page graphs (Daytime and AH playbooks) —
no inference from our own Guava reimplementation.

## Open Hours (Daytime playbook: "TTU Online + EL (Daytime Production)")

Entry gate: start page `ef1cc9fe739fa549` → formula page `8d991e9486d2c843` checks
`working_hours == "open"`. If not open, it exits immediately via outcome `Route to AH
Bot` — **the Daytime playbook never speaks at all when hours are closed**; it hands off
before any greeting, to the [After Hours](#after-hours-ah-playbook-ttu-online--el-ah-production)
section below. Everything below only runs when `working_hours == "open"`.

Greeting (page `13cc1c008f156e45`, "Initial Directory"): "Thank you for calling Texas
Tech Online! My name is Grace, your virtual assistant... Please note that this call may
be recorded." Then: "How may I direct your call?"

### Step 1 — caller's opening phrase → destination page

| Caller says (link name, verbatim) | Routes to |
|---|---|
| "I would like to talk to someone about Flexible Learning" | [Flexible Learning](#flexible-learning-c4520e6f68232703) |
| "I would like to talk to someone about continuing education" | [Flexible Learning](#flexible-learning-c4520e6f68232703) |
| "I would like to talk to someone about Microcredentials" | [Microcredentials](#microcredentials-30e4af9cfcc9827f) |
| "I wanted to talk to someone about Career Certificates" | [Career Certificates](#career-certificates-2535dec0767d6b8b) |
| "I would like to talk to someone about Online Plus" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I would like to talk to someone about your online degree" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I would like to talk to someone about the 8 week courses" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I would like to talk to someone about the accelerated courses" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I'm looking to complete my degree" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I'm calling about a bachelor's degree" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I would like to talk to someone about undergraduate degrees" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "I would like to talk to someone about Self Paced" | [Self Paced](#self-paced-a52a204d7ff8269f) |
| "I would like to talk to someone about the 10-K Degree Completion" | [10-K](#10-k) |
| "I would like to talk to someone about Kay Twelve" | [K12](#k12) |
| "I wanted to talk to someone about Online Graduate Programs" | [Grad](#grad) |
| "I'm not sure" / "I would like help with a new program" / "More information on an advertisement" / "I have a question." / "I need help." / *(none of the above)* | [None of the Above](#none-of-the-above-909fbbfbb686d9cb) |

### Step 2 — per-destination outcome

<a id="online-plus-ca3f8a559261e71e"></a><a id="self-paced-a52a204d7ff8269f"></a><a id="microcredentials-30e4af9cfcc9827f"></a><a id="career-certificates-2535dec0767d6b8b"></a>
**Online Plus / Self Paced / Microcredentials / Career Certificates / Flexible
Learning / "Flexible Learning - other"** (reached via Flexible Learning's own
sub-clarify — see below) all ask: *"Do you want to talk with Ava, or be placed in
the queue?"* with links "I want to talk to Ava" / "I want to be placed in the
queue" / "I want to talk to a human" / *(none of the above)*.

| Program page | "Ava" choice → | "queue"/"human"/none choice → |
|---|---|---|
| Online Plus | `End - Route to Online ElevenLabs` → **+18882817949** | `End - Route to Online` (page-level label "Signature Plus Rep") → **+18067422810** |
| Self Paced | same → **+18882817949** | same target page → **+18067422810** (the "Self Paced Rep" outcome name on this page is never used — `is_exit_page: false` here, so it can't fire; the actual exit page's outcome is "End - Route to Online") |
| Microcredentials | same → **+18882817949** | `End - Route to Flexible Learning` → **+18067423714** |
| Career Certificates | same → **+18882817949** | same → **+18067423714** |
| Flexible Learning - other | same → **+18882817949** | same → **+18067423714** |

<a id="flexible-learning-c4520e6f68232703"></a>
**Flexible Learning** (the direct Step-1 destination) is itself a sub-clarify page,
not a terminal Ava/queue page: *"Which Flexible Learning program were you interested
in?"*
| Sub-choice | Routes to |
|---|---|
| Microcredentials | [Microcredentials](#microcredentials-30e4af9cfcc9827f) (outcomes above) |
| "Self Pace courses" | [Self Paced](#self-paced-a52a204d7ff8269f) (outcomes above) |
| "other Flexible Learning options" | Flexible Learning - other (outcomes above, same table) |
| Career Certificates | [Career Certificates](#career-certificates-2535dec0767d6b8b) (outcomes above) |
| *(none of the above)* | Higher Ed Transfer → `End - Route to Default Higher Ed` → **+18067427227** |

#### 10-K

*"Do you want to talk with Ava, or be placed in the queue?"* — this hands the
caller off into the 10K program's own call flow (its "queue" destination here is
the exact same address as 10K's own daytime "Talk to a live agent" outcome).
- Ava → `End - Route to 10K ElevenLabs` → **+18889707775**
- queue/human/none → `End - Route to 10K` → **+18067420526**

#### K12

Same question shape — hands off into K12's own call flow (same address as K12's own
daytime "Transfer to Queue" outcome).
- Ava → `End - Route to K12 ElevenLabs` → **+18884178511**
- queue/human/none → `End - Route to K12` → **+18067427101**

#### Grad

Same question shape — hands off into Grad's own call flow (same address as Grad's
own daytime "Transfer to Queue" outcome).
- Ava → `End - Route to Grad ElevenLabs` → **+18883323870**
- queue/human/none → `End - Route to Grad` → **+18067426441**

#### None of the Above (909fbbfbb686d9cb)

Script: "Ok, just one second... let's see if we can narrow it
down": *"Were you looking into 4 credit options to complete your degree or, some of
our non-credit Flexible Learning options?"*
| Sub-choice | Routes to |
|---|---|
| "for-credit (4 credit)" / "accelerated courses" / "bachelor's degree" | [Online Plus](#online-plus-ca3f8a559261e71e) |
| "non-credit (not for credit)" | [Flexible Learning](#flexible-learning-c4520e6f68232703) |
| "Yes" / "Correct" | ["Yes" clarify page](#yes-clarify-page) (below) |
| "I don't know" / "I'm not sure" / *(none of the above)* | Higher Ed Transfer → **+18067427227** |

<a id="yes-clarify-page"></a>
#### "Yes" clarify page

Script empty: *"Great! And which program were you looking
into?"* — offers Flexible Learning, Microcredentials, Online Plus (+ several
phrasings), 10-K. **Does not offer K12 or Grad as explicit choices** — any of those
callers falls to Higher Ed Transfer (**+18067427227**) via "I'm not sure"/"I don't
know"/none-of-the-above, since there's no link here for K12/Grad specifically.

### Full destination summary (Open Hours)

| Destination | Address | Reached via |
|---|---|---|
| Online ElevenLabs | +18882817949 | Ava from Online Plus, Self Paced, Microcredentials, Career Certificates, or Flexible Learning-other |
| Online Signature Plus Rep | +18067422810 | queue/human/none from Online Plus or Self Paced |
| Flexible Learning (live) | +18067423714 | queue/human/none from Microcredentials, Career Certificates, or Flexible Learning-other |
| 10K ElevenLabs | +18889707775 | Ava from 10-K |
| 10K (live) | +18067420526 | queue/human/none from 10-K |
| K12 ElevenLabs | +18884178511 | Ava from K12 |
| K12 (live) | +18067427101 | queue/human/none from K12 |
| Grad ElevenLabs | +18883323870 | Ava from Grad |
| Grad (live) | +18067426441 | queue/human/none from Grad |
| Higher Ed Default | +18067427227 | Flexible Learning sub-clarify none-of-above; None-of-the-Above→"I don't know"/"not sure"/none; "Yes" page→"not sure"/"I don't know"/none |
| **Self Paced Rep** | **+18067424035** | **UNREACHABLE** — defined as an outlet node and as a stale `outcome_name` label on the (non-exit) Self Paced page, but no live link anywhere routes here. Confirmed dead. |

## After Hours (AH playbook: "TTU Online + EL (AH Production)")

Entry: start page `8b84713fa712df2e` → formula page `959fccfada8e0f9e` checks
`holiday_status == "closed"`.
- **Closed for holiday** → "Holidays" page (`46e82ec66a3bdb69`): "Thank you for
  calling... Our offices are currently closed in observance of `<<holiday_name>>`...
  transfer you to our virtual assistant Ava, or you can also choose to leave a
  voicemail." Choices: "Speak with Ava" / "Leave a message" / "I have a question
  about" / "Transfer to virtual assistant" — the **first, third, and fourth all route
  to the same place** (Initial Directory); only "Leave a message" differs.
- **Normal after-hours (not a holiday)** → "Normal" page (`5301b3fbf361672c`): "...Our
  offices are currently closed. Live agents will be available during business hours...
  connect you with our virtual assistant Ava, or... transfer you to our support
  center to leave a voicemail." Choices: "Speak with Ava" / "Leave a message" /
  "Leave a voicemail" (last two are the same target).

Either way:
- **"Leave a message"/"Leave a voicemail"** → Voicemail page (`bebca97547a59607`) →
  `End - Route to Higher Ed Default` → **+18067427227**.
- **"Speak with Ava"** (or its "I have a question about"/"Transfer to virtual
  assistant" equivalents, Holidays only) → Initial Directory (`13cc1c008f156e45`, AH
  version — this is a **different page than Daytime's**, same `page_id` but distinct
  content in this separate playbook file): script "Sounds good. But first, I need to
  narrow down what you are calling about." → *"Do you know what program you are
  wanting information on?"*

### AH Initial Directory → destination

**Confirmed by tracing every link explicitly — do not assume symmetry with Daytime.**
The overwhelming majority of phrasings route straight to Ava-Online, with three
named exceptions:

| Caller says | Routes to |
|---|---|
| "Kay Twelve Program" | Ava - K12 → `End - Route to K12 ElevenLabs` → **+18884178511** |
| "Online Graduate/Grad Programs" | Ava - Grad → `End - Route to Grad ElevenLabs` → **+18883323870** |
| **"Microcredentials"** | Ava - 10K → `End - Route to 10K ElevenLabs` → **+18889707775** — **not** Online ElevenLabs. This looks like a source-data authoring mistake (Microcredentials is an Online/Flexible-Learning sub-program in Daytime, not 10-K), but it is exactly what the AH playbook does. |
| "10-K Degree Completion" | Ava - 10K → **+18889707775** (this one is expected) |
| "Yes" | ["Yes" sub-clarify page (AH version)](#yes-sub-clarify-page-ah-version) (below) |
| Everything else — "Flexible Learning", "Online Plus", "Self Paced" *(not an explicit link here — falls through fuzzy/none-of-above)*, "8 week courses", "accelerated courses", "I'm not sure", "I don't know", "help with a new program", "continuing education", "complete my degree", "advertisement", "interested in getting my degree", "going back to school", "No", *(none of the above)* | Ava - Online → `End - Route to Online ElevenLabs` → **+18882817949** |

#### "Yes" sub-clarify page (AH version)

*"Great! And which program were you looking
into?"* — same shape as the top-level list: Kay Twelve → Ava-K12; Grad Programs →
Ava-Grad; **Microcredentials → Ava-10K (same quirk repeated)**; 10-K Degree
Completion → Ava-10K; everything else → Ava-Online.

### What is confirmed NOT reachable after hours

No live-queue, rep-line, or direct program-escalation number is reachable anywhere in
this playbook — confirmed by exhaustive trace, not assumption. Specifically
**unreachable in AH**: +18067422810 (Signature Plus Rep), +18067423714 (Flexible
Learning live), +18067420526 (10K live), +18067427101 (K12 live), +18067426441 (Grad
live), +18067424035 (Self Paced Rep, unreachable everywhere per above). Only 5
destinations exist in this playbook's routing_outcomes: Higher Ed Default, and the
4 ElevenLabs numbers.

### Full destination summary (After Hours)

| Destination | Address | Reached via |
|---|---|---|
| Online ElevenLabs | +18882817949 | Nearly every program phrasing (see table) |
| 10K ElevenLabs | +18889707775 | "10-K Degree Completion" **or** "Microcredentials" (quirk) |
| K12 ElevenLabs | +18884178511 | "Kay Twelve Program" |
| Grad ElevenLabs | +18883323870 | "Online Graduate/Grad Programs" |
| Higher Ed Default (voicemail) | +18067427227 | "Leave a message"/"Leave a voicemail" from the Holidays or Normal closed-message page |

## Notes

- **Two orphaned duplicate pages exist in the Daytime playbook**: `page_id: 'a'`
  ("Initial Directory (1)") and `page_id: '5'`("Initial Directory (2)") are
  byte-for-byte copies of the real Initial Directory page's script/links, but **no
  link anywhere in the file targets either page_id** — they are unreachable dead
  nodes, not part of the live call graph. Confirmed by scanning every `target_id` in
  the file.
- **`+18067424035` (Self Paced Rep) is unreachable in every scenario, day or night** —
  confirmed twice now (Daytime trace above, and it was never a link target in AH
  either since AH has no live-queue destinations at all).
- **Self Paced has no dedicated link in the AH Initial Directory** at all (unlike
  Daytime) — a caller saying "self paced" after hours has no exact-match link and
  would need to fall through none-of-the-above handling to Ava-Online, same
  destination as most other phrasings anyway.
- **The Microcredentials→10K-ElevenLabs mapping in the AH playbook is almost certainly
  a data/authoring error** relative to Daytime's Microcredentials→Online-ElevenLabs
  mapping, but it is what the source file actually specifies — flagged, not corrected,
  since this document's job is to state the legacy source's actual defined behavior.
- **Daytime's hours gate is binary and immediate**: if `working_hours != "open"`, the
  Daytime playbook exits to `Route to AH Bot` before speaking a single word — there is
  no partial daytime script that also handles closed hours.
- **The "Yes" sub-clarify page (both playbooks) never offers K12 or Grad as an
  explicit choice in Daytime** (it does in AH) — a caller reaching this specific
  sub-page in Daytime and asking for K12/Grad falls to Higher Ed Default instead of
  the correct program, per the literal defined links.

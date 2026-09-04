# K12 — Expected Behavior

Traced from the legacy platform's two playbooks, "K12 Initial + EL (Production)" and
"K12 AH + EL (Production)". Every page-to-page link traced from each playbook's
`start_page_id` to a terminal outcome. Not cross-checked against any Guava reimplementation.

Destination addresses:
- **TTU K12** (live queue) — `+18067427101`
- **ElevenLabs** ("Ava"/"Ava") — `+18884178511`

## Open Hours (playbook: "K12 Initial + EL (Production)")

Entry: `start_page_id` (Placeholder, `742f89079ecd`) → unconditional → "Time of Day" formula
(`710e5035a29d313a`, connector "Time of Day (Holidays/Weekend)", checks `working_hours == "open"`).

- **`working_hours != "open"`** (`no_matching_condition_page_id`) → page `fdd7771170ca2925`
  ("AH - Bot Routing", exit page) → outcome **`Outcome - Route to TTU K12 After Hours Bot`** — hands
  off to the K12 AH bot (see [After Hours](#after-hours-playbook-k12-ah--el-production) below).
  No destination address of its own; it's a bot-to-bot transition in the call-flow graph.
- **`working_hours == "open"`** → page `50d30f8edc184ced` ("Greeting"), script: *"Thank you for
  calling Tea Tea You Kay twelve! My name is Grace, your virtual assistant. Please note that this
  call may be recorded. I can transfer you to our virtual assistant, Ava, who can help answer
  questions right away, or place you in the queue to wait for an agent."* `link_question`: "How
  would you like to proceed?" (`transfer_options`), two choices:

| Caller choice | Target page | outcome_name | Destination |
|---|---|---|---|
| "Virtual Assistant Ava" | `705b8b53826fd1c2` ("Route to Ava") | `End - Route to ElevenLabs` | `+18884178511` |
| "Transfer to Queue" | `d29c156792ed14f0` ("Route to K12") | `End - Route to TTU K12` | `+18067427101` |

That's the entire daytime tree — exactly 2 reachable terminal outcomes, both a direct transfer, no
other branching.

## After Hours (playbook: "K12 AH + EL (Production)")

Entry: `start_page_id` (`fbefd049a4cc2373`, "New Logic Page", formula, connector "Time of Day
(Holidays/Weekend)", checks `holiday_status == "closed"`).

- **`holiday_status == "closed"`** → page `030e978a5abd0254` ("AH (Holidays)"), script: *"...Our
  offices are currently closed in observance of `<<holiday_name>>`. If you have any questions, I
  will transfer you to our virtual assistant Ava. You can also choose to leave a voicemail for
  the team, or receive a text message with the link to submit a ticket."*
- **else** (`no_matching_condition_page_id`) → page `620ef64e4fc77035` ("AH (Normal)", carries a
  page-level `outcome_name: Route to AH` but `is_exit_page: false` — **not an actual exit, a stale/
  inert label**), script: *"...Our offices are currently closed. Live agents will be available
  during business hours. If you have any questions, I will transfer you to our virtual assistant
  Ava. You can also choose to leave a voicemail for the team, or receive a text message with the
  link to submit a ticket."*

Both branches converge unconditionally on the same page: `ee3d7d6db9514764` ("Initial Inquiry"),
`link_question`: "What can I help you with?" (`initial_inquiry`), with 7 links:

| Caller choice | Target page | Resolves to |
|---|---|---|
| "Voicemail" | `50d0c3a4cc1786f8` | `End - Route to TTU K12` → `+18067427101` |
| "Speak with someone" | `50d0c3a4cc1786f8` (same page) | `End - Route to TTU K12` → `+18067427101` |
| "Leave a message" | `50d0c3a4cc1786f8` (same page) | `End - Route to TTU K12` → `+18067427101` |
| "Questions" | `cc7f1d3c65d749c3` | `End - Route to ElevenLabs` → `+18884178511` |
| "Ava" | `cc7f1d3c65d749c3` (same page) | `End - Route to ElevenLabs` → `+18884178511` |
| "None of the Above" (default) | `cc7f1d3c65d749c3` (same page) | `End - Route to ElevenLabs` → `+18884178511` |
| "Text Message" | `52b15d87233d4307` | see below — does NOT resolve directly |

**Three caller-facing labels ("Voicemail", "Speak with someone", "Leave a message") are all the same
target page**, whose own script says: *"Ok, give me just a moment and I will transfer you to that
number. You will hear another message that we are closed and then you will be able to leave a
voicemail. Thanks again for contacting Tea Tea You Kay Twelve."* This is a **live phone transfer to
the exact same number as the daytime live queue** (`+18067427101`) — it is *not* a distinct
voicemail mailbox in this system; "voicemail" happens on the receiving end (presumably TTU's own PBX
routes an unattended line to voicemail), not via a different destination here.

**Three labels ("Questions", "Ava", "None of the Above")** all resolve to the same target page
(`cc7f1d3c65d749c3`, "Questions - Ava"), script: *"Ok, give me just a moment and I will transfer you
to Ava."* → `End - Route to ElevenLabs` → `+18884178511`.

**"Text Message"** → page `52b15d87233d4307` ("Student Status Check"), a yes/no form field: *"But
first, are you currently a student with Tea Tea You Kay 12?"* (`student_status`), script: "I will
send a text message to the number you are calling from." → unconditional → page `325f3dde41f23abd`
("Student Status Logic", formula):

- **`student_status == "no"`** → page `a87f70fd5334182e` ("Potential Student"), script: "Ok, great!
  We are excited you called." → unconditional → page `0180709c868e7bba` ("Text Message - RFI",
  connector **"Send K12 RFI"**), script: *"I've sent a text message with a link to a form to collect
  some general information from you, once you have completed that form, a representative from our
  office will reach out within the next 24 business hours to provide more information."* →
  unconditional → page `71aabafe1739a4c6` ("End"), outcome **`End - Hangup`**, script: "Thanks again
  for calling and have a great day." **No phone transfer — text message sent via connector, then
  hangup.**
- **else / `student_status == "yes"`** (`no_matching_condition_page_id`) → page `acc4d85a8c0f82cc`
  ("Current Student"), script: "Ok, great!" → unconditional → page `99f04a0eda1a839f` ("Text Message
  - ServiceNow", connector **"Send K12 ServiceNow"**), script: *"I've sent a text message with a
  link to our service portal. If you create a ticket, you will typically receive a response within
  the next 24 business hours."* → unconditional → same `71aabafe1739a4c6` ("End"), outcome
  **`End - Hangup`**. **No phone transfer here either.**

### Summary of AH reachable outcomes

| Outcome | Destination | How many of the 7 Initial-Inquiry choices lead here |
|---|---|---|
| `End - Route to TTU K12` (live transfer; rings to voicemail after hours on the receiving end) | `+18067427101` | 3 ("Voicemail", "Speak with someone", "Leave a message") |
| `End - Route to ElevenLabs` | `+18884178511` | 3 ("Questions", "Ava", "None of the Above") |
| `End - Hangup` (text message sent, no transfer) | none — SMS only, via "Send K12 RFI" or "Send K12 ServiceNow" connector depending on `student_status` | 1 ("Text Message", branching further by student status) |

This matches the AH-bot's `outcome_keys` exactly: `["End - Hangup", "End - Route to TTU K12",
"End - Route to ElevenLabs"]` — 3 total reachable outcomes, all accounted for above. The
`default_route` for the AH bot is also `End - Route to TTU K12` (i.e. if nothing else matches, default
to the live-transfer/voicemail number).

## Notes

- Page `37ab066f4e8b29d3` ("Placeholder", in the AH playbook) links back to the playbook's own
  `start_page_id` (`fbefd049a4cc2373`), but **nothing in the traced flow links to
  `37ab066f4e8b29d3`** — it appears to be a dead/unreferenced page, not reachable from the actual
  entry point.
- Page `620ef64e4fc77035` ("AH (Normal)") carries a page-level `outcome_name: Route to AH`, but
  since `is_exit_page: false`, this is inert — it never actually fires as an outcome; the real exit
  happens later, at the Initial Inquiry tree's terminal pages.
- The daytime playbook's `input_variables` is `[working_hours]` only; the AH playbook's is
  `[holiday_name, holiday_status]` only — the two playbooks use entirely separate gating variables:
  `working_hours` decides day vs. AH bot at the call-flow level; `holiday_status`/`holiday_name` only
  matter once already inside the AH bot, to pick which greeting copy plays — both AH branches reach
  the identical downstream tree.
- No "Higher Ed Default"-style universal fallback number (the kind seen in the Online program) exists
  anywhere in K12's call-flow or either playbook — K12's only two phone destinations, day or night,
  are the TTU K12 live number and the ElevenLabs number.
- Every outcome_name referenced in both playbooks' pages has a matching outlet/hangup node — no
  dangling/unreachable outcome names found.

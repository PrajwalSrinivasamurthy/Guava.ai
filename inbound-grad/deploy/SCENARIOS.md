# Graduate — Expected Behavior

Documents the legacy system's exported configuration directly, with no reference to
our own Guava reimplementation — this is what the legacy system actually specifies.

Destination addresses:
- **Escalation** → `+18067426441` (used by both `End - Route to Online Grad` and
  `End - Route to TTU Online Grad` outcome names — same physical outlet)
- **End - Route to ElevenLabs** → `+18883323870`
- `End - Hangup` / `hang_up` → no destination, call simply ends

## Open Hours (playbook: "Grad + EL (Production)", start page `742f89079ecd`)

Flow: `742f89079ecd` (Placeholder, unconditional) → `710e5035a29d313a` ("Time of Day",
formula on `working_hours`) →
- if `working_hours == "open"` → `d29c156792ed14f0` ("Greeting")
- otherwise (`no_matching_condition_page_id`) → `fdd7771170ca2925`, an immediate exit
  page with `outcome_name: Outcome - Route to TTU Online Grad After Hours Bot` (hands
  off to the AH bot — no destination number, a bot-to-bot transition; see
  [After Hours](#after-hours-playbook-grad--el-ah-production-start-page-fbefd049a4cc2373)
  below)

`d29c156792ed14f0` ("Greeting") speaks: *"Thank you for calling Tea Tea You Online
Grad! My name is Grace, your virtual assistant... I can transfer you to our virtual
assistant Ava, who can help answer questions right away, or place you in the queue
to wait for an agent."* This page carries its own `outcome_name`
(`End - Route to Online Grad`) but `is_exit_page: false`, so that label never fires —
the two real exits are its links:

| Caller choice | Target page | outcome_name | Destination |
|---|---|---|---|
| "Virtual Assistant Ava" | `dd34e0f203f12602` ("Route to Ava") | `End - Route to ElevenLabs` | `+18883323870` |
| "Transfer to Queue" | `a0d7c295b0d80d2d` ("Route to Grad") | `End - Route to TTU Online Grad` | `+18067426441` |

That's the complete open-hours scenario set: exactly 2 reachable outcomes (Ava or
queue), gated only by `working_hours`.

## After Hours (playbook: "Grad + EL AH (Production)", start page `fbefd049a4cc2373`)

Flow: `fbefd049a4cc2373` ("New Logic Page", formula on `holiday_status`) →
- if `holiday_status == "closed"` → `030e978a5abd0254` ("AH (Holidays)")
- otherwise → `620ef64e4fc77035` ("AH (Normal)")

Both greeting pages differ only in spoken script (holiday name mentioned vs. generic
"currently closed") and both have exactly one unconditional link to the same next
page: `fe39a43d459e807e` ("Initial Inquiry").

`fe39a43d459e807e` asks *"What can I help you with?"* with exactly 3 choices:

| Caller choice | Target page | outcome_name | Destination |
|---|---|---|---|
| "Voicemail" | `075394a357d8e696` ("Voicemail") | `End - Route to TTU Online Grad` | `+18067426441` (same number as daytime's "Transfer to Queue") |
| "Text Message" | `99f04a0eda1a839f` ("Text Message - ServiceNow", connector "Send K12 ServiceNow") → `71aabafe1739a4c6` ("End") | `End - Hangup` | none — sends an SMS with a ServiceNow ticket link, then hangs up |
| "Questions" | `60ad98206a0de2f9` ("Questions - Ava") | `End - Route to ElevenLabs` | `+18883323870` |

That's the complete after-hours scenario set: exactly 3 reachable outcomes.
**No live-queue/rep-line destination is reachable after hours** — "Voicemail" reaches
the same phone number as the daytime queue option, relying on the receiving side's own
phone system to route an unattended line to voicemail; the playbook itself doesn't
distinguish "ring live" vs "go to voicemail" — it just dials the same address.

## Notes — orphaned/unreachable content in the AH playbook

Traced every `links[].target_id`, `conditional_links[].target_id`, and
`no_matching_condition_page_id` in the AH playbook from `start_page_id` outward. The
following pages exist in the file but **are not reachable from `start_page_id` by any
path** — no other page links to them:

- `52b15d87233d4307` ("Student Status Check") — asks "But first, are you currently a
  student with Tea Tea You Online Grad?"
- `325f3dde41f23abd` ("New Logic Page (1)") — branches on `student_status`
- `acc4d85a8c0f82cc` ("Current Student")
- `a87f70fd5334182e` ("Potential Student")
- `d5f0c2849b42d360` ("Text or VM - Existing")
- `e05f037de0c29760` ("Text or VM - New")
- `0180709c868e7bba` ("Text Message - RFI", connector "Send K12 RFI")
- `ee3d7d6db9514764` ("Program Details - Grad")
- `37ab066f4e8b29d3` ("Placeholder") — its own link points back to `start_page_id`,
  but nothing points to it

This entire orphaned cluster is the current-vs-potential-student distinction (RFI form
for prospective students vs. ServiceNow ticket for current ones) that a summary read of
this playbook would suggest is the real after-hours behavior. **It is not** — as
currently configured/exported, the live after-hours flow is the much simpler 3-choice
"Initial Inquiry" tree above, and every caller who picks "Text Message" gets the
ServiceNow-ticket page (`99f04a0eda1a839f`) regardless of whether they're a current or
prospective student, because the only path that would have asked that distinction is
unreachable.

This orphaning could be a real configuration bug in the source system (a page that used
to be wired in and was later bypassed, e.g. when "Initial Inquiry" was added to route
"Text Message" straight to ServiceNow) rather than an intentional design — worth
confirming with Texas Tech before treating either the simple 3-choice tree or the
orphaned student-status tree as the "correct" one to build toward, since the exported
file is genuinely ambiguous about intent here even though only one path is technically
reachable.

Also note: the AH playbook's connector names and script text reference "K12" (`Send K12
RFI`, `Send K12 ServiceNow`, "our Tea Tea You K12 self help portal") even though this
playbook is named "Grad + EL AH (Production)" and its bot is "Online Grad AH Bot" — this
is in the source data exactly as found, not a transcription error here. Given the
orphaned pages containing this branding are also the ones that are unreachable, it's
possible this K12-labeled content was copy-pasted from K12's AH playbook as a starting
point and then abandoned/bypassed rather than cleaned up.

# 10K Degree Completion — Expected Behavior

Day and after-hours logic live in **one** playbook here, unlike Online/Grad/K12's
separate-playbook pattern. `input_variables: [working_hours]` only — there is no
`holiday_status`/`holiday_name` variable in this playbook (unlike Online/Grad/K12's
AH playbooks), so there is no holiday-specific branch here at all.

Flow entry: `start_page_id: d7ac69462bc3cfbd` ("Placeholder", unconditional) →
`3dc805316343afe4` ("Time_of_day", a formula page using the "Time of Day
(Holidays/Weekend)" connector) → if `working_hours == "open"` →
[`81ef51cb1eee7e1e` ("OpenHours")](#open-hours-openhours-page-81ef51cb1eee7e1e);
otherwise (`no_matching_condition_page_id`) →
[`20737df74277` ("AfterHours")](#after-hours-afterhours-page-20737df74277).
Both branches live in this same file — unlike Online/Grad/K12, there's no separate
bot-to-bot hand-off here.

## Open Hours ("OpenHours" page, `81ef51cb1eee7e1e`)

Greeting: *"Thank you for calling Tea Tea You Online. My name is Grace... I can
transfer you to our virtual assistant, Ava, who can help answer questions right
away, or place you in the queue to wait for an agent."*
`link_question`: "How can I help you today?"

| Caller's choice | Target page | outcome_name | Destination |
|---|---|---|---|
| "Transfer to Ava" | `00290035c5752519` ("Questions - Ava") | `End - Route to ElevenLabs` | `+18889707775` |
| "Talk to a live agent" | `b9dc3d5195e330e0` ("Transfer to Live Agent") | `End - Transfer to Live Agent` | **no address in export** (see Notes) |
| "Transfer to support center" | `b9dc3d5195e330e0` (same target as above) | `End - Transfer to Live Agent` | **no address in export** |

**No enrollment path exists during open hours.** `OpenHours`'s link list has exactly
these 3 options — there is no "I would like to enroll" link here at all; the
enrollment funnel (below) is reachable only from the `AfterHours` page in this
playbook.

## After Hours ("AfterHours" page, `20737df74277`)

Greeting: *"Thank you for calling Tea Tea You Online... Our offices are currently
closed. Live agents will be available during business hours... If you have any
questions, I will transfer you to our virtual assistant Ava. If you are interested
in enrolling in the program, I can get your information and set up an appointment
with an advisor, or you can choose to leave a voicemail with our team."*
`link_question`: "How can I help you today?"

| Caller's choice | Target page | outcome_name | Destination |
|---|---|---|---|
| "I would like to get more information about your 10 Kay Degree Program" | `0e5e07ae29249d08` ("Questions - Ava (AH)") | `End - Route to ElevenLabs` | `+18889707775` |
| "Transfer to Ava" | `0e5e07ae29249d08` — **identical target** to the row above | `End - Route to ElevenLabs` | `+18889707775` |
| "I would like to enroll into the 10 Kay Degree Program" | `0d93e521478719ac` ("Enroll") | *(continues into the enrollment funnel below)* | — |
| "Leave a voicemail" | `5f85e63981016467` ("Voicemail") | `End - Route to TTU Online` | `+18067420526` |

So after hours there are exactly 3 distinct outcomes: ElevenLabs, the enrollment
funnel, or the voicemail number — no live-agent/queue destination is reachable at all
after hours (consistent with `OpenHours` being the only place "Talk to a live
agent"/"Transfer to support center" appear).

### Enrollment funnel (from "Enroll", `0d93e521478719ac`)

1. **Enroll** (`0d93e521478719ac`) — script "I would be happy to help you with
   that." `link_question`: "How did you hear about the program?" (`marketing_source`).
   All 9 options (Billboard, Online, Online search, Search engine, Game, Facebook,
   LinkedIn, Social Media, None of the Above) target the **same** next page,
   `30ce7e65a9e8a2a4` — the marketing-source answer never branches the flow.

2. **Interested?** (`30ce7e65a9e8a2a4`) — script "If you are interested, I can
   gather some information and setup a meeting with an advisor." Form field
   `enrollment_interest` (Yes/No), question "Would that be alright?" → unconditionally
   to `b44d34d4ac091c40` ("Interest_formula").

3. **Interest_formula** (`b44d34d4ac091c40`, formula page):
   - `enrollment_interest == "Yes"` → `7cee59522461ad0a` ("Enrollment")
   - `enrollment_interest == "No"` → `10f2f3e1dbd575fb` ("Not Interested")
   - `no_matching_condition_page_id` → `10f2f3e1dbd575fb` (same as "No" — any other
     value also lands on Not Interested)

#### Branch: interested (Yes)

4. **Enrollment** (`7cee59522461ad0a`) — collects `10K_enrollment_first_name`,
   `10K_enrollment_last_name`, `10K_enrollment_phone_number`, `10K_enrollment_email`,
   `10K_contact_preference` (email or phone call). Script: "Great, I can help get you
   started. I am going to gather a few details." `link_question`: "Ok, great, thank
   you! When were you hoping to get started?" (`10K_enrollment_when_to_start`, free
   text) → unconditionally to `647284566c28f672` ("Qualifiers").

5. **Qualifiers** (`647284566c28f672`) — collects `10k_college_credits` (integer,
   "How many college credits do you currently have?") and `10k_live` (multiple choice:
   Dallas / Fort Worth / El Paso, "Do you live in Dallas/Fort Worth or El Paso?").
   Script: "And just 2 more questions related to the program." → unconditionally to
   `3ef000c2d69c8ed1` ("70+ Credits").

6. **"70+ Credits"** (`3ef000c2d69c8ed1`, formula page) — `conditional_links`, in
   this order:
   - `10k_live == "Dallas"` → `5fc022649b229a31` ("Willing To Travel")
   - `10k_live == "Fort Worth"` → `5fc022649b229a31` (same target)
   - `10k_live == "El Paso"` → `5fc022649b229a31` (same target)
   - `10k_college_credits > 69` → `5974ef8fecce3e31` ("ThankYouForCalling", hang_up)
   - `no_matching_condition_page_id` → `5974ef8fecce3e31` (same as the credits row)

   **Since `10k_live` is a required field with only those 3 possible values, one of
   the first three conditions always matches before the credits>69 condition could
   ever be reached** (reading the list in order, first-match-wins). Structurally, the
   `10k_college_credits > 69` condition on this page is dead — every caller who
   answers the location question proceeds to "Willing To Travel" regardless of
   credits. (This reads the static graph in listed order; I can't independently
   confirm the runtime evaluates conditions in this exact order, but there is no
   other selection rule given in the export.)

7. **Willing To Travel** (`5fc022649b229a31`) — form field `willing_to_travel`
   (yes/no), question "Are you able to travel to make these sessions?" Script: "Ok,
   this program meets twice a month in person at the Dallas/Fort Worth location in
   Irving, Texas or at our El Paso location." → unconditionally to `ca33281d4242df2e`
   ("LG willing to travel").

8. **"LG willing to travel"** (`ca33281d4242df2e`, formula page):
   - `willing_to_travel == "Yes"` → `d294a741be21e37b` ("LG yes travel check credits")
   - `willing_to_travel == "No"` → `5974ef8fecce3e31` ("ThankYouForCalling", hang_up)
   - `no_matching_condition_page_id`: **empty string** — no fallback target defined
     here at all (a real gap in the export, though practically unreachable for a
     yes/no field).

9. **"LG yes travel check credits"** (`d294a741be21e37b`, formula page, only reached
   if `willing_to_travel == "Yes"`):
   - `10k_college_credits > 69` → `5974ef8fecce3e31` ("ThankYouForCalling", hang_up)
   - `no_matching_condition_page_id` → `5974ef8fecce3e31` — **identical target either
     way.**

   **Conclusion: every path through the "interested" branch of the enrollment funnel
   terminates at the same page, `5974ef8fecce3e31` ("ThankYouForCalling"),
   regardless of location, college credits, or travel willingness.** There is no
   live-transfer outcome anywhere in the enrollment funnel — it always ends in a
   scripted hangup: *"Perfect! I will pass this information along to one of our team
   members and they will get back with you right away to schedule time with an
   advisor."* This flows into `db3d308f1b759368` ("Any Thing Else" — "Are there any
   other questions I can answer?", `fire_and_forget_connector: true`, one
   unconditional outgoing link regardless of what's said) → `71faf1c34a3397f5`
   ("Disconnect", `is_exit_page: true`, outcome `hang_up`) — *"Well, thanks again for
   calling Texas Tech Online! Have a great day!"*

#### Branch: not interested (No, or `Interest_formula`'s fallback)

10. **Not Interested** (`10f2f3e1dbd575fb`) — form field `not_interested_answer`
    (yes/no), question *"If it's okay with you, I would like to send you an email
    with additional details about the program."* → unconditionally to
    `9a512f1856416d82` ("LG Not Interested Email", formula page).

11. **"LG Not Interested Email"** (`9a512f1856416d82`):
    - `not_interested_answer == "Yes"` → `0dd5ca08333cef65` ("CaptureNot Interested
      Email")
    - `no_matching_condition_page_id` → `1aea2e3e6a88bf50` ("Not Interested End",
      `is_exit_page: true`, outcome `hang_up`) — *"No problem. Please feel free to
      call back if you think of any other questions or if you decide to enroll.
      Thanks again for calling Texas Tech Online."* (this is the destination for
      "No" and for any other/unmatched answer)

12. **CaptureNot Interested Email** (`0dd5ca08333cef65`) — collects
    `10K_enrollment_email` ("What is your email address?"). Script: "Great." →
    unconditionally to `1a2604f83e9f8bf6` ("Not Interested - Send Email",
    `is_exit_page: true`, outcome `hang_up`, `fire_and_forget_connector: true`) —
    *"Great, thank you. Please feel free to call back if you think of any other
    questions or if you decide to enroll. Thanks again for calling Texas Tech
    Online."*

Every branch of "Not Interested" ends in `hang_up` — no live transfer, no ElevenLabs,
no voicemail-number transfer.

## Notes

- **`End - Transfer to Live Agent` has no corresponding outlet/address anywhere in
  the export data.** The outlet nodes are only `End - Route to TTU Online`
  (`+18067420526`) and `End - Route to ElevenLabs` (`+18889707775`). The playbook's
  own `routing_outcomes` list includes `End - Transfer to Live Agent` as a real,
  reachable outcome (from `OpenHours`'s "Talk to a live agent"/"Transfer to support
  center" choices), but this export gives no phone number for it. Do not assume it
  maps to `+18067420526` — that address is explicitly named `End - Route to TTU
  Online` in the export, a different outcome name, reached only via the AH
  "Leave a voicemail" path. This is a genuine gap in the source data, not something
  to infer.
- `hang_up` outcomes (`ThankYouForCalling`→`Disconnect`, `Not Interested End`, `Not
  Interested - Send Email`) correctly have no address — they're call terminations,
  not transfers.
- The **enrollment funnel is only reachable after hours** in this playbook — there is
  no "I would like to enroll" option anywhere in `OpenHours`'s links.
- The two "get more information" / "Transfer to Ava" links on the `AfterHours`
  page are worded differently but are **structurally identical** (same target page,
  same outcome).
- The export data also has two connectors: `Set Phone Number Tag` (tags the
  session with the caller's E.164 number) and `10K Power Automate -> Sharepoint
  (collect on hangup)` (fires on hangup, presumably logging enrollment data
  externally) — neither is a caller-facing branch, both are side-effects layered on
  top of the page flow traced above.
- `Self-Paced Rep`/other-program specific numbers do not appear anywhere in this
  file — 10K's destination set is exactly the 2 addresses above, plus the
  no-address `End - Transfer to Live Agent` gap.

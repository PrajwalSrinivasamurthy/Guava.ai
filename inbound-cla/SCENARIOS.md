# Career Learning Academy — Expected Behavior

There is no legacy Grace playbook for this line; this documents the flow implemented in
`__main__.py`.

Destination addresses (set in `.env` or the "Shared Config" sheet):
- **Live queue** → `LIVE_NUMBER` (`cla_live`)
- **ElevenLabs** ("Ava") → `ELEVENLABS_NUMBER` (`cla_elevenlabs`)
- A destination with no number configured is never transferred to: the agent apologizes,
  says someone will follow up, and hangs up.

## Open Hours

Greeting, then one question ("Be connected to our virtual assistant" or "Be transferred
to a queue to talk to a person"):

| Caller choice | Outcome | Destination |
|---|---|---|
| Virtual assistant (including "transfer me to Ava / the bot") | `End - Route to CLA ElevenLabs` | `ELEVENLABS_NUMBER` |
| Queue / a person | `End - Route to CLA` | `LIVE_NUMBER` |

## After Hours

Business hours are Monday–Friday, 8am–5pm Central; `settings.HOLIDAYS` are closed. The
greeting names the holiday when there is one. Three choices:

| Caller choice | Outcome | Destination |
|---|---|---|
| Virtual assistant | `End - Route to CLA ElevenLabs` | `ELEVENLABS_NUMBER` |
| Leave a voicemail | `End - Route to CLA (voicemail)` | `LIVE_NUMBER` |
| Receive a text message | texts `CLA_AH_TEXT_URL`, then hangs up | none |

If the text can't be sent (no link configured, or the send fails), the agent apologizes,
says someone will follow up, and hangs up.

## Fallback

A `continue_with` value outside the choices above routes to `LIVE_NUMBER`.

## Knowledge-service flow

Used when `KB_SERVICE_URL` and `KB_API_KEY` are set and `KB_ENABLED` isn't `false`. The
sections above describe the flow without it. The task is `assist` and its field is
`outcome`.

Open hours: greeting, then the caller asks any number of questions (answered by
`kb-service`) until they pick one of two outcomes.

| Outcome | Result | Destination |
|---|---|---|
| Transfer to a person (asked for a person, the support center or a representative) | `End - Route to CLA` | `LIVE_NUMBER` |
| No more questions | goodbye, hang up | none |

After hours: same, with three outcomes.

| Outcome | Result | Destination |
|---|---|---|
| Leave a voicemail | `End - Route to CLA (voicemail)` | `LIVE_NUMBER` |
| Receive a text message (only offered when `CLA_AH_TEXT_URL` is set) | texts the link, hangs up | none |
| No more questions | goodbye, hang up | none |

The virtual assistant (`ELEVENLABS_NUMBER`) is not offered in this flow. A transfer is
announced as "our support center". An unrecognized outcome goes to `LIVE_NUMBER`, and a
destination with no number configured ends the call with a follow-up message.

Questions: the service's answer is spoken when it has one. When it has none, or can't be
reached in time, the agent says: "I'm sorry, I don't have an answer for that. I can
transfer you to our support center, or you can ask me something else." Question text is
never logged: the agent doesn't log it, and `privacy.py` redacts the line the Guava SDK writes.

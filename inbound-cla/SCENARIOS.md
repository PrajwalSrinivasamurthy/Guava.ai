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

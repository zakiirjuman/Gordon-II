# Encounter Review — Test Script

Scripted two-speaker dialogue for testing **Gordon II Encounter review** (speaker diarization + officer inference + star evaluation) on the DGX Spark.

---

## How to use

1. Open Gordon II in the browser on a **secure (HTTPS) origin** so the mic is allowed.
2. Scroll to **Encounter review** in the sidebar.
3. Optionally enter an officer device ID (for star tracking).
4. Click **Start encounter recording**.
5. Perform the script below with **two distinct speakers** — two people in the room, or one person switching voices clearly.
6. **Pause 1–2 seconds** between each labeled line so silence-based turn splitting can work.
7. Target **2–4 minutes** for the primary script; use the short script for a quick smoke test.
8. Click **Start encounter recording** again to stop; wait while Gordon runs **diarize → transcribe → Nemotron evaluation** (may take a few minutes on first GPU load).
9. Review the result panel: officer speaker label, intent, rationale, star (or silent), and the diarized transcript.

**Goal:** prove that Gordon separates **Speaker 1 / Speaker 2**, correctly infers which speaker is the officer, and applies the star rubric (award only for clearly strong work; stay silent on mediocre or poor conduct).

---

## Prerequisites checklist

Before running the script, confirm the stack is ready on Spark:

| Check | How to verify | If not ready |
|-------|----------------|--------------|
| **App running** | `curl -s http://gx10-49d1:8080/api/health` returns `"status":"ok"` | `./scripts/deploy_gx10.sh` from repo root |
| **`gpu_interaction_ready: true`** | Same health response includes `"gpu_interaction_ready": true` | Start or rebuild the Parakeet interaction service (below) |
| **HTTPS for microphone** | Open app via Tailscale Serve URL, not plain HTTP | On Spark: `sudo tailscale serve --bg 8080` → use `https://gx10-49d1.<tailnet>.ts.net/` |
| **Parakeet ASR + diarization** | Health shows `nim_ready: true`; UI footer shows `GPU diarization: … + Parakeet on cuda` | Rebuild/restart Parakeet container |
| **Ollama / Nemotron** | Health shows expected model; evaluation returns JSON (not parse errors) | Ensure `nemotron3:33b` is pulled on Spark |

### Rebuild Parakeet (if `gpu_interaction_ready` is false)

```bash
cd asr/parakeet-spark
export NGC_API_KEY=...          # required to pull NVIDIA base image
./build-and-run.sh              # container gordon-parakeet-asr on port 8010
sudo docker logs -f gordon-parakeet-asr   # wait for model load
```

Then redeploy or restart the main app if needed and re-check `/api/health`. The interaction pipeline calls `POST /v1/interaction/analyze` on the Parakeet service; the health endpoint must report a `speaker_model` for GPU diarization to be considered ready.

---

## Primary script — traffic stop (~2–4 min)

**Setting:** Daytime traffic stop. Vehicle pulled to the curb for a minor equipment violation. Officer and driver only.

**Directions:** Read top to bottom — speakers alternate every line. Read the label silently; speak only the quoted line. Pause between turns.

1. **Officer:** "Good afternoon. Toronto Police Service. I'm Constable Chen, badge four-two-one-seven. I stopped you because your rear license plate light isn't working. Can I get your driver's license and registration, please?"

2. **Other person (driver):** "Afternoon, officer. Sure — here's my license and the registration in the glove box."

3. **Officer:** "Thank you. While I run that, can you tell me where you're headed today?"

4. **Other person (driver):** "I'm driving home from work, just a few blocks from here."

5. **Officer:** "I appreciate you keeping your hands on the steering wheel. I'm going to step back to my cruiser for a moment to verify your documents."

6. **Other person (driver):** "Okay. My hands are on the wheel. Do you need me to turn the engine off?"

7. **Officer:** "Your license and registration are valid. The plate light is a Highway Traffic Act equipment issue — I'm going to issue a notice to repair, not a criminal charge."

8. **Other person (driver):** "I didn't realize the light was out. Thanks for telling me."

9. **Officer:** "You have the right to ask questions about the stop. The reason is the plate light; that's an articulable ground for the stop."

10. **Other person (driver):** "Can you explain what a notice to repair means? I've never gotten one before."

11. **Officer:** "If you disagree with the notice, you can contest it through the process on the form. I'm not asking you to admit guilt today."

12. **Other person (driver):** "I'm not trying to argue. I just want to understand my options."

13. **Officer:** "Before I give you the paperwork, is there anything you need me to clarify about why we pulled you over?"

14. **Other person (driver):** "Will this go on my driving record as a conviction?"

15. **Officer:** "No — it's an equipment notice, not a criminal conviction. It won't appear on your record the same way a moving violation would."

16. **Other person (driver):** "No, I think I understand. I'll get the light fixed this week."

17. **Officer:** "I'll document the stop in my notes: equipment violation, cooperative interaction, notice issued."

18. **Other person (driver):** "Okay, that helps. Thank you for explaining it clearly."

19. **Officer:** "Here's your documents back, and a copy of the notice. Please repair the light within the timeframe on the form."

20. **Other person (driver):** "I'll take the notice and get it fixed. Appreciate you giving the documents back."

21. **Officer:** "You're free to go when it's safe. Drive carefully, and have a good afternoon."

22. **Other person (driver):** "Thank you, officer. Have a good afternoon."

23. **Officer:** "If you need a supervisor's name for a complaint or commendation, it's on my business card here."

24. **Other person (driver):** "No, I'm good. Thanks for keeping it professional."

25. **Officer:** "Stay safe out there."

26. **Other person (driver):** "You too. Bye."

---

## Alternate script — quick smoke test (~1 min)

Use this when you only need to confirm diarization and evaluation end-to-end.

1. **Officer:** "Toronto Police. I'm stopping you for speeding in a school zone. License and registration, please."

2. **Other person:** "Okay, officer. Here are my documents."

3. **Officer:** "I'm going to run your documents. Stay in the vehicle with your hands visible."

4. **Other person:** "Understood. Hands on the wheel."

5. **Officer:** "Everything checks out. I'm issuing a warning today. Drive safely near schools."

6. **Other person:** "Thank you for the warning. I'll slow down."

7. **Officer:** "You're free to go."

8. **Other person:** "Thanks. Have a good day."

---

## Optional variant — strong star (de-escalation language)

Use the **same driver lines** from the primary script (turns 2, 4, 6, …). Read **only the officer lines** below in place of the primary officer lines to test that Gordon awards a **★ STAR** for clearly strong, accountable conduct (articulable grounds, distance, calm control, rights advisement, documentation).

1. **Officer:** "Good afternoon. Toronto Police Service. Constable Chen, badge four-two-one-seven. I'm stopping you for a specific reason: your rear license plate light is out. That's an equipment violation under the Highway Traffic Act. May I see your driver's license and registration?"

2. **Other person (driver):** *(same as primary turn 2)*

3. **Officer:** "Thank you. I'm going to maintain some distance at the door while we talk. Where are you headed today?"

4. **Other person (driver):** *(same as primary turn 4)*

5. **Officer:** "I appreciate you keeping your hands visible on the steering wheel. I'm stepping back to my cruiser to verify your documents — you're not being detained beyond this traffic stop."

6. **Other person (driver):** *(same as primary turn 6)*

7. **Officer:** "Your documents are valid. The plate light is fixable equipment — I'm issuing a notice to repair, not a criminal charge, and I'm explaining that before you sign anything."

8. **Other person (driver):** *(same as primary turn 8)*

9. **Officer:** "You have the right to ask why you're stopped and to contest any notice through the proper channel. The articulable ground today is the plate light only."

10. **Other person (driver):** *(same as primary turn 10)*

11. **Officer:** "I'm not asking for a statement about fault. If you want a supervisor, I can provide my name and badge number now."

12. **Other person (driver):** *(same as primary turn 12)*

13. **Officer:** "Is there anything about your rights or the reason for the stop that you want clarified before I finish the paperwork?"

14. **Other person (driver):** *(same as primary turn 14)*

15. **Officer:** "No — it's an equipment notice, not a criminal conviction. It won't appear on your record the same way a moving violation would."

16. **Other person (driver):** *(same as primary turn 16)*

17. **Officer:** "I'm documenting the stop: equipment violation, cooperative driver, notice issued, no search, no arrest."

18. **Other person (driver):** *(same as primary turn 18)*

19. **Officer:** "Here's your license, registration, and a copy of the notice. Repair the light by the date on the form."

20. **Other person (driver):** *(same as primary turn 20)*

21. **Officer:** "You're free to leave when traffic is clear. Thank you for keeping the interaction calm."

22. **Other person (driver):** *(same as primary turn 22)*

23. **Officer:** "My supervisor contact is on the card if you want to file feedback — positive or negative."

24. **Other person (driver):** *(same as primary turn 24)*

25. **Officer:** "Take care."

26. **Other person (driver):** *(same as primary turn 26)*

**Expected:** `star_awarded: true`, rationale citing clear grounds, calm tone, distance, rights, and documentation.

---

## Optional variant — no star (poor officer language)

Use the **same driver lines** from the primary script (turns 2, 4, 6, …). Read **only the officer lines** below in place of the primary officer lines to test that Gordon stays **silent** — no star for mediocre or poor conduct.

1. **Officer:** "Police. You know why I pulled you over. License. Now."

2. **Other person (driver):** *(same as primary turn 2)*

3. **Officer:** "Don't get smart with me. Just answer the question."

4. **Other person (driver):** *(same as primary turn 4)*

5. **Officer:** "Keep your hands where I can see them. I'm not repeating myself."

6. **Other person (driver):** *(same as primary turn 6)*

7. **Officer:** "You're getting a ticket. Sign it or we'll do this the hard way."

8. **Other person (driver):** *(same as primary turn 8)*

9. **Officer:** "You don't need to know my name. Do what I say."

10. **Other person (driver):** *(same as primary turn 10)*

11. **Officer:** "If you keep talking, this gets worse for you."

12. **Other person (driver):** *(same as primary turn 12)*

13. **Officer:** "Stop complaining. Everybody says the same thing."

14. **Other person (driver):** *(same as primary turn 14)*

15. **Officer:** "It's just paperwork. Sign it and move on."

16. **Other person (driver):** *(same as primary turn 16)*

17. **Officer:** "I'm not writing a novel in my notes. Equipment violation. Done."

18. **Other person (driver):** *(same as primary turn 18)*

19. **Officer:** "Here's your stuff. Fix the light or next time it's on you."

20. **Other person (driver):** *(same as primary turn 20)*

21. **Officer:** "Get out of here before I change my mind."

22. **Other person (driver):** *(same as primary turn 22)*

23. **Officer:** "No, you're not getting a supervisor. Drive."

24. **Other person (driver):** *(same as primary turn 24)*

25. **Officer:** "Go."

26. **Other person (driver):** *(same as primary turn 26)*

**Expected:** `star_awarded: false` (silent on bad work), officer still inferred correctly, rationale noting poor tone / lack of explanation / escalation risk; `danger` may flag if language appears unsafe.

---

## Pass / fail criteria — diarization & evaluation

### Pass (demo success)

| Criterion | What to look for |
|-----------|------------------|
| **Two speakers separated** | Diarized transcript shows both **Speaker 1** and **Speaker 2** with distinct turns (not one merged block). |
| **Turn count plausible** | Roughly matches number of exchanges (primary: ~26 turns; smoke: ~8). |
| **Officer inferred** | `Officer speaker: Speaker 1` or `Speaker 2` matches the person who read officer lines. |
| **Intent summary** | Mentions traffic stop, equipment/documents, or similar — not nonsense. |
| **Engine path** | UI shows GPU diarization (`speaker_model` + Parakeet on cuda), not only CPU fallback. |
| **Star rubric (strong variant)** | Strong-star run awards a star; poor-variant run does **not** award a star. |
| **Latency** | Processing completes without timeout; timings appear in the UI. |

### Fail (investigate before demo)

| Symptom | Likely cause |
|---------|----------------|
| Single speaker only | Overlapping speech, no pauses, or one mic / one voice too similar |
| Swapped officer label | Both voices too similar; officer lines not clearly authoritative |
| Empty or garbled transcript | ASR down — check Parakeet logs and `nim_ready` |
| `gpu_interaction_ready: false` | Parakeet container not running or missing interaction endpoint |
| CPU fallback only | GPU service unreachable from app (`NIM_ASR_URL` / port 8010) |
| Evaluation parse error | Ollama/Nemotron unavailable or returned non-JSON |
| Star on poor variant | Rubric misfire — note rationale and retry; not a diarization pass/fail by itself |

---

## Tips for reliable results

- **Pause between lines.** Gordon splits turns on silence; a full beat after each speaker helps more than rushing.
- **Do not overlap.** Wait until the other person finishes before you speak. Simultaneous talk collapses diarization on a single microphone.
- **One mic limitation.** Browser recording is typically one channel — both speakers share the same mic. Separation depends on voice clustering, not separate tracks. Distinct pitch, pace, or accent between speakers helps.
- **Consistent roles.** One person always reads **Officer**; the other always reads **Other person**. Do not swap mid-script.
- **Room noise.** Quiet room beats TV, music, or hallway chatter.
- **HTTPS only.** Safari and many browsers block `getUserMedia` on HTTP; use Tailscale Serve.
- **First run slower.** Cold GPU load for Parakeet + Nemotron can take several minutes; run the smoke test once before a judge demo.
- **Optional officer ID.** Set a device ID before recording if you want star counts to accumulate under `/api/officers/`.

---

## Quick reference

| Item | Value |
|------|--------|
| UI section | **Encounter review** |
| Health check | `GET /api/health` → `gpu_interaction_ready` |
| API | `POST /api/interaction/evaluate` (UI handles upload after stop) |
| Sessions | `data/interactions/` on Spark |
| Stars | `data/officers/` on Spark |
| Docs | [GORDON_II.md](./GORDON_II.md), [JUDGING.md](./JUDGING.md), [DEPLOY.md](./DEPLOY.md) |

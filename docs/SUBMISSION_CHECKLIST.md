# Gordon II — submission checklist (May 31, due 11:00)

**Team:** Gordon II · Urban Operations · Toronto Open Data Hackathon  
**Reader for demo video:** Zak (Zakiir Juman)

## Status at a glance

| Item | Owner | Status | Link / notes |
|------|-------|--------|--------------|
| Team name & roster | Leon | Done | Gordon II — see submission doc |
| Project description | Leon | Done | In `FOR ZAKGordon_II_Submission.docx` |
| Demo script (4 min) | Leon | Done | Same doc, §4 |
| **Demo video (3–5 min)** | **Zak** | **TODO** | Unlisted YouTube or Vimeo |
| **README** | **Zak** | **Done in repo** | [README.md](../README.md) |
| **Deployed URL** | **Zak** | **Live** | See below |
| **Repo public** | **Zak** | **Done** | https://github.com/zakiirjuman/Gordon-II |
| Submission form | Zak | TODO | Paste video + URLs before 11:00 |

## Deployed demo URLs

| URL | Use |
|-----|-----|
| https://gx10-49d1.tail935b6d.ts.net | **Submit this** — HTTPS, mic works, Tailscale |
| http://gx10-49d1:8080 | Backup if judges are on tailnet HTTP |

**Pre-flight (run before recording):**

```bash
curl -s https://gx10-49d1.tail935b6d.ts.net/api/health | python3 -m json.tool
curl -s http://gx10-49d1:8080/api/health | python3 -m json.tool
```

Expect: `"status":"ok"`, `"corpus_version":"gordon-ii-0.4"`, `"nim_ready":true`, `"rag_mode":"embeddings"`.

If briefs are slow, warm cache once:

```bash
curl -s -X POST https://gx10-49d1.tail935b6d.ts.net/api/patrol-brief -o /dev/null
```

## Demo video shot list (follow submission doc §4)

Record screen + voice. Target **4:00**, hard cap **5:00**. Use QuickTime or OBS; 1080p is enough.

| Time | Show | Say (short) |
|------|------|-------------|
| 0:00–0:30 | Title / you on camera optional | Problem: officer stress, culture, Gordon = Jim Gordon not Batman |
| 0:30–1:15 | Map with layers on | Live Toronto data: restrictions, construction, KSI, wards, schools, fire |
| 1:15–2:00 | Click map → patrol brief | Lookout / Authority / Do not, cited cards, local Nemotron |
| 2:00–3:10 | Ask Gordon or voice | Officer decompresses after hard call; private, no file |
| 3:10–3:40 | `/api/health` or NVIDIA badge in UI | Spark = privacy; nothing leaves the car |
| 3:40–4:00 | Map + brief visible | Close: lawful, local, in their corner |

**Must-show beats:** map click brief (your screenshot location is perfect), one Ask or voice answer, mention simulated units are demo-only.

**Optional if time:** encounter recording → star (adds ~45s).

Upload **unlisted** YouTube; title: `Gordon II — Lawful Patrol Copilot (Toronto Open Data Hackathon 2026)`.

## Screenshots (if form asks for capture)

Already captured during dev; grab fresh if needed:

1. Full dashboard (map + sidebar stats)
2. Point brief open (Gatineau / Ward 21 example)
3. Ask Gordon answer with law cards expanded

## Morning timeline (7:45 → 11:00)

| Time | Action |
|------|--------|
| 7:45–8:15 | Push final README; verify Spark health |
| 8:15–9:15 | **Record demo video** (one take + one backup take) |
| 9:15–9:45 | Upload video; copy unlisted link |
| 9:45–10:15 | Fill hackathon submission form (video, repo, demo URL) |
| 10:15–10:45 | Live rehearsal on HTTPS URL (map click → brief → ask) |
| 10:45–11:00 | Submit; keep Spark running |

## What to paste in the form

- **GitHub:** https://github.com/zakiirjuman/Gordon-II
- **Demo URL:** https://gx10-49d1.tail935b6d.ts.net *(note: Tailscale — judges may need access or use video)*
- **Video:** unlisted link after upload
- **Track:** Urban Operations

## Teammate handoff

- **Leon:** final project description wording if form has character limits
- **Tushar:** optional 30s UI polish screenshot for slide deck (already shipped Hearth skin)

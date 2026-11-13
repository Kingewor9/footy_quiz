# Footy Quiz (Telegram mini app)

Admin schedules a quiz, the bot posts it in your channel, fans play in the mini app, a daily leaderboard
resets at midnight and the bot posts a winner image card the next day.

**Stack:** React + TypeScript (Vite) frontend, Python FastAPI backend in `api/`, MongoDB. Frontend and
backend deploy together to Vercel as one project.

```
api/index.py        Vercel entrypoint (FastAPI app)
api/_lib/           routes, auth, grading, leaderboard, Telegram helpers, winner card (Pillow), jobs
src/                React app: Home, Leaderboard, Play, Admin (Send quiz + Analytics)
tests/              backend tests (pytest, in-memory Mongo)
```

## How it behaves

- **Quizzes** hold several questions. Each question is a **poll** (options + correct one), a **text answer**
  (comma-separated accepted answers, case/accent/punctuation ignored) or an **image** question (image link,
  with options or a typed answer). You set the points per question.
- **One play per quiz.** Correct answers never reach the browser; grading and timing happen on the server.
- **Score** = sum of points for correct answers. The admin sets each quiz's time limit (1–3600 seconds,
  default 60); players see a countdown and their answers submit when it expires. **Total time** is measured
  by the server in whole seconds and only breaks ties.
- **Several quizzes a day** add up on that day's leaderboard. The day runs 00:00-23:59 in `APP_TZ`.
- Leaderboard arrows show how many places the most recent quiz moved a player (green up, red down, dash = no
  change or first quiz of the day).
- A quiz stays playable for 24 hours after it is posted.
- **Winner card:** the first tick after midnight posts a 1080x1080 card (name, profile photo, points, time)
  to the channel. It falls back to initials if the photo can't be fetched. Posted once per day, retried on failure.

## 1. Telegram setup

1. Create a bot in @BotFather, copy the token (`BOT_TOKEN`).
2. Add the bot as an **admin of your channel** (permission to post).
3. In BotFather: `/newapp`, pick the bot, set the Web App URL to your Vercel URL and choose a short name
   (for example `play`). Your direct link is `https://t.me/<bot_username>/<short_name>` and goes in `MINI_APP_LINK`.
4. Get your own numeric Telegram id (for example from @userinfobot) and put it in `ADMIN_IDS`.

## 2. Deploy to Vercel

1. Create a free MongoDB Atlas cluster, allow access from anywhere (`0.0.0.0/0`, Vercel IPs change) and copy the connection string.
2. Push this folder to GitHub and import it in Vercel (framework is detected as Vite; `vercel.json` handles the API rewrite).
3. Add the environment variables from `.env.example` in Vercel > Settings > Environment Variables.
4. Deploy, then put the deployed URL into BotFather (step 3 above).

## 3. Scheduler (important)

Vercel has no always-on process, so scheduled quizzes and the midnight winner post run when
`GET /api/cron/tick` is called. It publishes any quiz whose time has come and announces yesterday's winner.

- **Free option that works on any plan:** create a job at https://cron-job.org that calls
  `https://YOUR-APP.vercel.app/api/cron/tick` **every minute** with the header
  `Authorization: Bearer <CRON_SECRET>` (or add `?key=<CRON_SECRET>` to the URL).
- **Vercel Cron:** on a Pro plan you can add `"crons": [{ "path": "/api/cron/tick", "schedule": "* * * * *" }]`
  to `vercel.json`. Vercel sends `CRON_SECRET` automatically. Hobby plans only allow one run per day,
  so use cron-job.org there.

"Send now" quizzes don't need the scheduler; only scheduled ones and winner announcements do.

## Local development

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
npm install
$env:MONGODB_URI = "mongomock://"
$env:DEV_MODE = "1"
$env:ADMIN_IDS = "1001"
npm run api                     # FastAPI on :8000
```

In another terminal, run `npm run dev` for the frontend on `:5173`. Run backend tests with
`python -m pytest -q tests`.

**macOS / Linux**

```bash
pip install -r requirements-dev.txt && npm install
export MONGODB_URI=mongomock:// DEV_MODE=1 ADMIN_IDS=1001   # in-memory DB, resets on restart
npm run api                     # FastAPI on :8000
npm run dev                     # Vite on :5173 (proxies /api), acts as dev user 1001 (admin)
python -m pytest -q tests       # backend tests
```
`DEV_MODE` lets a plain browser pretend to be a Telegram user. Never set it on Vercel.

## Good to know

- Admin routes are protected on the server using Telegram's signed login data, not just hidden in the UI.
- The winner card font (Poppins, OFL licence) covers Latin letters; emoji and other scripts in a name are dropped from the card.
- If the channel post fails when you send a quiz, it still goes live in the app and the Admin page shows the reason.

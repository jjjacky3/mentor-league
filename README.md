# Fantasy Football "Mentor League" Overlay Application

A custom fantasy football overlay system designed for 10-team leagues on **Sleeper**, where teams are grouped into **5 pairs of 2 teams** (1 "Beginner" + 1 "Expert/Mentor").

While each team drafts independently and plays on Sleeper's standard weekly schedule, this application combines each pair's weekly results, applies specialized bonus rules (like the **1.5× Upset Bonus** when a Beginner beats a Mentor), tracks **Mentee Performance**, and publishes an automated static dashboard ready for GitHub Pages.

---

## ⚡ Key Rules Implemented

- **Weekly Pair Records**: Teammates' individual results combine per week:
  - Both win: **2-0** | Split: **1-1** | Both lose: **0-2**
- **Upset Bonus**: If a Beginner defeats an Expert opponent from another pair, that win counts as **1.5 wins** instead of 1.0!
- **Teammate Head-to-Head Wash**: If two teammates face each other on Sleeper's schedule, the matchup naturally washes to **1-1** with no upset bonus applied internally.
- **Season Tiebreaker**: Ranked by total combined wins (with upset bonuses), with **Total Points For** as the official tiebreaker.
- **Top Mentee Performance**: Secondary leaderboard ranked by weighted scoring:
  $$\text{Weighted Score} = 0.70 \times \text{Beginner Points} + 0.30 \times \text{Mentor Points}$$
- **Peer Leaderboards**: Pure individual head-to-head rankings for Beginners (1–5) and Mentors (1–5).
- **Weekly Awards**: Auto-computed badges for *Highest Combined Score*, *Best Upset*, *Biggest Blowout*, and *Closest Match*.
- **The Mentor Cup Playoffs**: Top 4 pairs qualify for a 2-round virtual head-to-head bracket (Seed 1 vs Seed 4, Seed 2 vs Seed 3) decided by combined pair points.

---

## 🚀 Quickstart

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Preview with Mock Demo Data
You can test the entire pipeline, scoring engine, and HTML dashboard right away with realistic 3-week mock data:
```bash
python -m src.main --mock
```
This generates:
- `docs/index.html` — Interactive static dashboard with dark mode and tabs.
- `docs/standings.csv` — CSV export of pair standings.
- `data/standings.json` — Structured JSON data.

Open `docs/index.html` in your browser to explore the dashboard.

---

## ⚙️ Connecting Your Sleeper League

### Step 1: Add Your League ID
In `config/pairs.json`, replace `"REPLACE_WITH_SLEEPER_LEAGUE_ID"` with your Sleeper League ID (found in League Settings or your browser URL: `sleeper.com/leagues/<LEAGUE_ID>`):

```json
{
  "league_id": "123456789012345678",
  "season": "2024",
  "upset_bonus_multiplier": 1.5,
  "weighted_score": { "beginner_weight": 0.7, "expert_weight": 0.3 },
  "playoff_qualifiers": 4,
  "pairs": [ ... ]
}
```

### Step 2: Inspect League & Assign Pairs
Run the league inspection helper:
```bash
python -m src.main --init-pairs
```
This prints all 10 teams, owners, and their Sleeper `roster_id`s so you can easily assign the 5 pairs in `config/pairs.json`.

### Step 3: Fetch Live League Data & Build Dashboard
```bash
python -m src.main --fetch
```

---

## 🧪 Running Tests

Execute the automated test suite covering upset bonuses, partner washes, weighted scores, and tiebreakers:
```bash
python -m pytest tests/ -v
```

---

## 🌐 Publishing to GitHub Pages

1. Push your repository to GitHub.
2. In your repository on GitHub:
   - Go to **Settings** → **Pages**.
   - Under **Build and deployment**, set **Source** to **Deploy from a branch**.
   - Select your main branch and the `/docs` folder.
   - Click **Save**.
3. The included GitHub Action (`.github/workflows/weekly-update.yml`) will automatically run every Tuesday at 09:00 UTC (after Monday Night Football), pull the latest Sleeper scores, recalculate standings, and commit the updated site to GitHub Pages!


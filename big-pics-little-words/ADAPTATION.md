# ADAPTATION.md - effective-html (plannotator)

## 1. Source
- Repo: https://github.com/plannotator/effective-html
- Branch: main (tar.gz archive pulled via codeload.github.com on 2026-10-22)
- Version: no explicit tag; SKILL.md frontmatter only has name/description, no version field
- Author: plannotator (GitHub org)
- Package manifest (19 files):
  - 7 SKILL.md (one per skill)
  - 7 agents/openai.yaml (agent model config, not executable)
  - html/references/*.md (5): charts-and-data / creative-direction / diagrams / documents-and-presentations / interfaces

## 2. Audit conclusion
- Rating: **P2 (pure Markdown instructions, no executable code)**, safe to install directly.
- Per-criterion:
  - Executable code (scripts/shell/python/curl|bash/eval): none
  - Data exfiltration (webhook/hardcoded domain/base64 upload .env): none
  - Prompt injection (ignore previous instructions/override system prompt/don't tell user): none
  - Credential reads (SSH key/token/.env/browser cookie): none
  - Destructive actions (unconfirmed delete/rm -rf/git push --force): none
  - Dependency download (postinstall/pip/npm install): only design-artifact mentions optional `npm install -g @plannotator/tot` to publish finished HTML as a public share page, explicitly gated behind user consent ("Never publish or install without the user's explicit consent") - not postinstall, not auto-run -> low-risk note, recorded.
- Upstream README vs reality: README's `npx skills add` installs into `.claude/skills/` (Claude Code dir), which WorkBuddy does not read; this install follows community-skill-install flow into `~/.workbuddy/skills/`, upstream SKILL.md preserved verbatim.

## 3. Path mapping
- Upstream assumed paths -> WorkBuddy actual (default mapping):
  - User-level SOUL.md/USER.md/MEMORY.md -> `C://Users//Lenovo//.workbuddy//` (already exists, not recreated)
  - Daily log -> `<workspace>\.workbuddy\memory\YYYY-MM-DD.md` (append-only)
  - Long-term notes -> `<workspace>\.workbuddy\memory\MEMORY.md`
  - Inter-skill refs `../<sibling>/SKILL.md` -> valid because all 7 skills are siblings under `~/.workbuddy/skills/`
  - Upstream `tot` CLI (tot.page share) not built into WorkBuddy -> only `npm install -g @plannotator/tot` on explicit user consent, else skip

## 4. Division of labor with installed skills
- Role: big visuals + minimal text explainers of the current subject (from bro's big-pics-little-words).
- Overlaps: answer-me-with-html (single-page visual explainer).
- Division: use for 'a picture is worth a thousand words' explainers; use answer-me-with-html to turn a specific answer into a standard explainer page.

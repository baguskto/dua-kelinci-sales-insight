# antislop Delivery Gate: CEO view (branch ceo-view)

antislop active: during (session override). Direction: [DESIGN.md](../DESIGN.md) (owner file, copied verbatim, icon list appended).

Design Read: one-screen sales dashboard for a Commercial Director / CEO and Head of Sales, in a calm "measuring instrument" language (zinc + one Dua Kelinci red, heavy use of numbers, tick meters), dial ENERGY 2 / RHYTHM 2 / MOTION 1.

Result: **PASS**, no open FAIL. Evidence below was produced on 26-27 Nov 2026 on this branch.

## Block 1: Hard Gate

| Rule | Status | Evidence |
|---|---|---|
| R-02 em dash | PASS | `grep "—"` over templates, app.js, app.css, summary.py, views.py, DESIGN.md: no match. `test_dashboard_redesign_parts` asserts no U+2014 in the page. |
| R-03 mobile | PASS | 390x844: scrollWidth 390, one column in desktop order (`test_mobile_layout_is_one_column_in_order`), no element outside its card (`test_nothing_clipped_or_overflowing[390]`). Tap targets 44px on phone (icon buttons, info, selects, chips). Long outlet name ends in an ellipsis with the full name in `title`. |
| R-17 numbers | PASS | Every number comes from `analytics.story()` / `weakest_outlets()` on the loaded file; unit tests pin them (`test_story_matches_the_month_on_month_numbers`, `test_top_contributor_and_growth_without_it`). No placeholder numbers. |
| R-18 testimonials | PASS | None. |
| R-23 assets | PASS | Logo is the existing Dua Kelinci asset already approved; map outline from Natural Earth (public domain); icons Lucide (owner decision). No avatars or invented assets. |
| R-24 navigation | PASS | No nav to missing pages; the old rail was removed. |
| R-25 contrast | PASS | contrast-check.py: zinc-900 on white 17.72, zinc-900 on zinc-100 16.12, zinc-500 on white 4.83, zinc-600 on zinc-100 7.03, white on #DC2B2D 4.74, zinc-900 on zinc-200 13.96. zinc-500 on zinc-100 is 4.40 (FAIL), so it is never used on the canvas (`--muted-on-canvas` = zinc-600 for header and footer). |
| R-26 controls | PASS | Click-through below; every control navigates, opens a dialog, downloads or copies. |
| R-27 states | PASS | Empty: no file ("No data yet" + upload), no data in access, filter with no sales ("Clear filters"), month without an earlier month (totals-only cards, "No earlier month to compare with"), no weak outlet. Loading: upload shows progress + "Checking file...". Error: English error page (404/403/500), upload rejection alert keeps the current data. |
| R-28 FAQ | PASS | None. |
| R-32 keyboard | PASS | Skip link is the first Tab stop; every control is a native button/link; dialogs close with Escape (checked for 4 drawers); line chart is focusable, arrow keys / Home / End move the tooltip, Escape hides it (`test_line_chart_tooltip_follows_keyboard`); 2px zinc-900 focus ring. |
| R-33 no patch scripts | PASS | Features are in the source. Edits during the session were made to source files; no patch script is kept in the repo. `scripts/build_map.py` generates a data asset (the outline JSON) from Natural Earth, it does not rewrite source or CSS. |
| R-34 themes | PASS | No theme toggle; light only (business tool, brand white). |
| R-35 verified | PASS | Built and run (`python app.py`), 177 tests green (unit, integration, 12 e2e in Chromium), ruff, mypy, bandit, live_eval 37/37 + 24/24. Click-through list below, no console errors. |
| R-36 claims | PASS | No security/performance claims on the page. Performance numbers in docs are byte sizes measured with `ls`/`wc`, not Web Vitals (not measured). |
| R-37 direction | PASS | DESIGN.md from the owner. Lucide conflict (R-04) raised and decided by Bagus: keep. |
| R-38 content | PASS | Real data only; chat example questions are real questions the offline engine answers. |
| R-39 semantics | PASS | `cursor: pointer` set once for a, button, summary, select, label[for]; disabled = not-allowed; icon-only buttons have `aria-label`; icons `aria-hidden`; every img has alt; selects have labels; hover/active states on every control; no motion; one h1, `lang="en"`, unique titles, header/main/footer landmarks; viewport allows zoom. |
| R-40 performance | PASS | All `<img>` have width/height; no third-party script (ECharts removed, 1,034,102 bytes less); app.js deferred; no Web Vitals reported. |

## Block 2: Purpose-Gate

| Rule | Status | Reason written |
|---|---|---|
| R-01 gradients/glow | PASS | None. |
| R-04 icons | PASS (owner override) | Lucide kept by Bagus's decision; per-glyph relevance listed in DESIGN.md. Icons sit in card heads and on row actions only. |
| R-06 typography | PASS | Plus Jakarta Sans: Indonesian-made, rounded, tabular figures; weights 400/500 only; no monospace (the old `.mono` class now only sets tabular figures). |
| R-07 background pattern | PASS | None. |
| R-08 arrows | PASS | "→" only inside data labels (Sep → Oct, 9 → 18) where it means "changed to"; no decorative button arrows. |
| R-09 badges | PASS | No capsule badges; the data-quality badge is a real status button. |
| R-10 glass | PASS | None. |
| R-12 shadow | PASS | Only the tooltip chips (info and line chart) have a shadow: they float over content. |
| R-13 glow | PASS | None. |
| R-14 cards | PASS | Same card shell (system), different content per card: line, diverging bars, day ticks, map, bridge, bars, composition, table, meter. Hierarchy: bridge, map and weak outlets span two columns because they carry the most rows. |
| R-19 animation | PASS | MOTION 1: no entrance animation. |
| R-22 illustration | PASS | The only drawing is the region map, which carries data. |

## Block 3: Liveliness

| Question | Answer |
|---|---|
| Dials set | Yes: ENERGY 2 / RHYTHM 2 / MOTION 1. |
| Output matches dials | Yes: one card system, content varies; no motion beyond hover/focus/tooltip. |
| Focal point | Yes: the red current-period series (line, Oct total bar) and the red selected chip; red appears nowhere else except filled ticks and the one primary button. |
| Structural whitespace | Yes: 16px gaps, 16px card padding, dashed separators inside cards. |
| One accent | Yes: Dua Kelinci red only. |
| Identity motif | Yes: thin vertical tick meters (top-outlet share, trading days, weakest outlets, data quality). |
| Design Read declared | Yes (top of this file). |

## Block 4: Craftsmanship and Quality Locks

All answers "no": no AI-default-only decisions (C-1); no dead controls (C-2); every card answers one question from the brief or the story (C-3); no break at 1440x900, 1280x800, 1024x768, 390x844 or keyboard-only (C-4); no fabricated content (C-5); not a template layout (R-05: no hero, no bento; equal card grid with three double-width cards for the row-heavy content); radius 12/10/8 by role (R-11); CTAs specific and at most 2 words: "Open summary", "Details", "Ask", "Send", "Copy", "Print" (R-15); no buzzwords (R-16); identity holds without the logo through the red-on-zinc instrument look and tick meters (R-20); light theme by brand (R-21); palette zinc + 1 accent (R-29); not a clone (R-30); every major decision has a one-line reason in DESIGN.md or here (R-31).

## UI Skill Checklist

| Item | Answer |
|---|---|
| Palette from DESIGN.md | Yes, all colors are tokens in `:root` of app.css. |
| Accent at the key moment only | Yes. |
| No decorative emoji | Yes (▲▼ ✓ are data symbols). |
| Compositions vary per RHYTHM | Yes (RHYTHM 2: consistent cards, varied content). |
| No bento, terminal, pricing columns, left stripes | Yes. |
| No pill above the H1 | Yes. |
| Every control has a destination | Yes (click-through). |
| Motion follows the dial | Yes. |
| Glass/glow/shadow/radius at dose caps | Yes. |
| Every dot marks a real state | Yes (legend dots = segments; no status lights). |
| Layout built around the decision | Yes: change, is it real, where from, what to decide. |
| Navigation shell designed | Yes: the old rail was removed; header holds period, filters, data quality and Ask; works the same on phone. |
| Real numbers only | Yes. |
| Empty cells honest | Yes. |
| Empty/loading/error states name cause and action | Yes. |
| Holds at every breakpoint and keyboard-only | Yes. |
| Media sized, no blocking third-party script, metrics measured | Yes. |

## Click-through (1440x900, local server, sales.csv)

```
Period chips Sep / Oct / Sep-Oct -> reload with ?period=, Sep shows totals-only cards (e2e)
Region and brand selects -> submit the filter, chip appears, chip x removes it (e2e)
Map circle W. Java -> ?region=Jawa Barat, chip "West Java" (e2e)
Bridge "Grosir Lancar Jaya" -> /outlet/OUT1036 (e2e); "West Java" -> ?region=Jawa%20Barat
Line chart -> tooltip at Oct 31; ArrowLeft Oct 30; Home Oct 1; Escape hides (e2e)
Data quality 'Details' -> opens #dq-drawer, Escape closes
Header data-quality badge -> opens #dq-drawer, Escape closes
'Method' -> opens #def-drawer, Escape closes
'Open summary' -> opens #tg-drawer, Escape closes; 'Copy' copies the summary (e2e); 'Print' -> 200 English page
'Ask' -> opens #chat-drawer; question and example chip answer with a source (e2e); Escape closes
Info icons: 11/11 show their tooltip on keyboard focus
'CSV' -> 200 text/csv
Schedule visit (.ics) -> downloads visit-OUT1003.ics, SUMMARY "Visit Toko Sinar Abadi (OUT1003)" (e2e)
Copy task -> clipboard "Visit task: Toko Sinar Abadi (OUT1003)...", status "Task copied." (e2e)
Top outlet title, share line, weakest outlet name -> outlet pages
Brand share legend -> ?brand=Kacang Dua Kelinci; brand movers row -> ?brand=Pilus
Logo -> /; first Tab -> "Skip to content"
Upload a broken file -> "File rejected." and the dashboard keeps Rp 878.4M (e2e)
Console errors: none
```

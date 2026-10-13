# Nutrition Intelligence 2.0

## Directed audit

Base main after PR40: `ccf566bf38b365e0bffe1628c8b86a9e2ab4ad77`. Existing sources are Meal/MealItem, NutritionGoal, WaterLog, NutritionPlan/PlannedMeal/PlannedFood and Recipe/RecipeIngredient. Meals already use owned activity receipts; plans have atomic import and archival. No independent food inventory or price database exists.

GET goals formerly created default targets; period aggregates also fabricated default goals. Food estimates were editable in the UI but their provenance was discarded on save. Macros are per recorded quantity unit, not implicitly per 100g. Existing floats and legacy totals must remain intact; deterministic projections use Decimal and display rounding only at the boundary.

Image support imports diet documents/photos, not recognition of dishes. Preserve that capability and label extracted plan composition as estimated/unverified. Do not introduce another image service, storage or paid infrastructure.

## Contracts and decisions

Reuse historical meals as templates/favorites and existing user preferences for explicit availability, exclusions and optional budget/price declarations. Favorite references do not duplicate meal history. Reuse the owned receipt transaction for confirmed quick registration; previews never write meals, XP, finance or calendars.

Migration `c9e42a7d160b` adds six new nullable fields: meal-item, planned-food and recipe provenance, meal source references and goal confirmation metadata. It does not rewrite old values or infer which historical defaults were intentionally selected. Old goals remain visible as unconfirmed until explicitly saved; missing goals remain missing. Nutrition evidence records supplied macro fields, including explicit zero, registered/estimated source and the declared unit. Missing fields remain unknown even when legacy storage uses numeric zero.

The Nutrition Engine owns nutrition calculations. Finance provides only explicit budget limits; declared prices remain known or estimated and never become expenses. Recorded training/calendar commitments supply context, never calorie expenditure or clinical needs. Organization proposals have dates and meal references, not competing scheduling or automatic fixed-commitment changes. Life State and Agent reuse these contracts and their existing permissions.

## Usage and boundaries

The Nutrition **Inteligência** tab reads the selected local date on demand. Each macro separates registered, estimated and historical unverified values. A missing macro makes the complete total and remaining target unknown; a supplied zero is known. Empty dates show zero recorded consumption, not a claim that the person did not eat. Only explicitly confirmed target fields are used; historical defaults stay available for human review, never automatically confirmed.

Own historical meals, active planned meals and saved recipes supply alternatives. Favorites, declared available foods, exclusions and optional per-unit prices stay in the existing user-preferences namespace. A portion factor changes a preview; **Registrar com confirmação** creates a new owned meal with a receipt and source reference. Recipes require a chosen meal type. Existing units are literal: a planned `100 g` portion is one such portion, not 100 implicit servings. Unknown legacy composition remains unknown; positive AI/plan composition remains estimated.

Optional financial budgets are read through FinanceEngine, with remaining recorded capacity and a matching month. Daily budget proposals cannot borrow the next day's capacity. Missing prices do not prove affordability. No expense, purchase, stock or training expenditure is inferred. Nutrition organization is a dated proposal; the Life State adapter exposes dated active-plan candidates to the single Global Planner without invented duration or automatic scheduling. Fixed calendar commitments remain fixed.

The existing PDF/photo import now opens an editable preview backed by an owned upload receipt in the existing ActivityReceipt table, valid for 24 hours. Only receipt metadata is saved during preview: no plan, meal, target or XP. Confirmation requires that receipt and verifies document structure/origin; permitted edits are plan name/start date and declared food quantity/macros. The preview is consumed, the plan saved and existing import XP granted in one owned transaction. Concurrent confirmations with fresh request keys reuse that result; changed payloads, foreign/expired previews and injected structure are rejected. A bare PlanBody cannot claim imported provenance or XP. Confirmation does not fabricate consumption or overwrite targets. No image service or storage was added; historical imported meals and XP remain untouched.

Every import request is preview-only, including absent or legacy `preview=false` flags. Identical file bytes reuse the owned upload receipt before another AI/upload call; confirmed documents return the existing plan with no additional XP. Expired unconsumed receipts can be renewed only by analyzing the upload again, under the same owner lock. The receipt validates the full upload hash, not just its shortened request-key prefix. No historical imports are rewritten or deduplicated retrospectively.

An owner/digest reservation is committed in a short ActivityReceipt transaction before external upload/analysis across workers. No database connection is retained during remote work. Concurrent identical uploads return 409 with Retry-After; retry reuses the completed preview. Upload/AI have 60/180-second deadlines; reservations expire after five minutes for crash recovery. Completion verifies the exact reservation token and expiry, rejecting stale workers. Cancellation/failure releases only its own reservation in a shielded short transaction. A recorded itemless meal is unknown composition, unlike an empty date. Existing diets repeat within their inclusive start/end dates; generated/imported day-position plans remain one-off dated days.

## Performance, safety and verification

State and scenario reads use owned read-only repeatable snapshots. The daily projection loads only that day's meals; historical template detail, plan, recipe and routine reads have explicit limits and expose partial coverage or reject unsafe totals. Life State reuses the same projection without rereading training/calendar domains. Receipt transactions serialize confirmed writes and guard lost-response retries; namespace updates preserve unrelated preferences.

Coverage includes Decimal/unknown-source regressions, PostgreSQL ownership, partial goals, concurrent replay, favorites/deletion, recipe ingredients, own financial-budget capacity/month, preview side effects and plan confirmation. The browser suite exercises unknowns, failed-preview retry, confirmed registration with an uncertain-response retry and editable document preview at all five required widths. All existing suites and four CI workflows remain required.

Period aggregates, weekly trends, dashboard, reports and daily briefing propagate unknown composition rather than treating placeholder numbers as complete consumption. Report calories/protein and daily-briefing calories accept null for unknown composition. Daily briefing caches that explicit unknown without fabricated numbers; changes to meal count or the nullable calorie total invalidate and replace even fresh cache rows. Final save rechecks those owned facts under the user lock; stale AI analysis returns a retryable conflict without overwriting a newer snapshot. Historical numeric rows are preserved. Empty dates remain recorded zero.

The additive migration also relaxes nullability for report calories/protein and daily-summary calories; it does not rewrite any existing values. Downgrade refuses unknown snapshots instead of replacing them with invented totals.

Individual meal/recipe responses and nutrition XLSX/PDF exports use the same macro evidence: unknown values remain unknown, including itemless records and mixed legacy/new foods. Raw historical reported totals remain available separately as unverified evidence. Generated recipes preserve supplied zero macros; omitted fields and historical default zeros remain unknown.

Plan meal/day summaries and the mean daily totals are derived on the server from reviewed food masks using Decimal without premature rounding. Missing composition propagates null at every level; aggregate client fields cannot override those derived facts. Nine existing plan/day/meal aggregate columns accept null, in addition to the three report/briefing columns; no historical values are rewritten. Calendar uses the same owned SQL macro expression, without loading whole food histories or extra queries.

## Delivery status

Phase 11 is published and validated on 2026-10-13 UTC at functional merge `9a4008962da23ff8de3c8acbfbda96d828f6181b`. Migration `c9e42a7d160b` was applied through the protected workflow after mandatory owner approval, before merge. Both production deploys and read-only health/routes/frontend checks passed. See the [publication record](history/PHASE_11_PUBLICATION.md) for exact CI/review/migration/deployment evidence. No production test writes or real AI calls in tests. Phase 12 is not authorized.

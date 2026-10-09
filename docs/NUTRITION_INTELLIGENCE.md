# Nutrition Intelligence 2.0

## Directed audit

Base main after PR40: `ccf566bf38b365e0bffe1628c8b86a9e2ab4ad77`. Existing sources are Meal/MealItem, NutritionGoal, WaterLog, NutritionPlan/PlannedMeal/PlannedFood and Recipe/RecipeIngredient. Meals already use owned activity receipts; plans have atomic import and archival. No independent food inventory or price database exists.

GET goals formerly created default targets; period aggregates also fabricated default goals. Food estimates were editable in the UI but their provenance was discarded on save. Macros are per recorded quantity unit, not implicitly per 100g. Existing floats and legacy totals must remain intact; deterministic projections use Decimal and display rounding only at the boundary.

Image support imports diet documents/photos, not recognition of dishes. Preserve that capability and label extracted plan composition as estimated/unverified. Do not introduce another image service, storage or paid infrastructure.

## Contracts and decisions

Reuse historical meals as templates/favorites and existing user preferences for explicit availability, exclusions and optional budget/price declarations. Favorite references do not duplicate meal history. Reuse the owned receipt transaction for confirmed quick registration; previews never write meals, XP, finance or calendars.

Migration `c9e42a7d160b` adds nullable provenance, source references and goal confirmation to existing models. It does not rewrite old values or infer which historical defaults were intentionally selected. Old goals remain visible as unconfirmed until explicitly saved; missing goals remain missing. Nutrition evidence records supplied macro fields, registered/estimated source and the declared unit. Missing fields remain unknown even when legacy storage uses numeric zero.

The Nutrition Engine owns nutrition calculations. Finance provides only explicit budget limits; declared prices remain known or estimated and never become expenses. Recorded training/calendar commitments supply context, never calorie expenditure or clinical needs. Organization proposals have dates and meal references, not competing scheduling or automatic fixed-commitment changes. Life State and Agent reuse these contracts and their existing permissions.

## Usage and boundaries

The Nutrition **Inteligência** tab reads the selected local date on demand. Each macro separates registered, estimated and historical unverified values. A missing macro makes the complete total and remaining target unknown; a supplied zero is known. Empty dates show zero recorded consumption, not a claim that the person did not eat. Only explicitly confirmed target fields are used; historical defaults stay available for human review, never automatically confirmed.

Own historical meals, active planned meals and saved recipes supply alternatives. Favorites, declared available foods, exclusions and optional per-unit prices stay in the existing user-preferences namespace. A portion factor changes a preview; **Registrar com confirmação** creates a new owned meal with a receipt and source reference. Recipes require a chosen meal type. Existing units are literal: a planned `100 g` portion is one such portion, not 100 implicit servings. Unknown legacy composition remains unknown; positive AI/plan composition remains estimated.

Optional financial budgets are read through FinanceEngine, with remaining recorded capacity and a matching month. Daily budget proposals cannot borrow the next day's capacity. Missing prices do not prove affordability. No expense, purchase, stock or training expenditure is inferred. Nutrition organization is a dated proposal; the Life State adapter exposes dated active-plan candidates to the single Global Planner without invented duration or automatic scheduling. Fixed calendar commitments remain fixed.

The existing PDF/photo import now opens an editable preview. Confirmation saves the plan and its existing idempotent import XP; it does not fabricate consumed meals or overwrite confirmed targets. No image service or storage was added. Historical imported meals and XP remain untouched.

## Performance, safety and verification

State and scenario reads use owned read-only repeatable snapshots. The daily projection loads only that day's meals; historical template detail, plan, recipe and routine reads have explicit limits and expose partial coverage or reject unsafe totals. Life State reuses the same projection without rereading training/calendar domains. Receipt transactions serialize confirmed writes and guard lost-response retries; namespace updates preserve unrelated preferences.

Coverage includes Decimal/unknown-source regressions, PostgreSQL ownership, partial goals, concurrent replay, favorites/deletion, recipe ingredients, own financial-budget capacity/month, preview side effects and plan confirmation. The browser suite exercises unknowns, failed-preview retry, confirmed registration with an uncertain-response retry and editable document preview at all five required widths. All existing suites and four CI workflows remain required.

## Delivery status

Phase 11 explicitly authorized in the current session. Implementation and validation are in progress. Production migration requires the protected workflow and mandatory owner approval before merge. No production test writes or real AI calls in tests. Phase 12 is not authorized.

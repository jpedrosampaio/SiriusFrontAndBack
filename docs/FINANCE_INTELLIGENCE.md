# Finance Intelligence 2.0

## Pre-edit audit

Phase 9 starts from published main9804e21a7532538f7b5035c300c424a4ed1cd580 (Phase8 PR35). FinancialTransaction, Budget, CreditCard, CardPurchase, Invoice, Projection and MonthlyBill already use SQL Numeric/Decimal and owned transaction locks. Keep these ledgers, receipts and endpoints. MonthlyBill has a month, not a daily due date; CreditCard has an explicit configured due day. Fixed projections already materialize thirteen months and repeats already materialize each installment: do not expand them a second time.

One obligation can have a Projection, its imported MonthlyBill and a card Invoice aggregate. A paid bill creates a ledger transaction. A current-month card charge creates a ledger expense and an invoice. New analysis must deduplicate by explicit source links, never by similar descriptions or amounts. Invoice paid flags do not necessarily create ledger payments. Existing GET monthly-bills imports projections under a user lock: the new read-only engine must never call it.

The legacy projection summary copies this month's income to any future month, and the percentage-budget UI posts fields that BudgetBody ignores. Both are observable contract bugs. Percentage rules are configuration attached to an owned existing Budget through User.preferences; the money ledger stays in SQL. Old ignored percentages cannot be recovered or guessed.

There is no bank opening balance, interest-rate ledger or monetary target on personal Goal. Recorded net is not bank balance. Known materialized card obligations are not a complete external debt balance. Personal goals retain their original progress and dates, without inferred financial amounts. Unknown rates remain unknown; amortization requires explicit scenario rates and minimum payments.

## Implementation contract

FinanceEngine exposes a bounded, repeatable-read owner snapshot and Decimal money strings. Forecasts separate recorded future entries from estimated obligations and hypothetical additions. No past salary is carried forward. A forecast is a ledger-flow projection, not a bank statement. Opening balance, additional recurring income/expense and payment assumptions exist only inside read-only scenarios.

Canonical obligation precedence: imported bill overrides its projection; a paid bill or its linked ledger expense suppresses that obligation. Paid invoices suppress corresponding card estimates with a warning when source flags disagree. Card invoice aggregates contribute only a positive residual not represented by bills, projections or purchase-linked transactions for the same owner/card/month. Explicit future transactions are included once. Monthly-only obligations have no invented daily deadline; card due dates are derived from the recorded card configuration and clamped to that month's last day.

Debt comparison uses declared principals, monthly rates, minimum payments and a fixed monthly envelope. Interest is rounded to cents with ROUND_HALF_UP at each modeled month; minimum payments precede extra allocation. Snowball sorts current principal, avalanche sorts known rates, custom uses an explicit complete order. Without every rate, ranking is available but payoff months/interest are unavailable. Infeasible minimums or a bounded horizon leave explicit remaining debt; they never imply repayment. This is a disclosed hypothetical model, not a lender payoff quote.

Insights are deterministic comparisons of equal elapsed calendar periods, budget overruns and explicit fixed commitments. AI can explain the facts, not calculate new balances, rates or future income. Agent tools cannot transfer, purchase, contract credit or pay bills. Scenarios never write transactions, goals, XP, receipts or commitments. No new service or schema migration is planned.

Publication, final validation counts and any review corrections must be recorded only after they actually pass.

## API and limits

- GET `/api/finance/intelligence/state?months=6`: typed FinanceState, 1–12 months from account-local today. READ ONLY REPEATABLE READ transaction. Income/expense and spending comparisons are SQL aggregates, not hydrated transaction histories.
- POST `/api/finance/intelligence/simulate`: typed Decimal scenario, optional owner snapshot fingerprint, monthly additions and explicit full-value payment-date moves. Unknown/foreign sources404, stale fingerprints409, invalid precision/dates422. No persistence or idempotency receipt is created.
- POST `/api/finance/intelligence/compare-debts`: typed declared debt scenario and typed comparison response. 1–20 debts, 1–360 months, explicit complete custom order, rates0–100% monthly (unknown remains null). Exact cents throughout; high-growth models use bounded sufficient Decimal precision.
- Existing POST `/api/budgets` accepts fixed or percentage rules. Percentage configuration lives under `finance_budget_policies[owned budget UUID]`; no source ledger is moved. GET budgets, Finance State and Agent budget status use income and expenses through the account-local current date. Future-dated entries participate in forecasts only. A month without income through that date has an indeterminate percentage limit, not a fabricated base.
- The analysis panel refreshes after successful mutations through the existing data-change event, coalescing bursts. The legacy bill-importing GET is explicitly classified as a mutation. Read-only financial scenario and projection-insight POSTs do not emit mutation notifications or invalidate the current preview.

Overdue projections without imported bills or paid invoices remain bounded pending obligations and enter the current forecast bucket. Paid historical sources are excluded through owner-scoped correlated SQL checks, without hydrating the closed history or recreating expenses.

At most1000 projection/bill/invoice details per source,200 cards/budgets/categories,100 personal goals,200 displayed insights; truncated source inputs suspend forecasting and scenarios. Old closed bill/card-charge coverage is grouped in SQL and restricted to the selected invoice keys. Forecast uses all bounded obligations; UI initially shows one month on mobile/three on larger screens and can expand every month. Debt flow display shows first24 months while totals use the full modeled horizon. Recorded card obligations cover only the selected materialized horizon and do not assert a complete external loan balance. Future income/expenses are explicitly dated existing ledger entries; estimated sources and scenario additions remain separate fields.

Agent shares one financial snapshot between prefetched context and degraded reads. New read tools: get_finance_state, simulate_finances, compare_debt_strategies. Existing expense proposals now validate Decimal precision and keep literal monetary strings; actual writes still require confirmation. Provider-free real SQL regression verifies one snapshot and no writes/actions. The chat presents financial facts and scenario summaries with human labels and module links rather than internal metadata.

Local validation snapshot:246 full PostgreSQL tests passed before two additional charge/Agent integration cases;150 pure regressions/security5 and frontend52 unit/lint/build/new five-width financial smoke passed. Full13 browser suites and exact-head remote CI/review remain pending. Schema check reports no new upgrade operations. Final published state will be recorded in HANDOFF and PR metadata after deployment.

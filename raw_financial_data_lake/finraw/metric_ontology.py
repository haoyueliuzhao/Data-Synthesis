from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from finraw.builds import deactivate_active_rows, finish_build, start_build
from finraw.db.client import DBProtocol

Metric = dict[str, Any]
Alias = dict[str, Any]


SEC_METRICS: list[dict[str, Any]] = [
    {
        "metric_id": "revenue",
        "canonical_name": "Revenue",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; do not mix GAAP and non-GAAP variants",
        "revision_risk": "medium",
        "ambiguity_notes": "May appear as Revenues, SalesRevenueNet, Net sales, or revenue from contracts. Operating revenue and non-GAAP revenue are separate concepts unless explicitly mapped.",
        "concepts": [
            "us-gaap:Revenues",
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap:SalesRevenueNet",
        ],
        "raw_names": ["Revenue", "Total revenue", "Net sales", "Sales revenue", "GAAP revenue"],
        "confidence": 0.92,
    },
    {
        "metric_id": "operating_income",
        "canonical_name": "Operating Income",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Do not confuse with operating revenue or non-GAAP operating income.",
        "concepts": ["us-gaap:OperatingIncomeLoss"],
        "raw_names": ["Operating income", "Income from operations", "Operating income (loss)"],
        "confidence": 0.98,
    },
    {
        "metric_id": "net_income",
        "canonical_name": "Net Income",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; attributable-to-parent variants must be handled separately when present",
        "revision_risk": "medium",
        "ambiguity_notes": "May refer to consolidated net income or net income attributable to common shareholders; use source concept to disambiguate.",
        "concepts": ["us-gaap:NetIncomeLoss"],
        "raw_names": ["Net income", "Net income attributable to common shareholders", "Profit loss"],
        "confidence": 0.9,
    },
    {
        "metric_id": "gross_profit",
        "canonical_name": "Gross Profit",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Depends on cost-of-revenue classification; compare across industries carefully.",
        "concepts": ["us-gaap:GrossProfit"],
        "raw_names": ["Gross profit"],
        "confidence": 0.98,
    },
    {
        "metric_id": "cost_of_revenue",
        "canonical_name": "Cost of Revenue",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Cost of goods sold and cost of revenue can differ by industry and company presentation.",
        "concepts": ["us-gaap:CostOfRevenue", "us-gaap:CostOfGoodsAndServicesSold", "us-gaap:CostOfGoodsSold"],
        "raw_names": ["Cost of revenue", "Cost of sales", "Cost of goods sold"],
        "confidence": 0.88,
    },
    {
        "metric_id": "research_and_development_expense",
        "canonical_name": "Research and Development Expense",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "May include acquired in-process R&D under some reporting presentations.",
        "concepts": ["us-gaap:ResearchAndDevelopmentExpense"],
        "raw_names": ["Research and development", "R&D expense"],
        "confidence": 0.98,
    },
    {
        "metric_id": "selling_general_and_administrative_expense",
        "canonical_name": "Selling, General and Administrative Expense",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Some companies split sales/marketing and G&A; mapping is exact only for reported SG&A concepts.",
        "concepts": ["us-gaap:SellingGeneralAndAdministrativeExpense"],
        "raw_names": ["SG&A", "Selling, general and administrative", "Sales and marketing", "General and administrative"],
        "confidence": 0.82,
    },
    {
        "metric_id": "total_assets",
        "canonical_name": "Total Assets",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; do not sum across periods",
        "revision_risk": "medium",
        "ambiguity_notes": "Balance-sheet point-in-time metric; fiscal date matters.",
        "concepts": ["us-gaap:Assets"],
        "raw_names": ["Assets", "Total assets"],
        "confidence": 0.99,
    },
    {
        "metric_id": "total_liabilities",
        "canonical_name": "Total Liabilities",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; do not sum across periods",
        "revision_risk": "medium",
        "ambiguity_notes": "Can be reported separately from commitments and contingencies.",
        "concepts": ["us-gaap:Liabilities"],
        "raw_names": ["Liabilities", "Total liabilities"],
        "confidence": 0.99,
    },
    {
        "metric_id": "shareholders_equity",
        "canonical_name": "Shareholders' Equity",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; do not sum across periods",
        "revision_risk": "medium",
        "ambiguity_notes": "Stockholders' equity can include or exclude noncontrolling interests depending on concept.",
        "concepts": ["us-gaap:StockholdersEquity"],
        "raw_names": ["Stockholders' equity", "Shareholders' equity", "Total equity"],
        "confidence": 0.9,
    },
    {
        "metric_id": "cash_and_cash_equivalents",
        "canonical_name": "Cash and Cash Equivalents",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; do not sum across periods",
        "revision_risk": "medium",
        "ambiguity_notes": "Do not mix with cash, cash equivalents, and marketable securities unless separately mapped.",
        "concepts": ["us-gaap:CashAndCashEquivalentsAtCarryingValue"],
        "raw_names": ["Cash and cash equivalents", "Cash, cash equivalents, restricted cash and restricted cash equivalents"],
        "confidence": 0.86,
    },
    {
        "metric_id": "inventory",
        "canonical_name": "Inventory",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time",
        "revision_risk": "medium",
        "ambiguity_notes": "Inventory accounting method and write-down policy can affect comparability.",
        "concepts": ["us-gaap:InventoryNet"],
        "raw_names": ["Inventory", "Inventories"],
        "confidence": 0.98,
    },
    {
        "metric_id": "accounts_receivable_net",
        "canonical_name": "Accounts Receivable, Net",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time",
        "revision_risk": "medium",
        "ambiguity_notes": "Current/non-current presentation and allowance treatment may vary.",
        "concepts": ["us-gaap:AccountsReceivableNetCurrent", "us-gaap:AccountsReceivableNet"],
        "raw_names": ["Accounts receivable, net", "Trade receivables"],
        "confidence": 0.92,
    },
    {
        "metric_id": "long_term_debt",
        "canonical_name": "Long-Term Debt",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; current and non-current components may need separate handling",
        "revision_risk": "medium",
        "ambiguity_notes": "Do not confuse non-current long-term debt with total debt.",
        "concepts": ["us-gaap:LongTermDebtNoncurrent", "us-gaap:LongTermDebtAndFinanceLeaseObligationsNoncurrent"],
        "raw_names": ["Long-term debt", "Long-term debt, noncurrent", "Non-current long-term debt"],
        "related_terms": ["Current portion of long-term debt", "Long-term debt, current", "Current maturities of long-term debt", "Total debt"],
        "confidence": 0.86,
    },
    {
        "metric_id": "net_cash_provided_by_used_in_operating_activities",
        "canonical_name": "Net Cash Provided by Used in Operating Activities",
        "metric_category": "financial_statement",
        "statement_type": "cash_flow",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Cash-flow sign convention follows reported value.",
        "concepts": ["us-gaap:NetCashProvidedByUsedInOperatingActivities"],
        "raw_names": ["Net cash provided by operating activities", "Operating cash flow"],
        "confidence": 0.99,
    },
    {
        "metric_id": "net_cash_provided_by_used_in_investing_activities",
        "canonical_name": "Net Cash Provided by Used in Investing Activities",
        "metric_category": "financial_statement",
        "statement_type": "cash_flow",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Cash-flow sign convention follows reported value.",
        "concepts": ["us-gaap:NetCashProvidedByUsedInInvestingActivities"],
        "raw_names": ["Net cash provided by investing activities", "Investing cash flow"],
        "confidence": 0.99,
    },
    {
        "metric_id": "net_cash_provided_by_used_in_financing_activities",
        "canonical_name": "Net Cash Provided by Used in Financing Activities",
        "metric_category": "financial_statement",
        "statement_type": "cash_flow",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period",
        "revision_risk": "medium",
        "ambiguity_notes": "Cash-flow sign convention follows reported value.",
        "concepts": ["us-gaap:NetCashProvidedByUsedInFinancingActivities"],
        "raw_names": ["Net cash provided by financing activities", "Financing cash flow"],
        "confidence": 0.99,
    },
    {
        "metric_id": "capital_expenditures",
        "canonical_name": "Capital Expenditures",
        "metric_category": "financial_statement",
        "statement_type": "cash_flow",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; source sign may represent cash outflow",
        "revision_risk": "medium",
        "ambiguity_notes": "XBRL payments-to-acquire PPE is usually an investing cash outflow; sign handling must be explicit.",
        "concepts": ["us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"],
        "raw_names": ["Capital expenditures", "Payments to acquire property, plant and equipment", "Capex"],
        "confidence": 0.9,
    },
    {
        "metric_id": "earnings_per_share_basic",
        "canonical_name": "Earnings per Share, Basic",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "per_share",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "not_additive; use reported period value",
        "revision_risk": "medium",
        "ambiguity_notes": "Do not mix basic and diluted EPS; split adjustments matter.",
        "concepts": ["us-gaap:EarningsPerShareBasic"],
        "raw_names": ["Basic EPS", "Earnings per share basic"],
        "confidence": 0.99,
    },
    {
        "metric_id": "earnings_per_share_diluted",
        "canonical_name": "Earnings per Share, Diluted",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "per_share",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "not_additive; use reported period value",
        "revision_risk": "medium",
        "ambiguity_notes": "Do not mix basic and diluted EPS; split adjustments matter.",
        "concepts": ["us-gaap:EarningsPerShareDiluted"],
        "raw_names": ["Diluted EPS", "Earnings per share diluted"],
        "confidence": 0.99,
    },
]


SEC_METRICS.extend([
    {
        "metric_id": "sales_revenue_goods_net",
        "canonical_name": "Sales Revenue, Goods, Net",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; component of revenue, do not compare as total revenue",
        "revision_risk": "medium",
        "ambiguity_notes": "Goods revenue component; must not be merged with total revenue unless components are explicitly summed.",
        "concepts": ["us-gaap:SalesRevenueGoodsNet"],
        "raw_names": ["Sales revenue, goods, net"],
        "confidence": 0.98,
    },
    {
        "metric_id": "sales_revenue_services_net",
        "canonical_name": "Sales Revenue, Services, Net",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; component of revenue, do not compare as total revenue",
        "revision_risk": "medium",
        "ambiguity_notes": "Services revenue component; must not be merged with total revenue unless components are explicitly summed.",
        "concepts": ["us-gaap:SalesRevenueServicesNet"],
        "raw_names": ["Sales revenue, services, net"],
        "confidence": 0.98,
    },
    {
        "metric_id": "profit_loss_including_noncontrolling_interest",
        "canonical_name": "Profit/Loss Including Noncontrolling Interest",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; not the same as net income attributable to parent",
        "revision_risk": "medium",
        "ambiguity_notes": "Includes noncontrolling interest; keep separate from parent net income.",
        "concepts": ["us-gaap:ProfitLoss"],
        "raw_names": ["Profit loss", "Net income including noncontrolling interest"],
        "confidence": 0.98,
    },
    {
        "metric_id": "net_income_available_to_common_stockholders_basic",
        "canonical_name": "Net Income Available to Common Stockholders, Basic",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; per common stockholder attribution basis",
        "revision_risk": "medium",
        "ambiguity_notes": "Attributable to common stockholders; keep separate from consolidated net income.",
        "concepts": ["us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic"],
        "raw_names": ["Net income available to common stockholders, basic"],
        "confidence": 0.98,
    },
    {
        "metric_id": "stockholders_equity_including_noncontrolling_interest",
        "canonical_name": "Stockholders' Equity Including Noncontrolling Interest",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; not the same as parent stockholders' equity",
        "revision_risk": "medium",
        "ambiguity_notes": "Includes noncontrolling interest; keep separate from parent stockholders' equity.",
        "concepts": ["us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "raw_names": ["Stockholders' equity including noncontrolling interest"],
        "confidence": 0.98,
    },
    {
        "metric_id": "cash_cash_equivalents_restricted_cash_and_restricted_cash_equivalents",
        "canonical_name": "Cash, Cash Equivalents, Restricted Cash and Restricted Cash Equivalents",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; broader than cash and cash equivalents",
        "revision_risk": "medium",
        "ambiguity_notes": "Includes restricted cash; do not mix with cash and cash equivalents only.",
        "concepts": ["us-gaap:CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        "raw_names": ["Cash, cash equivalents, restricted cash and restricted cash equivalents"],
        "confidence": 0.98,
    },
    {
        "metric_id": "selling_and_marketing_expense",
        "canonical_name": "Selling and Marketing Expense",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; component expense",
        "revision_risk": "medium",
        "ambiguity_notes": "Component of operating expenses; do not merge with SG&A total without explicit aggregation.",
        "concepts": ["us-gaap:SellingAndMarketingExpense"],
        "raw_names": ["Selling and marketing expense"],
        "confidence": 0.98,
    },
    {
        "metric_id": "general_and_administrative_expense",
        "canonical_name": "General and Administrative Expense",
        "metric_category": "financial_statement",
        "statement_type": "income_statement",
        "period_type": "period_flow",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "sum_over_period; component expense",
        "revision_risk": "medium",
        "ambiguity_notes": "Component expense; do not merge with SG&A total without explicit aggregation.",
        "concepts": ["us-gaap:GeneralAndAdministrativeExpense"],
        "raw_names": ["General and administrative expense"],
        "confidence": 0.98,
    },
    {
        "metric_id": "long_term_debt_current",
        "canonical_name": "Long-Term Debt, Current",
        "metric_category": "financial_statement",
        "statement_type": "balance_sheet",
        "period_type": "point_in_time",
        "default_unit": "monetary",
        "default_currency": None,
        "accounting_standard": "US_GAAP",
        "aggregation_rule": "latest_point_in_time; current component of long-term debt",
        "revision_risk": "medium",
        "ambiguity_notes": "Current maturities; keep separate from non-current long-term debt.",
        "concepts": ["us-gaap:LongTermDebtCurrent"],
        "raw_names": ["Long-term debt, current", "Current portion of long-term debt", "Current maturities of long-term debt"],
        "related_terms": ["Long-term debt", "Long-term debt, noncurrent", "Total debt"],
        "confidence": 0.98,
    },
])

STANDARD_MACRO_METRICS: list[dict[str, Any]] = [
    ("gdp_current_usd", "Gross Domestic Product, Current USD", "macro", "period_flow", "USD", "USD", "annual_or_quarterly_flow; fiscal/calendar basis must be source-specific", "high", "GDP can be annual, quarterly SAAR, local currency, real, or current USD. Keep units/frequency explicit."),
    ("real_gdp_growth_pct", "Real GDP Growth", "macro", "period_flow", "percent", None, "period_growth_rate", "high", "Annual, quarterly, and annualized growth rates are not interchangeable."),
    ("real_gdp_chained_usd", "Real GDP, Chained Dollars", "macro", "period_flow", "chained_usd", "USD", "period_flow", "high", "Base year and chain-type dollars vary by source vintage."),
    ("gdp_constant_usd", "Gross Domestic Product, Constant USD", "macro", "period_flow", "constant_USD", "USD", "annual_period_flow", "high", "Constant-price GDP depends on the source base year and revision vintage."),
    ("gdp_deflator_growth_pct", "GDP Deflator Growth", "macro", "period_flow", "percent", None, "annual_growth_rate", "high", "Implicit GDP deflator growth is not interchangeable with CPI inflation."),
    ("gdp_per_capita_current_usd", "GDP per Capita, Current USD", "macro", "period_flow", "USD_per_person", "USD", "annual", "high", "Depends on GDP and population vintage."),
    ("consumer_price_index", "Consumer Price Index", "macro", "point_in_time", "index", None, "index_level", "high", "Index base period differs by source; do not compare levels across base periods without rebasing."),
    ("core_consumer_price_index", "Core Consumer Price Index", "macro", "point_in_time", "index", None, "index_level", "high", "Excludes food and energy; definition can vary by source."),
    ("inflation_rate_cpi", "Inflation, Consumer Prices", "macro", "period_flow", "percent", None, "period_growth_rate", "high", "YoY CPI inflation, average CPI inflation, and point-to-point inflation differ."),
    ("trade_pct_gdp", "Trade, Percent of GDP", "macro", "period_flow", "percent", None, "annual_ratio", "high", "Trade is exports plus imports of goods and services divided by GDP."),
    ("central_government_debt_pct_gdp", "Central Government Debt, Percent of GDP", "macro", "point_in_time", "percent", None, "reported_ratio", "high", "Central government debt coverage differs from general government gross debt."),
    ("government_revenue_excluding_grants_pct_gdp", "Government Revenue Excluding Grants, Percent of GDP", "macro", "period_flow", "percent", None, "annual_ratio", "high", "Excludes grants and depends on government-sector coverage."),
    ("government_education_expenditure_pct_gdp", "Government Education Expenditure, Percent of GDP", "macro", "period_flow", "percent", None, "annual_ratio", "high", "Government education expenditure coverage and reporting years vary."),
    ("current_health_expenditure_pct_gdp", "Current Health Expenditure, Percent of GDP", "macro", "period_flow", "percent", None, "annual_ratio", "high", "Current health expenditure excludes capital formation and can be revised."),
    ("gini_index", "Gini Index", "macro", "point_in_time", "index", None, "reported_index", "high", "Survey year, welfare concept, and interpolation policy differ across countries."),
    ("co2_emissions_per_capita", "CO2 Emissions per Capita", "macro", "period_flow", "metric_tons_per_capita", None, "annual_per_capita", "high", "Territorial emissions methodology and population vintage matter."),
    ("internet_users_pct_population", "Individuals Using the Internet", "macro", "point_in_time", "percent", None, "reported_rate", "high", "Survey and estimation methods vary across countries and years."),
    ("producer_price_index", "Producer Price Index", "macro", "point_in_time", "index", None, "index_level", "high", "Index base and commodity scope differ by source."),
    ("unemployment_rate", "Unemployment Rate", "macro", "point_in_time", "percent", None, "reported_rate", "medium", "Seasonal adjustment and labor-force definitions matter."),
    ("labor_force_participation_rate", "Labor Force Participation Rate", "macro", "point_in_time", "percent", None, "reported_rate", "medium", "Population universe and seasonal adjustment matter."),
    ("employment_population_ratio", "Employment-Population Ratio", "macro", "point_in_time", "percent", None, "reported_rate", "medium", "Population universe and seasonal adjustment matter."),
    ("nonfarm_payrolls", "Nonfarm Payroll Employment", "macro", "point_in_time", "persons", None, "level", "high", "Payroll data are revised frequently."),
    ("initial_claims", "Initial Unemployment Claims", "macro", "period_flow", "claims", None, "sum_or_reported_weekly", "high", "Weekly observations are revised and seasonally adjusted variants differ."),
    ("job_openings", "Job Openings", "macro", "point_in_time", "persons", None, "level", "high", "JOLTS is revised and sampled."),
    ("federal_funds_rate", "Federal Funds Rate", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Daily effective and monthly average Fed funds rates differ."),
    ("treasury_yield_1mo", "Treasury Yield, 1-Month", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Constant maturity yields are not bond returns."),
    ("treasury_yield_3mo", "Treasury Yield, 3-Month", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Constant maturity yields are not bond returns."),
    ("treasury_yield_2y", "Treasury Yield, 2-Year", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Constant maturity yields are not bond returns."),
    ("treasury_yield_5y", "Treasury Yield, 5-Year", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Constant maturity yields are not bond returns."),
    ("treasury_yield_10y", "Treasury Yield, 10-Year", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Constant maturity yields are not bond returns."),
    ("treasury_yield_30y", "Treasury Yield, 30-Year", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Constant maturity yields are not bond returns."),
    ("treasury_spread_10y_2y", "Treasury Spread, 10-Year Minus 2-Year", "market", "point_in_time", "percent", None, "reported_spread", "medium", "Spread convention must be explicit."),
    ("treasury_spread_10y_3mo", "Treasury Spread, 10-Year Minus 3-Month", "market", "point_in_time", "percent", None, "reported_spread", "medium", "Spread convention must be explicit."),
    ("mortgage_rate_30y", "30-Year Fixed Mortgage Rate", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Survey methodology matters."),
    ("corporate_bond_yield_aaa", "Corporate Bond Yield, Aaa", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Moody's seasoned yield methodology applies."),
    ("corporate_bond_yield_baa", "Corporate Bond Yield, Baa", "market", "point_in_time", "percent", None, "reported_rate", "medium", "Moody's seasoned yield methodology applies."),
    ("industrial_production_index", "Industrial Production Index", "macro", "point_in_time", "index", None, "index_level", "high", "Index base and revisions matter."),
    ("capacity_utilization", "Capacity Utilization", "macro", "point_in_time", "percent", None, "reported_rate", "high", "Revised with industrial production."),
    ("housing_starts", "Housing Starts", "macro", "period_flow", "units", None, "reported_period_value", "high", "Seasonal adjustment and annualization matter."),
    ("building_permits", "Building Permits", "macro", "period_flow", "units", None, "reported_period_value", "high", "Seasonal adjustment and annualization matter."),
    ("new_home_sales", "New Home Sales", "macro", "period_flow", "units", None, "reported_period_value", "high", "Monthly housing data are revised."),
    ("existing_home_sales", "Existing Home Sales", "macro", "period_flow", "units", None, "reported_period_value", "high", "Monthly housing data are revised."),
    ("retail_sales", "Retail Sales", "macro", "period_flow", "currency", "USD", "reported_period_value", "high", "Advance retail sales are revised."),
    ("consumer_sentiment", "Consumer Sentiment", "macro", "point_in_time", "index", None, "index_level", "medium", "Survey methodology and preliminary/final releases differ."),
    ("real_disposable_personal_income", "Real Disposable Personal Income", "macro", "period_flow", "chained_usd", "USD", "period_flow", "high", "Revised with national accounts."),
    ("personal_saving_rate", "Personal Saving Rate", "macro", "point_in_time", "percent", None, "reported_rate", "high", "Revised with personal income data."),
    ("money_supply_m2", "Money Supply M2", "macro", "point_in_time", "currency", "USD", "level", "high", "Monetary aggregates have methodology revisions."),
    ("monetary_base", "Monetary Base", "macro", "point_in_time", "currency", "USD", "level", "high", "Series methodology changed around H.6 updates."),
    ("consumer_loans", "Consumer Loans", "macro", "point_in_time", "currency", "USD", "level", "high", "Bank loan data are revised."),
    ("commercial_and_industrial_loans", "Commercial and Industrial Loans", "macro", "point_in_time", "currency", "USD", "level", "high", "Bank loan data are revised."),
    ("real_estate_loans", "Real Estate Loans", "macro", "point_in_time", "currency", "USD", "level", "high", "Bank loan data are revised."),
    ("fx_usd_per_eur", "FX Rate, USD per EUR", "market", "point_in_time", "USD/EUR", "USD", "reported_rate", "medium", "Quote direction matters."),
    ("fx_jpy_per_usd", "FX Rate, JPY per USD", "market", "point_in_time", "JPY/USD", "JPY", "reported_rate", "medium", "Quote direction matters."),
    ("fx_cny_per_usd", "FX Rate, CNY per USD", "market", "point_in_time", "CNY/USD", "CNY", "reported_rate", "medium", "Quote direction matters."),
    ("broad_us_dollar_index", "Broad U.S. Dollar Index", "market", "point_in_time", "index", "USD", "index_level", "medium", "Index base and weighting methodology matter."),
    ("population_total", "Population, Total", "macro", "point_in_time", "persons", None, "level", "medium", "Population series may be revised by census updates."),
    ("exports_goods_services_current_usd", "Exports of Goods and Services, Current USD", "macro", "period_flow", "USD", "USD", "period_flow", "high", "Balance-of-payments and national accounts bases can differ."),
    ("imports_goods_services_current_usd", "Imports of Goods and Services, Current USD", "macro", "period_flow", "USD", "USD", "period_flow", "high", "Balance-of-payments and national accounts bases can differ."),
    ("current_account_balance_current_usd", "Current Account Balance, Current USD", "macro", "period_flow", "USD", "USD", "period_flow", "high", "BOP revisions are common."),
    ("current_account_balance_pct_gdp", "Current Account Balance, Percent of GDP", "macro", "period_flow", "percent", None, "ratio", "high", "Numerator and GDP denominator vintages matter."),
    ("foreign_direct_investment_net_inflows_current_usd", "Foreign Direct Investment, Net Inflows, Current USD", "macro", "period_flow", "USD", "USD", "period_flow", "high", "FDI reporting has country-specific methodology differences."),
    ("external_debt_total_current_usd", "External Debt, Total, Current USD", "macro", "point_in_time", "USD", "USD", "level", "high", "May be unavailable for high-income economies or not applicable."),
    ("government_expense_pct_gdp", "Government Expense, Percent of GDP", "macro", "period_flow", "percent", None, "ratio", "high", "Government finance definitions differ by source."),
    ("tax_revenue_pct_gdp", "Tax Revenue, Percent of GDP", "macro", "period_flow", "percent", None, "ratio", "high", "Tax coverage differs across countries."),
    ("real_interest_rate", "Real Interest Rate", "market", "point_in_time", "percent", None, "reported_rate", "high", "Inflation adjustment method matters."),
    ("official_exchange_rate_lcu_per_usd", "Official Exchange Rate, LCU per USD", "market", "point_in_time", "LCU/USD", None, "reported_rate", "medium", "Quote direction and official/market rate distinction matter."),
    ("broad_money_pct_gdp", "Broad Money, Percent of GDP", "macro", "point_in_time", "percent", None, "ratio", "high", "Monetary aggregate definitions differ by country."),
    ("domestic_credit_private_sector_pct_gdp", "Domestic Credit to Private Sector, Percent of GDP", "macro", "point_in_time", "percent", None, "ratio", "high", "Financial sector coverage differs."),
    ("government_consumption_pct_gdp", "Government Consumption, Percent of GDP", "macro", "period_flow", "percent", None, "ratio", "high", "National accounts revisions matter."),
    ("gross_capital_formation_pct_gdp", "Gross Capital Formation, Percent of GDP", "macro", "period_flow", "percent", None, "ratio", "high", "National accounts revisions matter."),
    ("government_gross_debt_pct_gdp", "General Government Gross Debt, Percent of GDP", "macro", "point_in_time", "percent", None, "ratio", "high", "Debt perimeter and GDP vintages matter."),
    ("government_net_lending_pct_gdp", "General Government Net Lending/Borrowing, Percent of GDP", "macro", "period_flow", "percent", None, "ratio", "high", "Fiscal balance signs and definitions matter."),
    ("share_of_world_gdp_ppp", "Share of World GDP, PPP", "macro", "period_flow", "percent", None, "ratio", "high", "PPP benchmark revisions matter."),
]

FRED_ALIASES = {
    "GDP": "gdp_current_usd",
    "GDPC1": "real_gdp_chained_usd",
    "A191RL1Q225SBEA": "real_gdp_growth_pct",
    "GNP": "gross_national_product_current_usd",
    "PCE": "personal_consumption_expenditures",
    "PCEPI": "pce_price_index",
    "PCEPILFE": "core_pce_price_index",
    "CPIAUCSL": "consumer_price_index",
    "CPILFESL": "core_consumer_price_index",
    "PPIACO": "producer_price_index",
    "UNRATE": "unemployment_rate",
    "PAYEMS": "nonfarm_payrolls",
    "CIVPART": "labor_force_participation_rate",
    "EMRATIO": "employment_population_ratio",
    "ICSA": "initial_claims",
    "JTSJOL": "job_openings",
    "CES0500000003": "average_hourly_earnings_private",
    "AWHMAN": "average_weekly_hours_manufacturing",
    "FEDFUNDS": "federal_funds_rate",
    "DFF": "federal_funds_rate",
    "DGS1MO": "treasury_yield_1mo",
    "DGS3MO": "treasury_yield_3mo",
    "DGS2": "treasury_yield_2y",
    "DGS5": "treasury_yield_5y",
    "DGS10": "treasury_yield_10y",
    "DGS30": "treasury_yield_30y",
    "T10Y2Y": "treasury_spread_10y_2y",
    "T10Y3M": "treasury_spread_10y_3mo",
    "MORTGAGE30US": "mortgage_rate_30y",
    "AAA": "corporate_bond_yield_aaa",
    "BAA": "corporate_bond_yield_baa",
    "INDPRO": "industrial_production_index",
    "TCU": "capacity_utilization",
    "HOUST": "housing_starts",
    "PERMIT": "building_permits",
    "HSN1F": "new_home_sales",
    "EXHOSLUSM495S": "existing_home_sales",
    "RSAFS": "retail_sales",
    "UMCSENT": "consumer_sentiment",
    "DSPIC96": "real_disposable_personal_income",
    "PSAVERT": "personal_saving_rate",
    "M2SL": "money_supply_m2",
    "BOGMBASE": "monetary_base",
    "TOTLL": "consumer_loans",
    "BUSLOANS": "commercial_and_industrial_loans",
    "REALLN": "real_estate_loans",
    "DEXUSEU": "fx_usd_per_eur",
    "DEXJPUS": "fx_jpy_per_usd",
    "DEXCHUS": "fx_cny_per_usd",
    "DTWEXBGS": "broad_us_dollar_index",
}

WORLD_BANK_ALIASES = {
    "NY.GDP.MKTP.CD": "gdp_current_usd",
    "NY.GDP.MKTP.KD.ZG": "real_gdp_growth_pct",
    "NY.GDP.PCAP.CD": "gdp_per_capita_current_usd",
    "SP.POP.TOTL": "population_total",
    "FP.CPI.TOTL.ZG": "inflation_rate_cpi",
    "NE.EXP.GNFS.CD": "exports_goods_services_current_usd",
    "NE.IMP.GNFS.CD": "imports_goods_services_current_usd",
    "BN.CAB.XOKA.CD": "current_account_balance_current_usd",
    "BX.KLT.DINV.CD.WD": "foreign_direct_investment_net_inflows_current_usd",
    "DT.DOD.DECT.CD": "external_debt_total_current_usd",
    "GC.XPN.TOTL.GD.ZS": "government_expense_pct_gdp",
    "GC.TAX.TOTL.GD.ZS": "tax_revenue_pct_gdp",
    "SL.UEM.TOTL.ZS": "unemployment_rate",
    "SL.TLF.CACT.ZS": "labor_force_participation_rate",
    "FR.INR.RINR": "real_interest_rate",
    "PA.NUS.FCRF": "official_exchange_rate_lcu_per_usd",
    "FM.LBL.BMNY.GD.ZS": "broad_money_pct_gdp",
    "FS.AST.PRVT.GD.ZS": "domestic_credit_private_sector_pct_gdp",
    "NE.CON.GOVT.ZS": "government_consumption_pct_gdp",
    "NE.GDI.TOTL.ZS": "gross_capital_formation_pct_gdp",
    "NY.GDP.MKTP.KD": "gdp_constant_usd",
    "NY.GDP.DEFL.KD.ZG": "gdp_deflator_growth_pct",
    "NE.TRD.GNFS.ZS": "trade_pct_gdp",
    "GC.DOD.TOTL.GD.ZS": "central_government_debt_pct_gdp",
    "GC.REV.XGRT.GD.ZS": "government_revenue_excluding_grants_pct_gdp",
    "SE.XPD.TOTL.GD.ZS": "government_education_expenditure_pct_gdp",
    "SH.XPD.CHEX.GD.ZS": "current_health_expenditure_pct_gdp",
    "SI.POV.GINI": "gini_index",
    "EN.ATM.CO2E.PC": "co2_emissions_per_capita",
    "IT.NET.USER.ZS": "internet_users_pct_population",
}

IMF_ALIASES = {
    "weo_ngdpd_current_usd_gdp": "gdp_current_usd",
    "weo_real_gdp_growth": "real_gdp_growth_pct",
    "weo_gdp_per_capita_current_usd": "gdp_per_capita_current_usd",
    "weo_inflation_average_consumer_prices": "inflation_rate_cpi",
    "weo_unemployment_rate": "unemployment_rate",
    "weo_current_account_balance_usd": "current_account_balance_current_usd",
    "weo_current_account_balance_pct_gdp": "current_account_balance_pct_gdp",
    "weo_general_government_gross_debt_pct_gdp": "government_gross_debt_pct_gdp",
    "weo_general_government_net_lending_pct_gdp": "government_net_lending_pct_gdp",
    "weo_share_of_world_gdp_ppp": "share_of_world_gdp_ppp",
}

DOCUMENT_METRICS = [
    ("sec_filing_10k", "SEC Form 10-K Filing Document", "financial_statement", "filing_document", "period_flow", "document", None, "source_document", "low", "Raw filing document, not an extracted financial metric."),
    ("sec_filing_10q", "SEC Form 10-Q Filing Document", "financial_statement", "filing_document", "period_flow", "document", None, "source_document", "low", "Raw filing document, not an extracted financial metric."),
    ("sec_filing_8k", "SEC Form 8-K Filing Document", "financial_statement", "filing_document", "point_in_time", "document", None, "source_document", "low", "Current report document, not an extracted financial metric."),
    ("cninfo_annual_report", "CNInfo Annual Report PDF", "financial_statement", "filing_document", "period_flow", "document", None, "source_document", "low", "Raw PDF document; table extraction not run."),
    ("cninfo_semiannual_report", "CNInfo Semiannual Report PDF", "financial_statement", "filing_document", "period_flow", "document", None, "source_document", "low", "Raw PDF document; table extraction not run."),
    ("cninfo_q1_report", "CNInfo First Quarter Report PDF", "financial_statement", "filing_document", "period_flow", "document", None, "source_document", "low", "Raw PDF document; table extraction not run."),
    ("cninfo_q3_report", "CNInfo Third Quarter Report PDF", "financial_statement", "filing_document", "period_flow", "document", None, "source_document", "low", "Raw PDF document; table extraction not run."),
]


def refresh_metric_ontology(db: DBProtocol, config: dict[str, Any], output_dir: str | None = None) -> dict[str, Any]:
    build_id = start_build(db, layer="fact_build", command="refresh-metrics", prefix="metric_ontology")
    metrics, aliases, diagnostics = build_metric_ontology(db, config)
    deactivate_active_rows(db, "metric_alias_map", build_id)
    deactivate_active_rows(db, "metrics", build_id)
    for metric in metrics:
        db.execute(
            """
            INSERT INTO metrics (
                metric_id, canonical_name, metric_category, statement_type, period_type,
                default_unit, default_currency, accounting_standard, aggregation_rule,
                revision_risk, ambiguity_notes, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (metric_id) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                metric_category=excluded.metric_category,
                statement_type=excluded.statement_type,
                period_type=excluded.period_type,
                default_unit=excluded.default_unit,
                default_currency=excluded.default_currency,
                accounting_standard=excluded.accounting_standard,
                aggregation_rule=excluded.aggregation_rule,
                revision_risk=excluded.revision_risk,
                ambiguity_notes=excluded.ambiguity_notes,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL,
                updated_at=CURRENT_TIMESTAMP
            """,
            [
                metric.get("metric_id"),
                metric.get("canonical_name"),
                metric.get("metric_category"),
                metric.get("statement_type"),
                metric.get("period_type"),
                metric.get("default_unit"),
                metric.get("default_currency"),
                metric.get("accounting_standard"),
                metric.get("aggregation_rule"),
                metric.get("revision_risk"),
                metric.get("ambiguity_notes"),
                build_id,
                1,
                None,
            ],
        )
    for alias in aliases:
        db.execute(
            """
            INSERT INTO metric_alias_map (
                alias_id, metric_id, source_id, raw_field_name, raw_concept_name, confidence_score, build_id, is_active, superseded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (alias_id) DO UPDATE SET
                metric_id=excluded.metric_id,
                source_id=excluded.source_id,
                raw_field_name=excluded.raw_field_name,
                raw_concept_name=excluded.raw_concept_name,
                confidence_score=excluded.confidence_score,
                build_id=excluded.build_id,
                is_active=1,
                superseded_by=NULL
            """,
            [
                alias.get("alias_id"),
                alias.get("metric_id"),
                alias.get("source_id"),
                alias.get("raw_field_name"),
                alias.get("raw_concept_name"),
                alias.get("confidence_score"),
                build_id,
                1,
                None,
            ],
        )
    report = {
        "build_id": build_id,
        "metric_count": len(metrics),
        "alias_count": len(aliases),
        "metric_category_counts": dict(sorted(Counter(metric.get("metric_category") or "unknown" for metric in metrics).items())),
        "statement_type_counts": dict(sorted(Counter(metric.get("statement_type") or "unknown" for metric in metrics).items())),
        "diagnostics": diagnostics,
        "sample_metrics": metrics[:30],
        "sample_aliases": aliases[:40],
        "related_terms": diagnostics.get("related_terms", {}),
    }
    if output_dir:
        paths = write_metric_ontology_report(report, output_dir)
        report["written_files"] = [str(path) for path in paths]
    finish_build(db, build_id, "success", f"metric_count={len(metrics)}; alias_count={len(aliases)}")
    return report


def build_metric_ontology(db: DBProtocol, config: dict[str, Any]) -> tuple[list[Metric], list[Alias], dict[str, Any]]:
    source_entities = [dict(row) for row in db.fetchall("SELECT * FROM source_entities")]
    raw_records = [dict(row) for row in db.fetchall("SELECT source_id, record_type, record_json, metric_hint FROM raw_records")]
    metrics: dict[str, Metric] = {}
    aliases: dict[str, Alias] = {}
    diagnostics: dict[str, Any] = {
        "unmapped_sec_concepts_sample": [],
        "unmapped_fred_series": [],
        "unmapped_worldbank_indicators": [],
        "unmapped_imf_targets": [],
        "notes": [
            "Metric ontology maps strict raw field/concept aliases to canonical metrics but does not extract standardized facts yet.",
            "Fiscal/calendar period, units, currency, GAAP/non-GAAP, and revision vintage must remain attached during fact extraction.",
            "related_terms are intentionally not inserted into metric_alias_map; they are hints for review and prompt/template caution only.",
        ],
        "related_terms": {},
    }

    for spec in SEC_METRICS:
        _add_metric(metrics, _metric_from_spec(spec))
        if spec.get("related_terms"):
            diagnostics["related_terms"][spec["metric_id"]] = list(spec.get("related_terms", []))
        for raw_name in spec.get("raw_names", []):
            _add_alias(aliases, spec["metric_id"], None, raw_name, None, 0.8)
        for concept in spec.get("concepts", []):
            _add_alias(aliases, spec["metric_id"], "sec_companyfacts", concept.split(":", 1)[-1], concept, spec.get("confidence", 0.9))

    for row in STANDARD_MACRO_METRICS:
        _add_metric(metrics, _macro_metric(*row))

    _add_document_metrics(metrics, aliases)
    _add_fred_metrics(metrics, aliases, source_entities, diagnostics)
    _add_worldbank_metrics(metrics, aliases, source_entities, diagnostics)
    _add_imf_metrics(metrics, aliases, raw_records, diagnostics)
    _add_observed_sec_concept_aliases(metrics, aliases, raw_records, diagnostics)
    _add_observed_document_aliases(aliases, raw_records)

    return (
        sorted(metrics.values(), key=lambda row: row["metric_id"]),
        sorted(aliases.values(), key=lambda row: (row["metric_id"], row.get("source_id") or "", row.get("raw_concept_name") or "", row.get("raw_field_name") or "")),
        diagnostics,
    )


def write_metric_ontology_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "metric_ontology_report.json"
    md_path = out / "metric_ontology_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return [json_path, md_path]


def _metric_from_spec(spec: dict[str, Any]) -> Metric:
    return {key: spec.get(key) for key in [
        "metric_id", "canonical_name", "metric_category", "statement_type", "period_type",
        "default_unit", "default_currency", "accounting_standard", "aggregation_rule",
        "revision_risk", "ambiguity_notes",
    ]}


def _macro_metric(metric_id: str, name: str, category: str, period_type: str, unit: str | None, currency: str | None, aggregation: str, revision: str, notes: str) -> Metric:
    return {
        "metric_id": metric_id,
        "canonical_name": name,
        "metric_category": category,
        "statement_type": None,
        "period_type": period_type,
        "default_unit": unit,
        "default_currency": currency,
        "accounting_standard": None,
        "aggregation_rule": aggregation,
        "revision_risk": revision,
        "ambiguity_notes": notes,
    }


def _add_document_metrics(metrics: dict[str, Metric], aliases: dict[str, Alias]) -> None:
    for row in DOCUMENT_METRICS:
        (
            metric_id, name, category, statement_type, period_type, unit, currency,
            aggregation, revision, notes,
        ) = row
        _add_metric(metrics, {
            "metric_id": metric_id,
            "canonical_name": name,
            "metric_category": category,
            "statement_type": statement_type,
            "period_type": period_type,
            "default_unit": unit,
            "default_currency": currency,
            "accounting_standard": None,
            "aggregation_rule": aggregation,
            "revision_risk": revision,
            "ambiguity_notes": notes,
        })
    for form, metric_id in {"10-K": "sec_filing_10k", "10-Q": "sec_filing_10q", "8-K": "sec_filing_8k"}.items():
        _add_alias(aliases, metric_id, "sec_filings", form, form, 0.96)
    for report_type, metric_id in {"annual": "cninfo_annual_report", "semiannual": "cninfo_semiannual_report", "q1": "cninfo_q1_report", "q3": "cninfo_q3_report"}.items():
        _add_alias(aliases, metric_id, "cninfo_announcements", report_type, report_type, 0.96)


def _add_fred_metrics(metrics: dict[str, Metric], aliases: dict[str, Alias], source_entities: list[dict[str, Any]], diagnostics: dict[str, Any]) -> None:
    for entity in source_entities:
        if entity.get("source_id") != "fred_observations":
            continue
        series_id = entity.get("source_code")
        metadata = _json_value(entity.get("raw_metadata"))
        metric_id = FRED_ALIASES.get(series_id)
        if not metric_id:
            metric_id = f"fred_{_slug(series_id)}"
            diagnostics["unmapped_fred_series"].append({"series_id": series_id, "title": entity.get("source_name")})
        if metric_id not in metrics:
            _add_metric(metrics, {
                "metric_id": metric_id,
                "canonical_name": entity.get("source_name") or series_id,
                "metric_category": _infer_fred_category(series_id, metadata),
                "statement_type": None,
                "period_type": _infer_period_type(metadata),
                "default_unit": metadata.get("units") if isinstance(metadata, dict) else None,
                "default_currency": "USD" if _text_contains(metadata, "U.S. Dollar") else None,
                "accounting_standard": None,
                "aggregation_rule": "use source frequency and vintage; do not mix daily/monthly/quarterly without resampling rule",
                "revision_risk": "high",
                "ambiguity_notes": "FRED series can be revised; preserve realtime/vintage dates where available.",
            })
        _add_alias(aliases, metric_id, "fred_observations", entity.get("source_name") or series_id, series_id, 0.94 if series_id in FRED_ALIASES else 0.72)


def _add_worldbank_metrics(metrics: dict[str, Metric], aliases: dict[str, Alias], source_entities: list[dict[str, Any]], diagnostics: dict[str, Any]) -> None:
    for entity in source_entities:
        if entity.get("source_id") != "worldbank_indicators":
            continue
        metadata = _json_value(entity.get("raw_metadata"))
        if not isinstance(metadata, dict) or metadata.get("kind") != "indicator":
            continue
        indicator = entity.get("source_code")
        metric_id = WORLD_BANK_ALIASES.get(indicator)
        if not metric_id:
            diagnostics["unmapped_worldbank_indicators"].append({"indicator": indicator, "name": entity.get("source_name")})
            continue
        if metric_id not in metrics:
            _add_metric(metrics, {
                "metric_id": metric_id,
                "canonical_name": entity.get("source_name") or indicator,
                "metric_category": "macro",
                "statement_type": None,
                "period_type": "period_flow" if _looks_flow(indicator) else "point_in_time",
                "default_unit": None,
                "default_currency": "USD" if indicator.endswith(".CD") else None,
                "accounting_standard": None,
                "aggregation_rule": "annual country observation; preserve country, year, unit, and source vintage",
                "revision_risk": "high",
                "ambiguity_notes": "World Bank indicators may be revised and may contain null values for unavailable country/year cells.",
            })
        _add_alias(aliases, metric_id, "worldbank_indicators", entity.get("source_name") or indicator, indicator, 0.96)


def _add_imf_metrics(metrics: dict[str, Metric], aliases: dict[str, Alias], raw_records: list[dict[str, Any]], diagnostics: dict[str, Any]) -> None:
    seen = set()
    for record in raw_records:
        if record.get("record_type") != "imf_sdmx_response":
            continue
        target = record.get("metric_hint")
        if not target or target in seen:
            continue
        seen.add(target)
        metric_id = IMF_ALIASES.get(target)
        if not metric_id:
            diagnostics["unmapped_imf_targets"].append({"target": target})
            continue
        _add_alias(aliases, metric_id, "imf_sdmx", target, target, 0.9)


def _add_observed_sec_concept_aliases(metrics: dict[str, Metric], aliases: dict[str, Alias], raw_records: list[dict[str, Any]], diagnostics: dict[str, Any]) -> None:
    concept_to_metric = {}
    for spec in SEC_METRICS:
        for concept in spec.get("concepts", []):
            concept_to_metric[concept] = spec["metric_id"]
    observed_unknown = Counter()
    observed_known_labels: dict[str, str] = {}
    for record in raw_records:
        if record.get("record_type") != "sec_companyfacts_json":
            continue
        payload = _json_value(record.get("record_json"))
        facts = payload.get("facts", {}) if isinstance(payload, dict) else {}
        if not isinstance(facts, dict):
            continue
        for namespace, namespace_facts in facts.items():
            if not isinstance(namespace_facts, dict):
                continue
            for concept_name, concept_payload in namespace_facts.items():
                full = f"{namespace}:{concept_name}"
                if full in concept_to_metric:
                    label = concept_payload.get("label") if isinstance(concept_payload, dict) else None
                    observed_known_labels.setdefault(full, label or concept_name)
                else:
                    observed_unknown[full] += 1
    for concept, raw_label in observed_known_labels.items():
        _add_alias(aliases, concept_to_metric[concept], "sec_companyfacts", raw_label, concept, 0.97)
    diagnostics["unmapped_sec_concepts_sample"] = [
        {"raw_concept_name": concept, "observed_company_count": count}
        for concept, count in observed_unknown.most_common(100)
    ]


def _add_observed_document_aliases(aliases: dict[str, Alias], raw_records: list[dict[str, Any]]) -> None:
    sec_map = {"10-K": "sec_filing_10k", "10-Q": "sec_filing_10q", "8-K": "sec_filing_8k"}
    cn_map = {"annual": "cninfo_annual_report", "semiannual": "cninfo_semiannual_report", "q1": "cninfo_q1_report", "q3": "cninfo_q3_report"}
    for record in raw_records:
        if record.get("record_type") == "sec_filing_document" and record.get("metric_hint") in sec_map:
            form = record.get("metric_hint")
            _add_alias(aliases, sec_map[form], "sec_filings", form, form, 0.98)
        elif record.get("record_type") == "cninfo_pdf_announcement" and record.get("metric_hint") in cn_map:
            kind = record.get("metric_hint")
            _add_alias(aliases, cn_map[kind], "cninfo_announcements", kind, kind, 0.98)


def _add_metric(metrics: dict[str, Metric], metric: Metric) -> None:
    existing = metrics.get(metric["metric_id"])
    if not existing:
        metrics[metric["metric_id"]] = metric
        return
    for key, value in metric.items():
        if existing.get(key) in {None, ""} and value not in {None, ""}:
            existing[key] = value


def _add_alias(
    aliases: dict[str, Alias],
    metric_id: str,
    source_id: str | None,
    raw_field_name: Any,
    raw_concept_name: Any,
    confidence_score: float,
) -> None:
    raw_field = str(raw_field_name).strip() if raw_field_name is not None else None
    raw_concept = str(raw_concept_name).strip() if raw_concept_name is not None else None
    if not raw_field and not raw_concept:
        return
    alias_id = _alias_id(metric_id, source_id, raw_field, raw_concept)
    row = {
        "alias_id": alias_id,
        "metric_id": metric_id,
        "source_id": source_id,
        "raw_field_name": raw_field,
        "raw_concept_name": raw_concept,
        "confidence_score": confidence_score,
    }
    existing = aliases.get(alias_id)
    if not existing or confidence_score > existing.get("confidence_score", 0):
        aliases[alias_id] = row


def _alias_id(metric_id: str, source_id: str | None, raw_field: str | None, raw_concept: str | None) -> str:
    digest = hashlib.sha1(f"{metric_id}|{source_id or ''}|{raw_field or ''}|{raw_concept or ''}".lower().encode("utf-8")).hexdigest()[:16]
    return f"malias_{digest}"


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _slug(value: Any) -> str:
    text = str(value or "unknown").lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"


def _infer_fred_category(series_id: str | None, metadata: Any) -> str:
    text = f"{series_id or ''} {json.dumps(metadata, default=str) if isinstance(metadata, dict) else metadata or ''}".lower()
    market_patterns = [
        r"\byield\b",
        r"\bexchange rate\b",
        r"\binterest rate\b",
        r"\bfederal funds rate\b",
        r"\bmortgage\b",
        r"\bbond\b",
        r"\btreasury\b",
        r"\bdollar index\b",
    ]
    if any(re.search(pattern, text) for pattern in market_patterns):
        return "market"
    return "macro"


def _infer_period_type(metadata: Any) -> str:
    if not isinstance(metadata, dict):
        return "point_in_time"
    title = str(metadata.get("title") or "").lower()
    units = str(metadata.get("units") or "").lower()
    if "index" in units or "percent" in units or re.search(r"\brate\b", title):
        return "point_in_time"
    if any(token in title for token in ["sales", "starts", "permits", "product", "income", "expenditures"]):
        return "period_flow"
    return "point_in_time"


def _text_contains(value: Any, needle: str) -> bool:
    return needle.lower() in json.dumps(value, default=str).lower()


def _looks_flow(indicator: str | None) -> bool:
    text = str(indicator or "")
    return any(part in text for part in ["GDP", "EXP", "IMP", "CAB", "DINV", "XPN", "TAX", "CON", "GDI"])


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Metric Ontology Report", ""]
    lines.append(f"Metrics: {report['metric_count']}")
    lines.append(f"Aliases: {report['alias_count']}")
    lines.append("")
    lines.append("## Categories")
    lines.append("")
    for category, count in report.get("metric_category_counts", {}).items():
        lines.append(f"- {category}: {count}")
    lines.append("")
    lines.append("## Samples")
    lines.append("")
    lines.append("| metric_id | canonical_name | category | statement_type | period_type | revision_risk |")
    lines.append("|---|---|---|---|---|---|")
    for metric in report.get("sample_metrics", [])[:30]:
        lines.append(
            "| {metric_id} | {canonical_name} | {metric_category} | {statement_type} | {period_type} | {revision_risk} |".format(
                metric_id=metric.get("metric_id") or "",
                canonical_name=str(metric.get("canonical_name") or "").replace("|", "\\|"),
                metric_category=metric.get("metric_category") or "",
                statement_type=metric.get("statement_type") or "",
                period_type=metric.get("period_type") or "",
                revision_risk=metric.get("revision_risk") or "",
            )
        )
    lines.append("")
    lines.append("## Diagnostics")
    lines.append("")
    diagnostics = report.get("diagnostics", {})
    lines.append(f"- Unmapped SEC concept sample size: {len(diagnostics.get('unmapped_sec_concepts_sample', []))}")
    lines.append(f"- Unmapped FRED series: {len(diagnostics.get('unmapped_fred_series', []))}")
    lines.append(f"- Unmapped World Bank indicators: {len(diagnostics.get('unmapped_worldbank_indicators', []))}")
    lines.append(f"- Unmapped IMF targets: {len(diagnostics.get('unmapped_imf_targets', []))}")
    for note in diagnostics.get("notes", []):
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)

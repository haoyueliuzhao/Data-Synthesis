"""Finite reviewer source-resolution ledger, not model-authored data or an online gate.

Addresses and source choices are explicitly authored against already reviewed
public records. Matching numbers alone never supplies an absent ledger entry.
The new relation comparison is performed only after these rules are frozen.
"""

GOALS = {
    "N1": {
        "quantity": "global_leased_facility_area_share",
        "period": "2015 disclosed snapshot",
        "unit": "percent",
        "relation": "leased_area_divided_by_total_area",
    },
    "N2": {
        "quantity": "money_pool_cash_use_share_of_receivables",
        "period": "2004",
        "unit": "percent",
        "relation": "cash_use_magnitude_divided_by_year_end_receivables",
    },
    "N4": {
        "quantity": "average_company_defined_cash_flow",
        "period": "2004-2006",
        "unit": "USD_million",
        "relation": "arithmetic_mean_of_three_cash_flow_values",
    },
    "N5": {
        "quantity": "net_change_unpaid_restructuring_liability",
        "period": "2006",
        "unit": "USD_million",
        "relation": "closing_balance_minus_opening_balance",
    },
    "N6": {
        "quantity": "increase_in_total_average_trading_assets",
        "period": "2008 minus 2007",
        "unit": "USD_million",
        "relation": "difference_between_two_asset_category_sums",
    },
}

SOURCES = {
    "N1": {
        "body.left.left": ("source:t2c3n0", "global leased facilities", "million square feet"),
        "body.left.right": ("source:t3c3n0", "global total facilities", "million square feet"),
    },
    "N2": {
        "body.left.left": ("source:q0n0", "2004 money-pool cash-use magnitude", "USD_million"),
        "body.left.right.left": (
            "source:t2c0n0",
            "2004 year-end money-pool receivables",
            "USD_thousand",
        ),
    },
    "N4": {
        "body.left.left.left": ("source:t3c1n0", "2006 company-defined cash flow", "USD_million"),
        "body.left.left.right": ("source:t3c2n0", "2005 company-defined cash flow", "USD_million"),
        "body.left.right": ("source:t3c3n0", "2004 company-defined cash flow", "USD_million"),
    },
    "N5": {
        "body.left": ("source:t8c1n0", "closing liability at December 31 2006", "USD_million"),
        "body.right": (
            "source:t4c1n0",
            "closing liability at December 31 2005 / opening 2006",
            "USD_million",
        ),
    },
    "N6": {
        "body.left.left": (
            "source:t1c2n0",
            "2008 average debt/equity trading assets",
            "USD_million",
        ),
        "body.left.right": (
            "source:t2c2n0",
            "2008 average trading derivative receivables",
            "USD_million",
        ),
        "body.right.left": (
            "source:t1c3n0",
            "2007 average debt/equity trading assets",
            "USD_million",
        ),
        "body.right.right": (
            "source:t2c3n0",
            "2007 average trading derivative receivables",
            "USD_million",
        ),
    },
}
CONSTANTS = {
    "N1": {"body.right": ("100", "proportion-to-percent scale")},
    "N2": {
        "body.left.right.right": ("1000", "thousand-to-million conversion"),
        "body.right": ("100", "proportion-to-percent scale"),
    },
    "N4": {"body.right": ("3", "arithmetic-mean member count")},
    "N5": {},
    "N6": {},
}
CONTEXT = {
    "N1": ["t0c0", "t0c3", "t2c0", "t3c0", "p3"],
    "N2": ["p13", "q0", "t0c0", "t1c0"],
    "N4": ["t0c0", "t0c1", "t0c2", "t0c3", "t3c0", "p20"],
    "N5": ["p1", "t4c0", "t8c0"],
    "N6": ["p0", "t0c0", "t0c2", "t0c3", "t1c0", "t2c0"],
}
# For literal occurrences these pointers only establish a model declaration.
# They do not turn metadata into tool-consumed variables. None means the source
# resolution belongs to the reviewer, based on public role/period/unit evidence.
DECLARATIONS = {
    "A_N1_01": {},
    "T_N1_01": {
        "body.left.left": ["variables", "leased_sqft", "source"],
        "body.left.right": ["variables", "total_sqft", "source"],
    },
    "T_N1_02": {
        "body.left.left": ["sources", "numerator"],
        "body.left.right": ["sources", "denominator"],
    },
    "T_N2_01": {},
    "T_N2_02": {
        "body.left.left": ["variables", "use_millions", "source"],
        "body.left.right.left": ["variables", "receivables_thousands", "source"],
    },
    "A_N2_02": {
        "body.left.left": ["sources", "42.5"],
        "body.left.right.left": ["sources", "61592"],
    },
    "T_N4_01": {
        "body.left.left.left": ["sources", "2006"],
        "body.left.left.right": ["sources", "2005"],
        "body.left.right": ["sources", "2004"],
    },
    "T_N4_02": {
        "body.left.left.left": ["sources", "2006 cash flow"],
        "body.left.left.right": ["sources", "2005 cash flow"],
        "body.left.right": ["sources", "2004 cash flow"],
    },
    "T_N5_01": {
        "body.left": ["variables", "ending_2006", "source"],
        "body.right": ["variables", "ending_2005", "source"],
    },
    "T_N5_02": {
        "body.left": ["variables", "closing_2006", "source"],
        "body.right": ["variables", "opening_2006", "source"],
    },
    "T_N6_01": {
        "body.left.left": ["sources", "2008_debt_equity"],
        "body.left.right": ["sources", "2008_derivative_receivables"],
        "body.right.left": ["sources", "2007_debt_equity"],
        "body.right.right": ["sources", "2007_derivative_receivables"],
    },
    "T_N6_02": {
        "body.left.left": ["sources", "384102"],
        "body.left.right": ["sources", "121417"],
        "body.right.left": ["sources", "381415"],
        "body.right.right": ["sources", "65439"],
    },
}
FORMAT_RECOVERIES = {
    "T_N1_01": {
        "before": 0,
        "after": 1,
        "before_sha256": "fc642a1c5700fec91181189bb0f848958f854fc2b52f9ad2fb7cba0b18002abf",
        "after_sha256": "3c2ea27f3f70c090d913e710c004d3868325f090dcdd47338e724fd2afcb2399",
        "before_anchor": '"value":81/10',
        "after_anchor": '"value":8.1',
        "interpretation": (
            "The original public message already selects 8.1 million leased / 56.0 million "
            "total; the invalid unquoted 81/10 represents the same 8.1 source value. Only "
            "JSON numeric representation is repaired, with no prior execution."
        ),
    },
    "T_N6_01": {
        "before": 0,
        "after": 1,
        "before_sha256": "83dac3f0fed4b48ce3faf1c0e73779268367c7ec39f33e002d2f8365b6ba8f87",
        "after_sha256": "e670b70356e33a504c822524cd868843b6b11ddafbc9aa16f26b555cf69260ec",
        "before_anchor": '"value":384102+121417',
        "after_anchor": "(384102+121417) - (381415+65439)",
        "interpretation": (
            "The first public message and source annotations already select 2008 "
            "asset-category sum minus 2007 sum. Unevaluated sums in JSON numeric value "
            "positions move to expression; the financial relation, source pairing and "
            "unit do not change. There is no first tool result to invent."
        ),
    },
}

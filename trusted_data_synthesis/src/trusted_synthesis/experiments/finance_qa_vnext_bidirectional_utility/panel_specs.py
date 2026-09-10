"""Human source-reviewed IDs, original questions and private sufficient relations.

Bindings name a source segment AND original numeric token, optionally its exact
span index. They are not a search for any equal-valued number in a document.
Nothing here is exposed to a model. No teacher outcome informed this selection.
"""


def spec(
    index,
    qa_id,
    unit,
    expression,
    bindings,
    interpretation,
    *,
    alternative=None,
    relations=None,
    annotation_factor=None,
):
    return dict(
        array_index=index,
        qa_id=qa_id,
        unit=unit,
        expression=expression,
        bindings=bindings,
        interpretation=interpretation,
        alternative=alternative,
        relations=relations or {},
        annotation_factor=annotation_factor or ("100" if unit == "percent" else "1"),
    )


TRAIN = {
    "X1": spec(
        914,
        "ETR/2004/page_239.pdf-2",
        "USD_million",
        "e-b",
        dict(
            e=("t4c1", "426.6"), b=("t1c1", "380.2"), rate=("t2c1", "48.3"), other=("t3c1", "-1.9")
        ),
        (
            "Entergy Mississippi 2003 versus 2002 net revenue (company-defined gross margin), "
            "not consolidated net income. Complete variance bridge: base rates plus other. The "
            "unrelated gross wholesale revenue decline 35.9 is not an extra bridge item."
        ),
        alternative="rate+other",
        relations={"e": "b+rate+other"},
    ),
    "X2": spec(
        1086,
        "PPG/2006/page_42.pdf-4",
        "USD_million",
        "e-b",
        dict(
            e=("q11", "10"),
            b=("q11", "4"),
            charge=("q12", "4", 3),
            cash=("q13", "5"),
            acquired=("q14", "7"),
        ),
        (
            "PPG product-warranty reserve, 2006 minus 2005: 10-4=6. Actual 2006 movements are 4 "
            "pretax warranty charges, minus 5 cash outlays, plus 7 obligations acquired. The "
            "separate asset-retirement obligation and pension table are not the target object."
        ),
        alternative="charge-cash+acquired",
        relations={"e": "b+charge-cash+acquired"},
    ),
    "X3": spec(
        1040,
        "GRMN/2008/page_85.pdf-1",
        "USD_million",
        "e-b",
        dict(
            e=("t8c1", "214.4"),
            b=("t8c2", "126.6"),
            opening=("t1c1", "126.6"),
            prioradd=("t2c1", "14.2"),
            priorreduce=("t3c1", "-4.6"),
            currentadd=("t4c1", "83.8"),
            expiry=("t7c1", "-5.6"),
        ),
        (
            "Garmin unrecognized tax benefits, fiscal 2008 ending amount minus fiscal 2007 "
            "ending amount, in millions. The prior-year closing column is corroborated by 2008 "
            "opening. Four nonzero 2008 movements sum to 87.8; the two dash rows are disclosed "
            "nil movements. Do not subtract interest again: the reconciled disclosed object is "
            "used consistently. Using a different physical duplicate endpoint source remains a "
            "different full behavior signature."
        ),
        alternative="prioradd+priorreduce+currentadd+expiry",
        relations={"e": "opening+prioradd+priorreduce+currentadd+expiry", "opening": "b"},
    ),
}

ADOBE_TAX = dict(
    e=("t6c1", "139549"),
    b=("t0c1", "201808"),
    a=("t1c1", "14009"),
    c=("t2c1", "11350"),
    s=("t3c1", "-81213"),
    l=("t4c1", "-3512"),
    f=("t5c1", "-2893"),
)
ADOBE_SCOPE = (
    "Adobe fiscal 2008 gross unrecognized tax-benefit liability, excluding interest and "
    "penalties. The 139549 table endpoint corresponds to the prose's approximately 139.5 "
    "million, establishing a thousands scale; do not mix in the separate 15.3 million "
    "interest/penalties."
)
DEV = {
    "D01": spec(
        951,
        "ADBE/2008/page_89.pdf-1",
        "USD_thousand",
        "e-b",
        ADOBE_TAX,
        ADOBE_SCOPE,
        alternative="a+c+s+l+f",
        relations={"e": "b+a+c+s+l+f"},
    ),
    "D02": spec(
        27,
        "ADBE/2008/page_89.pdf-2",
        "percent",
        "(e-b)/b*100",
        ADOBE_TAX,
        ADOBE_SCOPE,
        alternative="(a+c+s+l+f)/b*100",
        relations={"e": "b+a+c+s+l+f"},
    ),
    "D03": spec(
        89,
        "RSG/2018/page_94.pdf-1",
        "percent",
        "(e-b)/b*100",
        dict(
            e=("t4c1", "34.3"),
            b=("t1c1", "38.9"),
            charge=("t2c1", "34.8"),
            writeoff=("t3c1", "39.4"),
        ),
        (
            "Republic Services 2018 allowance decline relative to opening allowance. The "
            "parentheses around 39.4 indicate a write-off reduction although the uniform "
            "numeric catalog stores the positive literal. Signed change is negative; an "
            "explicitly worded positive decline magnitude can be interpreted under the "
            "unchanged orientation policy. Monetary scale cancels."
        ),
        alternative="(charge-writeoff)/b*100",
        relations={"e": "b+charge-writeoff"},
    ),
    "D04": spec(
        83,
        "AWK/2012/page_117.pdf-4",
        "percent",
        "classified/e*100",
        dict(
            classified=("q0", "74360"),
            e=("t6c1", "180993"),
            b=("t3c1", "158578"),
            a=("t4c1", "40620"),
            r=("t5c1", "-18205"),
        ),
        (
            "2012 other-long-term-liability portion of American Water's gross unrecognized tax "
            "benefits, not all corporate liabilities. Disclosed denominator or complete 2012 "
            "roll-forward denominator is sufficient. This dual-sufficient evaluation item is a "
            "share, not a net-change question; no route preference is rewarded. Monetary scale "
            "cancels."
        ),
        alternative="classified/(b+a+r)*100",
        relations={"e": "b+a+r"},
    ),
    "D05": spec(
        301,
        "ADBE/1999/page_64.pdf-1",
        "USD_million",
        "severance+lease",
        dict(severance=("q1", "0.3"), lease=("q1", "0.1")),
        (
            "Original question asks for only severance and lease-termination balances. Sum the "
            "two disclosed million-dollar components; the canceled-contract component is not "
            "requested. The overall 0.8 million balance alone is insufficient."
        ),
    ),
    "D06": spec(
        671,
        "RSG/2012/page_93.pdf-2",
        "percent",
        "(now-before)/before*100",
        dict(now=("t2c1", "29.7"), before=("t2c2", "21.0")),
        (
            "Change in the additions charged to expense, 2012 versus 2011, not change in the "
            "allowance balance. Original question specifically selects a movement component. "
            "Endpoint balances cannot determine this component's cross-year growth by "
            "themselves."
        ),
    ),
    "D07": spec(
        386,
        "AWK/2018/page_146.pdf-4",
        "million shares",
        "a+b",
        dict(a=("q5", "0.6"), b=("q5", "0.7")),
        (
            "Actual repurchased common shares in 2018 and 2017, in millions of shares. Add 0.6 "
            "and 0.7, not the dollar purchase costs or remaining authorization. The full "
            "original source provides annual components, not a sufficient endpoint difference."
        ),
    ),
    "D08": spec(
        238,
        "LMT/2016/page_49.pdf-2",
        "USD_million",
        "sales-profit",
        dict(sales=("t1c1", "6608"), profit=("t2c1", "1018")),
        (
            "Original 2016 operating-expense question refers to the MFC segment table, not all "
            "Lockheed Martin. Net sales less operating profit yields 5590 million. This is "
            "metric-component integration, not a required R roll-forward and not an invented "
            "companywide expense measure."
        ),
    ),
    "D09": spec(
        117,
        "NCLH/2018/page_64.pdf-1",
        "percent",
        "(now-before)/before*100",
        dict(now=("p15", "30.4"), before=("p15", "29.0")),
        (
            "Norwegian actual capitalized interest, 2018 versus 2017. Not future contracted "
            "capital expenditure or interest-payment maturity buckets."
        ),
    ),
    "D10": spec(
        14,
        "AWK/2014/page_121.pdf-2",
        "percent",
        "(now-before)/before*100",
        dict(now=("p22", "6348"), before=("p22", "6241")),
        (
            "American Water Medicare Part D subsidy-tax accounting adjustment: corresponding "
            "deferred-tax-asset reduction/regulatory-asset increase in 2014 versus 2013, not "
            "unrecognized-tax-benefit roll-forward."
        ),
    ),
    "D11": spec(
        189,
        "LMT/2016/page_49.pdf-4",
        "USD_million",
        "avg(a,b,c)",
        dict(a=("t2c1", "1018"), b=("t2c2", "1282"), c=("t2c3", "1344")),
        (
            "Arithmetic mean of MFC operating profits for 2016, 2015 and 2014; not aeronautics "
            "profits or sales."
        ),
    ),
    "D12": spec(
        1037,
        "LMT/2016/page_49.pdf-1",
        "percent",
        "(now-before)/before*100",
        dict(now=("t1c1", "6608"), before=("t1c2", "6770")),
        (
            "MFC net-sales growth in 2016 versus 2015, signed negative. Do not use the rounded "
            "prose 2% when an exact table calculation is published."
        ),
    ),
}

ECOLAB = dict(
    e=("t13c5", "7167.1"),
    b=("t1c5", "6490.8"),
    mid=("t8c5", "6383.0"),
    a=("t4c5", "3.7"),
    bplus=("t5c5", "3.6"),
    f16=("t7c5", "-115.1"),
    c=("t9c5", "599.1"),
    d=("t10c5", "0.1"),
    sale=("t11c5", "-42.6"),
    f17=("t12c5", "227.5"),
)
ECOLAB_SCOPE = (
    "Ecolab total carrying goodwill, not one reporting segment. Total-column zero "
    "reclassifications do not change the total; business combinations, dispositions and FX do. "
    "No goodwill impairment was recorded in these years."
)
CONFIRM = {
    "C01": spec(
        330,
        "AMT/2008/page_107.pdf-4",
        "USD_thousand",
        "e-b",
        dict(
            e=("t0c5", "7327"),
            b=("t0c1", "20963"),
            expense=("t0c2", "496"),
            cash=("t0c3", "-12389"),
            other=("t0c4", "-1743"),
        ),
        (
            "American Tower 2006 assumed employee-separation liability: 2006 ending less 2005 "
            "ending, or all three actual 2006 movements. The one-row table embeds dates and "
            "amounts in each cell; source selection must not take the date as the amount."
        ),
        alternative="expense+cash+other",
        relations={"e": "b+expense+cash+other"},
    ),
    "C02": spec(
        1010,
        "AMT/2006/page_113.pdf-3",
        "USD_thousand",
        "e-b",
        dict(e=("t1c7", "301"), b=("t1c4", "665"), expense=("t1c5", "84"), cash=("t1c6", "-448")),
        (
            "American Tower employee-separation restructuring liability during 2005 only, not "
            "2004 or the whole restructuring total."
        ),
        alternative="expense+cash",
        relations={"e": "b+expense+cash"},
    ),
    "C03": spec(
        1061,
        "ABMD/2008/page_86.pdf-3",
        "percent",
        "(e-b)/b*100",
        dict(e=("t2c1", "168"), b=("t0c1", "224"), reduction=("t1c1", "-56")),
        (
            "Abiomed formal unrecognized-tax-benefit roll-forward excluding accrued interest, "
            "April 2007 to March 2008. Not the rounded prose total 0.2 million including "
            "interest."
        ),
        alternative="reduction/b*100",
        relations={"e": "b+reduction"},
    ),
    "C04": spec(
        259,
        "AAPL/2004/page_68.pdf-1",
        "USD_million",
        "e-b",
        dict(
            e=("t6c1", "8.2"),
            b=("t0c1", "5.5"),
            a=("t1c1", "0.5"),
            c=("t2c1", "1.2"),
            d=("t4c1", "0.5"),
            f=("t5c1", "0.5"),
        ),
        (
            "Apple asset-retirement-liability cumulative change across fiscal 2003 and 2004 "
            "from the 2002 opening amount. Four movement entries are distinct facts even when "
            "their values coincide."
        ),
        alternative="a+c+d+f",
        relations={"e": "b+a+c+d+f"},
    ),
    "C05": spec(
        1001,
        "MRK/2013/page_125.pdf-1",
        "percent",
        "(e-b)/b*100",
        dict(
            e=("t7c2", "4425"),
            b=("t7c3", "4277"),
            opening=("t1c2", "4277"),
            a=("t2c2", "496"),
            c=("t3c2", "58"),
            r=("t4c2", "-320"),
            s=("t5c2", "-67"),
            l=("t6c2", "-19"),
        ),
        (
            "Merck 2012 versus 2011 year-end unrecognized tax benefits. The 2012 movement "
            "column closes exactly; the unrelated OCR 2014 in the 2011 expiry cell is not "
            "consumed."
        ),
        alternative="(a+c+r+s+l)/b*100",
        relations={"opening": "b", "e": "opening+a+c+r+s+l"},
    ),
    "C06": spec(
        377,
        "ECL/2017/page_69.pdf-1",
        "percent",
        "(e-b)/b*100",
        ECOLAB,
        ECOLAB_SCOPE,
        alternative="(a+bplus+f16+c+d+sale+f17)/b*100",
        relations={"mid": "b+a+bplus+f16", "e": "mid+c+d+sale+f17"},
    ),
    "C07": spec(
        776,
        "ECL/2017/page_69.pdf-2",
        "percent",
        "(e-mid)/mid*100",
        ECOLAB,
        ECOLAB_SCOPE,
        alternative="(c+d+sale+f17)/mid*100",
        relations={"e": "mid+c+d+sale+f17"},
    ),
    "C08": spec(
        283,
        "KHC/2018/page_132.pdf-3",
        "million shares",
        "e-b",
        dict(
            e=("t7c3", "1220"),
            b=("t1c3", "1214"),
            a=("t2c3", "3"),
            c=("t4c3", "2"),
            d=("t6c3", "1"),
        ),
        (
            "Kraft Heinz outstanding common shares over the complete 2016-2018 period: January "
            "3 2016 opening through December 29 2018 closing. Use outstanding shares, not "
            "issued or treasury shares; selected column has no OCR-nil ambiguity."
        ),
        alternative="a+c+d",
        relations={"e": "b+a+c+d"},
    ),
    "C09": spec(
        410,
        "AMT/2012/page_118.pdf-1",
        "USD_thousand",
        "abs(current+noncurrent)",
        dict(current=("t5c1", "-5536"), noncurrent=("t6c1", "-38519")),
        (
            "Total amount of liabilities assumed in the final Brazilian acquisition allocation. "
            "Two negative net-asset contribution lines correspond to a positive liability "
            "amount of 44055 thousand; preliminary allocation and assets are not added."
        ),
    ),
    "C10": spec(
        735,
        "AMT/2014/page_149.pdf-2",
        "USD_million",
        "(closing-fx)/1000",
        dict(closing=("t7c1", "28524"), fx=("t5c1", "-4934")),
        (
            "Original question explicitly excludes the FX translation adjustment and asks "
            "millions. Table is explicitly thousands: (28524-(-4934))/1000 = 33.458 million. "
            "Original executable annotation omits this unit conversion; it is retained, not "
            "treated as a 33458-million financial target."
        ),
        annotation_factor="1/1000",
    ),
    "C11": spec(
        1081,
        "BKR/2017/page_56.pdf-3",
        "USD_million",
        "operating+investing+financing",
        dict(operating=("t1c3", "1277"), investing=("t2c3", "-466"), financing=("t3c3", "-515")),
        (
            "Original 2015 net-cash-change question over the three disclosed cash-flow activity "
            "categories. The complete source does not give 2014 and 2015 cash endpoints. The "
            "target is the disclosed activity sum; do not assert unreported FX effects are "
            "measured."
        ),
    ),
    "C12": spec(
        1129,
        "BKR/2017/page_56.pdf-4",
        "USD_million",
        "operating+investing+financing",
        dict(operating=("t1c2", "262"), investing=("t2c2", "-472"), financing=("t3c2", "-102")),
        (
            "Original 2016 net-cash-change question over the three disclosed activity "
            "categories. The source gives 2016 cash but not a sufficient 2015 endpoint, so no "
            "endpoints were artificially hidden. Target is the disclosed activity sum, not a "
            "claim about unreported FX."
        ),
    ),
    "C13": spec(
        733,
        "UNP/2009/page_42.pdf-2",
        "USD_million",
        "total-interest",
        dict(total=("t3c1", "2975"), interest=("q2", "914")),
        (
            "Union Pacific capital-lease principal only. The table total includes the footnoted "
            "914 million interest; exclude that component, not the 4763 million interest on a "
            "different debt category."
        ),
    ),
    "C14": spec(
        736,
        "AAPL/2006/page_131.pdf-1",
        "shares",
        "held+unvested",
        dict(held=("t9c1", "149768"), unvested=("q62", "450000")),
        (
            "Original hypothetical asks Oppenheimer's total if the excluded RSUs vest. Footnote "
            "11 explicitly excludes 450000 unvested RSUs from the 149768 reported holding, so "
            "adding is appropriate; no analogous double-counting of already included indirect "
            "shares."
        ),
    ),
    "C15": spec(
        595,
        "ABMD/2012/page_79.pdf-1",
        "USD_million",
        "a+b+c",
        dict(a=("p26", "1.6"), b=("p26", "2.7"), c=("p26", "2.2")),
        (
            "Original question requires total actual operating-lease rent expense for three "
            "fiscal years 2010-2012. Complete source provides the three annual components, not "
            "a stock-endpoint relation. This is multi-period expense integration, not a "
            "roll-forward."
        ),
    ),
    "C16": spec(
        1060,
        "UNP/2016/page_52.pdf-3",
        "percent",
        "(c16+c15+c14)/(t16+t15+t14)*100",
        dict(
            c16=("t4c1", "2440"),
            c15=("t4c2", "3237"),
            c14=("t4c3", "4127"),
            t16=("t9c1", "19941"),
            t15=("t9c2", "21813"),
            t14=("t9c3", "23988"),
        ),
        (
            "Coal's share of aggregate operating revenue across 2014-2016. Integrate the three "
            "coal amounts and three operating-revenue totals; not average annual percentages "
            "and not freight-only denominators."
        ),
    ),
    "C17": spec(
        285,
        "AMT/2014/page_160.pdf-1",
        "percent",
        "(now-before)/before*100",
        dict(now=("q0", "655.0"), before=("q0", "495.2")),
        (
            "Actual aggregate operating-lease rent expense, 2014 versus 2013, not future "
            "minimum lease commitments."
        ),
    ),
    "C18": spec(
        256,
        "AMT/2014/page_160.pdf-3",
        "percent",
        "(now-before)/before*100",
        dict(now=("q0", "495.2"), before=("q0", "419.0")),
        (
            "Actual aggregate operating-lease rent expense, 2013 versus 2012, not future "
            "maturity buckets."
        ),
    ),
    "C19": spec(
        1052,
        "ABMD/2012/page_79.pdf-3",
        "percent",
        "(now-before)/before*100",
        dict(now=("p17", "64350"), before=("p17", "40000")),
        (
            "Monthly Danvers facility base-rent increase from November 2008-June 2010 terms to "
            "July 2010-February 2014 terms; not the companywide annual rent expense."
        ),
    ),
    "C20": spec(
        1084,
        "ABMD/2012/page_79.pdf-4",
        "percent",
        "(now-before)/before*100",
        dict(now=("p17", "66000"), before=("p17", "64350")),
        (
            "Monthly Danvers facility base-rent increase from July 2010-February 2014 terms to "
            "March 2014-February 2016 terms."
        ),
    ),
    "C21": spec(
        490,
        "MRK/2013/page_3.pdf-1",
        "percent",
        "(now-before)/before*100",
        dict(now=("t1c1", "44033"), before=("t1c2", "47267")),
        (
            "Merck total sales growth in 2013 versus 2012; not pharmaceutical-only or a "
            "selected product."
        ),
    ),
    "C22": spec(
        653,
        "MRK/2013/page_3.pdf-2",
        "percent",
        "(now-before)/before*100",
        dict(now=("t1c2", "47267"), before=("t1c3", "48047")),
        "Merck total sales growth in 2012 versus 2011; not one segment or product.",
    ),
    "C23": spec(
        1070,
        "UNP/2018/page_74.pdf-3",
        "percent",
        "year/total*100",
        dict(year=("t3c2", "159"), total=("t7c2", "898")),
        (
            "2021 share of total minimum capital-lease payments, including interest; not "
            "present value 754 or operating leases."
        ),
    ),
    "C24": spec(
        1075,
        "UNP/2018/page_74.pdf-4",
        "percent",
        "year/total*100",
        dict(year=("t2c2", "155"), total=("t7c2", "898")),
        (
            "2020 share of total minimum capital-lease payments, including interest; "
            "denominator unchanged from the original contractual-payment object."
        ),
    ),
}

REJECTED_SCREEN = {
    "CMCSA/2015/page_112.pdf-2": (
        "Selected-year acquisitions nil is OCR 2014 in model-visible numeric table; not used to "
        "fabricate a complete numeric movement route."
    ),
    "ADBE/1999/page_64.pdf-3": (
        "Total-charges nil is OCR 2014; chosen only the separate native component-sum question "
        "-1, not this dual-route candidate."
    ),
    "AWK/2014/page_121.pdf-1": (
        "Original program adds 157 interest/penalties although gross roll-forward explicitly "
        "excludes them; not used as a net-change target."
    ),
    "ETR/2016/page_23.pdf-2": (
        "Already used in prior difficulty work; new training source uses a different original "
        "report page and question."
    ),
    "ETR/2013/page_21.pdf-3": (
        "Already in the old Student evaluation panel; new training source chosen elsewhere "
        "before generation."
    ),
    "ETR/2016/page_374.pdf-3": (
        "Original question year is 20016; preferred an unambiguous original-year training question."
    ),
    "NCLH/2018/page_64.pdf-2": (
        "Program selects forecast 2019/2020 capital expenditure for a question asking "
        "2017/2018; not used."
    ),
    "AMT/2016/page_125.pdf-4": (
        "Question says tax penalties, but available figures combine penalties and interest; not "
        "used as penalties-only."
    ),
    "AAPL/2006/page_131.pdf-2": (
        "Program adds indirect shares already explicitly included in table total; not used. The "
        "separate RSU question -1 explicitly excludes its component and is retained."
    ),
    "ABMD/2008/page_86.pdf-4": (
        "Conditional share-price reductions complicate an unconditional expected "
        "contingent-payment total; not used."
    ),
    "MRK/2013/page_125.pdf-2": (
        "Average settlement value has avoidable signed-reduction versus amount ambiguity; not used."
    ),
}

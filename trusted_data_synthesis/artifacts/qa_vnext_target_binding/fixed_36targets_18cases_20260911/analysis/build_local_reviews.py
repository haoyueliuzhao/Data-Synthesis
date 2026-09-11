"""Transcribe eighteen explicitly read cases, not infer new grades from old scores."""

import json
import re
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_target_binding.cases import validate_evidence
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    CASE_KEYS,
    OUTPUT,
    ZeroModelGuard,
    history_guard,
    read_json,
    read_phase,
    record,
    reference,
    require,
    require_frozen_ledger,
    seal,
)

FAMILIES = {
    "C04/pi0_11": "c04_named",
    "C04/pi0_29": "c04_named",
    "C04/pi0_47": "c04_named",
    "C04/minus_D_11": "c04_named",
    "C04/minus_D_29": "c04_flat",
    "C04/minus_D_47": "c04_named",
    "C08/pi0_11": "c08_ends_final_aliases",
    "C08/pi0_29": "c08_wrong_end_replacement",
    "C08/pi0_47": "c08_wrong_end_replacement",
    "C08/minus_D_11": "c08_wrong_end_direct",
    "C08/minus_D_29": "c08_ends_final_aliases",
    "C08/minus_D_47": "c08_ends_no_final_aliases",
    "C09/pi0_11": "c09_whole_cell",
    "C09/pi0_29": "c09_numeric",
    "C09/pi0_47": "c09_sum",
    "C09/minus_D_11": "c09_whole_cell",
    "C09/minus_D_29": "c09_numeric",
    "C09/minus_D_47": "c09_numeric",
}


def response(packet, index, quote=None):
    raw = next(
        r["content"]
        for r in packet["all_generated_public_responses"]
        if r["response_index"] == index
    )
    return {"kind": "response", "response_index": index, "quote": raw if quote is None else quote}


def sources(packet, *segments):
    return [
        {
            "kind": "source",
            "segment_id": segment,
            "quote": packet["public_document"]["segments"][segment]["text"],
        }
        for segment in segments
    ]


def question(packet):
    return {"kind": "question", "quote": packet["public_document"]["question"]}


def final_span(packet):
    index = next(e["response_index"] for e in packet["original_events"] if e["final"])
    raw = next(
        r["content"]
        for r in packet["all_generated_public_responses"]
        if r["response_index"] == index
    )
    match = re.search(r'"final"\s*:\s*', raw)
    require(match is not None, "transcription.actual_Final_key")
    _, consumed = json.JSONDecoder(parse_float=str).raw_decode(raw[match.end() :])
    return response(packet, index, raw[match.end() : match.end() + consumed])


def contract(packet, quote):
    require(quote in packet["recorded_public_system"], "transcription.exact_contract")
    return {"kind": "contract", "quote": quote}


def claim(
    role,
    location,
    explanation,
    evidence,
    *,
    current=True,
    equal=None,
    derived=None,
    relevant=None,
    withdrawal=None,
):
    return {
        "location": location,
        "explanation": explanation,
        "evidence": evidence,
        "withdrawal_evidence": withdrawal or [],
        "parameters": {
            "role": role,
            "current": current,
            "source_value_equal": equal,
            "derivation_supported": derived,
            "reference_relevant": relevant,
            "consumed": False,
            "withdrawal_supported": not current and bool(withdrawal),
        },
    }


def base(packet, selected, *, public_scope, registered_scope, completed):
    return {
        "case_key": packet["case_key"],
        "reviewer": (
            "same Codex execution assistant; all eighteen original cases read; "
            "known-output diagnostic"
        ),
        "not_independent_or_blind": True,
        "selected_calculation": selected,
        "binding_parameters": {
            "local_relation": "PASS",
            "public_scope_match": public_scope,
            "registered_scope_match": registered_scope,
            "final_chain_completes_public_target": completed,
        },
        "source_claims": [],
    }


def c04(packet, family):
    result = base(packet, "tool:1", public_scope="PASS", registered_scope="PASS", completed="PASS")
    source_evidence = sources(packet, "p0", "t0c0", "t0c1", "t6c0", "t6c1")
    result.update(
        claimed_target_scope=(
            "公开问题所问 2002 余额到 2004-09-25 余额的资产退休负债净变化，百万美元。"
        ),
        formula_explanation=(
            "当前消息明确 2002 的 5.5 与 2004 的 8.2，实际字面式为后值减前值；"
            "公开 ARO 表首尾记录和百万尺度支持原任务。不是只对模型另选的目标作判断。"
            "原表首日期印为 September 29 2002；保留其原文，不用另一段长期资产年度日期改写它。"
        ),
        formula_evidence=[question(packet), response(packet, 0), *source_evidence],
        chain_explanation=(
            "唯一真实成功 calculate 为 tool:1，既有结果 27/10，实际第一 Final 为 2.7，"
            "保留原 million dollars/millions 字段并引用 tool:1。期间和物理量完成链成立；"
            "来源元数据的声明语义另列，不把这里的 PASS 当成完整轨迹新评分。"
        ),
        chain_evidence=[response(packet, 0), final_span(packet), *source_evidence],
    )
    for year, value, row in (("2002", "5.5", "t0c1"), ("2004", "8.2", "t6c1")):
        location = (
            f"response 0 arguments.variables.value_{year} + arguments.sources.value_{year}"
            if family == "c04_named"
            else f"response 0 message: {year} value is {value}"
        )
        result["source_claims"].append(
            claim(
                "DIRECT_SOURCE_VALUE",
                location,
                f"公开当前输入声明为 {year} 的 {value}；对应 ARO 表 {row}。"
                "这是对源值/期间的直接说明；字面算式没有消费命名变量，不会使该声明消失。",
                [response(packet, 0), *sources(packet, row, row.replace("c1", "c0"))],
                equal=True,
            )
        )
    if family == "c04_named":
        result["source_claims"].append(
            claim(
                "DERIVED_FROM_SOURCES",
                "response 1 Final.sources named input map and result_id",
                "Final.sources 用 value_2002/value_2004 标识两个输入的来源，"
                "结合明确减法与 tool:1，是差额的推导来源，不声称两个源单元格都直接包含 2.7。",
                [response(packet, 0), final_span(packet), *source_evidence],
                derived=True,
            )
        )
    else:
        shared = [
            contract(packet, "arguments.variables maps names to decimal/fraction numbers"),
            contract(packet, '{"value":number,"source":optional_source_id,"unit":optional_text}'),
            contract(packet, "Optional arguments.sources maps variable names to source IDs"),
            *sources(packet, "t6c0", "t6c1"),
        ]
        for location, evidence in (
            ("response 0 flat arguments.variables.{value,source,unit}", response(packet, 0)),
            ("response 1 Final.{value,source,unit}", final_span(packet)),
        ):
            result["source_claims"].append(
                claim(
                    "UNRESOLVED",
                    location,
                    "value=2.7 与 source:t6c1 并列，而源单元格为 8.2；若视作直接源值等式，"
                    "两值不等。但公开合同只定义嵌套变量对象/独立 sources 映射，未定义此扁平配对。"
                    "同一消息把 2.7 的关系表述为两余额之差，因而推导引用/普通引用解释不能被排除。"
                    "字段未被消费不是忽略它的理由；它也没有被撤回。"
                    "角色保持未定，不自动 FAIL 或 PASS。",
                    [evidence, response(packet, 0), *shared],
                    equal=False,
                )
            )
    return result


def withdrawn_c08_mapping(packet):
    return claim(
        "DIRECT_SOURCE_VALUE",
        "responses 0/1 old calculate variable-to-SEGMENT associations",
        "旧请求用 arguments.sources（部分还重复在嵌套 source）关联变量与 SEGMENT 标识。"
        "这些标识无法由所给公共目录核实。响应 2 明确换成字面式，variables/sources 为空："
        "这仅将旧调用参数映射替换为非当前映射，不认证旧标识，也不表示后来的引用自动撤回。"
        "若 Final 再次列出这些标识，作为新的当前引用单独记录。",
        [response(packet, 0), response(packet, 1)],
        current=False,
        equal=None,
        withdrawal=[response(packet, 2)],
    )


def c08(packet, family):
    wrong = family in {"c08_wrong_end_replacement", "c08_wrong_end_direct"}
    direct = family == "c08_wrong_end_direct"
    selected, index = ("tool:1", 0) if direct else ("tool:3", 2)
    result = base(
        packet,
        selected,
        public_scope="UNDETERMINED",
        registered_scope="FAIL",
        completed="FAIL" if wrong else "UNDETERMINED",
    )
    anchors = sources(packet, "p25", "t0c3", "t1c0", "t1c3", "t3c0", "t3c3", "t7c0", "t7c3")
    result.update(
        claimed_target_scope=(
            "模型明确声称 2016 与 2018 两个年末，且将 1214 称为 2016 年末。"
            if wrong
            else "当前量是 2016 与 2018 两个年末的差额；"
            "在仅写年份的响应中，年末归属由 t3c3/t7c3 与 1217/1220 的原表位置判明，"
            "不把这一推断冒充模型逐字写出的日期。"
        ),
        formula_explanation=(
            "后端点减前端点作为局部变化关系成立；公开题面仍未唯一选择年初/年末起点。"
            "登记范围是 2016-01-03 至 2018-12-29，不能由模型的年末自述替换。"
            "registered_scope_match 核对完整公开语义链，不等于旧数量字段是否恰好命中 6。"
        ),
        formula_evidence=[question(packet), response(packet, 0), response(packet, index), *anchors],
        chain_explanation=(
            "当前成功调用的文字仍明确断言 end of 2016 = 1214；公开表中该值属于 January 3，"
            "December 31 的值是 1217。Final 没有纠正这一期间声明。"
            "因此，按模型声明的年末窗口，依赖链用了错误期间值；按登记的年初窗口，"
            "也不能把仍明确标成年末的输入静默重定向到年初。"
            "链条 FAIL 来自这条独立可核实的期间冲突，并非用私有参考消除了题面歧义。"
            "旧数量 PASS 保持不变，不能将数值命中充作目标绑定证据。"
            if wrong
            else "当前真实计算 1220-1217 得 3，实际 Final 明确百万股。"
            "它完成的是公开表可支持的两个年末比较，而非已登记的完整三财政年度区间。"
            "由于原公开题目没有唯一确定起点，公开任务适用性/完成链保留未定；"
            "不按模型自选窗口或私有的 6 自动晋升 PASS。原数量 FAIL 不重写。"
        ),
        chain_evidence=[response(packet, index), final_span(packet), *anchors],
    )
    if not direct:
        result["source_claims"].append(withdrawn_c08_mapping(packet))
    if direct:
        for value, segment in (("1214", "t1c3"), ("1220", "t7c3")):
            result["source_claims"].append(
                claim(
                    "DIRECT_SOURCE_VALUE",
                    f"response 0/1 named value {value} source:{segment}n0",
                    f"数字 {value} 与其明确引用的 {segment} 原单元格相符；"
                    "这一字面对应为真，不替模型把该单元格的日期重新命名。",
                    [response(packet, 0), final_span(packet), *sources(packet, segment)],
                    equal=True,
                )
            )
    else:
        result["source_claims"].append(
            claim(
                "DIRECT_SOURCE_VALUE",
                "current 2018 outstanding-shares operand",
                "当前 2018 期末 outstanding shares 为 1220，与公开表对应；"
                "只核对明确对象和期间，不认证先前 SEGMENT 别名。",
                [response(packet, 0), response(packet, index), *sources(packet, "t7c0", "t7c3")],
                equal=True,
            )
        )
    result["source_claims"].append(
        claim(
            "DIRECT_SOURCE_VALUE",
            "current message assertion: end-of-2016 outstanding shares"
            if wrong
            else "current 2016 outstanding-shares operand and its selected table location",
            (
                "当前明确声称 2016 年末是 1214，但 t3c3 的年末值为 1217；"
                "1214 是 t1c3 年初。此处直接期间—源值声明为假，即使另一个数值—ID 对应为真，"
                "即使变量没有被字面计算消费，都不能修复这条仍有效的错误声明。"
                if wrong
                else "当前使用 1217，先前变量名/所选表位置及对应原表显示它属于 2016 年末。"
                "这是合法的年末源值，不代表公开问题已经唯一要求年末起点。"
            ),
            [
                response(packet, 0),
                response(packet, index),
                *sources(packet, "t1c0", "t1c3", "t3c0", "t3c3"),
            ],
            equal=not wrong,
        )
    )
    if family == "c08_ends_final_aliases":
        aliases = json.loads(final_span(packet)["quote"])["sources"]
        available = set(packet["public_document"]["segments"]) | {
            item["id"] for item in packet["public_document"]["numeric_catalog"]
        }
        require(
            all(alias not in available for alias in aliases), "transcription.aliases_unresolved"
        )
        result["source_claims"].append(
            claim(
                "GENERAL_REFERENCE",
                "response 3 Final.sources SEGMENT12n2/SEGMENT13n3",
                "Final 再次列出未解释的 SEGMENT 引用，所以不能说它们已被全局撤回。"
                "当前引用无法核实相关来源；不按相同数字猜配、不自动修成 t7c3/t3c3，"
                "也不因它不是数值源值等式而忽略。引用支持保持未定。",
                [
                    final_span(packet),
                    contract(packet, "source IDs from\nthe complete numeric catalog"),
                ],
                relevant=None,
            )
        )
    if not wrong:
        result["source_claims"].append(
            claim(
                "DERIVED_FROM_SOURCES",
                "actual Final value derived from the current year-end operands",
                "现有成功计算和 Final 对齐到 1220/1217 的年末差额；"
                "此项仅认证该局部推导，不认证登记年初窗口，也不替未解析 Final 引用作担保。",
                [
                    response(packet, index),
                    final_span(packet),
                    *sources(packet, "t3c0", "t3c3", "t7c0", "t7c3"),
                ],
                derived=True,
            )
        )
    return result


def c09(packet, family):
    result = base(
        packet,
        "tool:1",
        public_scope="UNDETERMINED",
        registered_scope="FAIL",
        completed="UNDETERMINED",
    )
    anchors = sources(packet, "p3", "t0c1", "t5c0", "t5c1", "t6c0", "t6c1")
    result.update(
        claimed_target_scope=(
            "模型称之为 sum/total liabilities，实际对最终分配两条负值作有符号求和。"
            "不把“净资产贡献”冒充其逐字声明；该术语只描述所执行负值的物理解释之一。"
        ),
        formula_explanation=(
            "同一最终购买价分配列中的两项负债贡献可作有符号相加，局部关系与实际执行成立。"
            "但承担负债的正金额与有符号净资产贡献不是同一所问量。"
            "原公开问法仍未唯一决定二者，不能用私有正额或模型自己称"
            " total liabilities 认证目标绑定。"
        ),
        formula_evidence=[question(packet), response(packet, 0), *anchors],
        chain_explanation=(
            "唯一真实成功计算输出 -44055，实际第一 Final 仍为 -44055 thousand dollars。"
            "没有后续 abs、符号转换或正金额交付。解释负号表示"
            " liability/net liability 也不等于完成转换。"
            "所以登记正金额的完整绑定不成立；公开目标口径则保持未定，而不是从私有正号判定公开题意。"
            "若后继任务明确问正金额，中间负贡献可以合法存在，但终局还必须完成请求；本例没有。"
        ),
        chain_evidence=[response(packet, 0), final_span(packet), response(packet, 1), *anchors],
    )
    variable_names = (
        ("value1", "value2")
        if family == "c09_sum"
        else ("current_liabilities", "other_non_current_liabilities")
    )
    for name, segment in zip(variable_names, ("t5c1", "t6c1"), strict=True):
        result["source_claims"].append(
            claim(
                "DIRECT_SOURCE_VALUE",
                f"response 0 arguments.variables.{name} + arguments.sources.{name}",
                (
                    f"当前负值与最终分配 {segment} 的负债行及其符号对应。"
                    "whole-cell 坐标可由原表核对同一财务数量；不增加 numeric-ID-only 门槛，"
                    "也不宣称该字符串已经由 read_source 或计算器认证。"
                    if family == "c09_whole_cell"
                    else f"当前变量通过 arguments.sources 指向 {segment}n0；金额、"
                    "负债组成和最终分配列相符。真实字面计算未消费命名变量，"
                    "但明确源值声明仍需核对，本例成立。"
                ),
                [
                    response(packet, 0),
                    *sources(packet, segment, segment.replace("c1", "c0"), "t0c1"),
                ],
                equal=True,
            )
        )
    result["source_claims"].append(
        claim(
            "DERIVED_FROM_SOURCES",
            "response 1 Final.sources with preceding explicit sum relation",
            "Final 中的两组成来源说明有符号合计由它们推导；"
            "并未断言每个单元格都等于合计 -44055。该来源推导成立，"
            "不等于所问正/负物理量已消歧，也不等于完整原任务 PASS。",
            [response(packet, 0), final_span(packet), *anchors],
            derived=True,
        )
    )
    return result


def main():
    root = Path(__file__).resolve().parents[5]
    require(Path(__file__).resolve().parents[1] == root / OUTPUT, "transcription.exact_new_output")
    history_guard(root)
    with ZeroModelGuard(root) as guard:
        ledger, ledger_manifest = require_frozen_ledger(root)
        packets, packets_manifest = read_phase(root, "case_packets")
        require(
            set(FAMILIES) == {f"{t}/{a}_{s}" for t, a, s in CASE_KEYS}, "transcription.exact_18"
        )
        reviews, packet_refs = {}, []
        for registration in packets["registrations"]:
            name = registration["case_key"]
            relative = OUTPUT + "/case_packets/" + registration["packet_path"]
            packet = read_json(root / relative)
            family = FAMILIES[name]
            successful = [
                e["tool_call"]
                for e in packet["original_events"]
                if e["tool_call"] is not None
                and e["tool_call"]["name"] == "calculate"
                and e["tool_call"]["output"]["status"] == "ok"
            ]
            require(len(successful) == 1, "transcription.exact_observed_single_calculation")
            require(
                successful[0]["output"]["result"]["resolved_variables"] == {},
                "transcription.observed_literal_execution",
            )
            make = c04 if name.startswith("C04/") else c08 if name.startswith("C08/") else c09
            review = make(packet, family)
            for field in ("formula_evidence", "chain_evidence"):
                validate_evidence(packet, review[field])
            for statement in review["source_claims"]:
                validate_evidence(packet, statement["evidence"])
                if not statement["parameters"]["current"]:
                    validate_evidence(packet, statement["withdrawal_evidence"])
            reviews[name] = review
            packet_refs.append(reference(root, relative))
        report = record(
            "local_review_transcription",
            cases=18,
            all_case_responses_events_and_original_review_quotes_read=True,
            old_generated_public_responses_read=packets["old_original_responses_copied"],
            ledger_id=ledger["id"],
            ledger_manifest_id=ledger_manifest["id"],
            case_packets_manifest_id=packets_manifest["id"],
            packet_references=packet_refs,
            transcription_families=FAMILIES,
            source_claim_occurrences=sum(len(r["source_claims"]) for r in reviews.values()),
            original_semantic_judgments_overwritten=0,
            other_234_sessions_rejudged=0,
            no_new_primary_score=True,
            same_executor_not_independent_or_blind=True,
            guard=guard.receipt(),
        )
        manifest = seal(root, "manual_reviews", {"report.json": report, "reviews.json": reviews})
        print(
            json.dumps(
                {
                    "id": report["id"],
                    "manifest_id": manifest["id"],
                    "cases": len(reviews),
                    "source_claims": report["source_claim_occurrences"],
                }
            )
        )
    history_guard(root)


if __name__ == "__main__":
    main()

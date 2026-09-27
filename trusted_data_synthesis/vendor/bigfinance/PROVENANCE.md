# Restricted BigFinance-derived VTDO harness

This project adapts the short, injected-provider ReAct loop and per-step trace
structure from **Rogo Technologies, Big Finance Harness 1.0.0**. It is not a
reproduction of the official Big Finance benchmark or its default configuration.

- Upstream: <https://github.com/Rogo-Technologies/big-finance-benchmark>
- Fixed commit: `d794a65fe583edc6852b44c817b0a2aef33ca831`
- Local source review and adaptation date: 2026-09-28.
- Upstream code license: Apache-2.0, copied unmodified as [LICENSE](LICENSE).
- Upstream project authors listed in its pinned `pyproject.toml`: Rogo
  Technologies, Alex Wang, Georg Meinhardt, Jacob Katz, Joseph H. Kim, Pratyush K.
  Chaudhary, Chase Blagden, and Eric Xu.
- No upstream `NOTICE` file is present in the reviewed commit.

Reviewed source SHA-256:

| File | SHA-256 |
| --- | --- |
| `big_finance_harness/agent.py` | `c731d4b1d12c182aaa7275df9c2a73fc8000f3cb196e953b6dca1950e12e03f9` |
| `big_finance_harness/types.py` | `671c8764397d1a6136956b301ea1b419815e1d194c727c1ae3d367c186bfb95a` |
| `LICENSE` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |

## Adopted structure and changes

The implementation lives in
`src/trusted_synthesis/finance_research/harness.py`, with newly implemented
offline tools in the adjacent `tools.py`. The source carries a prominent modified
file notice. The upstream loop was inspected directly, not inferred only from
documentation. We retained the small injected `chat` loop, explicit context
failure, tool dispatch/error observation, append-only conversation history, and
per-step trace approach. We removed/replaced the following upstream behaviors:

| Upstream behavior | Restricted derivative |
| --- | --- |
| 50 steps, 65,536 output tokens by default | Explicit `RunConfig`, defaults 32 / 2,048 / 24,576 context |
| No tool calls can accept plain text as final | Plain text stops with `no_tool_call`, no final answer |
| Multiple tools execute concurrently | Reject multiple calls; execute none |
| Public question plus private reference in run records | Loop and tools accept only a `PublicTask`; scoring is offline |
| Network/EDGAR/fetch tools and Python subprocess | Full original public sources, source list/read, bounded decimal AST arithmetic, final submission |
| Provider-normalized text/usage trace | Retain `ModelTurn`, optional real token receipt, raw/normalized/executed arguments, raw/visible output |
| In-memory step recording | Durable caller-provided event hook before and after every provider/tool invocation |

Final submission supports numeric, span, and list answers, a separate scale, and
an optional FinQA DSL program for offline official scoring. The program is not
executed by the final-answer tool. Calculation is not mandatory for every task.
No answer, score, gold program, hidden retry, auxiliary generation, reader model,
summary, history truncation, or compaction is introduced into the loop.

The `prev:<call_id>.<path>` syntax is inspired by the structured-output references
described for FinanceHarness in the user's research report. Our small recursive
resolver is newly implemented, resolves only this episode's successful actual
tool outputs, and is **not** an integration or reproduction of FinanceHarness.
There is no network financial-research mode in this first-stage QA harness.

## Scope and limits

No Big Finance question subset, private rubric, or dataset is copied into this
integration. The code license does not grant rights to independently licensed
benchmark data. No benchmark accuracy, full-generation equivalence, training
benefit, or official Big Finance compatibility is claimed by wiring tests.
Scripted providers are explicitly fixtures and issue no model calls or fabricated
token receipts. VTDO feedback requires actual aligned token/logprob receipts;
passing the native-evaluation path alone does not confer feedback admission.

The arithmetic tool walks a restricted AST; it is not a Python interpreter or a
general sandbox. It supports only scalar `+`, `-`, `*`, `/`, `**`, parentheses,
and explicit variables. Expressions, AST nodes, values, exponent sizes, and
variable counts are bounded. Decimal precision is 34 and units/scales are never
silently converted. Full sources and tool outputs are not truncated: excess
context must end explicitly at the provider's registered limit.

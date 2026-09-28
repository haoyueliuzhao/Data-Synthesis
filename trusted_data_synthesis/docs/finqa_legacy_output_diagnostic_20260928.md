# 旧 FinQA Probe 库存：公开正文／程序／原生指标非准入诊断

本诊断保持原 1320 槽、旧资格与 train/sealed 用途不变；没有重采、重判资格或训练。
官方 execution 来自实际预测程序的固定 FinQA v2 评分，不以 Final 数字正确代替。
此处 unknown 是诊断或评分不能确定；不改写为模型零分。

| 用途 | 固定分母 | 原生execution正确 | 原生未知 | 全分母execution均值 |
|---|---:|---:|---:|---:|
| all | 1320 | 804 | 0 | 0.6090909090909091 |
| train | 990 | 606 | 0 | 0.6121212121212121 |
| sealed | 330 | 198 | 0 | 0.6 |

## 公开正文交叉诊断

| 用途 | 正文 | 槽数 | 程序结构合法 | 程序可执行 | execution正确 | execution未知 | program正确 |
|---|---|---:|---:|---:|---:|---:|---:|
| all | empty | 85 | 80 | 80 | 53 | 0 | 48 |
| all | nonempty | 1235 | 1142 | 1137 | 751 | 0 | 650 |
| all | unknown | 0 | 0 | 0 | 0 | 0 | 0 |
| train | empty | 63 | 59 | 59 | 36 | 0 | 32 |
| train | nonempty | 927 | 858 | 855 | 570 | 0 | 489 |
| train | unknown | 0 | 0 | 0 | 0 | 0 | 0 |
| sealed | empty | 22 | 21 | 21 | 17 | 0 | 16 |
| sealed | nonempty | 308 | 284 | 282 | 181 | 0 | 161 |
| sealed | unknown | 0 | 0 | 0 | 0 | 0 | 0 |

完整五维交叉表见 summary.json；逐槽结果见 slots.tsv 与 slots.jsonl。
原生正确不证明公开说明正确，也不升级任何旧 unknown/invalid 为 CompletePass。
正文非空是存在性检测，不是其金融断言的语义裁定。程序结构合法也不等于可执行或答案正确。

## 事前固定的有界公开正文样本

按原 task/slot 顺序取前12个非空正文槽，每槽只展示最早2条非空 public content 的前200个字符。
只作解释，不能代表全部非空正文；没有读取或展示 private reasoning，没有删除原正文。

### APD/2019/page_53.pdf-2 / slot 0 / train

turn 0（原文 65 字符）：

```json
"I'll read the table source to confirm the pension expense values."
```

turn 1（原文 28 字符）：

```json
"The decrease is 91.8 − 27.6."
```


### APD/2019/page_53.pdf-2 / slot 1 / train

turn 0（原文 62 字符）：

```json
"I'll read the table source to get the pension expense figures."
```

turn 1（原文 62 字符）：

```json
"The pension expense dropped from $91.8 (2018) to $27.6 (2019)."
```


### APD/2019/page_53.pdf-2 / slot 2 / train

turn 0（原文 97 字符）：

```json
"I'll solve this by reading the source table to find the pension expense values for 2019 and 2018."
```

turn 2（原文 54 字符）：

```json
"The values contain \"$\" and commas, so I'll strip them."
```


### APD/2019/page_53.pdf-2 / slot 3 / train

turn 0（原文 65 字符）：

```json
"I'll read the table source to confirm the pension expense values."
```

turn 3（原文 109 字符）：

```json
"The pension expense decreased from $91.8 million (2018) to $27.6 million (2019), a decrease of $64.2 million."
```


### APD/2019/page_53.pdf-2 / slot 4 / train

turn 0（原文 66 字符）：

```json
"I'll read the table source to confirm the pension expense figures."
```

turn 1（原文 35 字符）：

```json
"The decrease is 91.8 − 27.6 = 64.2."
```


### APD/2019/page_53.pdf-2 / slot 5 / train

turn 0（原文 97 字符）：

```json
"I'll solve this by reading the pension expense data and computing the decrease from 2018 to 2019."
```

turn 1（原文 68 字符）：

```json
"Pension expense: 2018 = $91.8, 2019 = $27.6. Decrease = 91.8 - 27.6."
```


### APD/2019/page_53.pdf-2 / slot 7 / sealed_diagnostic

turn 0（原文 52 字符）：

```json
"I'll analyze the pension expense data for 2018-2019."
```

turn 1（原文 50 字符）：

```json
"Pension expense 2019 is $27.6M and 2018 is $91.8M."
```


### STT/2013/page_71.pdf-1 / slot 0 / train

turn 0（原文 49 字符）：

```json
"I'll read the table source to confirm the values."
```

turn 1（原文 51 字符）：

```json
"I'll compute the growth rate: (3749 − 3365) / 3365."
```


### STT/2013/page_71.pdf-1 / slot 1 / train

turn 0（原文 51 字符）：

```json
"I'll read the table source to get the exact values."
```

turn 2（原文 71 字符）：

```json
"The values include a \"$ \" prefix. Let me use numeric literals directly."
```


### STT/2013/page_71.pdf-1 / slot 2 / train

turn 0（原文 55 字符）：

```json
"I'll read the table source to confirm the exact values."
```

turn 1（原文 55 字符）：

```json
"Now I'll compute the growth rate: (3749 - 3365) / 3365."
```


### STT/2013/page_71.pdf-1 / slot 3 / train

turn 0（原文 67 字符）：

```json
"I'll start by reading the table source to confirm the exact values."
```

turn 1（原文 93 字符）：

```json
"The average total short-duration advances: 2013 = 3749, 2012 = 3365. Now compute growth rate."
```


### STT/2013/page_71.pdf-1 / slot 4 / train

turn 0（原文 86 字符）：

```json
"I'll start by reading the table source to confirm the short-duration advances figures."
```

turn 1（原文 51 字符）：

```json
"I'll compute the growth rate: (3749 - 3365) / 3365."
```

## 解释边界

每题有8个相关生成槽，这不是1320道独立金融题。train与sealed分别报告；sealed不转入训练。
旧资格首因仍是原有限认证器的首阻断，不等于已经逐条审阅所有公开声明。
未扫描旧R/G/H结果、未执行qualification或Mapper、未删除内容、未改原始记录。
模型/API/GPU调用均为0。任何新生成协议及训练准入均需独立登记。

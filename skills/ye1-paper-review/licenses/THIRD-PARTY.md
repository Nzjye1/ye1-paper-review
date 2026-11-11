# 第三方代码说明

本 Skill 中以下代码来自 [Aperivue/medsci-skills v6.2.0](https://github.com/Aperivue/medsci-skills/releases/tag/v6.2.0)，提交 `cc462bc2069064b557c2fea12a1f83ed1fe67f66`：

- `scripts/check_table_percentages.py`：上游 `skills/self-review/scripts/check_table_percentages.py`。

上述代码遵循随附 [MEDSCI-MIT.txt](MEDSCI-MIT.txt)，保留原版权和许可。此包不含上游第三方报告规范原文或 CSL 样式；规范及其他第三方资料如需另行复制，应逐项核对许可。

自然化指导参考 [Yila-AI academic-humanizer](https://github.com/Yila-AI/awesome-research-skills/tree/9457733ecf6dbef4cad8debf2e58cc3bbd378e79/skills/academic-humanizer)，随包保留其 [Apache 2.0 许可](ACADEMIC-APACHE-2.0.txt)及[第三方声明](ACADEMIC-THIRD-PARTY.md)。

`scripts/ye1_word.py`、`scripts/ye1_table_check.py` 和 `scripts/ye1_pubmed.py` 是本项目为该 Skill 编写的辅助代码，不是上述上游文件；其中个别文件仅存在于相应 Skill 包。

`scripts/ye1_reference_audit.py` 为本次新写的公开题录核对工具；调用 Crossref 和 NCBI 公共 API，非上述上游脚本。

`scripts/ye1_fidelity_audit.py` 为本项目新编写的本地文本标记核对工具。

`scripts/ye1_compare.py` 和 `scripts/ye1_revision_check.py` 是本次新编写的 Word 比较和修订核查工具，分别依赖本机 Microsoft Word 和 OOXML 文档结构。设计和能力核对时参考了 MedSci 的 Word 比较及修订检查方案；为保留溯源，随包保留 [MEDSCI-MIT.txt](MEDSCI-MIT.txt)。

## 保留的兼容工具

`scripts/check_rewrite_fidelity.py` 来自 MedSci v6.2.0，遵循 [MEDSCI-MIT.txt](MEDSCI-MIT.txt)；`scripts/check_medical_fidelity.py` 来自 [ecpp/humanize-medical-writing](https://github.com/ecpp/humanize-medical-writing/tree/5eceb6e4fd614e542f9e4f352cb717f07a54b30a)，遵循 [MEDICAL-HUMANIZER-MIT.txt](MEDICAL-HUMANIZER-MIT.txt)；`scripts/check_academic_invariants.py` 来自 [Yila-AI academic-humanizer](https://github.com/Yila-AI/awesome-research-skills/tree/9457733ecf6dbef4cad8debf2e58cc3bbd378e79/skills/academic-humanizer)，遵循 [ACADEMIC-APACHE-2.0.txt](ACADEMIC-APACHE-2.0.txt) 和 [ACADEMIC-THIRD-PARTY.md](ACADEMIC-THIRD-PARTY.md)。后两项原脚本只改名。

`scripts/verify_refs.py` 为 MedSci v6.2.0 代码的本项目修改版，保留 [MEDSCI-MIT.txt](MEDSCI-MIT.txt)。

# ClashRule

支持直接在 GitHub 网页修改规则，自动构建、验证并提交最终文件到 main。[查看自动构建状态](https://github.com/dearjnana/ClashRule/actions/workflows/build.yml)。

面向 OpenClash / Mihomo 的分流规则、订阅转换配置和容器部署示例。规则源只维护一份，构建结果自动生成；不保留原始快照、旧配置副本或空占位文件。

## 入口

- [主配置](profiles/openclash.ini)：按顺序去重的主规则与两份原生规则集。
- [手机配置](profiles/android.ini)：与 OpenClash 共用规则，关闭局域网监听并降低测速频率。
- [完整展开配置](profiles/expanded.ini)：完整展开规则，便于对照兼容性。
- [Gemini 规则](rules/ai/Gemini.list)：网页版、手机应用和 AI Studio 的专用服务域名。
- [使用说明](docs/使用与回退.md)、[文件索引](docs/仓库文件索引.md)、[旧地址迁移](docs/根目录迁移链接.md)。
- [部署示例](deploy/README.md)：公网转换器、内网转换器和 Sub-Store。

**转换配置均须使用 `expand=true`，转换后运行 `tools/finalize.py`，再导入客户端。** 该步骤恢复转换器无法完整保留的原生策略组字段。不要把未经整理的输出直接替换现用配置。

## 维护

日常维护只需在 GitHub 编辑 `rules/` 中的规则，或 `config/` 中的顺序、策略组和基础设置，提交到 main。等待“自动构建规则”显示成功后，生成文件会由机器人自动更新；无需本地 Python，也无需手动上传生成目录。具体操作见 [网页维护与自动构建](docs/网页维护与自动构建.md)。

需要在本地开发构建工具时，可以手动执行：

```sh
python -m pip install -r tools/requirements.txt
python tools/build.py
python tools/verify.py
python tools/check_repository.py
```

`generated/`、`providers/`、`profiles/`、`templates/` 和 `docs/仓库文件索引.md` 为生成结果，请修改对应源文件。验证失败不会回写生成文件；已有更新提交时，旧任务不会覆盖新提交。测试临时文件和运行报告不会提交到仓库。所有维护注释使用中文；协议字段、程序标识符、来源名称与许可证法律正文保持原有拼写。

旧根目录文件和八份旧 INI 已移除，仓库外的旧地址需要更换。历史变更可以通过 Git 提交查询，不在工作目录另存原始文件。

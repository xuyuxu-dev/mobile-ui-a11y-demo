# 安全说明

## 报告问题

这是一个个人 demo 项目，没有安全响应流程。若发现注入/越权/隐私问题，
请在 issue 里描述**复现步骤**即可。

## 设计上的安全边界

1. **默认只读、默认 dry-run**：不加 `--allow-taps` 不会产生任何点击。
2. **能力白名单**：`engine/capabilities.json` 列出允许驱动的包/组件，默认拒绝。
3. **输入校验**：流程字段只允许 `[A-Za-z0-9_.$/]`；未知操作直接拒绝。
4. **数据最小化**：采集结果只含计数；截图与 trace 落在 `data/`（gitignore）。
5. **无网络**：全部代码不发起网络请求。

## 已知限制

- 白名单是包名级，不是页面级
- `--redact` 只脱敏页面来源的文字，流程自带的说明文字仍会记录
- OCR 依赖 Windows 系统 OCR 引擎
## Intended use

The audit side is read-only and intended for interfaces the operator owns or is authorised
to inspect. The flow engine is intended for apps under development, and ships with a
capability allowlist (`engine/capabilities.json`); `--allow-any` exists for local
experimentation and shifts responsibility to the operator.

## Hardening in place

- traces are redacted by default; `--no-redact` is required to keep raw text
- `tools/clean_local.py` removes screenshots, traces and build output
- the capability allowlist supports page-level entries (`page_allowlist`)
- CI pins action commits and runs with `permissions: contents: read`
- OCR invokes an absolute `powershell.exe` path, not one resolved from PATH

## Known residual risks

- `data/` is gitignored but remains on disk until cleaned; screenshots there may show interface content.
- The OCR channel depends on the Windows OCR engine; it is unavailable elsewhere.
- The capability allowlist restricts listed packages, page-level granularity only where configured.
- The repository was recreated after history was rewritten; earlier objects are no
  longer reachable by SHA.
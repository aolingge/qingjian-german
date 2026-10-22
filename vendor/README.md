# candle-core 的 ZIP 安全兼容补丁

此目录保留 crates.io 发布的 `candle-core 0.11.0` 源码与原始 LICENSE，避免为修复 ZIP 漏洞而引入模型库尚未发布的其他行为变更。

来源：https://crates.io/crates/candle-core/0.11.0 。下载时已按 crates.io API 的 SHA-256 核对发布包。

相对发布包仅修改：

- `Cargo.toml`：ZIP 依赖升级到 `9.0.5`。
- `src/npy.rs`、`src/pickle.rs`：适配 ZIP 9 返回可失败文件名的 API，传播读取错误，不忽略错误。
- `tests/serialization_tests.rs`：保留上游 ZIP 9 UTF-8、CP437 和无效归档回归测试。

兼容改动依据：https://github.com/huggingface/candle/pull/4041 。没有引入该分支的其他提交。

根工作区通过 `[patch.crates-io]` 使用此副本。上游正式发布兼容 ZIP 9 的版本、并通过本项目三平台检查后，应升级官方依赖并删除此临时副本。

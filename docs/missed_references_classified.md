# (a) 桶 95 条归类：不是「没看到」，是「没兑上」

来源：`prism-go-all` / `20261008_083914`。**这 95 条的位置都落在我们审过的 hunk 里** ——
检索那条链是好的。归类的问的是另一件事：**为什么没兑上**。

| 类 | 含义 | 条数 |
|---|---|---|
| **A1** | 提示词六维度里的事（逻辑/边界/跨文件/意图一致/隐式契约/安全），没做出来 | 52 |
| **A2** | 我们报了，没兑上 —— 同一根因只报一次 / 一条评论只兑一条参考 / 说在别的行或别的文件 | 19 |
| **A3** | 六维度之外：可维护性与设计意图（命名措辞、调试残留、重复、分层、惯用法） | 24 |

判定是**人读出来的**（逐条读参考原文 + 对照我们在同一 PR 报了什么），不是脚本算的。
可算的那部分已经排除在外：**5 条**参考的位置与另一条**已命中**的参考重合（数据集在
同一处写了两遍，先到的那条兑走了行号额度），已归入 A2。

---

## A1 · 六维度内，没做出来（52 条）

- **[02]** `pkg/gofr/http_server.go:42`（gofr-dev__gofr）— 中间件顺序变了 → 逻辑
    - 参考：The middleware order has been changed such that `Logging` is now applied after `CORS` and `Metrics`. This means that if the `CORS` middleware handles 
- **[06]** `internal/checker/checker.go:10845`（microsoft__typescript-go）— 切片越界 panic → 边界
    - 参考：Potential runtime panic: String slicing may cause index out of bounds. The code attempts to slice t.symbol.Name[4:len(t.symbol.Name)-7] but doesn't ch
- **[07]** `cmd/cmd.go:801`（ollama__ollama）— 进度初值硬编码 0 → 逻辑
    - 参考：Logic issue: Hardcoding the initial progress value to 0 instead of using resp.Completed will cause the progress bar to incorrectly start from zero eve
- **[08]** `server/internal/cache/blob/chunked.go:56`（ollama__ollama）— EOF 语义被改写 → 逻辑
    - 参考：This EOF handling may be incorrect. io.CopyN returns EOF when it successfully reads exactly n bytes. This code converts ALL EOF errors to ErrUnexpecte
- **[11]** `server/internal/client/ollama/registry.go:421`（ollama__ollama）— 进度记账把失败重试也算进去 → 逻辑
    - 参考：Concurrency/progress accounting concern: `trackingReader.Read` adds bytes even when `err != nil` (including non-EOF errors). This can over-report prog
- **[13]** `server/internal/client/ollama/registry.go:606`（ollama__ollama）— 注释与代码不一致 → 意图一致（同维度、别的实例我们报了）
    - 参考：The comment states that Config is "always set to an empty digest", but the code no longer explicitly sets the Config field. It now relies on the zero-
- **[14]** `server/internal/client/ollama/registry.go:783`（ollama__ollama）— 丢掉底层 err，未用 %w → 错误处理
    - 参考：Error handling bug: on invalid digest parse, the returned error drops the underlying parse error (and formats bytes with %q but passes []byte). Prefer
- **[16]** `server/internal/registry/server.go:280`（ollama__ollama）— ticker 未 Stop，goroutine 泄漏 → 边界
    - 参考：Resource leak: The ticker 't' is created but never stopped. This will cause a goroutine leak. Add 'defer t.Stop()' after creating the ticker to ensure
- **[17]** `server/internal/registry/server.go:283`（ollama__ollama）— ticker 只在 n>0 才启动 → 逻辑
    - 参考：Logic risk: the ticker only starts (Reset to 100ms) when `n > 0`. If the pull errors/finishes before any progress update with `n > 0`, no periodic upd
- **[18]** `server/internal/registry/server.go:294`（ollama__ollama）— 复用 Digest 字段传 model 名 → 意图一致
    - 参考：The progress update JSON incorrectly repurposes the 'Digest' field to transmit the model name string, violating its semantic meaning as a content iden
- **[19]** `server/internal/registry/server.go:316`（ollama__ollama）— 成功时没发 success 状态 → 逻辑
    - 参考：Logic error: When the pull completes successfully (err == nil), no success status is sent to the client. The code should encode a success status befor
- **[20]** `internal/ast/ast.go:754`（microsoft__typescript-go）— 移除 case 会 panic → 边界
    - 参考：Removing KindJSDocImportTag from this switch statement may cause runtime panics when calling ModuleSpecifier() on JSDocImportTag nodes. Since JSDocImp
- **[21]** `internal/ast/utilities.go:2367`（microsoft__typescript-go）— 对错误节点类型调 AsImportDeclaration → 边界
    - 参考：`IsDefaultImport` now accepts `KindJSImportDeclaration` but still calls `node.AsImportDeclaration()`. This is safe only if `JSImportDeclaration` is re
- **[22]** `internal/checker/checker.go:29386`（microsoft__typescript-go）— 同上，KindExportDeclaration → 边界
    - 参考：Calling `AsImportDeclaration()` on a node of kind `KindExportDeclaration` will cause a panic because `ExportDeclaration` uses a different struct than 
- **[23]** `internal/parser/reparser.go:122`（microsoft__typescript-go）— clone 后直接改字段，破坏不可变约定 → 隐式契约
    - 参考：Directly mutating IsTypeOnly after cloning may violate immutability assumptions present in other parts of the codebase. Consider using a factory metho
- **[24]** `internal/printer/printer.go:3956`（microsoft__typescript-go）— switch 里该 case 没实现 → 逻辑
    - 参考：Unhandled `KindJSImportDeclaration` case in `emitStatement` switch lacks implementation; must either add dedicated emit logic or explicitly panic if t
- **[29]** `internal/transformers/externalmoduleinfo.go:50`（microsoft__typescript-go）— 两种节点类型不能互换使用同一转换 → 边界
    - 参考：Grouping ast.KindImportDeclaration and ast.KindJSImportDeclaration assumes interchangeable use of .AsImportDeclaration(). Please verify that both node
- **[36]** `server/create.go:267`（ollama__ollama）— 新 API 的 Go 版本兼容 → 隐式契约
    - 参考：Potential compatibility risk: `os.OpenRoot` / `Root.OpenFile` are newer APIs. Please confirm the project Go toolchain version supports them; otherwise
- **[37]** `internal/execute/outputs.go:270`（microsoft__typescript-go）— 类型断言缺 nil 检查 → 边界
    - 参考：The type assertion for `DefaultValueDescription` lacks a nil check on the resulting `*diagnostics.Message` pointer, risking a runtime panic when acces
- **[38]** `internal/execute/outputs.go:311`（microsoft__typescript-go）— 条件判断疑似写错 → 逻辑
    - 参考：The condition 'if valueCandidates != nil' inside the defaultValueDescription block seems incorrect. It should probably check if we previously added va
- **[41]** `pkg/remote/fileshare/fsutil/fsutil.go:89`（wavetermdev__waveterm）— 前缀在目标路径被改写前算好 → 逻辑
    - 参考：There is a logical issue here: `destPathPrefix` is calculated using `destConn.Path` before `DetermineCopyDestPath` is called. `DetermineCopyDestPath` 
- **[47]** `pkg/wshrpc/wshremote/wshremote.go:322`（wavetermdev__waveterm）— 错误消息里用错变量 → 逻辑
    - 参考：Incorrect URI variable used in error message. Should be destUri since we're failing to parse the destination URI.
- **[48]** `pkg/blockcontroller/blockcontroller.go:149`（wavetermdev__waveterm）— err == 应改 errors.Is → 错误处理
    - 参考：Improper error comparison may miss wrapped `fs.ErrNotExist` errors. Replace direct `err == fs.ErrNotExist` comparison with `errors.Is(err, fs.ErrNotEx
- **[49]** `pkg/blockcontroller/blockcontroller.go:285`（wavetermdev__waveterm）— 命令串校验不足以防注入 → 安全
    - 参考：Insufficient command string validation when shell execution is disabled; the current space check doesn't prevent command injection via other special c
- **[50]** `pkg/waveobj/wtypemeta.go:52`（wavetermdev__waveterm）— 带点的 JSON tag 兼容性 → 隐式契约
    - 参考：These new fields introduce dotted JSON tags like `cmd:initscript.sh`. Plain `encoding/json` treats the tag as a literal key (fine), but if any layer l
- **[51]** `pkg/wslconn/wslconn.go:121`（wavetermdev__waveterm）— Debugf 调了 Infof → 逻辑
    - 参考：This Debugf method is calling blocklogger.Infof instead of blocklogger.Debugf. This is likely a copy-paste error and should probably use Debugf to mat
- **[53]** `pkg/gofr/datasource/pubsub/nats/client.go:83`（gofr-dev__gofr）— 后台重连改共享字段无同步 → 边界（并发）
    - 参考：Critical concurrency issue: The retryConnect() method runs in a goroutine and modifies shared fields (c.connManager, c.streamManager, c.subManager) wi
- **[54]** `pkg/gofr/datasource/pubsub/nats/client.go:150`（gofr-dev__gofr）— 吞掉真实错误、恒定返回同一个 → 错误处理
    - 参考：Serious logical issue: The Subscribe method calls checkClient() but ignores its actual error and always returns errClientNotConnected. This prevents p
- **[55]** `core/http/endpoints/jina/rerank.go:22`（mudler__LocalAI）— appConfig 无 nil 检查 → 边界
    - 参考：New line unconditionally dereferences `appConfig` (`appConfig.MachineTag`). If `appConfig` can ever be nil (e.g., miswired endpoint, tests, older call
- **[56]** `core/http/endpoints/localai/vad.go:22`（mudler__LocalAI）— appConfig 无 nil 检查 → 边界
    - 参考：Potential nil-deref: if `appConfig` can be nil (e.g., endpoint wired without full ApplicationConfig), this will panic. Consider guarding with `if appC
- **[58]** `core/http/endpoints/openai/chat.go:186`（mudler__LocalAI）— 非空即真，"false" 反而打开 → 逻辑
    - 参考：The logic `c.Get("LocalAI-Extra-Usage", "") != ""` evaluates to `true` for any non-empty value, including "false" or "0". This means a user trying to 
- **[59]** `core/http/endpoints/openai/edit.go:30`（mudler__LocalAI）— 同 58 → 逻辑
    - 参考：The opt-in flag check may have a logic issue. Currently, any non-empty value (including 'false', '0', 'no') will be treated as true. Consider checking
- **[60]** `core/http/endpoints/openai/embeddings.go:26`（mudler__LocalAI）— appConfig 无 nil 检查 → 边界
    - 参考：Potential nil dereference: `appConfig` is used without a nil check. If `EmbeddingsEndpoint` can ever be constructed/called with `appConfig == nil` (e.
- **[62]** `core/http/endpoints/openai/files.go:125`（mudler__LocalAI）— 无条件回机器信息，应 opt-in → 安全
    - 参考：The unconditional inclusion of the `LocalAI-Machine-Tag` header in all responses risks exposing sensitive machine information; this behavior must be m
- **[63]** `core/http/endpoints/openai/image.go:69`（mudler__LocalAI）— c.Set 设的是响应头，方向错 → 意图一致
    - 参考：New line sets a **response** header via `c.Set`. If the intent is to tag downstream backend requests, this won’t have any effect (would need to set he
- **[64]** `core/http/endpoints/openai/list.go:17`（mudler__LocalAI）— appConfig 无 nil 检查 → 边界
    - 参考：Potential panic: `appConfig` is dereferenced without a nil-check. If the caller passes nil (e.g., endpoint wiring not updated everywhere), this will c
- **[65]** `core/http/endpoints/openai/transcription.go:28`（mudler__LocalAI）— appConfig 无 nil 检查 → 边界
    - 参考：New line can panic: `appConfig` is a pointer and is dereferenced without a nil check. If `TranscriptEndpoint` is ever wired with `appConfig == nil` (t
- **[66]** `cmd/wsh/cmd/wshcmd-connserver.go:232`（wavetermdev__waveterm）— token 存在性从 stdout 泄漏 → 安全
    - 参考：* `askForJwtToken` leaks token presence via stdout ("HAVE-JWT"); switch to stderr with non-sensitive message to avoid security exposure. * `askForJwtT
- **[70]** `pkg/remote/conncontroller/conncontroller.go:333`（wavetermdev__waveterm）— 与旧版 connserver 的兼容 → 隐式契约
    - 参考：Potential backward compatibility issue: This code waits for a JWT status line from the remote connserver with a 3-second timeout. If the remote connse
- **[74]** `pkg/util/shellutil/shellutil.go:57`（wavetermdev__waveterm）— 2>/dev/null 吞掉安全操作的错误 → 错误处理
    - 参考：Duplicate PATH manipulation and silent error suppression in Zsh startup script. The script redundantly adds WAVETERM_WSHBINDIR to PATH in two location
- **[75]** `pkg/util/shellutil/shellutil.go:143`（wavetermdev__waveterm）— 重定向 stderr 掩盖失败 → 错误处理
    - 参考：Redirecting stderr to `/dev/null` when sourcing the token script hides important errors from the `wsh token` command, preventing failure diagnosis.
- **[77]** `pkg/util/shellutil/tokenswap.go:41`（wavetermdev__waveterm）— token 用标准 base64，URL 里会坏 → 安全
    - 参考：Security/logic: this uses standard Base64 for a token that will likely be transported in URLs/CLI args. StdEncoding includes '+' and '/' and may intro
- **[78]** `pkg/util/shellutil/tokenswap.go:46`（wavetermdev__waveterm）— 解码只认一种编码、不校验字段 → 逻辑
    - 参考：Robustness: Unpack uses StdEncoding to decode. If you switch to URL-safe (recommended) or accept tokens from multiple sources, consider attempting bot
- **[79]** `pkg/util/shellutil/tokenswap.go:78`（wavetermdev__waveterm）— 条目从不设 Exp，会被立刻清掉 → 逻辑
    - 参考：Potential logic issue: entries are never assigned an expiration in this file, but removeExpiredTokens relies on Exp. If callers forget to set Exp, Exp
- **[80]** `pkg/wshrpc/wshrpctypes.go:266`（wavetermdev__waveterm）— 响应结构加字段，破坏 JSON 形状 → 隐式契约
    - 参考：Potential compatibility issue: adding new return fields (Env/InitScriptText) to CommandAuthenticateRtnData changes the JSON shape of an existing respo
- **[82]** `ml/backend.go:402`（ollama__ollama）— 接口加方法是破坏性变更 → 隐式契约
    - 参考：Adding `Ints() []int32` to the `Tensor` interface is an API-breaking change: all concrete tensor implementations and any test fakes/mocks must impleme
- **[83]** `ml/backend/ggml/ggml.go:1007`（ollama__ollama）— C.int 长度截断 → 边界
    - 参考：The use of `C.GoBytes` with `C.int` cast for the length creates a risk of data truncation. `C.int` is typically 32-bit, so if the tensor size exceeds 
- **[84]** `ml/backend/ggml/ggml.go:1007`（ollama__ollama）— 两条分支都没有时静默返回 nil → 错误处理
    - 参考：The `Bytes()` method now handles CPU tensors by using `C.GoBytes()` which creates a copy of the data. However, there's a potential issue: if the tenso
- **[85]** `ml/backend/ggml/ggml.go:1029`（ollama__ollama）— 同上 → 错误处理
    - 参考：Good addition of the `Ints()` method to complement `Floats()` and `Bytes()`. However, the same concern applies here: when both `sync` is nil and `C.gg
- **[87]** `runner/ollamarunner/runner.go:711`（ollama__ollama）— 除零 → 边界
    - 参考：Potential runtime panic: vocabSize := len(outputs) / activeBatch.batch.Outputs.Dim(0) will divide by zero if Outputs is empty (Dim(0)==0). Even if nor
- **[89]** `cmd/cmd.go:128`（ollama__ollama）— goroutine 闭包捕获循环变量 → 边界（并发）
    - 参考：**Critical Bug: Closure Variable Capture Issue** The loop variables `f` and `digest` are being captured by the goroutine closure. Since goroutines run
- **[91]** `pkg/gofr/logging/ctx_logger.go:37`（gofr-dev__gofr）— 格式函数也注入了 trace map，格式串会错 → 逻辑
    - 参考：**Incorrect Trace Info Injection for Formatted Logging Functions** The formatted logging methods (Debugf, Logf, Infof, Noticef, Warnf, Errorf, Fatalf)

## A2 · 我们报了，没兑上（19 条）

- **[01]** `pkg/gofr/http/middleware/config.go:14`（gofr-dev__gofr）— 我们 config.go:36 报的就是这条（字符串严格比较，TRUE 被判为关）
    - 参考：The `LogDisableProbes` field in `MiddlewareConfig` should be a boolean instead of a string to enforce valid true/false values and eliminate unnecessar
- **[03]** `pkg/gofr/http_server.go:42`（gofr-dev__gofr）— 同 01 —— 同一根因，报在另一行
    - 参考：Potential logic/config issue: `LogDisableProbes` is compared to the literal string "true". If this config is ever represented as a boolean, or uses ot
- **[04]** `pkg/gofr/http/responder.go:31`（gofr-dev__gofr）— 我们 responder.go:97 报的就是这条（omitempty 对 interface{} 失效）
    - 参考：Potential inconsistency in metadata handling. When v.Metadata is nil, this will result in omitting the metadata field due to json:"metadata,omitempty"
- **[12]** `server/internal/client/ollama/registry.go:482`（ollama__ollama）— 我们 registry.go:482 报的就是这条；同位置有两条参考，额度只兑一条
    - 参考：There is a potential race condition here. The `defer chunked.Close()` is called at function exit, but `chunked` is being used inside goroutines spawne
- **[34]** `server/create.go:52`（ollama__ollama）— 我们 create.go:172 报的就是这条（validRelative 会拒 ./model.safetensors）
    - 参考：The validation is performed on the original path before it is cleaned with `filepath.Clean()`. This causes `validRelative()` to reject paths like `"./
- **[39]** `pkg/gofr/testutil/port.go:37`（gofr-dev__gofr）— 我们 port.go:37 报的就是这条；同位置有两条重复参考，先到的兑走了
    - 参考：The documentation comment refers to `ServerConfigsProvider`, but the function name is `NewServerConfigs`. Please correct the comment to match the func
- **[42]** `pkg/remote/fileshare/pathtree/pathtree.go:73`（wavetermdev__waveterm）— 我们 pathtree.go:64 报的就是这条调试日志
    - 参考：Debug log should be removed.
- **[43]** `pkg/remote/fileshare/pathtree/pathtree.go:81`（wavetermdev__waveterm）— 同 42（同一条日志的另一处）
    - 参考：Debug log should be removed.
- **[44]** `pkg/remote/fileshare/s3fs/s3fs.go:210`（wavetermdev__waveterm）— 我们 s3fs.go:724 报了同一类 per-object 日志
    - 参考：Debug log statements using `log.Printf` appear to be left in the code. Please remove them before merging.
- **[45]** `pkg/remote/fileshare/s3fs/s3fs.go:299`（wavetermdev__waveterm）— 同 44
    - 参考：Debug log statement.
- **[46]** `pkg/remote/fileshare/s3fs/s3fs.go:703`（wavetermdev__waveterm）— 同 44
    - 参考：Debug log statement. There are multiple `log.Printf` calls in this function that should be removed.
- **[68]** `cmd/wsh/cmd/wshcmd-root.go:156`（wavetermdev__waveterm）— 我们 wshproxy.go:144 报了同一类「token 明文进日志」
    - 参考：Sensitive authentication token is logged in plain text. Replace the log statement to omit the token value and prevent credential exposure.
- **[69]** `pkg/blockcontroller/blockcontroller.go:365`（wavetermdev__waveterm）— 同 68
    - 参考：Logging swap token value in plaintext exposes sensitive information; remove the token value from the debug log statement to prevent potential leakage.
- **[71]** `pkg/shellexec/shellexec.go:323`（wavetermdev__waveterm）— 同 68
    - 参考：Sensitive token value (SwapToken.Token) is logged in plain text, risking credential exposure; the log statement must redact the token value.
- **[72]** `pkg/shellexec/shellexec.go:324`（wavetermdev__waveterm）— 我们 tokenswap.go:85 / shellexec.go:258 都报了 nil 检查
    - 参考：Potential nil pointer dereference: cmdOpts.SwapToken could be nil. Add a nil check before accessing SwapToken.Token to prevent panic.
- **[73]** `pkg/shellexec/shellexec.go:483`（wavetermdev__waveterm）— 同 68
    - 参考：The swap token is logged in plaintext in debug output, risking exposure of sensitive information. Replace the token value with a redacted placeholder 
- **[81]** `kvcache/encoder.go:94`（ollama__ollama）— 我们 causal.go:203 报了同一根因（Positions.Ints() 可能为空）
    - 参考：Potential panic/semantic change: switching to `batch.Positions.Ints()[...]` assumes `Ints()` returns a non-nil slice with at least the required length
- **[90]** `pkg/gofr/handler.go:86`（gofr-dev__gofr）— 我们 handler.go:71 报了同一处（替换共享 logger 的竞态）
    - 参考：Due to the race condition mentioned above, accessing `h.container.Logger` here is unsafe and incorrect. It should use the local `ctxLogger` instance c
- **[92]** `internal/execute/watcher.go:83`（microsoft__typescript-go）— 我们 watch.go:45 报了同一类（Fprint→Fprintln 多空格），只是没查另一个文件
    - 参考：The change to `fmt.Fprintln` introduces unintended spaces between arguments in the log message due to automatic space insertion. Replace with `fmt.Fpr

## A3 · 六维度之外：可维护性与设计意图（24 条）

- **[05]** `internal/checker/checker.go:10844`（microsoft__typescript-go）— 复用仓库已有的工具函数
    - 参考：The manual loop for validating ASCII letters in HTML element names should be replaced with the existing `stringutil.IsASCIILetter` utility function fo
- **[09]** `server/internal/chunks/chunks.go:37`（ollama__ollama）— 格式串显式性（可维护性）
    - 参考：fmt %q expects a string; here `s` is a type parameter (string or []byte). While it will likely work via interface formatting, it can produce confusing
- **[10]** `server/internal/chunks/chunks.go:41`（ollama__ollama）— 错误文案措辞
    - 参考：Error messages use "invalid start to %q" / "invalid end to %q" which reads like a typo (likely meant "in" or "for"). Consider rephrasing for clarity a
- **[15]** `server/internal/registry/server.go:199`（ollama__ollama）— 注释语法错误
    - 参考：Grammar error in comment: 'if the client decisively it to false' should be 'if the client decisively set it to false' or 'if the client decided to set
- **[25]** `internal/transformers/commonjsmodule.go:66`（microsoft__typescript-go）— 这个 AST 节点该在哪个 pass 处理（分层）
    - 参考：CommonJSModuleTransformer should not handle `JSImportDeclaration` directly; this node kind should be normalized by earlier passes (e.g., type eraser o
- **[26]** `internal/transformers/esmodule.go:43`（microsoft__typescript-go）— 同 25
    - 参考：The `JSImportDeclaration` node should not be set to nil in this transformer; it must be processed during an earlier transformation phase instead.
- **[27]** `internal/transformers/esnext.go:371`（microsoft__typescript-go）— 同 25
    - 参考：The addition of `KindJSImportDeclaration` to the `transformUsingDeclarations` switch case is misplaced; this node type should be processed in an earli
- **[28]** `internal/transformers/externalmoduleinfo.go:50`（microsoft__typescript-go）— 同 25
    - 参考：The change to include `ast.KindJSImportDeclaration` in the import handling switch case is invalid because type-only imports are elided during compilat
- **[30]** `internal/transformers/importelision.go:31`（microsoft__typescript-go）— 同 25
    - 参考：The addition of `ast.KindJSImportDeclaration` to the import case statement is incorrect because `JSImportDeclaration` nodes should have been processed
- **[31]** `internal/transformers/importelision.go:169`（microsoft__typescript-go）— 同 25
    - 参考：Adding ast.KindJSImportDeclaration to the switch case is redundant because typeeraser.go is designed to handle JSImportDeclaration nodes.
- **[32]** `internal/transformers/typeeraser.go:258`（microsoft__typescript-go）— 同 25
    - 参考：ast.KindJSImportDeclaration should be handled in a separate case to elide the node, not grouped with ast.KindImportDeclaration which requires differen
- **[33]** `envconfig/config.go:171`（ollama__ollama）— 校验该放在哪一层（配置层 vs 消费方）
    - 参考：The context length validation (`CheckContextLength`) should be moved from the configuration package to the consumer layer (scheduler/llm) to enforce b
- **[35]** `server/create.go:161`（ollama__ollama）— 重复实现 stdlib（io/fs.ValidPath）
    - 参考：The newly added `validRelative` function duplicates standard library functionality; replace it with `io/fs.ValidPath` for correctness and simplicity.
- **[40]** `pkg/gofr/testutil/port.go:51`（gofr-dev__gofr）— 同一 API 返回多种格式（host:port vs URL）
    - 参考：Hosts are returned in mixed formats: HTTP/Metrics include scheme (`http://...`) while gRPC returns `host:port` without scheme. This inconsistency can 
- **[52]** `pkg/gofr/datasource/pubsub/nats/client.go:75`（gofr-dev__gofr）— 重复代码
    - 参考：Code duplication between Connect and retryConnect methods; retryConnect duplicates server logging and connection manager initialization logic from Con
- **[57]** `core/http/endpoints/openai/chat.go:174`（mudler__LocalAI）— header 设了两遍
    - 参考：**Issue: Header set multiple times** The `LocalAI-Machine-Tag` header is set here at line 174, and then again at line 330 for streaming responses. Thi
- **[61]** `core/http/endpoints/openai/files.go:86`（mudler__LocalAI）— 该收进中间件
    - 参考：The 'LocalAI-Machine-Tag' header is being set directly in the ListFilesEndpoint instead of a shared middleware, risking inconsistent application acros
- **[67]** `cmd/wsh/cmd/wshcmd-connserver.go:234`（wavetermdev__waveterm）— 常量来源不统一
    - 参考：Inconsistent constant usage: Most of the codebase uses wshutil.WaveJwtTokenVarName, but this new code uses wavebase.WaveJwtTokenVarName directly. Whil
- **[76]** `pkg/util/shellutil/tokenswap.go:16`（wavetermdev__waveterm）— 惯用法：Mutex 用值不用指针
    - 参考：Idiomatic Go prefers declaring Mutex as a value rather than a pointer. You can use `var tokenMapLock sync.Mutex`. Also, `tokenSwapMap` can be initiali
- **[86]** `model/input/input.go:61`（ollama__ollama）— 拼写
    - 参考：The word 'indicies' is misspelled. It should be 'indices'. ```suggestion // Outputs are the set of indices into Inputs for which output data should //
- **[88]** `cmd/cmd.go:127`（ollama__ollama）— 已知数量，不必用 mutex+map（简化）
    - 参考：The current mutex-protected map implementation for concurrent file processing is unnecessarily complex; replace it with a pre-allocated slice since th
- **[93]** `pkg/gofr/datasource/mongo/mongo.go:46`（gofr-dev__gofr）— 产品名措辞
    - 参考：The `errIncorrectURI` error message should use "MongoDB" instead of "mongo" for consistency with the official product name.
- **[94]** `pkg/gofr/datasource/mongo/mongo.go:94`（gofr-dev__gofr）— 同 93
    - 参考：The error log message for MongoDB URI generation uses the abbreviated term "mongo" instead of the official product name "MongoDB". Update the string t
- **[95]** `pkg/gofr/datasource/mongo/mongo.go:116`（gofr-dev__gofr）— 同 93
    - 参考：The error log message uses inconsistent capitalization "mongoDB" instead of the standard "MongoDB" product name. Update the log string to use correct 

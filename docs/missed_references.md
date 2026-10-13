# 未命中的参考评论清单（可逐条读、可打标签）

数据：`prism-gofr` 的 `20261009_135923` 那一局。**每条参考一个问题：那个位置，我们有没有机会看到？**

| 桶 | 含义 | 条数 |
|---|---|---|
| (c) | 行号命中了但裁判判为「不是同一件事」 | 5 |
| (a) | 位置落在我们审过的 hunk 里，附近一条评论都没有 | 9 |
| (b) | 位置不在我们审过的任何 hunk 里 | 0 |
| (d) | 结构上不可达（非 `.go` / 测试文件） | 4 |

**怎么用**：把 `⬜` 改成 `✅`，觉得分错桶就直接改括号里的字母。
判 (a)/(b) 的判据是**确定算出来的**（参考行落没落在我们审过的 hunk 区间里），
所以 (b) 基本不用怀疑。

> ⚠️ **(a) 里必然混着一批其实属于 (c) 的**：判桶只看「参考行在不在我们审过的 hunk 里」，
> 分不出「同一件事说在别的行」。下面这个例子就是 —— 参考在 `config.go:14`、
> 我们说的是同一件事、但写在 `:36`：
>
> - 参考：`LogDisableProbes` 该用 bool 而不是 string
> - 我们（第 36 行）：`LogDisableProbes` 用 `GetOrDefault(..., "false")` 取值后
>   与 `== "true"` 严格比较，`TRUE`/`True` 会被判为关闭 —— **同一个问题**
>
> 所以读 (a) 时先扫一眼「同一个文件里的评论」，像上面那种直接改成 (c)。

## (c) 的 16 条（先从这一桶看：话已经说了，差的是角度）

- `gofr-dev__gofr@c1a26ad` `pkg/gofr/http/middleware/config.go:36` — There is a potential naming logic issue here. The config key `LOG_DISABLE_PROBES` defaul
- `gofr-dev__gofr@c1a26ad` `pkg/gofr/http_server.go:42` — The middleware order has been changed such that `Logging` is now applied after `CORS` an
- `gofr-dev__gofr@b9cdcbb` `pkg/gofr/http/responder.go:31` — The `resTypes.Response` type has a `Headers` field and a `SetCustomHeaders()` method to 
- `gofr-dev__gofr@49ab394` `pkg/gofr/datasource/pubsub/nats/client.go:83` — Serious logic issue: When `jetStream()` fails, `c.connManager` is already set to the new
- `gofr-dev__gofr@5e284ae` `pkg/gofr/logging/logger.go:254` — Potential logic issue: this extracts trace IDs only when the arg is exactly of type `map

## gofr-dev__gofr@c1a26ad（2 条未命中：c 2）

### ⬜ (c) `pkg/gofr/http/middleware/config.go:36-36`（right）

- **为什么在这个桶**：行号命中了，但裁判判为「不是同一件事」
- **参考原文**：There is a potential naming logic issue here. The config key `LOG_DISABLE_PROBES` defaults to `false`, and when set to `true`, it applies `LoggingWithoutProbes` middleware which skips logging for health check endpoints. The naming `LOG_DISABLE_PROBES` is confusing because it implies disabling the probe endpoints themselves, not just skipping logging for them. Consider renaming to `LOG_SKIP_PROBES` or `EXCLUDE_PROBES_FROM_LOGS` for clarity.
- **我们在同一个文件里的评论（2 条）**：
    - `14` 新增的 `LogDisableProbes` 用 `string` 而不是 `bool` 承载一个开关语义，把「字符串→布尔」的解析责任丢给了每一个消费点（当前唯一消费点 http_server.go:42 直接用 `== "true"` 比较字面量）。结果是配置大小写、空白、`"1"`/`"TRUE"` 等写法都会静默地按「不关闭」处理，而且以后每加一个消费点就要再抄一遍这个字面量比较。建议在本结构体里就用 `bool`（在 GetConfigs 中解析一次），或至少封装一个方法。
    - `36` 这里只是把原始字符串取出来，没有做布尔解析：`LOG_DISABLE_PROBES=TRUE`、`LOG_DISABLE_PROBES=1`（以及带首尾空格的值）都会在下游 `== "true"` 处被判为 false，功能静默不生效。仓库内同类配置（container.go:192 的 `MQTT_MESSAGE_ORDER`）用的是 `strconv.ParseBool`，此处用法与之不一致。建议在此处用 `strconv.ParseBool` 并忽略/记录错误，把结果存成 bool。

### ⬜ (c) `pkg/gofr/http_server.go:42-46`（right）

- **为什么在这个桶**：行号命中了，但裁判判为「不是同一件事」
- **参考原文**：The middleware order has been changed such that `Logging` is now applied after `CORS` and `Metrics`. This means that if the `CORS` middleware handles a request (e.g., OPTIONS preflight) or rejects it (e.g., invalid origin), the `Logging` middleware will not be executed, and these events will not be logged. It is recommended to register the `Logging` middleware before `CORS` and `Metrics` to ensure all requests are logged, including those terminated by subsequent middleware.
- **我们在同一个文件里的评论（2 条）**：
    - `38` 把 Logging 从这条 Use 列表移出、改到 CORS 之后（http_server.go:42-46），顺带改变了中间件嵌套顺序：以前 Logging 是最外层，CORS 对 OPTIONS 预检请求 `w.WriteHeader(200); return` 的短路响应也会被 Logging 记录；现在 Logging 在 CORS 内层，预检请求不再产生任何请求日志。如果这是有意减少噪音，建议在注释或文档里写明；如果不是，需要显式处理 OPTIONS 的日志。
    - `42` 这里用裸字面量 `"true"` 与配置字符串比较，把「配置值的合法写法」这一约定复制到了消费点：配置为 `TRUE`、`True`、`1` 或带空格时，用户以为已关闭探针日志，实际仍在记录，且没有任何报错或提示。配合 `MiddlewareConfig.LogDisableProbes` 为 string 的设计，建议改由 GetConfigs 用 strconv.ParseBool 解析一次、这里直接判断 bool。


## gofr-dev__gofr@b9cdcbb（2 条未命中：c 1 / a 1）

### ⬜ (c) `pkg/gofr/http/responder.go:31-32`（right）

- **为什么在这个桶**：行号命中了，但裁判判为「不是同一件事」
- **参考原文**：The `resTypes.Response` type has a `Headers` field and a `SetCustomHeaders()` method to apply custom HTTP response headers. However, this code doesn't call `v.SetCustomHeaders(r.w)`, which means any custom headers specified in the `Response` object will be ignored. You should add `v.SetCustomHeaders(r.w)` before setting the Content-Type header to ensure custom headers are properly applied.
- **我们在同一个文件里的评论（2 条）**：
    - `97` `Metadata interface{} `json:"metadata,omitempty"`` 的 omitempty 在这里完全不起作用：调用点（responder.go:32）传入的是 `v.Metadata`，即一个 `map[string]any`；即使它是 nil map，装进 `interface{}` 字段后接口本身也非 nil，`omitempty` 不会省略，序列化结果为 `"metadata":null`（responder_test.go:59 的期望正是这个）。于是所有走 `respo
    - `32` 新增的 `case resTypes.Response` 分支没有像 `default` 分支那样做 `isNil` 归一化（responder.go:41-44）。当 `v.Data` 是「带类型的 nil」（如 `response.Response{Data: (*T)(nil)}`）时，该值被直接放进 `response.Data`，`omitempty` 因接口非空而不生效，响应体从原来的 `{}`（字段被省略）变成 `"data":null`；doc 里承诺的「无数据时只保留必要字段」不再成立。建议在赋值

### ⬜ (a) `pkg/gofr/http/responder.go:31-32`（right）

- **为什么在这个桶**：落在我们审过的 H-02 里
- **参考原文**：Potential inconsistency in metadata handling. When v.Metadata is nil, this will result in omitting the metadata field due to json:"metadata,omitempty" in the response struct. However, tests expect "metadata":null when metadata is not provided. Consider initializing Metadata appropriately to match expected behavior.
- **我们在同一个文件里的评论（2 条）**：
    - `97` `Metadata interface{} `json:"metadata,omitempty"`` 的 omitempty 在这里完全不起作用：调用点（responder.go:32）传入的是 `v.Metadata`，即一个 `map[string]any`；即使它是 nil map，装进 `interface{}` 字段后接口本身也非 nil，`omitempty` 不会省略，序列化结果为 `"metadata":null`（responder_test.go:59 的期望正是这个）。于是所有走 `respo
    - `32` 新增的 `case resTypes.Response` 分支没有像 `default` 分支那样做 `isNil` 归一化（responder.go:41-44）。当 `v.Data` 是「带类型的 nil」（如 `response.Response{Data: (*T)(nil)}`）时，该值被直接放进 `response.Data`，`omitempty` 因接口非空而不生效，响应体从原来的 `{}`（字段被省略）变成 `"data":null`；doc 里承诺的「无数据时只保留必要字段」不再成立。建议在赋值


## gofr-dev__gofr@2c0c099（6 条未命中：a 2 / d 4）

### ⬜ (a) `pkg/gofr/testutil/port.go:37-40`（right）

- **为什么在这个桶**：落在我们审过的 H-04 里
- **参考原文**：The documentation comment refers to `ServerConfigsProvider`, but the function name is `NewServerConfigs`. Please correct the comment to match the function name. Additionally, there is a naming inconsistency between the function `NewServerConfigs` (Server) and the return type `ServiceConfigs` (Service). Consider renaming for consistency (e.g., `NewServiceConfigs`).
- **我们在同一个文件里的评论（2 条）**：
    - `37` 导出函数 NewServerConfigs 的文档注释以 “ServerConfigsProvider” 开头，与被注释的符号名不一致。golint/revive（本项目 CI 常见的 lint）会报 “comment on exported function NewServerConfigs should be of the form "NewServerConfigs ..."”；同时注释里承诺的 “Provider” 这个类型/角色在代码中也不存在，读者容易误以为有个叫 ServerConfigsProvid
    - `56` 同名字段语义不一致：HTTPHost / MetricsHost 带 “http://” scheme，而 GRPCHost 只有 “host:port”。字段都叫 Host，调用方却要按不同规则拼接（examples/grpc/grpc-server/main_test.go 直接把 GRPCHost 当 grpc.Dial 的目标使用，而 examples/http-server/main_test.go 是 HTTPHost+path）。这层不统一很容易让后续使用者把 GRPCHost 当成带 scheme 

### ⬜ (a) `pkg/gofr/testutil/port.go:43-45`（right）

- **为什么在这个桶**：落在我们审过的 H-04 里
- **参考原文**：`GetFreePort` is called three times independently; between calls another process/test can claim a previously-found free port, leading to flaky tests when a service actually binds later. If you need stability, consider reserving ports by keeping listeners open until the servers start (or allocate via `net.Listen("tcp", "127.0.0.1:0")` and return the listener/address to the caller).
- **我们在同一个文件里的评论（2 条）**：
    - `37` 导出函数 NewServerConfigs 的文档注释以 “ServerConfigsProvider” 开头，与被注释的符号名不一致。golint/revive（本项目 CI 常见的 lint）会报 “comment on exported function NewServerConfigs should be of the form "NewServerConfigs ..."”；同时注释里承诺的 “Provider” 这个类型/角色在代码中也不存在，读者容易误以为有个叫 ServerConfigsProvid
    - `56` 同名字段语义不一致：HTTPHost / MetricsHost 带 “http://” scheme，而 GRPCHost 只有 “host:port”。字段都叫 Host，调用方却要按不同规则拼接（examples/grpc/grpc-server/main_test.go 直接把 GRPCHost 当 grpc.Dial 的目标使用，而 examples/http-server/main_test.go 是 HTTPHost+path）。这层不统一很容易让后续使用者把 GRPCHost 当成带 scheme 

### ⬜ (d) `go.mod:3-5`（right）

- **为什么在这个桶**：非 .go 或在测试文件上 —— V1 结构上不可达
- **参考原文**：Using toolchain go1.23.4 with go 1.22.7 is technically supported, but this is an unusual configuration. Using a toolchain from a newer minor version (1.23.x) with an older Go version (1.22.x) may lead to unexpected behavior or compatibility issues. Consider either: 1. Using toolchain go1.22.x (matching the Go version) 2. Or upgrading the Go version to 1.23.x to match the toolchain This mismatch can cause issues with: - Standard library behavior differences - Compiler optimizations that may not be tested with the older Go version - Potential breaking changes in toolchain behavior ```suggestion go 1.23.4 toolchain go1.23.4 ```
- **我们在同一个文件里的评论**：一条都没有

### ⬜ (d) `pkg/gofr/datasource/file/ftp/go.mod:3-5`（right）

- **为什么在这个桶**：非 .go 或在测试文件上 —— V1 结构上不可达
- **参考原文**：Adding `toolchain go1.23.4` makes builds use Go 1.23 when available, which can be surprising if the repo (or other submodules) targets Go 1.22.x. Please confirm this is intended and consistent across all datasource submodules; otherwise consider omitting `toolchain` or aligning it with the repo’s chosen toolchain version. Also note: `go 1.22.7` is fine, but the `go` directive usually tracks the minimum language version, not patch level; many projects use `go 1.22` to avoid unnecessary churn across patch updates. Align with the root `go.mod` convention if one exists.
- **我们在同一个文件里的评论**：一条都没有

### ⬜ (d) `pkg/gofr/datasource/file/s3/go.mod:3-3`（right）

- **为什么在这个桶**：非 .go 或在测试文件上 —— V1 结构上不可达
- **参考原文**：Bumping the `go` directive from 1.22.4 to 1.22.7 can change module semantics/tool behavior (e.g., minimal version selection details, stdlib changes) and may require CI/build image updates. Please ensure the root module and all submodules are aligned on the intended Go minor/patch level, and that this version is available in all supported environments.
- **我们在同一个文件里的评论**：一条都没有

### ⬜ (d) `pkg/gofr/datasource/file/s3/go.mod:5-5`（right）

- **为什么在这个桶**：非 .go 或在测试文件上 —— V1 结构上不可达
- **参考原文**：Adding a `toolchain` directive forces/requests a specific Go toolchain (here 1.23.4). This can break consumers or CI that build with older Go versions or without toolchain auto-download enabled, especially for a nested submodule. Confirm this repository intends to require Go 1.23.4 to build/test, and consider aligning toolchain directives across modules (root + all submodules) or omitting it if you only want to declare minimum language version via `go`.
- **我们在同一个文件里的评论**：一条都没有


## gofr-dev__gofr@49ab394（3 条未命中：c 1 / a 2）

### ⬜ (c) `pkg/gofr/datasource/pubsub/nats/client.go:83-91`（right）

- **为什么在这个桶**：行号命中了，但裁判判为「不是同一件事」
- **参考原文**：Serious logic issue: When `jetStream()` fails, `c.connManager` is already set to the new connection manager, but the code sleeps and continues the loop without resetting it. This causes `checkClient()` to return nil error (since `c.connManager` is not nil and `isConnected()` returns true), even though the connection is not fully functional. The client state becomes inconsistent - it has a connection manager without a valid JetStream context. You should either set `c.connManager` only after all initialization succeeds, or reset it to nil/previous state when JetStream creation fails. ```suggestion js, err := connManager.jetStream() if err != nil { time.Sleep(defaultRetryTimeout) c.logger.Debugf("Failed to create jStream context: %v", err) continue } c.connManager = connManager c.streamManager = newStreamManager(js, c.logger) c.subManager = newSubscriptionManager(batchSize) c.logSuccessfulConnection() break ```
- **我们在同一个文件里的评论（7 条）**：
    - `83` 新加的 `Client.retryConnect` 在后台 goroutine 里直接写 `c.connManager` / `c.streamManager` / `c.subManager` 三个 Client 字段，而用户侧调用（`Publish`、`Subscribe`、`SubscribeWithHandler`、`CreateTopic` 等）会在其它 goroutine 上并发读这些字段，没有任何同步（`Client` 只有 `subMutex` 保护 `subscriptions`，这三个字段无锁）
    - `52` 该 goroutine 是一个永不退出的 `for` 循环（只有连接成功才 `break`），且 `Client.Close` 不会取消它。每次 `Client.Connect` 失败都会再 `go c.retryConnect()` 起一个；在重试期间 NATS 持续不可达时，每个循环还会新建一个 ConnectionManager/连接并（js 创建失败时）close。建议用 `sync.Once` 保证只启动一个重连 goroutine，并提供一个 done channel 在 `Close` 时退出循环。
    - `358` 新增 `checkClient` 只被 `Publish`/`Subscribe`/`CreateTopic`/`DeleteTopic`/`CreateStream`/`DeleteStream`/`CreateOrUpdateStream` 使用，但同一个 Client 上的 `SubscribeWithHandler`（client.go:178 `js, err := c.connManager.jetStream()`）仍然直接解引用 `c.connManager`。改动后 `Client.Connect
    - `358` `checkClient` 无锁读取 `c.connManager`，而新增的后台 `Client.retryConnect`（client.go:83）在另一 goroutine 中写 `c.connManager`，两者之间没有任何同步。`checkClient` 又被 `Publish`/`Subscribe`/`CreateTopic` 等对外接口调用，因此启动阶段会出现真实的 data race（`-race` 会告警），最坏情况下读到被写了一半的接口值。建议给 `Client` 的这几个字段加 `syn

### ⬜ (a) `pkg/gofr/datasource/pubsub/nats/client.go:75-75`（right）

- **为什么在这个桶**：落在我们审过的 H-04 里
- **参考原文**：Code duplication between Connect and retryConnect methods; retryConnect duplicates server logging and connection manager initialization logic from Connect.
- **我们在同一个文件里的评论（7 条）**：
    - `83` 新加的 `Client.retryConnect` 在后台 goroutine 里直接写 `c.connManager` / `c.streamManager` / `c.subManager` 三个 Client 字段，而用户侧调用（`Publish`、`Subscribe`、`SubscribeWithHandler`、`CreateTopic` 等）会在其它 goroutine 上并发读这些字段，没有任何同步（`Client` 只有 `subMutex` 保护 `subscriptions`，这三个字段无锁）
    - `52` 该 goroutine 是一个永不退出的 `for` 循环（只有连接成功才 `break`），且 `Client.Close` 不会取消它。每次 `Client.Connect` 失败都会再 `go c.retryConnect()` 起一个；在重试期间 NATS 持续不可达时，每个循环还会新建一个 ConnectionManager/连接并（js 创建失败时）close。建议用 `sync.Once` 保证只启动一个重连 goroutine，并提供一个 done channel 在 `Close` 时退出循环。
    - `358` 新增 `checkClient` 只被 `Publish`/`Subscribe`/`CreateTopic`/`DeleteTopic`/`CreateStream`/`DeleteStream`/`CreateOrUpdateStream` 使用，但同一个 Client 上的 `SubscribeWithHandler`（client.go:178 `js, err := c.connManager.jetStream()`）仍然直接解引用 `c.connManager`。改动后 `Client.Connect
    - `358` `checkClient` 无锁读取 `c.connManager`，而新增的后台 `Client.retryConnect`（client.go:83）在另一 goroutine 中写 `c.connManager`，两者之间没有任何同步。`checkClient` 又被 `Publish`/`Subscribe`/`CreateTopic` 等对外接口调用，因此启动阶段会出现真实的 data race（`-race` 会告警），最坏情况下读到被写了一半的接口值。建议给 `Client` 的这几个字段加 `syn

### ⬜ (a) `pkg/gofr/datasource/pubsub/nats/client.go:150-154`（right）

- **为什么在这个桶**：落在我们审过的 H-06 里
- **参考原文**：Serious logical issue: The Subscribe method calls checkClient() but ignores its actual error and always returns errClientNotConnected. This prevents proper error handling and debugging. Also, it sleeps and returns error without actually retrying the subscription.
- **我们在同一个文件里的评论（7 条）**：
    - `83` 新加的 `Client.retryConnect` 在后台 goroutine 里直接写 `c.connManager` / `c.streamManager` / `c.subManager` 三个 Client 字段，而用户侧调用（`Publish`、`Subscribe`、`SubscribeWithHandler`、`CreateTopic` 等）会在其它 goroutine 上并发读这些字段，没有任何同步（`Client` 只有 `subMutex` 保护 `subscriptions`，这三个字段无锁）
    - `52` 该 goroutine 是一个永不退出的 `for` 循环（只有连接成功才 `break`），且 `Client.Close` 不会取消它。每次 `Client.Connect` 失败都会再 `go c.retryConnect()` 起一个；在重试期间 NATS 持续不可达时，每个循环还会新建一个 ConnectionManager/连接并（js 创建失败时）close。建议用 `sync.Once` 保证只启动一个重连 goroutine，并提供一个 done channel 在 `Close` 时退出循环。
    - `358` 新增 `checkClient` 只被 `Publish`/`Subscribe`/`CreateTopic`/`DeleteTopic`/`CreateStream`/`DeleteStream`/`CreateOrUpdateStream` 使用，但同一个 Client 上的 `SubscribeWithHandler`（client.go:178 `js, err := c.connManager.jetStream()`）仍然直接解引用 `c.connManager`。改动后 `Client.Connect
    - `358` `checkClient` 无锁读取 `c.connManager`，而新增的后台 `Client.retryConnect`（client.go:83）在另一 goroutine 中写 `c.connManager`，两者之间没有任何同步。`checkClient` 又被 `Publish`/`Subscribe`/`CreateTopic` 等对外接口调用，因此启动阶段会出现真实的 data race（`-race` 会告警），最坏情况下读到被写了一半的接口值。建议给 `Client` 的这几个字段加 `syn


## gofr-dev__gofr@5e284ae（2 条未命中：c 1 / a 1）

### ⬜ (c) `pkg/gofr/logging/logger.go:254-264`（right）

- **为什么在这个桶**：行号命中了，但裁判判为「不是同一件事」
- **参考原文**：Potential logic issue: this extracts trace IDs only when the arg is exactly of type `map[string]any`. If callers pass `map[string]string`, `map[string]interface{}` (pre-1.18 aliasing), or a typed map, the type assertion will fail and trace_id will never be set. Consider supporting more map types or a small struct/key-value wrapper, or using reflection to read the `__trace_id__` key safely. Also note: if multiple args include `__trace_id__`, later ones are kept in output (since only the first is filtered). If the intent is to remove all trace metadata, filter all such maps after first extraction.
- **我们在同一个文件里的评论（1 条）**：
    - `255` 过滤使用的是保留 key `__trace_id__`，如果用户在业务日志里打印一个恰好含该 key 的 map，这个 map 会被整个丢弃（既不会进 message 也不会出现在输出里），属于静默吞掉用户数据。建议至少在文档/注释里声明该保留 key，或改用带类型的包装（如自定义类型 `traceFlag string`）避免与用户数据碰撞。

### ⬜ (a) `pkg/gofr/logging/ctx_logger.go:37-37`（right）

- **为什么在这个桶**：落在我们审过的 H-21 里
- **参考原文**：**Incorrect Trace Info Injection for Formatted Logging Functions** The formatted logging methods (Debugf, Logf, Infof, Noticef, Warnf, Errorf, Fatalf) are incorrectly calling `withTraceInfo(args...)` which appends a trace ID map to the variadic arguments. **Problem:** Format strings expect a specific number of arguments. Adding an extra map argument will cause format string mismatches and incorrect output. For example: ```go logger.Infof("User %s logged in", "john") // becomes: fmt.Sprintf("User %s logged in", "john", map[string]any{"__trace_id__": "..."}) // This produces: "User john logged in%!(EXTRA map[string]interface {}={...})" ``` **Suggested Fix:** The trace ID should be injected differently for formatted vs non-formatted logging. Either: 1. Modify the base logger's formatted functions to handle trace metadata separately, OR 2. Don't inject trace info for formatted logging functions (only for non-formatted ones) ``` Fix pkg/gofr/logging/ctx_logger.go:37-52: Remove trace info injection from formatted logging functions (lines 37, 39, 41, 43-45, 48, 50, 52). The withTraceInfo method appends a map to args, which breaks format string expectations. Only non-formatted logging functions (Debug, Log, Info, Notice, Warn, Error, Fatal) should call withTraceInfo. ```
- **我们在同一个文件里的评论（2 条）**：
    - `31` trace ID 是通过往参数末尾追加一个仅被内部 `*logger`（`extractTraceIDAndFilterArgs`）认识的魔法 key `"__trace_id__"` 来传递的。ContextLogger 包装的是接口 `Logger`，只要 base 换成其它实现（外部自定义 logger、mock、或者未来的另一套 logging 实现），这个 map 就会原样进入输出：非 *f 方法会打印出整个 map，*f 方法会被 fmt 当作多余参数追加成 `%!(EXTRA map[string]i
    - `31` `append(args, ...)` 直接对调用方传入的变参切片做追加：当调用方以 `logger.Debug(slice...)` 方式传入且 slice 还有剩余容量时，这会写入调用方底层数组的 len 位置，污染调用方的数据（若其之后 append 同一 slice，会看到被塞入的 trace map）。建议先拷贝再追加，例如 `out := make([]any, 0, len(args)+1); out = append(out, args...); return append(out, m)`。


## gofr-dev__gofr@dc0b3e6（3 条未命中：a 3）

### ⬜ (a) `pkg/gofr/datasource/mongo/mongo.go:46-46`（right）

- **为什么在这个桶**：落在我们审过的 H-02 里
- **参考原文**：The `errIncorrectURI` error message should use "MongoDB" instead of "mongo" for consistency with the official product name.
- **我们在同一个文件里的评论（5 条）**：
    - `156` 凭据被双重转义：url.UserPassword 内部会对 username/password 再做一次 userinfo 转义（encodeUserPassword），这里先 url.QueryEscape 一次，`%` 会被再转义成 `%25`。例如密码 `p@ss` → QueryEscape 得 `p%40ss` → String() 得 `p%2540ss`，MongoDB 解析出来是字面的 `p%40ss`，与真实密码不符，连接直接认证失败；含 `@ : / ? # ! $ & +` 或空格的密码都会中
    - `172` 新增的 scheme 校验只接受 `mongodb`，会拒掉 MongoDB 官方的 `mongodb+srv://`（Atlas 的标准连接串，也是驱动 options.ApplyURI 本来就支持的格式）。旧实现把 config.URI 原样交给驱动，这类 URI 可以正常连接；改动后 generateMongoURI 返回 errIncorrectURI，Connect 只打一条 Errorf 就 return（函数无返回值，调用方无从感知），原本可用的部署会直接连不上。建议同时接受 `mongodb+srv
    - `152` 路径被双重转义：url.URL.Path 应该存未转义的路径，String()/EscapedPath() 会自己按 encodePath 规则转义。这里先 url.PathEscape 再交给 Path，`%` 会被二次转义：数据库名 `my db` → PathEscape 得 `my%20db` → 最终 URI 变成 `/my%2520db`，驱动会把数据库名解析成 `my%20db`，与实际库名不符。修复：直接赋值未转义的库名，让 url 包自行转义。
    - `98` 这条 Debugf 打印的是 c.config.Host，而同一函数后半段（Ping 失败日志、成功日志）都改成了新拿到的 host 变量。当用户走「直接给 URI」这条路时（Config.URI 非空、Host 为空），这里会打印出空主机名，日志定位不到实际连的是哪个节点。建议统一用 host。

### ⬜ (a) `pkg/gofr/datasource/mongo/mongo.go:94-94`（right）

- **为什么在这个桶**：落在我们审过的 H-03 里
- **参考原文**：The error log message for MongoDB URI generation uses the abbreviated term "mongo" instead of the official product name "MongoDB". Update the string to "error generating MongoDB URI: %v" for naming consistency.
- **我们在同一个文件里的评论（5 条）**：
    - `156` 凭据被双重转义：url.UserPassword 内部会对 username/password 再做一次 userinfo 转义（encodeUserPassword），这里先 url.QueryEscape 一次，`%` 会被再转义成 `%25`。例如密码 `p@ss` → QueryEscape 得 `p%40ss` → String() 得 `p%2540ss`，MongoDB 解析出来是字面的 `p%40ss`，与真实密码不符，连接直接认证失败；含 `@ : / ? # ! $ & +` 或空格的密码都会中
    - `172` 新增的 scheme 校验只接受 `mongodb`，会拒掉 MongoDB 官方的 `mongodb+srv://`（Atlas 的标准连接串，也是驱动 options.ApplyURI 本来就支持的格式）。旧实现把 config.URI 原样交给驱动，这类 URI 可以正常连接；改动后 generateMongoURI 返回 errIncorrectURI，Connect 只打一条 Errorf 就 return（函数无返回值，调用方无从感知），原本可用的部署会直接连不上。建议同时接受 `mongodb+srv
    - `152` 路径被双重转义：url.URL.Path 应该存未转义的路径，String()/EscapedPath() 会自己按 encodePath 规则转义。这里先 url.PathEscape 再交给 Path，`%` 会被二次转义：数据库名 `my db` → PathEscape 得 `my%20db` → 最终 URI 变成 `/my%2520db`，驱动会把数据库名解析成 `my%20db`，与实际库名不符。修复：直接赋值未转义的库名，让 url 包自行转义。
    - `98` 这条 Debugf 打印的是 c.config.Host，而同一函数后半段（Ping 失败日志、成功日志）都改成了新拿到的 host 变量。当用户走「直接给 URI」这条路时（Config.URI 非空、Host 为空），这里会打印出空主机名，日志定位不到实际连的是哪个节点。建议统一用 host。

### ⬜ (a) `pkg/gofr/datasource/mongo/mongo.go:116-116`（right）

- **为什么在这个桶**：落在我们审过的 H-05 里
- **参考原文**：The error log message uses inconsistent capitalization "mongoDB" instead of the standard "MongoDB" product name. Update the log string to use correct "MongoDB" capitalization for consistency and professionalism.
- **我们在同一个文件里的评论（5 条）**：
    - `156` 凭据被双重转义：url.UserPassword 内部会对 username/password 再做一次 userinfo 转义（encodeUserPassword），这里先 url.QueryEscape 一次，`%` 会被再转义成 `%25`。例如密码 `p@ss` → QueryEscape 得 `p%40ss` → String() 得 `p%2540ss`，MongoDB 解析出来是字面的 `p%40ss`，与真实密码不符，连接直接认证失败；含 `@ : / ? # ! $ & +` 或空格的密码都会中
    - `172` 新增的 scheme 校验只接受 `mongodb`，会拒掉 MongoDB 官方的 `mongodb+srv://`（Atlas 的标准连接串，也是驱动 options.ApplyURI 本来就支持的格式）。旧实现把 config.URI 原样交给驱动，这类 URI 可以正常连接；改动后 generateMongoURI 返回 errIncorrectURI，Connect 只打一条 Errorf 就 return（函数无返回值，调用方无从感知），原本可用的部署会直接连不上。建议同时接受 `mongodb+srv
    - `152` 路径被双重转义：url.URL.Path 应该存未转义的路径，String()/EscapedPath() 会自己按 encodePath 规则转义。这里先 url.PathEscape 再交给 Path，`%` 会被二次转义：数据库名 `my db` → PathEscape 得 `my%20db` → 最终 URI 变成 `/my%2520db`，驱动会把数据库名解析成 `my%20db`，与实际库名不符。修复：直接赋值未转义的库名，让 url 包自行转义。
    - `98` 这条 Debugf 打印的是 c.config.Host，而同一函数后半段（Ping 失败日志、成功日志）都改成了新拿到的 host 变量。当用户走「直接给 URI」这条路时（Config.URI 非空、Host 为空），这里会打印出空主机名，日志定位不到实际连的是哪个节点。建议统一用 host。


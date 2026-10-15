# t3code-customize

[English](README.md) | [简体中文](README.zh-CN.md)

在 T3 Code 输入框下方显示 5 小时和每周用量、上下文使用量以及每秒生成的 token 数。

这是非官方项目，与 T3 Tools 无隶属关系。它针对**已经安装的 T3 Code Nightly**：
Linux AppImage、macOS 应用或 Windows 桌面应用。各平台共用同一组统计功能补丁。macOS 的安装与使用见英文版 README。

## 功能

- **用量进度条**：显示 5 小时和每周额度的使用情况，数据来自 T3 已经向模型服务商获取的额度信息。
- **上下文使用量**：显示当前会话的上下文占用。悬停可查看上下文窗口大小、自动压缩阈值，并使用立即压缩按钮。
- **每秒 token 数**：显示上一次回复的生成速度。悬停可查看该轮耗时和 token 详情。Claude 的速度根据流式响应测量；Codex 的速度会标注为近似值。
- **缓存命中率**：显示上一轮的缓存命中率。

定制应用复用官方安装中的原生依赖和 T3 Connect 公共配置。Windows 签名变化和平台限制见下文。

## 安装

请先安装 T3 Code **Nightly**。你需要 Git、Python **3.10 或更高版本**、
网络连接和至少约 **6 GB** 的可用磁盘空间。如果本机 Node 版本低于 24，
工具会下载适合当前平台的私有 Node 24，并校验下载文件的校验和。
首次构建通常需要约 **5–15 分钟**，具体取决于机器性能。

### Windows（PowerShell）

安装 Git for Windows 和 Python，并确保 `git` 和 `python.exe` 位于 PATH 中。
克隆本仓库后直接运行 Python，无需 Git Bash 或管理员权限：

```powershell
git clone https://github.com/btsouth/t3code-customize.git
cd t3code-customize
python .\t3code-customize build
```

如果应用安装在非标准位置，传入**已经安装的应用可执行文件**路径，
不要传入 NSIS 安装程序：

```powershell
python .\t3code-customize build --app 'C:\Apps\T3 Code\T3 Code (Nightly).exe'
```

也可以运行仓库中的 `install.ps1`。它会将本仓库克隆到工具的私有数据目录，
然后构建应用。使用 `-App` 指定应用可执行文件，使用 `-Branch` 测试指定分支。
该脚本不会修改 PowerShell 执行策略。

### Linux

```sh
bash -c "$(curl -fsSL https://raw.githubusercontent.com/btsouth/t3code-customize/main/install.sh)"
```

也可以克隆本仓库，再运行 `python3 ./t3code-customize build`。
工具会自动发现 `~/Applications`、`~/Downloads` 和其他标准搜索目录中的 AppImage。
如果文件位于其他位置，传入 `--app /path/to/T3-Code.AppImage`。
原有的 `--appimage` 参数仍然可用。

### 启用统计功能

构建成功后，**完全退出 T3 Code**。从 Windows 开始菜单或 Linux 应用启动器打开 **T3 Code (Customized)**，
然后启用 **Settings > General > Stats for nerds**。

定制版启动后会直接进入正常的 T3 Code 主页面，不会自动弹出单独的配置向导。
请手动打开 Settings；如果找不到开关，可以在设置中搜索 **Stats for nerds**。
该开关默认关闭。启用后，统计信息会显示在聊天输入框下方；具体可显示哪些数据，
取决于模型服务商和会话情况。

命令包装脚本位于 Linux 的 `~/.local/bin`，或 Windows 的
`%LOCALAPPDATA%\t3code-customize\bin`。如果该目录不在 PATH 中，
可以将其加入 PATH，或在仓库目录中使用 `python t3code-customize <command>`
运行命令（Linux 使用 `python3`）。

## 每次更新 T3 Code 后

```sh
t3code-customize
```

先更新**官方应用**，再运行工具。它会拉取最新补丁，为已安装的版本重新构建，
并提示何时重新打开应用。在重新构建之前，启动器会回退到官方 T3 Code。
Windows 定制副本已禁用自动更新；请从原来的官方启动入口更新官方应用。

## Nightly 更新导致补丁失效时

上游更新很快，有时 Nightly 会修改补丁涉及的代码。遇到这种情况：

- 如果已安装 Claude Code 或 Codex，工具会提供让它们就地迁移补丁的选项。
- 也可以等待仓库更新后，再运行 `t3code-customize`。项目通常会在一天左右跟进。
- 或者让编码代理查看本仓库，并按照 [AGENTS.md](AGENTS.md) 迁移补丁。

整个过程中，你当前的官方 T3 Code 仍然可以使用。

## 工作原理

T3 Code 是采用 MIT 许可证的开源项目。本工具保留了三个统计功能补丁，
并增加了一个使测试预期适用于不同平台的补丁。构建脚本会：

1. 读取已安装应用对应的精确上游提交，以及 T3 Connect 所需的公共配置。
2. 将补丁应用到该提交，并运行对应测试。
3. 重新构建 Web、服务端和桌面端 JavaScript。
4. 将构建结果覆盖到应用副本中，并逐字节检查归档中应保持不变的内容。
5. 更新 Windows 副本中 Electron 嵌入的归档完整性元数据。

对于包含 `server.asar` 独立归档的 Windows 应用，两个归档都会应用补丁。
Linux 使用合并的 `app.asar`。原生库和归档外的文件从已安装应用复制，
不会重新编译替代的原生二进制文件。

所有操作都在你的机器上执行。构建过程不会修改官方安装或 T3 数据。
定制应用运行时通常使用与官方应用相同的 T3 用户配置；切换前请退出官方应用。

## 命令

```text
t3code-customize             更新补丁，并为已安装的 T3 Code 构建
t3code-customize status      查看下次启动会打开哪个版本
t3code-customize off | on    切换官方版本和定制版本
t3code-customize uninstall   移除工具、启动器、构建产物和缓存
```

`off` 和 `on` 是两个独立命令。例如，运行 `t3code-customize off` 切回官方版本。

## 注意事项

- **问题反馈**：向 T3 Code 报告问题前，先运行 `t3code-customize off`，重新打开应用，确认官方版本也存在该问题。定制功能的问题请在本仓库反馈。
- **Windows 签名**：更新嵌入的归档哈希会修改副本中的可执行文件，因此它不再具有官方 Authenticode 签名。这是本地定制副本，不是带签名的可分发安装包。
- **Windows WSL 环境**：当前版本修改的是 Windows 原生服务端。内嵌的 WSL 运行时归档保持官方版本；本次适配尚不支持在 WSL 中运行的会话的新增统计功能。
- **处理器架构**：私有 Node 下载器支持 x64 和 arm64。请在与已安装应用相同的平台和架构上构建；该工具不支持跨平台编译。
- **Linux 文件位置**：数据和构建产物位于 `~/.local/share/t3code-customize`，源码和日志位于 `~/.cache/t3code-customize`。
- **Windows 文件位置**：数据和构建产物位于 `%LOCALAPPDATA%\t3code-customize`，源码和日志位于其中的 `cache` 子目录。

## 开发检查

```sh
python -m unittest discover -s tests -v
python t3code-customize verify
```

Linux 使用 `python3`。第一条命令通过测试样例验证应用布局、分离和合并归档、
更新后回退、文件锁、命令包装及完整性元数据。Windows 还会测试实际的 PE 资源 API。
第二条命令会将所有补丁应用到对应的基准提交，并运行 `checks.json` 中的全部测试和类型检查；
它需要下载上游源码和依赖。

CI 配置在 Linux 和 Windows 上运行平台测试，并在 Linux 上验证上游补丁。
测试样例验证与真实桌面启动、模型服务商集成的验证分别进行。

## 许可证

MIT，与 T3 Code 相同。

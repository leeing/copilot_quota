# Copilot Quota

GitHub Copilot Premium Request 配额查询工具。自动发现本地 GitHub Token，查询当月 Premium requests 用量。

## 运行

```bash
python copilot_quota.py
```

**无需安装任何依赖**，仅使用 Python 标准库（Python ≥ 3.12）。

## Token 查找顺序

1. 环境变量 `GITHUB_TOKEN`（优先）
2. `~/.config/github-copilot/hosts.json`（VS Code / Neovim）
3. `~/Library/Application Support/github-copilot/hosts.json`（macOS）
4. `~/.local/share/opencode/auth.json`（OpenCode）
5. `~/.config/github-copilot/apps.json`

也可手动指定：

```bash
GITHUB_TOKEN=ghp_xxxx python copilot_quota.py
```

## 输出示例

```
=== GitHub Copilot Premium 请求配额 ===
👤 用户:     octocat
📋 订阅计划: business
🏷️  SKU:     copilot_enterprise
🔹 总配额:   1000
🔸 已使用:   420 (使用比例 42.00%)
✅ 剩余次数: 580
```

## 开发

开发工具链使用 [uv](https://docs.astral.sh/uv/) 管理：

```bash
# 安装开发依赖
uv sync

# 格式化 + lint + 类型检查
uv run ruff format .
uv run ruff check --fix .
uv run mypy copilot_quota.py
```

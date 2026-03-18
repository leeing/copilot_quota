"""
GitHub Copilot Premium Request 配额查询工具
"""

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CopilotConfig:
    github_token: str


def get_config() -> CopilotConfig:
    """获取配置及 Token 信息"""
    token_env = os.environ.get("GITHUB_TOKEN")
    if token_env:
        logger.info("Using token from environment variable GITHUB_TOKEN")
        return CopilotConfig(github_token=token_env)

    # 常见平台的 Copilot 鉴权文件存储路径
    paths = [
        Path.home() / ".config" / "github-copilot" / "hosts.json",
        Path.home() / "Library" / "Application Support" / "github-copilot" / "hosts.json",
        Path.home() / ".local" / "share" / "opencode" / "auth.json",
        Path.home() / ".config" / "github-copilot" / "apps.json",
    ]

    for path in paths:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))

                # 处理标准 hosts.json 格式 (VS Code, Neovim 等)
                if "github.com" in data:
                    token = data["github.com"].get("oauth_token")
                    if token:
                        logger.info("Found token in: %s", path)
                        return CopilotConfig(github_token=str(token))

                # 处理 OpenCode auth.json 格式
                if "github-copilot" in data:
                    token = data["github-copilot"].get("refresh") or data["github-copilot"].get("access")
                    if token:
                        logger.info("Found token in: %s", path)
                        return CopilotConfig(github_token=str(token))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Failed to parse config file %s: %s", path, e)
                continue

    msg = "无法自动找到 GitHub Token。请设置 GITHUB_TOKEN 环境变量。"
    raise ValueError(msg)


def get_copilot_internal_token(oauth_token: str) -> str:
    """通过 GitHub Token 换取 Copilot Internal Token"""
    req = urllib.request.Request(
        "https://api.github.com/copilot_internal/v2/token",
        headers={
            "Accept": "application/json",
            "Authorization": f"token {oauth_token}",
            "User-Agent": "GithubCopilot/1.250.0",
            "Editor-Version": "vscode/1.95.0",
            "Editor-Plugin-Version": "copilot/1.250.0",
            "Copilot-Integration-Id": "vscode-chat",
            "Openai-Organization": "github-copilot",
            "X-GitHub-Api-Version": "2024-12-15",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            data = json.loads(resp.read())
            token = data.get("token")
            if token:
                logger.info("Successfully exchanged for Copilot session token")
                return str(token)
            return oauth_token
    except urllib.error.HTTPError as e:
        # 404 = token scope 不含 copilot（常见于 read:user scope 的 OAuth token）
        # 此时直接用原始 OAuth token 即可正常访问配额 API
        logger.debug(
            "Token exchange returned HTTP %s, using OAuth token directly (this is normal)",
            e.code,
        )
        return oauth_token
    except urllib.error.URLError as e:
        logger.debug("Token exchange network error: %s, using OAuth token directly", e)
        return oauth_token


def get_quota_data(token: str, oauth_token: str) -> dict[str, object]:
    """获取用户信息及配额"""
    auth_header = f"Bearer {token}" if token != oauth_token else f"token {oauth_token}"

    req = urllib.request.Request(
        "https://api.github.com/copilot_internal/user",
        headers={
            "Accept": "application/json",
            "Authorization": auth_header,
            "User-Agent": "GitHubCopilotChat/0.35.0",
            "Editor-Version": "vscode/1.107.0",
            "Editor-Plugin-Version": "copilot-chat/0.35.0",
            "Copilot-Integration-Id": "vscode-chat",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            result: dict[str, object] = json.loads(resp.read())
            return result
    except urllib.error.HTTPError as e:
        if token != oauth_token:
            logger.info("Retrying quota API with original OAuth token...")
            req.headers["Authorization"] = f"Bearer {oauth_token}"
            with urllib.request.urlopen(req) as fallback_resp:  # noqa: S310
                fallback_result: dict[str, object] = json.loads(fallback_resp.read())
                return fallback_result
        msg = f"Failed to fetch quota data: {e}"
        raise ValueError(msg) from e


def main() -> None:
    try:
        logger.info("Initializing GitHub Copilot Quota Checker...")
        config = get_config()

        logger.info("Requesting Copilot internal token...")
        copilot_token = get_copilot_internal_token(config.github_token)

        logger.info("Fetching user quota...")
        user_data = get_quota_data(copilot_token, config.github_token)

        snapshots = user_data.get("quota_snapshots")
        if not isinstance(snapshots, dict):
            print("❌ 未找到有效的数据格式。")  # noqa: T201
            return

        premium = snapshots.get("premium_interactions")
        if not isinstance(premium, dict):
            print("❌ 未找到 Premium requests 配额数据。可能您没有订阅 Copilot 或者尚未受限于此配额。")  # noqa: T201
            return

        if premium.get("unlimited"):
            print("🎉 您的 Premium requests 是无限配额 (Unlimited)。")  # noqa: T201
            return

        entitlement = int(premium.get("entitlement", 0))
        remaining = int(premium.get("remaining", 0))
        used = entitlement - remaining
        usage_ratio = (used / entitlement * 100) if entitlement > 0 else 0.0

        # 终端 UI 输出
        login = user_data.get("login", "unknown")
        plan = user_data.get("copilot_plan", "unknown")
        sku = user_data.get("access_type_sku", "unknown")

        print("\n=== GitHub Copilot Premium 请求配额 ===")  # noqa: T201
        print(f"👤 用户:     {login}")  # noqa: T201
        print(f"📋 订阅计划: {plan}")  # noqa: T201
        print(f"🏷️  SKU:     {sku}")  # noqa: T201
        print(f"🔹 总配额:   {entitlement}")  # noqa: T201
        print(f"🔸 已使用:   {used} (使用比例 {usage_ratio:.2f}%)")  # noqa: T201
        print(f"✅ 剩余次数: {remaining}")  # noqa: T201

    except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError):
        logger.exception("An error occurred")


if __name__ == "__main__":
    main()

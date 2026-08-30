# 工作区初始化与上手（由 Agent 执行）

当用户请求初始化或加入本工作区（「我要以 `<username>` 身份加入」「帮我初始化这个工作区」等），按本文件执行。每步完成后自检；未确认的信息（用户名、远程仓库地址）必须向用户询问，不要猜测。

## 0. 前置确认

- 确认 `<username>`：全小写英文或拼音（文件名与跨平台兼容需要）；用户没提供或提供的不符合要求时，先与用户确认。
- **区分两种场景**：
  - **加入已有工作台**（`workspaces/` 下已有其他用户目录，或远程仓库中已存在协作记录）：直接进入第 1 步。
  - **首次启用模版**（刚克隆的模版仓库，尚无协作者）：先执行第 0.1 步绑定新远程仓库，再继续第 1 步。

### 0.1 绑定远程仓库（仅首次启用模版时）

模版仓库本身不带协作历史，启用时需要绑定到该项目自己的远程仓库：

```bash
git remote set-url origin <new-repo-url>   # 地址向用户确认，不要猜测
git push -u origin main
```

若远程仓库非空：先 `git pull --rebase origin main` 合并后再 push。

## 1. 写入本地身份

```bash
echo "<username>" > workspaces/.current_user
```

该文件是设备本地状态（已 gitignore），告诉本机的 sync.py「这台电脑上的当前用户是谁」。

## 2. 创建工作区目录

```bash
mkdir -p workspaces/<username>/inbox workspaces/<username>/workspace
printf '# <username> 的工作日志\n' > workspaces/<username>/log.md
```

若 `workspaces/<username>/` 已存在：该用户可能已加入过——与用户确认后跳过第 2、3 步，仅确保 `.current_user` 内容正确。

## 3. 提交并推送

```bash
git add workspaces/<username> && git commit -m "docs: <username> joins the workspace" && git push
```

push 被拒：先 `git pull --rebase` 再 push（新建目录与他人的邮件不会冲突）。

## 4. 自测收信链路

```bash
cd workspaces
uv run scripts/sync.py write --to <username> --subject "欢迎加入" --content "这是你的第一封信，用于验证工作台链路正常。"
uv run scripts/sync.py check   # 应列出这封信
uv run scripts/sync.py read    # 应读取全文并标记已读
```

## 5. 向用户报告

告知用户：工作区已就绪；今后每次向 Agent 发起新一轮对话时都会自动检查新邮件（以「叮咚」形式提醒）；想给谁写信直接说即可。

#!/usr/bin/env python3
"""
用 GitHub API 推送本地 git commit（无需 git push）。

适用场景：
- 本机/自托管 runner 网络环境下，git(https) 访问 github.com 不稳定（TLS/代理/DNS 等），导致 `git push/fetch` 失败。
- 但 `gh` CLI 仍可正常访问 GitHub API（api.github.com）。

核心行为：
1) 读取本地某个 commit（默认 HEAD）引入的文件变更（相对父提交）
2) 以远端分支 HEAD 的 tree 作为 base_tree，在 GitHub 侧创建新 tree（只更新本次变更的路径）
3) 在 GitHub 侧创建新 commit（message/author/committer 尽量对齐本地 commit）
4) fast-forward 更新远端分支引用（force=false）

安全护栏（默认开启）：
- 对于本次 commit 修改/删除/重命名的路径，会检查远端 HEAD 对应文件的 blob sha
  是否与“本地父提交”一致；若不一致，说明远端已变更同一路径，脚本会中止避免覆盖。

依赖：
- 本机已安装并登录 `gh`（需具备 repo 权限）
- 本地仓库可读取目标 commit（不要求能访问远端）
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Optional
from urllib.parse import quote


class CmdError(RuntimeError):
    pass


def _run(cmd: list[str], *, cwd: Optional[str] = None, input_bytes: Optional[bytes] = None) -> bytes:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise CmdError(f"命令不存在: {cmd[0]}") from exc

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        raise CmdError(f"命令失败({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    return proc.stdout


def _run_text(cmd: list[str], *, cwd: Optional[str] = None) -> str:
    return _run(cmd, cwd=cwd).decode("utf-8", "replace")


def _git(repo_dir: str, args: list[str], *, input_bytes: Optional[bytes] = None) -> bytes:
    return _run(["git", *args], cwd=repo_dir, input_bytes=input_bytes)


def _git_text(repo_dir: str, args: list[str]) -> str:
    return _git(repo_dir, args).decode("utf-8", "replace")


def _gh_api_json(method: str, path: str, *, data: Optional[dict[str, Any]] = None) -> Any:
    cmd = ["gh", "api", path]
    if method.upper() != "GET":
        cmd += ["--method", method.upper(), "--input", "-"]
    if data is None:
        raw = _run(cmd)
    else:
        raw = _run(cmd, input_bytes=json.dumps(data).encode("utf-8"))
    return json.loads(raw.decode("utf-8", "replace"))


def _parse_owner_repo_from_remote_url(url: str) -> Optional[str]:
    url = url.strip()
    if not url:
        return None
    # https://github.com/<owner>/<repo>.git
    if url.startswith("http://") or url.startswith("https://"):
        # 仅支持 github.com 形式
        if "github.com/" not in url:
            return None
        tail = url.split("github.com/", 1)[1]
        tail = tail.removesuffix(".git")
        if "/" in tail:
            owner, repo = tail.split("/", 1)
            if owner and repo:
                return f"{owner}/{repo}"
        return None

    # git@github.com:<owner>/<repo>.git
    if url.startswith("git@github.com:"):
        tail = url.split("git@github.com:", 1)[1]
        tail = tail.removesuffix(".git")
        if "/" in tail:
            owner, repo = tail.split("/", 1)
            if owner and repo:
                return f"{owner}/{repo}"
        return None

    return None


def _gh_repo_name_with_owner(repo_dir: str) -> str:
    # 首选：gh 从当前 git 仓库解析（不依赖网络 git fetch/push）
    try:
        raw = _run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            cwd=repo_dir,
        )
        name = raw.decode("utf-8", "replace").strip()
        if name:
            return name
    except CmdError:
        pass

    # fallback：从本地 remote URL 解析（同样不需要网络）
    remote = _git_text(repo_dir, ["remote", "get-url", "origin"]).strip()
    parsed = _parse_owner_repo_from_remote_url(remote)
    if parsed:
        return parsed
    raise CmdError("无法确定仓库 owner/repo。请在 git 仓库目录中运行，或检查 origin remote URL。")


@dataclass(frozen=True)
class LocalCommitMeta:
    sha: str
    parent_sha: str
    message: str
    author_name: str
    author_email: str
    author_date_iso: str
    committer_name: str
    committer_email: str
    committer_date_iso: str


def _get_local_commit_meta(repo_dir: str, commit: str) -> LocalCommitMeta:
    # 限制：仅支持 1 个父提交（非 merge commit）
    parents = _git_text(repo_dir, ["rev-list", "--parents", "-n", "1", commit]).strip().split()
    if len(parents) < 2:
        raise CmdError("不支持 root commit（没有父提交）。")
    if len(parents) != 2:
        raise CmdError(f"不支持 merge commit（parents={len(parents)-1}）。请先 rebase/squash 后再推送。")

    sha, parent_sha = parents[0], parents[1]
    fmt = "%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI%x00%B"
    raw = _git(repo_dir, ["show", "-s", f"--format={fmt}", sha])
    parts = raw.split(b"\x00", 6)
    if len(parts) != 7:
        raise CmdError("解析 git commit 元信息失败。")

    author_name = parts[0].decode("utf-8", "replace").strip()
    author_email = parts[1].decode("utf-8", "replace").strip()
    author_date_iso = parts[2].decode("utf-8", "replace").strip()
    committer_name = parts[3].decode("utf-8", "replace").strip()
    committer_email = parts[4].decode("utf-8", "replace").strip()
    committer_date_iso = parts[5].decode("utf-8", "replace").strip()
    message = parts[6].decode("utf-8", "replace").rstrip("\n")

    if not message.strip():
        raise CmdError("commit message 为空，拒绝推送。")

    return LocalCommitMeta(
        sha=sha,
        parent_sha=parent_sha,
        message=message,
        author_name=author_name,
        author_email=author_email,
        author_date_iso=author_date_iso,
        committer_name=committer_name,
        committer_email=committer_email,
        committer_date_iso=committer_date_iso,
    )


@dataclass(frozen=True)
class FileChange:
    status: str  # A/M/D/R/C
    path: str
    old_path: Optional[str] = None


def _parse_name_status(lines: Iterable[str]) -> list[FileChange]:
    changes: list[FileChange] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if not parts:
            continue

        st = parts[0]
        if st.startswith("R") or st.startswith("C"):
            # R100\told\tnew
            if len(parts) != 3:
                raise CmdError(f"无法解析 rename/copy 变更: {line}")
            changes.append(FileChange(status=st[0], old_path=parts[1], path=parts[2]))
            continue

        if len(parts) != 2:
            raise CmdError(f"无法解析变更: {line}")
        changes.append(FileChange(status=st, path=parts[1]))
    return changes


def _get_commit_changes(repo_dir: str, commit: str) -> list[FileChange]:
    raw = _git_text(repo_dir, ["diff-tree", "--no-commit-id", "--name-status", "-r", commit])
    return _parse_name_status(raw.splitlines())


def _git_blob_sha_and_mode(repo_dir: str, commit: str, path: str) -> tuple[str, str]:
    # 输出：<mode> <type> <sha>\t<path>
    out = _git_text(repo_dir, ["ls-tree", commit, path]).strip()
    if not out:
        raise CmdError(f"无法从 commit {commit} 读取路径: {path}")
    header, _ = out.split("\t", 1)
    mode, obj_type, sha = header.split(" ", 2)
    if obj_type != "blob":
        raise CmdError(f"仅支持 blob 文件: {path}（type={obj_type}）")
    if mode not in ("100644", "100755"):
        raise CmdError(f"不支持的文件 mode: {mode}（path={path}）")
    return sha, mode


def _git_blob_sha_or_none(repo_dir: str, commit: str, path: str) -> Optional[str]:
    try:
        sha, _mode = _git_blob_sha_and_mode(repo_dir, commit, path)
        return sha
    except CmdError:
        return None


def _git_file_bytes(repo_dir: str, commit: str, path: str) -> bytes:
    return _git(repo_dir, ["show", f"{commit}:{path}"])


def _remote_head(owner: str, repo: str, branch: str) -> str:
    data = _gh_api_json("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    sha = data.get("object", {}).get("sha") if isinstance(data, dict) else None
    if not sha:
        raise CmdError(f"无法获取远端分支 HEAD：{owner}/{repo}@{branch}")
    return str(sha)


def _remote_base_tree(owner: str, repo: str, commit_sha: str) -> str:
    data = _gh_api_json("GET", f"/repos/{owner}/{repo}/git/commits/{commit_sha}")
    sha = data.get("tree", {}).get("sha") if isinstance(data, dict) else None
    if not sha:
        raise CmdError(f"无法获取远端 commit tree：{commit_sha}")
    return str(sha)


def _remote_blob_sha(owner: str, repo: str, path: str, ref: str) -> Optional[str]:
    # 使用 contents API：对私有仓库也适用，且能返回 blob sha（不需要下载全部内容）
    safe_path = quote(path, safe="/")
    try:
        data = _gh_api_json("GET", f"/repos/{owner}/{repo}/contents/{safe_path}?ref={ref}")
    except CmdError as exc:
        # 404 视为不存在
        if "HTTP 404" in str(exc) or "status\":\"404" in str(exc):
            return None
        raise

    if isinstance(data, dict) and data.get("type") == "file" and data.get("sha"):
        return str(data["sha"])
    # directory / symlink / submodule：当前脚本不支持
    raise CmdError(f"远端路径不是普通文件（不支持）：{path}")


def _create_blob(owner: str, repo: str, content_bytes: bytes) -> str:
    if len(content_bytes) > 10 * 1024 * 1024:
        raise CmdError("单文件超过 10MB：拒绝通过 API 推送（请改用 git push 或 LFS/Release）。")
    payload = {
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "encoding": "base64",
    }
    data = _gh_api_json("POST", f"/repos/{owner}/{repo}/git/blobs", data=payload)
    sha = data.get("sha") if isinstance(data, dict) else None
    if not sha:
        raise CmdError("创建 blob 失败：未返回 sha。")
    return str(sha)


def _create_tree(owner: str, repo: str, base_tree: str, entries: list[dict[str, Any]]) -> str:
    payload = {"base_tree": base_tree, "tree": entries}
    data = _gh_api_json("POST", f"/repos/{owner}/{repo}/git/trees", data=payload)
    sha = data.get("sha") if isinstance(data, dict) else None
    if not sha:
        raise CmdError("创建 tree 失败：未返回 sha。")
    return str(sha)


def _create_commit(owner: str, repo: str, message: str, tree_sha: str, parent_sha: str, meta: LocalCommitMeta) -> str:
    payload = {
        "message": message,
        "tree": tree_sha,
        "parents": [parent_sha],
        "author": {
            "name": meta.author_name,
            "email": meta.author_email,
            "date": meta.author_date_iso,
        },
        "committer": {
            "name": meta.committer_name,
            "email": meta.committer_email,
            "date": meta.committer_date_iso,
        },
    }
    data = _gh_api_json("POST", f"/repos/{owner}/{repo}/git/commits", data=payload)
    sha = data.get("sha") if isinstance(data, dict) else None
    if not sha:
        raise CmdError("创建 commit 失败：未返回 sha。")
    return str(sha)


def _update_ref(owner: str, repo: str, branch: str, sha: str) -> None:
    payload = {"sha": sha, "force": False}
    _gh_api_json("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", data=payload)


def _ensure_clean_proxy_config() -> None:
    # 本脚本自身不修改 ~/.gitconfig，但给出明确提示（避免 git 意外走本机代理导致莫名失败）。
    proc = subprocess.run(
        ["git", "config", "--global", "--get", "http.proxy"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    proxy = proc.stdout.decode("utf-8", "replace").strip() if proc.returncode == 0 else ""
    proc2 = subprocess.run(
        ["git", "config", "--global", "--get", "https.proxy"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    proxy2 = proc2.stdout.decode("utf-8", "replace").strip() if proc2.returncode == 0 else ""

    if proxy or proxy2:
        raise CmdError(
            "检测到全局 git 代理配置（http.proxy）。\n"
            "建议先执行：\n"
            "  git config --global --unset http.proxy\n"
            "  git config --global --unset https.proxy\n"
            f"当前: http.proxy={proxy or '<unset>'}, https.proxy={proxy2 or '<unset>'}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="用 GitHub API 推送本地 git commit（无需 git push）")
    parser.add_argument("--repo-dir", default=os.getcwd(), help="本地仓库目录（默认当前目录）")
    parser.add_argument("--branch", default="main", help="远端分支名（默认 main）")
    parser.add_argument("--commit", default="HEAD", help="要推送的本地 commit（默认 HEAD）")
    parser.add_argument("--no-guard", action="store_true", help="关闭远端覆盖护栏（不推荐）")
    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo_dir)
    branch = args.branch
    commit = args.commit

    try:
        _ensure_clean_proxy_config()

        meta = _get_local_commit_meta(repo_dir, commit)
        changes = _get_commit_changes(repo_dir, meta.sha)
        if not changes:
            raise CmdError("该 commit 未包含任何文件变更，停止。")

        name_with_owner = _gh_repo_name_with_owner(repo_dir)
        if "/" not in name_with_owner:
            raise CmdError(f"无法解析仓库名: {name_with_owner}")
        owner, repo = name_with_owner.split("/", 1)

        remote_parent = _remote_head(owner, repo, branch)
        base_tree = _remote_base_tree(owner, repo, remote_parent)

        # 构建 tree entries（先做护栏检查）
        entries: list[dict[str, Any]] = []

        def guard_check(path: str, local_expected_parent_blob: Optional[str]) -> None:
            if args.no_guard:
                return
            remote_blob = _remote_blob_sha(owner, repo, path, remote_parent)
            if remote_blob != local_expected_parent_blob:
                raise CmdError(
                    "远端与本地父提交在同一路径上已发生漂移，拒绝覆盖：\n"
                    f"- path: {path}\n"
                    f"- local parent blob: {local_expected_parent_blob}\n"
                    f"- remote head blob:  {remote_blob}\n"
                    "建议：先把远端最新内容同步到本地，再重新生成/调整该 commit。"
                )

        # 先展开 rename/copy -> delete+add，确保护栏覆盖
        expanded: list[FileChange] = []
        for ch in changes:
            if ch.status in ("R", "C") and ch.old_path:
                # old 删除（R 才删除；C 不删除 old）
                if ch.status == "R":
                    expanded.append(FileChange(status="D", path=ch.old_path))
                expanded.append(FileChange(status="A", path=ch.path))
            else:
                expanded.append(ch)

        for ch in expanded:
            status = ch.status
            path = ch.path

            if status == "D":
                local_parent_blob = _git_blob_sha_or_none(repo_dir, meta.parent_sha, path)
                guard_check(path, local_parent_blob)
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue

            if status in ("A", "M"):
                local_parent_blob = _git_blob_sha_or_none(repo_dir, meta.parent_sha, path)
                # A：若本地父提交不存在该文件，则期望远端也不存在；否则会覆盖别人的新增文件
                guard_check(path, local_parent_blob)

                _blob_sha, mode = _git_blob_sha_and_mode(repo_dir, meta.sha, path)
                content = _git_file_bytes(repo_dir, meta.sha, path)
                remote_blob_sha = _create_blob(owner, repo, content)
                entries.append({"path": path, "mode": mode, "type": "blob", "sha": remote_blob_sha})
                continue

            raise CmdError(f"不支持的变更状态: {status}（path={path}）")

        new_tree = _create_tree(owner, repo, base_tree, entries)
        new_commit = _create_commit(owner, repo, meta.message, new_tree, remote_parent, meta)
        _update_ref(owner, repo, branch, new_commit)

        print(f"OK: updated {owner}/{repo}@{branch} -> {new_commit}")
        print(f"https://github.com/{owner}/{repo}/commit/{new_commit}")
        return 0
    except CmdError as exc:
        print(str(exc).rstrip(), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

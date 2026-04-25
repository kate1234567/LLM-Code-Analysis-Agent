import subprocess


def run_git_command(repo_path, args):
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def is_git_repo(repo_path):
    code, out, err = run_git_command(repo_path, ["rev-parse", "--is-inside-work-tree"])
    return code == 0 and out == "true"


def get_current_branch(repo_path):
    code, out, err = run_git_command(repo_path, ["branch", "--show-current"])
    if code == 0:
        return out
    return None


def get_branches(repo_path):
    code, out, err = run_git_command(repo_path, ["branch", "--format=%(refname:short)"])
    if code == 0:
        return [line.strip() for line in out.splitlines() if line.strip()]
    return []


def get_changed_files(repo_path):
    code, out, err = run_git_command(repo_path, ["status", "--porcelain"])
    if code != 0:
        return []

    files = []
    for line in out.splitlines():
        if len(line) > 3:
            files.append(line[3:].strip())
    return files


def get_changed_files_between_branches(repo_path, base_branch, target_branch):
    code, out, err = run_git_command(
        repo_path,
        ["diff", "--name-only", f"{base_branch}..{target_branch}"]
    )
    if code == 0:
        return [line.strip() for line in out.splitlines() if line.strip()]
    return []


def get_diff_between_branches(repo_path, base_branch, target_branch):
    code, out, err = run_git_command(
        repo_path,
        ["diff", f"{base_branch}..{target_branch}"]
    )
    if code == 0:
        return out
    return ""


if __name__ == "__main__":
    repo_path = input("Repo path: ")
    base_branch = input("Base branch (default master): ").strip() or "master"
    target_branch = input("Target branch (default current): ").strip()

    current = get_current_branch(repo_path)
    if not target_branch:
        target_branch = current

    print("\nIS GIT REPO:", is_git_repo(repo_path))
    print("CURRENT BRANCH:", current)
    print("BRANCHES:", get_branches(repo_path))
    print("CHANGED FILES (working tree):", get_changed_files(repo_path))
    print("CHANGED FILES BETWEEN BRANCHES:", get_changed_files_between_branches(repo_path, base_branch, target_branch))

    diff = get_diff_between_branches(repo_path, base_branch, target_branch)
    print("\n===== BRANCH DIFF (first 1000 chars) =====\n")
    print(diff[:1000])
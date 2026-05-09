#pragma once

#include <string>
#include <vector>

std::string runCommand(const std::string& command);

std::string getFileDiff(
    const std::string& repoPath,
    const std::string& baseBranch,
    const std::string& currentBranch,
    const std::string& relativePath
);

std::vector<std::string> splitLines(const std::string& text);

bool isGitHubUrl(const std::string& input);

bool pathExists(const std::string& path);

std::string cloneRepository(
    const std::string& url,
    const std::string& tempPath
);

void ensureWorktree(
    const std::string& repoPath,
    const std::string& projectPath,
    const std::string& branchName
);

void removeWorktree(
    const std::string& repoPath,
    const std::string& projectPath
);
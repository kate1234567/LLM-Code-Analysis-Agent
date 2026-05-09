#include "git_utils.h"

#include <iostream>
#include <array>
#include <cstdio>
#include <stdexcept>
#include <filesystem>
#include <sstream>

namespace fs = std::filesystem;

std::string runCommand(const std::string& command) {
    std::array<char, 256> buffer{};
    std::string result;

    FILE* pipe = _popen(command.c_str(), "r");
    if (!pipe) {
        throw std::runtime_error("Failed to run command");
    }

    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) != nullptr) {
        result += buffer.data();
    }

    _pclose(pipe);
    return result;
}

std::string getFileDiff(
    const std::string& repoPath,
    const std::string& baseBranch,
    const std::string& currentBranch,
    const std::string& relativePath
) {
    std::string command =
        "git -C \"" + repoPath + "\" diff " + baseBranch + ".." + currentBranch + " -- \"" + relativePath + "\"";

    return runCommand(command);
}

std::vector<std::string> splitLines(const std::string& text) {
    std::vector<std::string> lines;
    std::stringstream ss(text);
    std::string line;

    while (std::getline(ss, line)) {
        if (!line.empty()) {
            while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) {
                line.pop_back();
            }
            if (!line.empty()) {
                lines.push_back(line);
            }
        }
    }

    return lines;
}

bool pathExists(const std::string& path) {
    return fs::exists(path);
}

void ensureWorktree(const std::string& repoPath, const std::string& projectPath, const std::string& branchName) {
    if (pathExists(projectPath)) {
        std::cout << "WORKTREE ALREADY EXISTS:\n" << projectPath << "\n\n";
        return;
    }

    std::string cmd =
        "git -C \"" + repoPath + "\" worktree add \"" + projectPath + "\" " + branchName;

    std::cout << "CREATING WORKTREE...\n";
    std::string output = runCommand(cmd);
    std::cout << output << "\n";
}

void removeWorktree(const std::string& repoPath, const std::string& projectPath) {
    if (!pathExists(projectPath)) {
        return;
    }

    std::string cmd =
        "git -C \"" + repoPath + "\" worktree remove \"" + projectPath + "\" --force";

    std::cout << "REMOVING WORKTREE...\n";
    std::string output = runCommand(cmd);
    std::cout << output << "\n";
}

std::string cloneRepository(
    const std::string& url,
    const std::string& tempPath
) {
    if (fs::exists(tempPath)) {
        std::string removeCmd =
            "rmdir /s /q \"" + tempPath + "\"";
        system(removeCmd.c_str());
    }

    std::string cloneCmd =
        "git clone " + url + " \"" + tempPath + "\"";

    std::cout << "\nCLONING REPOSITORY...\n";
    system(cloneCmd.c_str());

    return tempPath;
}

bool isGitHubUrl(const std::string& input) {
    return input.find("github.com") != std::string::npos;
}
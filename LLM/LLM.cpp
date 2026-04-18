#include <iostream>
#include <string>
#include <array>
#include <stdexcept>
#include <cstdio>
#include <sstream>

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

int main() {
    std::string repoPath = R"(C:\Users\katew\source\repos\LLM)";
    std::string worktreePath = R"(C:\Users\katew\source\repos\LLM_feature)";
    std::string baseBranch = "master";

    try {
        std::string branchCmd = "git -C \"" + worktreePath + "\" branch --show-current";
        std::string currentBranch = runCommand(branchCmd);

        while (!currentBranch.empty() && (currentBranch.back() == '\n' || currentBranch.back() == '\r')) {
            currentBranch.pop_back();
        }

        std::string diffFilesCmd =
            "git -C \"" + repoPath + "\" diff --name-only " + baseBranch + ".." + currentBranch;

        std::string changedFilesRaw = runCommand(diffFilesCmd);

        std::cout << "WORKTREE PATH:\n" << worktreePath << "\n\n";
        std::cout << "CURRENT BRANCH:\n" << currentBranch << "\n\n";
        std::cout << "CHANGED FILES BETWEEN BRANCHES:\n" << changedFilesRaw << "\n";

        std::string pythonCmd =
            "py C:\\Users\\katew\\source\\repos\\LLMAgent\\llm_test\\orchestrator.py \"" + worktreePath + "\"";

        std::stringstream ss(changedFilesRaw);
        std::string line;

        while (std::getline(ss, line)) {
            if (!line.empty()) {
                while (!line.empty() && (line.back() == '\r' || line.back() == '\n')) {
                    line.pop_back();
                }
                pythonCmd += " \"" + line + "\"";
            }
        }

        std::string output = runCommand(pythonCmd);

        std::cout << "\nPYTHON OUTPUT:\n" << output << std::endl;
    }
    catch (const std::exception& ex) {
        std::cerr << "ERROR: " << ex.what() << std::endl;
    }

    return 0;
}
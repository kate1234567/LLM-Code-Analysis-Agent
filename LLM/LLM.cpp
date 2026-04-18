#include <iostream>
#include <string>
#include <array>
#include <stdexcept>
#include <cstdio>
#include <sstream>
#include <vector>

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

std::vector<std::string> splitLines(const std::string& text) {
    std::vector<std::string> lines;
    std::stringstream ss(text);
    std::string line;

    while (std::getline(ss, line)) {
        if (!line.empty()) {
            lines.push_back(line);
        }
    }

    return lines;
}

int main() {
    std::string repoPath = R"(C:\Users\katew\source\repos\LLM)";
    std::string baseBranch = "master";

    try {
        std::string branchCmd = "git -C \"" + repoPath + "\" branch --show-current";
        std::string currentBranch = runCommand(branchCmd);

        while (!currentBranch.empty() && (currentBranch.back() == '\n' || currentBranch.back() == '\r')) {
            currentBranch.pop_back();
        }

        std::string diffFilesCmd =
            "git -C \"" + repoPath + "\" diff --name-only " + baseBranch + ".." + currentBranch;

        std::string changedFilesRaw = runCommand(diffFilesCmd);

        std::cout << "CURRENT BRANCH:\n" << currentBranch << "\n\n";
        std::cout << "CHANGED FILES BETWEEN BRANCHES:\n" << changedFilesRaw << "\n";

        std::vector<std::string> changedLines = splitLines(changedFilesRaw);

        std::string pythonCmd =
            "py C:\\Users\\katew\\source\\repos\\LLMAgent\\llm_test\\orchestrator.py \"" + repoPath + "\"";

        for (const auto& path : changedLines) {
            pythonCmd += " \"" + path + "\"";
        }

        std::string output = runCommand(pythonCmd);

        std::cout << "\nPYTHON OUTPUT:\n" << output << std::endl;
    }
    catch (const std::exception& ex) {
        std::cerr << "ERROR: " << ex.what() << std::endl;
    }

    return 0;
}
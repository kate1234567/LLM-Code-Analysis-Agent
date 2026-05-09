#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <map>

#include "scanner.h"
#include "git_utils.h"
#include "json_exporter.h"
#include "config_loader.h"

namespace fs = std::filesystem;

int main() {
    std::string repoInput;
    std::string repoPath;

    auto config = loadConfig("config.yaml");

    if (config.empty()) {
        std::cerr << "CONFIG NOT LOADED\n";
        return 1;
    }

    std::cout << "CONFIG LOADED SUCCESSFULLY\n";
    std::cout << "worktree_path: " << config["worktree_path"] << std::endl;
    std::cout << "json_context_path: " << config["json_context_path"] << std::endl;
    std::cout << "python_command: " << config["python_command"] << std::endl;

    std::cout << "ENTER REPOSITORY PATH OR GITHUB URL:\n";
    std::getline(std::cin, repoInput);

    if (repoInput.empty()) {
        std::getline(std::cin, repoInput);
    }

    if (isGitHubUrl(repoInput)) {
        repoPath = cloneRepository(
            repoInput,
            config["temp_repo_path"]
        );
    }
    else {
        repoPath = repoInput;
    }

    std::string baseBranch;
    std::string branchName;

    std::string worktreePath =
        config["worktree_path"];

    std::string jsonOutputPath =
        config["json_context_path"];

    std::cout << "ENTER BASE BRANCH (example: main or master):\n";
    std::getline(std::cin, baseBranch);

    std::cout << "ENTER BRANCH FOR ANALYSIS:\n";
    std::getline(std::cin, branchName);

    std::string analysisMode;
    bool forceReanalyze = false;

    std::cout << "SELECT ANALYSIS MODE:\n";
    std::cout << "1 - FAST (changed files only)\n";
    std::cout << "2 - FULL (full project analysis)\n";
    std::cout << "3 - FULL WITHOUT CACHE (force re-analysis)\n";
    std::cout << "Your choice: ";

    int modeChoice;
    std::cin >> modeChoice;

    if (modeChoice == 1) {
        analysisMode = "fast";
    }
    else if (modeChoice == 2) {
        analysisMode = "full";
    }
    else if (modeChoice == 3) {
        analysisMode = "full";
        forceReanalyze = true;
    }
    else {
        analysisMode = "full";
    }

    std::cout << "\nSELECTED MODE: "
        << analysisMode
        << "\n\n";

    try {
        std::string projectPath;

        if (isGitHubUrl(repoInput)) {
            projectPath = repoPath;
        }
        else {
            ensureWorktree(
                repoPath,
                worktreePath,
                branchName
            );

            projectPath = worktreePath;
        }

        std::vector<std::string> files =
            scanProject(projectPath);

        std::cout << "PROJECT PATH:\n"
            << projectPath
            << "\n\n";

        std::cout << "FOUND CODE FILES:\n";

        for (const auto& file : files) {
            std::cout << file << "\n";
        }

        std::cout << "\nTOTAL: "
            << files.size()
            << "\n";

        std::string branchCmd =
            "git -C \"" + projectPath +
            "\" branch --show-current";

        std::string currentBranch =
            runCommand(branchCmd);

        while (
            !currentBranch.empty() &&
            (
                currentBranch.back() == '\n' ||
                currentBranch.back() == '\r'
                )
            ) {
            currentBranch.pop_back();
        }

        exportContextToJson(
            jsonOutputPath,
            repoPath,
            projectPath,
            baseBranch,
            currentBranch,
            files
        );

        std::cout << "\nJSON EXPORTED TO:\n"
            << jsonOutputPath
            << "\n\n";

        std::string diffFilesCmd =
            "git -C \"" + repoPath +
            "\" diff --name-only " +
            baseBranch +
            ".." +
            currentBranch;

        std::string changedFilesRaw =
            runCommand(diffFilesCmd);

        std::vector<std::string> changedFiles =
            splitLines(changedFilesRaw);

        std::string changedFilesArg;

        for (const auto& file : changedFiles)
        {
            if (!isRelevantChangedFile(file))
            {
                continue;
            }

            if (!changedFilesArg.empty())
            {
                changedFilesArg += ";";
            }

            changedFilesArg += file;
        }

        std::cout << "CURRENT BRANCH:\n"
            << currentBranch
            << "\n\n";

        std::cout << "CHANGED FILES BETWEEN BRANCHES:\n";

        for (const auto& file : changedFiles)
        {
            std::cout << file << "\n";
        }

        std::cout << "\n";

        std::string pythonCmd =
            config["python_command"] + " " +
            "--path \"" + projectPath + "\" " +
            "--provider auto " +
            "--model deepseek-coder " +
            "--workers 4 " +
            "--mode " + analysisMode +
            " --base-branch " + baseBranch +
            " --source-branch " + branchName +
            " --target-branch " + baseBranch +
            " --json-context \"" + jsonOutputPath + "\" " +
            "--changed-files \"" + changedFilesArg + "\"";

        if (forceReanalyze) {
            pythonCmd += " --force-reanalyze";
        }

        std::cout << "\nRUNNING PYTHON ORCHESTRATOR:\n";
        std::cout << pythonCmd << "\n\n";

        std::string output =
            runCommand(pythonCmd);

        std::cout << "\nPYTHON OUTPUT:\n"
            << output
            << std::endl;
    }
    catch (const std::exception& ex) {
        std::cerr << "ERROR: "
            << ex.what()
            << std::endl;
    }

    return 0;
}
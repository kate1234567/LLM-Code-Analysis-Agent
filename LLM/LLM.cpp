#include <iostream>
#include <string>
#include <vector>
#include <filesystem>
#include <set>
#include <fstream>
#include <regex>
#include <map>
#include <algorithm>
#include <array>
#include <stdexcept>
#include <cstdio>
#include <sstream>

namespace fs = std::filesystem;

struct Symbols {
    std::vector<std::string> classes;
    std::vector<std::string> structs;
    std::vector<std::string> functions;
};

bool shouldIgnoreDir(const std::string& dirName) {
    static const std::set<std::string> ignored = {
        ".vs", "x64", "Debug", "Release", "build"
    };
    return ignored.count(dirName) > 0;
}

bool isCodeFile(const fs::path& path) {
    std::string ext = path.extension().string();
    return ext == ".cpp" || ext == ".h" || ext == ".hpp";
}

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

std::vector<std::string> scanProject(const std::string& projectPath) {
    std::vector<std::string> files;

    try {
        for (fs::recursive_directory_iterator it(projectPath), end; it != end; ++it) {
            const fs::path currentPath = it->path();

            if (it->is_directory()) {
                std::string dirName = currentPath.filename().string();
                if (shouldIgnoreDir(dirName)) {
                    it.disable_recursion_pending();
                }
                continue;
            }

            if (it->is_regular_file() && isCodeFile(currentPath)) {
                files.push_back(currentPath.string());
            }
        }
    }
    catch (const std::exception& ex) {
        std::cerr << "SCAN ERROR: " << ex.what() << std::endl;
    }

    return files;
}

std::vector<std::string> extractIncludes(const std::string& filePath) {
    std::vector<std::string> includes;
    std::ifstream file(filePath);

    if (!file.is_open()) {
        return includes;
    }

    std::string line;
    std::regex includeRegex(R"(\s*#include\s*[<"](.+?)[">])");

    while (std::getline(file, line)) {
        std::smatch match;
        if (std::regex_search(line, match, includeRegex) && match.size() > 1) {
            includes.push_back(match[1].str());
        }
    }

    return includes;
}

void addUnique(std::vector<std::string>& vec, const std::string& value) {
    if (std::find(vec.begin(), vec.end(), value) == vec.end()) {
        vec.push_back(value);
    }
}

Symbols extractSymbols(const std::string& filePath) {
    Symbols result;
    std::ifstream file(filePath);

    if (!file.is_open()) {
        return result;
    }

    std::string line;

    std::regex classRegex(R"(\bclass\s+([A-Za-z_]\w*))");
    std::regex structRegex(R"(\bstruct\s+([A-Za-z_]\w*))");
    std::regex functionRegex(R"((?:[A-Za-z_]\w*::)?([A-Za-z_]\w*)\s*\([^;{}()]*\)\s*(?:const)?\s*\{)");

    while (std::getline(file, line)) {
        std::smatch match;

        if (std::regex_search(line, match, classRegex) && match.size() > 1) {
            addUnique(result.classes, match[1].str());
        }

        if (std::regex_search(line, match, structRegex) && match.size() > 1) {
            addUnique(result.structs, match[1].str());
        }

        if (std::regex_search(line, match, functionRegex) && match.size() > 1) {
            std::string fn = match[1].str();
            if (fn != "if" && fn != "for" && fn != "while" && fn != "switch" && fn != "catch") {
                addUnique(result.functions, fn);
            }
        }
    }

    return result;
}

std::string escapeJson(const std::string& s) {
    std::string out;
    for (char c : s) {
        switch (c) {
        case '\\': out += "\\\\"; break;
        case '"':  out += "\\\""; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        default:   out += c; break;
        }
    }
    return out;
}

void writeStringArray(std::ofstream& out, const std::vector<std::string>& arr) {
    out << "[";
    for (size_t i = 0; i < arr.size(); ++i) {
        out << "\"" << escapeJson(arr[i]) << "\"";
        if (i + 1 < arr.size()) {
            out << ", ";
        }
    }
    out << "]";
}

std::string readFileSnippet(const std::string& filePath, size_t maxChars = 3000) {
    std::ifstream file(filePath);
    if (!file.is_open()) {
        return "";
    }

    std::string content(
        (std::istreambuf_iterator<char>(file)),
        std::istreambuf_iterator<char>()
    );

    if (content.size() > maxChars) {
        content = content.substr(0, maxChars);
    }

    return content;
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

void exportContextToJson(
    const std::string& outputPath,
    const std::string& repoPath,
    const std::string& projectPath,
    const std::string& baseBranch,
    const std::string& currentBranch,
    const std::vector<std::string>& files
) {
    std::ofstream out(outputPath);
    if (!out.is_open()) {
        std::cerr << "FAILED TO OPEN JSON FILE: " << outputPath << std::endl;
        return;
    }

    out << "{\n";
    out << "  \"project_path\": \"" << escapeJson(projectPath) << "\",\n";
    out << "  \"files\": [\n";

    for (size_t i = 0; i < files.size(); ++i) {
        const auto& file = files[i];

        auto includes = extractIncludes(file);
        auto symbols = extractSymbols(file);

        std::string relativePath = fs::relative(file, projectPath).string();
        std::replace(relativePath.begin(), relativePath.end(), '\\', '/');

        std::string diffText = getFileDiff(repoPath, baseBranch, currentBranch, relativePath);
        if (diffText.size() > 4000) {
            diffText = diffText.substr(0, 4000);
        }

        out << "    {\n";
        out << "      \"path\": \"" << escapeJson(file) << "\",\n";
        out << "      \"relative_path\": \"" << escapeJson(relativePath) << "\",\n";
        out << "      \"file_code\": \"" << escapeJson(readFileSnippet(file)) << "\",\n";
        out << "      \"diff\": \"" << escapeJson(diffText) << "\",\n";

        out << "      \"includes\": ";
        writeStringArray(out, includes);
        out << ",\n";

        out << "      \"symbols\": {\n";
        out << "        \"classes\": ";
        writeStringArray(out, symbols.classes);
        out << ",\n";
        out << "        \"structs\": ";
        writeStringArray(out, symbols.structs);
        out << ",\n";
        out << "        \"functions\": ";
        writeStringArray(out, symbols.functions);
        out << "\n";
        out << "      }\n";

        out << "    }";
        if (i + 1 < files.size()) {
            out << ",";
        }
        out << "\n";
    }

    out << "  ]\n";
    out << "}\n";

    out.close();
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
bool isGitHubUrl(const std::string& input) {
    return input.find("github.com") != std::string::npos;
}

std::string cloneRepository(const std::string& url) {
    std::string tempPath = R"(C:\Users\katew\source\repos\temp_repo)";

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

int main() {
    std::string repoInput;
    std::string repoPath;

    std::cout << "ENTER REPOSITORY PATH OR GITHUB URL:\n";
    std::getline(std::cin, repoInput);

    if (repoInput.empty()) {
        std::getline(std::cin, repoInput);
    }

    // если ссылка GitHub -> clone
    // если локальный путь -> просто используем его
    if (isGitHubUrl(repoInput)) {
        repoPath = cloneRepository(repoInput);
    }
    else {
        repoPath = repoInput;
    }

    std::string baseBranch;
    std::string branchName;

    std::string worktreePath =
        R"(C:\Users\katew\source\repos\LLM_feature)";

    std::string jsonOutputPath =
        R"(C:\Users\katew\source\repos\LLM\python\project_context.json)";

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

        std::string changedFilesArg =
            changedFilesRaw;

        std::replace(
            changedFilesArg.begin(),
            changedFilesArg.end(),
            '\n',
            ';'
        );

        std::replace(
            changedFilesArg.begin(),
            changedFilesArg.end(),
            '\r',
            ' '
        );

        std::cout << "CURRENT BRANCH:\n"
            << currentBranch
            << "\n\n";

        std::cout << "CHANGED FILES BETWEEN BRANCHES:\n"
            << changedFilesRaw
            << "\n";

        std::string pythonCmd =
            "py C:\\Users\\katew\\source\\repos\\LLM\\python\\orchestrator.py "
            "--path \"" + projectPath + "\" "
            "--provider auto "
            "--model deepseek-coder "
            "--workers 4 "
            "--mode " + analysisMode +
            " --base-branch " + baseBranch +
            " --json-context \"" + jsonOutputPath + "\" "
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
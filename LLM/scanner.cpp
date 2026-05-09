#include "scanner.h"

#include <iostream>
#include <fstream>
#include <regex>
#include <filesystem>
#include <set>
#include <algorithm>
#include <sstream>

namespace fs = std::filesystem;

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

std::string readFileSnippet(
    const std::string& filePath,
    size_t maxChars
) {
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
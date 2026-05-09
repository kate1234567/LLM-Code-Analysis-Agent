#pragma once

#include <string>
#include <vector>
#include <filesystem>

struct Symbols {
    std::vector<std::string> classes;
    std::vector<std::string> structs;
    std::vector<std::string> functions;
};

bool shouldIgnoreDir(const std::string& dirName);
bool isCodeFile(const std::filesystem::path& path);
std::vector<std::string> scanProject(const std::string& projectPath);
std::vector<std::string> extractIncludes(const std::string& filePath);
Symbols extractSymbols(const std::string& filePath);
std::string readFileSnippet(const std::string& filePath, size_t maxChars = 3000);
#pragma once

#include <string>
#include <vector>
#include <fstream>

void writeStringArray(
    std::ofstream& out,
    const std::vector<std::string>& arr
);

std::string escapeJson(const std::string& s);

void exportContextToJson(
    const std::string& outputPath,
    const std::string& repoPath,
    const std::string& projectPath,
    const std::string& baseBranch,
    const std::string& currentBranch,
    const std::vector<std::string>& files
);
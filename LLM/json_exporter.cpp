#include "json_exporter.h"
#include "scanner.h"
#include "git_utils.h"

#include <iostream>
#include <fstream>
#include <filesystem>
#include <algorithm>

namespace fs = std::filesystem;
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

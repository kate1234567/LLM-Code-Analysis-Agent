#include "config_loader.h"

#include <iostream>
#include <fstream>
#include <filesystem>
#include <algorithm>

namespace fs = std::filesystem;

std::map<std::string, std::string> loadConfig(const std::string& configPath) {
    std::map<std::string, std::string> config;
    std::ifstream file(configPath);

    if (!file.is_open()) {
        std::cerr << "FAILED TO OPEN CONFIG: " << configPath << std::endl;
        return config;
    }

    std::string line;

    while (std::getline(file, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }

        size_t pos = line.find(':');
        if (pos == std::string::npos) {
            continue;
        }

        std::string key = line.substr(0, pos);
        std::string value = line.substr(pos + 1);

        while (!value.empty() && value[0] == ' ') {
            value.erase(0, 1);
        }

        config[key] = value;
    }

    return config;
}

bool isRelevantChangedFile(const std::string& path) {
    std::string lower = path;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);

    return
        lower.ends_with(".cpp") ||
        lower.ends_with(".h") ||
        lower.ends_with(".hpp") ||
        lower.ends_with(".py") ||
        lower.ends_with(".sql");
}
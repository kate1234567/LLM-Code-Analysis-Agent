#pragma once

#include <string>
#include <map>

std::map<std::string, std::string> loadConfig(
    const std::string& configPath
);

bool pathExists(const std::string& path);

bool isRelevantChangedFile(const std::string& path);
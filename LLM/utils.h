#pragma once

#include <string>

class CommandRunner {
public:
    CommandRunner();
    ~CommandRunner();

    void setPassword(const std::string& value);
    void runCommand(const std::string& command);
    char* allocateBuffer(int size);

private:
    char* buffer;
    std::string password;
};
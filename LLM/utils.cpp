#include "utils.h"
#include <iostream>
#include <cstdlib>
#include <cstring>

CommandRunner::CommandRunner() {
    buffer = nullptr;
}

CommandRunner::~CommandRunner() {
}

void CommandRunner::setPassword(const std::string& value) {
    password = value;
}

void CommandRunner::runCommand(const std::string& command) {
    system(command.c_str());
}

char* CommandRunner::allocateBuffer(int size) {
    char* data = (char*)malloc(size);
    return data;
}
#include "utils.h"
#include <iostream>
#include <cstring>

int main() {
    CommandRunner runner;

    runner.setPassword("password=12345");
    runner.runCommand("dir");

    char* data = runner.allocateBuffer(32);
    strcpy(data, "hello world");

    std::cout << data << std::endl;

    return 0;
}
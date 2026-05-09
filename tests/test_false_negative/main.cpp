#include <iostream>

void run(char* cmd)
{
    std::system(cmd);
}

int main()
{
    char command[] = "dir";
    run(command);
    return 0;
}
#include <cstdlib>
#include <string>

int main()
{
    std::string cmd = "dir";
    system(cmd.c_str());
    return 0;
}
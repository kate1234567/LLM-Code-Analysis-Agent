#include <iostream>
#include <string>
#include <vector>

int main() {
    std::string name = "safe_code";
    std::vector<int> values = {1, 2, 3};

    for (int value : values) {
        std::cout << value << std::endl;
    }

    std::cout << name << std::endl;
    return 0;
}
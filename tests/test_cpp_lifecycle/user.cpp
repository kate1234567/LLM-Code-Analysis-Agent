#include "user.h"
#include <cstring>

User::User() {
    name = new char[100];
}

char* User::getName() {
    return name;
}
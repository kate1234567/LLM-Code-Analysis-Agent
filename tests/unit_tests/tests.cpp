#include <cassert>
#include <iostream>
#include <vector>
#include <string>
#include <fstream>

#include "../../LLM/scanner.h"

using namespace std;

void testExtractIncludes()
{
    string testFile = "temp_test.cpp";

    ofstream out(testFile);
    out << "#include \"user.h\"\n";
    out << "#include <iostream>\n";
    out.close();

    vector<string> includes = extractIncludes(testFile);

    assert(includes.size() == 2);
    assert(includes[0] == "user.h");
    assert(includes[1] == "iostream");

    cout << "testExtractIncludes PASSED" << endl;
}

void testInterfileSimple()
{
    string headerFile = "User.h";
    string cppFile = "User.cpp";

    ofstream h(headerFile);
    h <<
        "#pragma once\n"
        "class User {\n"
        "private:\n"
        "    char* name;\n"
        "public:\n"
        "    User();\n"
        "    char* getName();\n"
        "};\n";
    h.close();

    ofstream cpp(cppFile);
    cpp <<
        "#include \"User.h\"\n"
        "#include <cstring>\n"
        "\n"
        "User::User() {\n"
        "    name = new char[100];\n"
        "}\n"
        "\n"
        "char* User::getName() {\n"
        "    return name;\n"
        "}\n";
    cpp.close();

    vector<string> includes = extractIncludes(cppFile);

    assert(includes.size() >= 1);
    assert(includes[0] == "User.h");

    cout << "testInterfileSimple PASSED" << endl;
}

void testLifecycleSimple()
{
    string headerFile = "Lifecycle.h";

    ofstream h(headerFile);
    h <<
        "#pragma once\n"
        "class Lifecycle {\n"
        "private:\n"
        "    char* data;\n"
        "public:\n"
        "    Lifecycle();\n"
        "    char* getData();\n"
        "};\n";
    h.close();

    vector<string> includes = extractIncludes(headerFile);

    assert(includes.size() == 0);

    cout << "testLifecycleSimple PASSED" << endl;
}

int main()
{
    testExtractIncludes();
    testInterfileSimple();
    testLifecycleSimple();

    cout << endl;
    cout << "ALL UNIT TESTS PASSED" << endl;

    return 0;
}
#include <iostream>
#include <pqxx/pqxx>
#include <cstdlib>

int main() {
    try {
        pqxx::connection conn("dbname=llm user=postgres password=postgres host=127.0.0.1 port=5432");

        std::cout << "CONNECTED TO POSTGRESQL\n";

        pqxx::work txn(conn);

        pqxx::result r = txn.exec(
            "SELECT id, file_path, description, severity "
            "FROM Findings "
            "WHERE status = 'new' "
            "LIMIT 5"
        );

        for (auto row : r) {
            std::cout << "ID: " << row["id"].c_str() << std::endl;
            std::cout << "File: " << row["file_path"].c_str() << std::endl;
            std::cout << "Desc: " << row["description"].c_str() << std::endl;
            std::cout << "Severity: " << row["severity"].c_str() << std::endl;
            std::cout << "----------------------\n";

            std::string code = row["description"].c_str();

            // команда запуска Python
            std::string command = "py \"C:\\Users\\katew\\source\\repos\\LLMAgent\\llm_test\\llm_agent.py\" \"" + code + "\"";

            std::cout << "RUNNING LLM...\n";
            system(command.c_str());
        }

        txn.commit();
    }
    catch (const std::exception& e) {
        std::cout << "ERROR: " << e.what() << std::endl;
    }

    return 0;
}
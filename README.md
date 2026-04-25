# LLM Code Analysis Agent

Прототип LLM-агента для автоматизированного анализа C++-кода.

## Состав проекта

- LLM/ — C++ модуль Visual Studio
- python/ — Python-оркестратор анализа
- database/ — SQL-скрипты для PostgreSQL

## База данных

Используется PostgreSQL.

Для создания таблиц выполнить:

```bash
psql -U postgres -d llm -f database/schema.sql
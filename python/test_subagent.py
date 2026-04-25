from subagent_runner import run_subagent

with open(
    r"C:\Users\katew\source\repos\LLM\LLM\LLM.cpp",
    "r",
    encoding="utf-8",
    errors="ignore"
) as f:
    code = f.read()

result = run_subagent(
    file_path="LLM.cpp",
    file_code=code,
    dependencies=[],
    symbols={"classes": [], "structs": [], "functions": []},
    diff_text=""
)

print("\n===== RESULT =====\n")
print(result)
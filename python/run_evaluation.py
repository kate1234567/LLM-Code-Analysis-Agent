def normalize_bug_name(name):
    return name.strip().lower()


def calculate_metrics(ground_truth, detected_bugs):
    gt_set = set(
        (file, normalize_bug_name(bug))
        for file, bug in ground_truth
    )

    detected_set = set(
        (item["file"], normalize_bug_name(item["bug"]))
        for item in detected_bugs
    )

    tp = len(gt_set & detected_set)
    fp = len(detected_set - gt_set)
    fn = len(gt_set - detected_set)

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0
    )

    return {
        "ground_truth": len(gt_set),
        "detected": len(detected_set),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
    }


ground_truth = [
    ("utils.h", "raw-pointer-interface-without-release"),
    ("utils.cpp", "manual-allocation-without-visible-release"),
    ("main.cpp", "unsafe-command-execution"),
    ("main.cpp", "unsafe-string-copy"),
    ("user.h", "raw-pointer-field-in-interface"),
]

detected_bugs = [
    {"file": "utils.h", "bug": "raw-pointer-interface-without-release"},
    {"file": "utils.cpp", "bug": "manual-allocation-without-visible-release"},
    {"file": "main.cpp", "bug": "unsafe-command-execution"},
    {"file": "main.cpp", "bug": "unsafe-string-copy"},
    {"file": "user.h", "bug": "raw-pointer-field-in-interface"},
]

result = calculate_metrics(
    ground_truth,
    detected_bugs
)

print("\n===== FINAL EVALUATION METRICS =====\n")

for key, value in result.items():
    print(f"{key}: {value}")
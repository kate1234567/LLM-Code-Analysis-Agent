def validate_finding(bug, ast_data=None, graph_data=None):
    confidence = 0.5

    bug_name = bug.get("bug", "").lower()

    if "pointer" in bug_name:
        confidence += 0.2

        if ast_data and ast_data.get("raw_pointer_fields_count", 0) > 0:
            confidence += 0.2

    if "interfile" in bug.get("finding_scope", ""):
        confidence += 0.2

        if graph_data and graph_data.get("reverse_dependencies_count", 0) > 0:
            confidence += 0.2

    if confidence > 1.0:
        confidence = 1.0

    bug["confidence_score"] = round(confidence, 2)

    if confidence < 0.6:
        bug["validation_status"] = "REQUIRES_MANUAL_CHECK"
    else:
        bug["validation_status"] = "VALIDATED"

    return bug
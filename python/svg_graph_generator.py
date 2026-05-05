from html import escape


def build_dependency_svg(graph):
    if not graph:
        return "<p>No dependency graph data.</p>"

    nodes = list(graph.keys())
    node_index = {node: idx for idx, node in enumerate(nodes)}

    width = 1000
    height = max(260, len(nodes) * 90 + 80)

    x_left = 80
    x_right = 620
    y_start = 60
    y_step = 90

    positions = {}

    for idx, node in enumerate(nodes):
        x = x_left if idx % 2 == 0 else x_right
        y = y_start + idx * y_step
        positions[node] = (x, y)

    svg_parts = []

    svg_parts.append(f"""
    <svg width="100%" height="{height}" viewBox="0 0 {width} {height}"
         xmlns="http://www.w3.org/2000/svg">
        <defs>
            <marker id="arrow" markerWidth="10" markerHeight="10"
                    refX="10" refY="3" orient="auto">
                <path d="M0,0 L10,3 L0,6 Z" fill="#374151" />
            </marker>
        </defs>
    """)

    for source, data in graph.items():
        includes = data.get("includes", []) if isinstance(data, dict) else []

        source_x, source_y = positions.get(source, (0, 0))

        for inc in includes:
            target = None

            for node in nodes:
                if node.endswith(inc) or node.endswith(inc.replace("/", "\\")):
                    target = node
                    break

            if not target:
                continue

            target_x, target_y = positions.get(target, (0, 0))

            svg_parts.append(f"""
            <line x1="{source_x + 220}" y1="{source_y + 25}"
                  x2="{target_x}" y2="{target_y + 25}"
                  stroke="#374151"
                  stroke-width="2"
                  marker-end="url(#arrow)" />
            """)

    for node in nodes:
        x, y = positions[node]
        label = node.replace("\\", "/").split("/")[-1]

        svg_parts.append(f"""
        <rect x="{x}" y="{y}" width="220" height="50"
              rx="10" ry="10"
              fill="#ffffff"
              stroke="#111827"
              stroke-width="2" />

        <text x="{x + 12}" y="{y + 30}"
              font-family="Arial"
              font-size="14"
              fill="#111827">
            {escape(label)}
        </text>
        """)

    svg_parts.append("</svg>")

    return "\n".join(svg_parts)
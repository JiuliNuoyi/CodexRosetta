from __future__ import annotations

from codex_rosetta.search.base import SearchResponse


def format_search_results(search_response: SearchResponse) -> str:
    if not search_response.results:
        return f"搜索 \"{search_response.query}\" 未返回任何结果。"

    lines = [f"搜索 \"{search_response.query}\" 的结果（共 {len(search_response.results)} 条）：\n"]

    for i, result in enumerate(search_response.results, 1):
        lines.append(f"{i}. {result.title}")
        lines.append(f"   {result.url}")
        if result.snippet:
            lines.append(f"   {result.snippet}")
        lines.append("")

    return "\n".join(lines)

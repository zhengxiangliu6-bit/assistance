"""搜索模块 - 使用 Bing 搜索，国内可用，无需 API Key。"""

import re
import requests
from html.parser import HTMLParser


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _clean_html(text: str) -> str:
    """去除 HTML 标签。"""
    return re.sub(r'<[^>]+>', '', text).strip()


def _parse_bing_results(html: str, max_results: int) -> list[dict]:
    """从 Bing HTML 中提取搜索结果。"""
    results = []
    # 找到 b_algo 列表项中的 h2 > a 链接
    # 使用非贪婪匹配找每个 b_algo 块
    pattern = r'<li class="b_algo">(.*?)(?=<li class="b_algo">|</ol>)'
    blocks = re.findall(pattern, html, re.DOTALL)

    if not blocks:
        # 备用：直接从 h2 中提取
        h2_pattern = r'<h2>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>\s*</h2>'
        matches = re.findall(h2_pattern, html, re.DOTALL)
        for url, title in matches[:max_results]:
            title = _clean_html(title)
            if title and not url.startswith('javascript:'):
                results.append({"title": title, "body": "", "href": url})
        return results

    for block in blocks[:max_results]:
        # 提取链接和标题
        link_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
        if not link_match:
            continue
        url = link_match.group(1)
        title = _clean_html(link_match.group(2))
        # 提取摘要 - 通常在 <p> 或 class="b_lineclamp" 中
        desc = ""
        desc_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        if desc_match:
            desc = _clean_html(desc_match.group(1))
        if not desc:
            desc_match = re.search(r'class="[^"]*lineclamp[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
            if desc_match:
                desc = _clean_html(desc_match.group(1))

        if title and not url.startswith('javascript:'):
            results.append({"title": title, "body": desc, "href": url})

    return results


def web_search(query: str, max_results: int = 5) -> str:
    """通过 Bing 搜索网页。"""
    try:
        resp = requests.get(
            "https://cn.bing.com/search",
            params={"q": query, "count": str(max_results + 3)},
            headers=_HEADERS,
            timeout=10,
        )
        resp.encoding = "utf-8"
        resp.raise_for_status()

        results = _parse_bing_results(resp.text, max_results)

        if not results:
            return f"[失败] 未找到与 '{query}' 相关的结果。"

        lines = [f"[成功] 搜索: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            if r['body']:
                lines.append(f"   {r['body'][:150]}")
            lines.append(f"   链接: {r['href']}")
            lines.append("")
        return "\n".join(lines)
    except requests.Timeout:
        return "[失败] 搜索超时，请稍后再试。"
    except Exception as e:
        return f"[失败] 搜索出错: {e}"


def news_search(query: str, max_results: int = 5) -> str:
    """通过 Bing 搜索新闻。"""
    try:
        resp = requests.get(
            "https://cn.bing.com/news/search",
            params={"q": query},
            headers=_HEADERS,
            timeout=10,
        )
        resp.encoding = "utf-8"
        resp.raise_for_status()
        html = resp.text

        results = []
        # 提取新闻标题
        title_pattern = r'<a[^>]*class="[^"]*title[^"]*"[^>]*[^>]*>(.*?)</a>'
        matches = re.findall(title_pattern, html, re.DOTALL)
        for m in matches[:max_results]:
            title = _clean_html(m)
            if title:
                results.append({"title": title})

        if not results:
            # 备用：h2 + a
            h2_pattern = r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
            for url, title in re.findall(h2_pattern, html, re.DOTALL):
                title = _clean_html(title)
                if title and len(title) > 8 and 'bing.com' not in url:
                    results.append({"title": title})
                    if len(results) >= max_results:
                        break

        if not results:
            return f"[失败] 未找到与 '{query}' 相关的新闻。"

        lines = [f"[成功] 新闻: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
        return "\n".join(lines)
    except requests.Timeout:
        return "[失败] 新闻搜索超时。"
    except Exception as e:
        return f"[失败] 新闻搜索出错: {e}"

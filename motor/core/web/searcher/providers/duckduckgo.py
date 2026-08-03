def _parse_results(html: str) -> list[dict[str, str]]:
    """Parsea resultados de la página HTML de DuckDuckGo."""
    results = []
    titles = re.findall(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
    urls = re.findall(r'<a[^>]+class="result__url"[^>]*href="([^"]+)"', html)
    snippets = re.findall(r'<a[^>]+class<｜begin▁of▁sentence｜>class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

    for i in range(max(len(titles), len(urls), len(snippets))):
        title = re.sub(r"<[^>]+>", "", titles[i]) if i < len(titles) else ""
        url = urls[i] if i < len(urls) else ""
        snippet = re.sub(r"<[^>]+>", "", snippets[i]) if i < len(snippets) else ""
        if title and url:
            results.append(
                {
                    "title": title.strip(),
                    "url": url.strip(),
                    "snippet": snippet.strip(),
                }
            )  # Agregue una coma aquí
    return results

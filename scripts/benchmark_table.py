"""Render the README benchmark table without relying on GitHub inline CSS."""
import re
from html import escape


def render_svg(headers, rows, title):
    widths = [210] + [110] * (len(headers) - 1)
    header_height, row_height, pad = 46, 42, 2
    width = sum(widths) + 2 * pad
    height = header_height + len(rows) * row_height + 2 * pad

    def plain(cell):
        cell = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', cell).replace('**', '')
        return re.sub(r'\$\\color\{green\}\{([^}]+)\}\$', r'\1', cell)

    description = '; '.join(': '.join([plain(row[0]), ', '.join(
        f'{plain(name)} {plain(value)}' for name, value in zip(headers[1:], row[1:]))])
        for row in rows)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
           f'<title id="title">{escape(title)}</title>',
           f'<desc id="description">{escape(description)}</desc>',
           '''<style>
text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 14px; fill: #1f2328; font-variant-numeric: tabular-nums; }
.background { fill: #ffffff; }
.heading { fill: #f6f8fa; }
.grid { fill: none; stroke: #d1d9e0; stroke-width: 1; }
.best { fill: #1a7f37; }
.focus { fill: none; stroke: #0969da; stroke-width: 2; }
@media (prefers-color-scheme: dark) {
  text { fill: #f0f6fc; }
  .background { fill: #0d1117; }
  .heading { fill: #161b22; }
  .grid { stroke: #3d444d; }
  .best { fill: #3fb950; }
  .focus { stroke: #58a6ff; }
}
</style>''',
           f'<rect class="background" x="{pad}" y="{pad}" width="{sum(widths)}" height="{height-2*pad}"/>',
           f'<rect class="heading" x="{pad}" y="{pad}" width="{sum(widths)}" height="{header_height}"/>',
           f'<rect class="grid" x="{pad}" y="{pad}" width="{sum(widths)}" height="{height-2*pad}"/>']
    x = pad
    for cell_width in widths[:-1]:
        x += cell_width
        svg.append(f'<path class="grid" d="M{x} {pad} V{height-pad}"/>')
    for index in range(len(rows)):
        y = pad + header_height + index * row_height
        svg.append(f'<path class="grid" d="M{pad} {y} H{width-pad}"/>')
    for r, row in enumerate([headers, *rows]):
        y = pad + header_height / 2 if r == 0 else pad + header_height + (r - .5) * row_height
        x = pad
        for c, (cell, cell_width) in enumerate(zip(row, widths)):
            anchor = 'start' if c == 0 else 'middle' if r == 0 else 'end'
            tx = x + 16 if c == 0 else x + cell_width / 2 if r == 0 else x + cell_width - 16
            best = ' class="best"' if r'\color{green}' in cell else ''
            weight = ' font-weight="700"' if c == 1 and r == 0 else ' font-weight="600"' if r == 0 else ''
            svg.append(f'<text x="{tx:g}" y="{y+5:g}" text-anchor="{anchor}"{best}{weight}>{escape(plain(cell))}</text>')
            x += cell_width
    # A single outline encloses the full Pareto column; inner rules stay neutral.
    svg.append(f'<rect class="focus" x="{pad+widths[0]}" y="{pad}" width="{widths[1]}" height="{height-2*pad}"/>')
    return '\n'.join([*svg, '</svg>', ''])

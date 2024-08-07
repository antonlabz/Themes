#!/usr/bin/python3

import os
import json
import math
import hashlib
import shutil
from typing import Callable
from tqdm import tqdm

from string import Template

from defs import *

from utils import get_files, get_lines, get_subdirs, urlencode, git_last_changed, git_commit_count, datetime
from validation import validate_theme
from generate_icons import generate_icon_pack_table, get_ordered_icons, IconPack, generate_icon_pack_url, icons_blacklist


themes_featured = []
themes_icon_packs = []

recently_added = []
recently_updated = []


def main():
    global themes_featured

    if not os.path.exists(RELEASE_DIR):
        print("No themes released")
        return
    
    shutil.rmtree(PAGES_DIR)

    print("Generating READMEs...")

    released_themes = [
        os.path.splitext(file)[0]
        for file in get_files(RELEASE_DIR, "zip")]
    is_released = lambda theme: theme in released_themes

    themes_featured = list(filter(is_released, get_lines(FEATURED_ORDERING)))

    themes_custom = list(filter(is_released, get_lines(CUSTOM_ORDERING)))
    themes_custom.reverse()

    themes_remixed = list(filter(is_released, get_lines(REMIXED_ORDERING)))
    themes_remixed.reverse()

    standalone_icon_packs = get_ordered_icons()

    os.makedirs(PAGES_DIR, exist_ok=True)

    write_pages(themes_custom, "custom", generate_table_grid)
    write_pages(themes_remixed, "remixed", generate_table_grid)
    
    write_pages(themes_icon_packs, "icons_themes", generate_icon_pack_table)
    write_pages(standalone_icon_packs, "icons_standalone", generate_icon_pack_table)

    write_file(README_PATH, generate_index({
        "custom": len(themes_custom),
        "remixed": len(themes_remixed),
        "icons_themes": len(themes_icon_packs),
        "icons_standalone": len(standalone_icon_packs)
    }))

    print("Done")


def write_file(path: str, buffer: str):
    with open(path, "w+", encoding="utf-8") as outfile:
        outfile.write(WARN_GENERATED_FILE + buffer)


def apply_template(path: str, data: dict) -> str:
    with open(path, "r", encoding="utf-8") as file:
        template = Template(file.read())
    return template.substitute(data) + "\n"


def format_page_filename(page: int, num_pages: int) -> str:
    prefix = f"{num_pages - page:02}"
    page_hash = hashlib.shake_128(prefix.encode("utf-8")).hexdigest(2)
    return "index.md" if page == 0 else f"index-{prefix}-{page_hash[:2]}.md"


def generate_index(counts: dict):
    return apply_template(INDEX_TEMPLATE, {
        "HEADER": apply_template(HEADER_TEMPLATE, { "LINKS": generate_header_links(".", current_group="index") }),
        "INDEX": generate_index_list(counts),
        "THEMES_NEW": generate_recents_grid(recently_added),
        "THEMES_RECENTS": generate_recents_grid(recently_updated)
    })


def generate_index_list(counts: dict) -> str:
    buffer = ""
    for group_name, count in counts.items():
        _, link = HEADER_LINKS[group_name]
        buffer += f"### [{PAGE_TITLES[group_name]} ({count})]({rel_path(link, '.')})\n\n"
    return buffer


def generate_recents_grid(items: list[dict]) -> str:
    items.sort(key=lambda item: item["ts"], reverse=True)
    return apply_template(GRID_TEMPLATE, {"GRID_ITEMS": "\n\n".join(generate_item(item["theme"]) for item in items[:MAX_RECENTS])})


def write_pages(items: list, group_name: str, item_grid_generator: Callable[[list], str], page_size: int = 12, **opts):
    workdir = os.path.join(PAGES_DIR, group_name)
    os.makedirs(workdir, exist_ok=True)

    total = len(items)
    num_pages = math.ceil(total / page_size)

    for page in tqdm(range(num_pages), desc=PAGE_TITLES[group_name]):
        current_path = os.path.join(workdir, format_page_filename(page, num_pages))

        index = page * page_size
        batch = items[index  : index + page_size]
        
        buffer = ""
        buffer += apply_template(HEADER_TEMPLATE, { "LINKS": generate_header_links(current_path, current_group=group_name) })
        buffer += f"\n## {PAGE_TITLES[group_name]}\n\n*Page {page + 1} of {num_pages} — {total} items available*\n"
        buffer += item_grid_generator(batch, **opts) + "\n\n"

        if num_pages > 1:
            buffer += generate_pagination(page, num_pages)

        write_file(current_path, buffer)


def generate_header_links(current_path: str, current_group: str = None):
    links = []
    for group_name, [ text, link ] in HEADER_LINKS.items():
        if group_name == current_group:
            links.append(f"**{text}**")
        else:
            links.append(f"[{text}]({rel_path(link, current_path)})")
    return f"{LB_SPACER}•{LB_SPACER}".join(links)


def generate_pagination(current_page: int, num_pages: int) -> str:
    buffer = ""
    buffer += """---\n\n<table align="center"><tr>"""
    if current_page > 0:
        buffer += f"""<td align="right">\n\n[![Previous page]({PREV_PAGE_ICON_URL})]({format_page_filename(current_page - 1, num_pages)})\n\n</td>"""
    buffer += f"""<td align="center" valign="middle">\n\n{generate_page_links(current_page, num_pages)}\n\n</td>"""
    if current_page < num_pages - 1:
        buffer += f"""<td>\n\n[![Next page]({NEXT_PAGE_ICON_URL})]({format_page_filename(current_page + 1, num_pages)})\n\n</td>"""
    buffer += "</tr></table>"
    return buffer


def generate_page_links(current_page: int, num_pages: int) -> str:
    if num_pages <= 9:
        return generate_page_link_range(range(num_pages), current_page, num_pages)
    
    last_page = num_pages - 1
    cutoff = 5
    half_cut = math.floor(cutoff / 2)
    ellipsis = "&hellip;"

    is_low = current_page < cutoff
    is_high = current_page > last_page - cutoff
    
    buffer = ""
    buffer += generate_page_link(0, current_page, num_pages)
    buffer += " " + generate_page_link_range(range(1, cutoff + 2), current_page, num_pages) if is_low else NB_SPACE + ellipsis
    buffer += " " if is_low or is_high \
        else LB_SPACER + generate_page_link_range(range(current_page - half_cut, current_page + half_cut + 1), current_page, num_pages) + " "
    buffer += generate_page_link_range(range(last_page - cutoff - 1, last_page), current_page, num_pages) + " " if is_high else ellipsis + NB_SPACE
    buffer += generate_page_link(last_page, current_page, num_pages)
    return buffer


def generate_page_link_range(rng: range, current_page: int, num_pages: int) -> str:
    return " ".join(generate_page_link(page, current_page, num_pages) for page in rng)


def generate_page_link(page: int, current_page: int, num_pages: int) -> str:
    return f"{NB_SPACE}**{page + 1}**{NB_SPACE}" if page == current_page else f"[{NB_SPACE}{page + 1}{NB_SPACE}]({format_page_filename(page, num_pages)})"


def generate_table_grid(themes) -> str:
    buffer = ""

    for i, theme in enumerate(themes):
        if i > 0 and i % THEMES_COLS == 0:
            buffer += "</tr><tr>\n"
        buffer += generate_item(theme, index=i, collect_data=True)

    return apply_template(GRID_TEMPLATE, {"GRID_ITEMS": buffer})


def generate_item(theme: str, index: int = 0, collect_data: bool = False) -> str:
    dir_path = os.path.join(THEME_DIR, theme)
    is_valid, has_subdirs = validate_theme(dir_path)

    if not is_valid:
        print(f"  invalid theme: {theme}")
        return ""

    name_split = theme.split(" by ", maxsplit=1)
    name = name_split[0]
    author = name_split[1] if len(name_split) > 1 else ""
    description = ""

    is_featured = theme in themes_featured

    if not has_subdirs:
        with open(os.path.join(dir_path, "config.json"), "r", encoding="utf-8") as infile:
            config = json.load(infile)
        if "name" in config:
            name = config["name"]
        if "author" in config:
            author = config["author"]
        if "description" in config:
            description = config["description"]

    theme_subdirs = [f"themes/{theme}/{subdir}" for subdir in get_subdirs(dir_path)] if has_subdirs else [f"themes/{theme}"]

    if os.path.exists(f"themes/{theme}/preview.png"):
        preview_url = f"https://raw.githubusercontent.com/OnionUI/Themes/main/themes/{urlencode(theme)}/preview.png"
    else:
        preview_url = f"https://raw.githubusercontent.com/OnionUI/Themes/main/{urlencode(theme_subdirs[0])}/preview.png"
    release_url = f"https://raw.githubusercontent.com/OnionUI/Themes/main/release/{urlencode(theme)}.zip"
    history_url = f"https://github.com/OnionUI/Themes/commits/main/themes/{theme}"

    last_changed_datetime = git_last_changed(dir_path)
    last_updated = last_changed_datetime.strftime("%Y-%m-%d") if last_changed_datetime else ""
    commit_count = git_commit_count(dir_path)

    bgm_path = from_src(f"../{theme_subdirs[0]}/sound/bgm.mp3")
    has_bgm = os.path.isfile(bgm_path)

    has_icon_pack = any(os.path.isdir(f"{subdir}/icons") for subdir in theme_subdirs)
    
    readme_path = ""

    for readme_file in README_TEST:
        for subdir in theme_subdirs:
            readme_path = os.path.join(subdir, readme_file)
            if os.path.isfile(readme_path):
                break
            readme_path = ""
        if readme_path != "":
            break

    title = ""
    if name:
        title += f"Name: {name}&#013;"
    if author:
        title += f"Author: {author}&#013;"
    if last_updated:
        title += f"Last updated: {last_updated}&#013;"
    if description:
        title += f"Description: {description}&#013;"
    if is_featured:
        title += "Tags: [featured theme]&#013;"
    title += "(Click to download)"

    item = {
        "NAME": name + " ★" if is_featured else name,
        "AUTHOR": author or "&nbsp;",
        "TITLE": title,
        "HAS_BGM": f"{NB_SPACER}<a href=\"https://onionui.github.io/bgm_preview.html?theme={urlencode(theme_subdirs[0][7:])}\">{BGM_ICON}</a>" if has_bgm else "",
        "HAS_ICONPACK": f"{LB_SPACER}<a href=\"{generate_icon_pack_url(theme, theme_subdirs)}\">{HAS_ICONPACK_ICON}</a>" if has_icon_pack else "",
        "README": f"{NB_SPACER}<a href=\"{urlencode(readme_path)}\">{README_ICON}</a>" if len(readme_path) != 0 else "",
        "AUTHOR_BTN": f"{NB_SPACER}<a href=\"https://github.com/search?l=ZIP&q=filename%3A%22{urlencode(author)}%22+repo%3AOnionUI%2FThemes\">{AUTHOR_ICON}</a>" if author else "",
        "UPDATED": f"{last_updated} (v{commit_count})" if commit_count > 1 else last_updated,
        "PREVIEW_URL": preview_url,
        "RELEASE_URL": release_url,
        "HISTORY_URL": history_url,
        "COLUMN_SPANNER": THEMES_COLUMN_SPANNER if index < THEMES_COLS else "",
        "COLUMN_WIDTH": f"{100 / THEMES_COLS:.2f}%"
    }

    if collect_data:
        if has_icon_pack:
            valid_subdirs = [subdir for subdir in theme_subdirs if os.path.isdir(f"{subdir}/icons") and os.path.basename(subdir) not in icons_blacklist]
            themes_icon_packs.extend(IconPack(
                        dir_name=os.path.basename(subdir),
                        dir_path=os.path.join(subdir, "icons"),
                        theme=theme,
                        release_url=release_url,
                        theme_subdir=subdir)
                        for subdir in valid_subdirs)
        if last_changed_datetime:
            if commit_count <= 1:
                recents_maybe_append(recently_added, last_changed_datetime, theme)
            else:
                recents_maybe_append(recently_updated, last_changed_datetime, theme)

    return apply_template(ITEM_TEMPLATE, item)


def recents_maybe_append(recents: list[dict], timestamp: datetime, theme: str):
    if len(recents) < MAX_RECENTS or any(timestamp > item["ts"] for item in recents):
        recents.append({"ts": timestamp, "theme": theme})


if __name__ == "__main__":
    main()

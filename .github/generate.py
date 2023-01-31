#!/usr/bin/python3

import os
import json
import subprocess
import base64
from datetime import datetime
from urllib.parse import quote as _quote

from string import Template

from defs import (
    from_src,
    SRC_DIR,
    THEME_DIR,
    RELEASE_DIR,
    FEATURED_ORDERING,
    REMIXED_ORDERING,
    CUSTOM_ORDERING)

from utils import get_files, get_ordering, get_subdirs
from validation import validate_theme

README_PATH = from_src("../README.md")
README_TEMPLATE = from_src("template/README.template.md")
GRID_TEMPLATE = from_src("template/grid.template.html")
ITEM_TEMPLATE = from_src("template/item.template.html")

BGM_ICON_URL = "https://user-images.githubusercontent.com/44569252/194010780-d3659ecd-7348-4e44-a81d-06708a4e9734.png"
BGM_ICON = f"<img src=\"{BGM_ICON_URL}\" width=\"16\" title=\"Custom background music included (Click to download MP3 file)\">"

AUTHOR_ICON_URL = "https://user-images.githubusercontent.com/44569252/194037581-698a5004-8b75-4da6-a63d-b41d541ebde2.png"
AUTHOR_ICON = f"<img src=\"{AUTHOR_ICON_URL}\" width=\"16\" title=\"Search themes by this author (Requires GitHub account)\">"

HAS_ICONPACK_ICON_URL = "https://user-images.githubusercontent.com/44569252/215106002-fbcf1815-8080-447c-94c2-61f161efb503.png"
HAS_ICONPACK_ICON = f"<img src=\"{HAS_ICONPACK_ICON_URL}\" height=\"16\" title=\"This theme contains an icon pack\">"

README_ICON_URL = "https://user-images.githubusercontent.com/44569252/215358455-b6a1348b-8161-40d6-9cc1-cc31720377c4.png"
README_ICON = f"<img src=\"{README_ICON_URL}\" height=\"16\" title=\"README\">"

PREVIEW_ICON = f"<img src=\"{HAS_ICONPACK_ICON_URL}\" height=\"16\" title=\"Show full preview\">"

README_TEST = ["readme.md", "README.md", "readme.txt", "README.txt"]
REL_PATH = os.path.abspath(os.path.join(SRC_DIR, ".."))

COLUMNS = 3

urlencode = lambda s: _quote(s, safe="/?&=_-")


themes_with_icon_packs = []


def main():
    if not os.path.exists(RELEASE_DIR):
        print("No themes released")
        return

    print("Generating README...")

    released_themes = [
        os.path.splitext(file)[0]
        for file in get_files(RELEASE_DIR, "zip")]
    is_released = lambda theme: theme in released_themes

    custom = list(filter(is_released, get_ordering(CUSTOM_ORDERING)))
    featured = list(filter(is_released, get_ordering(FEATURED_ORDERING)))
    remixed = list(filter(is_released, get_ordering(REMIXED_ORDERING)))

    custom.reverse()
    featured.reverse()
    remixed.reverse()

    values = {
        "CUSTOM_THEMES": generate_table_grid(custom, True),
        "FEATURED_THEMES": generate_table_grid(featured),
        "REMIXED_THEMES": generate_table_grid(remixed, True),
        "ICON_PACKS": generate_icon_pack_overview()
    }

    with open(README_TEMPLATE, "r", encoding="utf-8") as infile:
        template = Template(infile.read())

    buffer = ("<!--" + ("!" * 56) + "\n" + ("\n" * 20) + "DO NOT EDIT THIS FILE!\n\n\nTHIS DOCUMENT WAS AUTOMATICALLY GENERATED\nRun the script `.github/generate.py` to remake this page.\n" + ("\n" * 20) + ("!" * 57) + "-->\n\n")

    buffer += template.substitute(values)

    with open(README_PATH, "w+", encoding="utf-8") as outfile:
        outfile.write(buffer)

    print("Done")


def generate_table_grid(themes, index_icon_packs: bool = False) -> str:
    buffer = ""

    for i, theme in enumerate(themes):
        if i > 0 and i % COLUMNS == 0:
            buffer += "</tr><tr>\n"
        buffer += generate_item(theme, index_icon_packs)

    with open(GRID_TEMPLATE, "r", encoding="utf-8") as file:
        template = Template(file.read())

    return template.substitute({"GRID_ITEMS": buffer}) + "\n"


def generate_item(theme: str, index_icon_packs: bool) -> str:
    dir_path = os.path.join(THEME_DIR, theme)
    is_valid, has_subdirs = validate_theme(dir_path)

    if not is_valid:
        print(f"  invalid theme: {theme}")
        return ""

    title = ""
    name_split = theme.split(" by ", maxsplit=1)
    name = name_split[0]
    author = name_split[1] if len(name_split) > 1 else ""

    if not has_subdirs:
        with open(os.path.join(dir_path, "config.json"), "r", encoding="utf-8") as infile:
            config = json.load(infile)
        if "name" in config:
            name = config["name"]
        if "author" in config:
            author = config["author"]
        if "description" in config:
            title = config["description"]

    if not title:
        title = f"{name} by {author}" if author else name

    theme_subdirs = [f"themes/{theme}/{subdir}" for subdir in get_subdirs(dir_path)] if has_subdirs else [f"themes/{theme}"]

    if os.path.exists(f"themes/{theme}/preview.png"):
        preview_url = f"themes/{urlencode(theme)}/preview.png?raw=true"
    else:
        preview_url = f"{urlencode(theme_subdirs[0])}/preview.png?raw=true"
    release_url = f"release/{urlencode(theme)}.zip?raw=true"
    history_url = f"https://github.com/OnionUI/Themes/commits/main/themes/{theme}"

    git_result = subprocess.run(
        ["git", "log", "-1", "--pretty=%cI", dir_path],
        stdout=subprocess.PIPE, check=True)
    datestr = git_result.stdout.decode('utf-8').strip()
    last_updated = datetime.fromisoformat(datestr).strftime("%Y-%m-%d") if datestr else ""

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

    item = {
        "NAME": name,
        "AUTHOR": author or "&nbsp;",
        "TITLE": title,
        "HAS_BGM": f"&nbsp;&nbsp;<a href=\"{urlencode(theme_subdirs[0])}/sound/bgm.mp3?raw=true\">{BGM_ICON}</a>" if has_bgm else "",
        "HAS_ICONPACK": f"&nbsp; <a href=\"{generate_icon_pack_url(theme, theme_subdirs)}\">{HAS_ICONPACK_ICON}</a>" if has_icon_pack else "",
        "README": f"&nbsp;&nbsp;<a href=\"{urlencode(readme_path)}\">{README_ICON}</a>" if len(readme_path) != 0 else "",
        "AUTHOR_BTN": f"&nbsp;&nbsp;<a href=\"https://github.com/search?l=ZIP&q=filename%3A%22{urlencode(author)}%22+repo%3AOnionUI%2FThemes\">{AUTHOR_ICON}</a>" if author else "",
        "UPDATED": last_updated,
        "PREVIEW_URL": preview_url,
        "RELEASE_URL": release_url,
        "HISTORY_URL": history_url
    }

    if has_icon_pack and index_icon_packs:
        for subdir in theme_subdirs:
            if os.path.isdir(f"{subdir}/icons"):
                themes_with_icon_packs.append({
                    "name": os.path.basename(subdir),
                    "path": os.path.join(subdir, "icons"),
                    "is_theme": True,
                    "theme": theme,
                    "release_url": release_url,
                    "preview_url": generate_icon_pack_url(theme, [subdir])
                })

    with open(ITEM_TEMPLATE, "r", encoding="utf-8") as file:
        template = Template(file.read())

    return template.substitute(item) + "\n"


def generate_icon_pack_url(theme: str, theme_subdirs: list[str]) -> str:
    icons_dirs = [f"{subdir}/icons" for subdir in theme_subdirs if os.path.isdir(f"{subdir}/icons")]

    url = f"https://onionui.github.io/iconpack_preview.html#{urlencode(theme)},"
    url += ",".join(f"{urlencode(os.path.basename(os.path.dirname(icons_dir)))}:{urlencode(icons_dir)}" for icons_dir in icons_dirs)

    return url


PREVIEW_ICONS = ["atari", "fc", "gb", "gba", "gbc", "md", "ms", "neogeo", "ps", "sfc"]
ALL_ICONS = ['32X', '5200', '7800', 'amiga', 'arcade', 'atari', 'atarist', 'c64', 'col', 'cpc', 'cps1', 'cps2', 'cps3', 'dos', 'fairchild', 'fc', 'fds', 'gb', 'gba', 'gbc', 'gg', 'gw', 'itv', 'lynx', 'md', 'megaduck', 'ms', 'msx', 'neocd', 'neogeo', 'ngp', 'ody', 'pce', 'pcecd', 'pico', 'poke', 'ports', 'ps', 'satella', 'scummvm', 'search', 'segacd', 'segasgone', 'sfc', 'sgb', 'sgfx', 'sufami', 'supervision', 'tic', 'vb', 'vdp', 'vectrex', 'ws', 'zxs']


def generate_icon_pack_overview():
    output = ""

    icon_packs = []

    for dir_name in os.listdir("icons"):
        dir_path = os.path.join("icons", dir_name)
        release_url = os.path.join("release", dir_path + ".zip")

        if not os.path.isfile(release_url):
            release_url = ""

        icon_packs.append({
            "name": dir_name,
            "path": dir_path,
            "release_url": f"{urlencode(release_url)}?raw=true",
            "preview_url": f"https://onionui.github.io/iconpack_preview.html#{urlencode(dir_name)}"
        })

    output += "### Standalone Icon Packs\n\nCheck out these standalone icon packs!\n\n> To install, extract to `Themes/icons/` on your SD card (icon switching will be available in V4.1)\n\n"
    output += generate_icon_pack_table(icon_packs)

    output += "### Theme Icon Packs\n\nCheck out these icon packs included in themes!\n\n> To install, extract the theme to `Themes/` on your SD card (icon switching will be available in V4.1)\n\n"
    output += generate_icon_pack_table(themes_with_icon_packs)

    return output


def generate_icon_pack_table(icon_packs):
    output = "<table align=center><tr>\n\n"
    
    for i, icon_pack in enumerate(icon_packs):
        if i > 0 and i % COLUMNS == 0:
            output += "</tr><tr>\n"
        output += generate_icon_pack_entry(**icon_pack)

    output += "</tr></table>\n\n"

    return output


def generate_icon_pack_entry(name, path, release_url, preview_url, is_theme: bool = False, theme: str = ""):
    output = ""

    output += f"<td>\n\n#### {name}\n\n"

    if len(release_url) != 0:
        dn_text = f"Download {theme} (theme)" if is_theme else f"Download {name} (icon pack)"
        output += f"[{dn_text}]({release_url})\n\n"

    for icon in PREVIEW_ICONS:
        icon_path = f"{path}/{icon}.png"
        if os.path.isfile(icon_path):
            output += f"<img src=\"{urlencode(icon_path)}\" width=\"64px\" title=\"{icon}\">"

    output += "\n\n"

    readme_path = ""

    for readme_file in README_TEST + [f"../{fn}" for fn in README_TEST]:
        readme_path = os.path.abspath(from_src(os.path.join("..", path, readme_file)))
        if os.path.isfile(readme_path):
            readme_path = readme_path[len(REL_PATH):]
            break
        readme_path = ""

    readme = f"<a href=\"{urlencode(readme_path)}\">{README_ICON}</a> &nbsp;&nbsp; " if len(readme_path) != 0 else ""

    icon_count = sum(os.path.isfile(f"{path}/{icon}.png") for icon in ALL_ICONS)
    output += f"<sub><sup>{icon_count}/{len(ALL_ICONS)} icons ({round(icon_count/len(ALL_ICONS)*100)}% complete)</sup> &nbsp;&nbsp; {readme}<a href=\"{preview_url}\">{PREVIEW_ICON}</a></sub>"

    output += "\n\n</td>\n\n"

    return output


if __name__ == "__main__":
    main()

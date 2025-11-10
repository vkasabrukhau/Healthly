#!/usr/bin/env python3
"""
Offline scraper for Duke's NetNutrition portal.

The script mirrors the AJAX traffic that powers https://netnutrition.cbord.com/nn-prod/Duke
and emits a hierarchical JSON artifact that can be fed into downstream LLM tooling.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

BASE_URL = "https://netnutrition.cbord.com/nn-prod/Duke"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json",
}
POST_HEADERS = {
    **HEADERS,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

IGNORE_UNITS = {
    "cafe",
    "duke marine lab",
    "freeman cafe",
    "nasher museum cafe",
    "trinity cafe",
    "marketplace",
}

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def normalize_label(value: str) -> str:
    """Normalize labels so we can safely deduplicate or compare names."""
    nfkd = unicodedata.normalize("NFKD", value or "")
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return ascii_only.strip().lower()


class HTMLNode:
    """Lightweight DOM node to help with structural parsing."""

    __slots__ = ("tag", "attrs", "parent", "children", "text_parts")

    def __init__(self, tag: str, attrs: Dict[str, str], parent: Optional["HTMLNode"] = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: List["HTMLNode"] = []
        self.text_parts: List[str] = []

    # Traversal helpers -------------------------------------------------
    def append_child(self, node: "HTMLNode") -> None:
        self.children.append(node)

    def add_text(self, data: str) -> None:
        self.text_parts.append(data)

    def class_list(self) -> List[str]:
        klass = self.attrs.get("class", "")
        return [part for part in klass.replace(",", " ").split() if part]

    def text(self, strip: bool = True) -> str:
        parts = list(self.text_parts)
        for child in self.children:
            parts.append(child.text(False))
        combined = "".join(parts)
        return " ".join(combined.split()) if strip else combined

    # Query helpers -----------------------------------------------------
    def iter(self) -> Iterable["HTMLNode"]:
        yield self
        for child in self.children:
            yield from child.iter()

    def find_all(
        self,
        tag: Optional[str] = None,
        predicate: Optional[Callable[["HTMLNode"], bool]] = None,
    ) -> List["HTMLNode"]:
        matches = []
        for node in self.iter():
            if tag and node.tag != tag:
                continue
            if predicate and not predicate(node):
                continue
            matches.append(node)
        return matches

    def find_first(
        self,
        tag: Optional[str] = None,
        predicate: Optional[Callable[["HTMLNode"], bool]] = None,
    ) -> Optional["HTMLNode"]:
        for node in self.iter():
            if tag and node.tag != tag:
                continue
            if predicate and not predicate(node):
                continue
            return node
        return None


class HTMLTreeBuilder(HTMLParser):
    """Minimal HTML parser that builds a DOM we can traverse."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HTMLNode("document", {})
        self._stack: List[HTMLNode] = [self.root]

    # HTMLParser overrides ----------------------------------------------
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attrs_dict = {name: (value or "") for name, value in attrs}
        parent = self._stack[-1]
        node = HTMLNode(tag, attrs_dict, parent)
        parent.append_child(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        # Pop to the most recent matching tag; HTML fragments can be uneven.
        for idx in range(len(self._stack) - 1, 0, -1):
            if self._stack[idx].tag == tag:
                self._stack = self._stack[: idx]
                return

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if not data:
            return
        self._stack[-1].add_text(data)


def parse_html(html_text: str) -> HTMLNode:
    builder = HTMLTreeBuilder()
    builder.feed(html_text or "")
    return builder.root


def find_node_by_id(root: HTMLNode, element_id: str) -> Optional[HTMLNode]:
    return root.find_first(predicate=lambda node: node.attrs.get("id") == element_id)


@dataclass
class UnitOption:
    name: str
    unit_id: int


@dataclass
class DateOption:
    label: str
    token: str


@dataclass
class MealOption:
    label: str
    meal_id: int


def extract_unit_options(root: HTMLNode) -> List[UnitOption]:
    container = find_node_by_id(root, "nav-unit-selector")
    if not container:
        return []
    options = []
    for link in container.find_all(tag="a"):
        try:
            unit_id = int(link.attrs.get("data-unitoid", "-1"))
        except ValueError:
            continue
        label = unescape(link.text()).strip()
        if unit_id >= 0 and label and normalize_label(label) not in IGNORE_UNITS and label.lower() != "show all units":
            options.append(UnitOption(label, unit_id))
    return options


def extract_date_options(root: HTMLNode) -> List[DateOption]:
    container = find_node_by_id(root, "nav-date-selector")
    if not container:
        return []
    options: List[DateOption] = []
    for link in container.find_all(tag="a"):
        raw = link.attrs.get("data-date", "").strip()
        label = unescape(link.text()).strip()
        if not raw or label.lower() == "show all dates":
            continue
        options.append(DateOption(label, raw))
    return options


def extract_meal_options(root: HTMLNode) -> List[MealOption]:
    container = find_node_by_id(root, "nav-meal-selector")
    if not container:
        return []
    seen = set()
    options: List[MealOption] = []
    for link in container.find_all(tag="a"):
        try:
            meal_id = int(link.attrs.get("data-mealoid", "-1"))
        except ValueError:
            continue
        label = unescape(link.text()).strip()
        if meal_id < 0 or label.lower() == "show all meals":
            continue
        if meal_id in seen:
            continue
        seen.add(meal_id)
        options.append(MealOption(label, meal_id))
    return options


class NetNutritionClient:
    """HTTP helper that handles cookies and mirrors NetNutrition AJAX calls."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookiejar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookiejar))

    def _make_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not path:
            return self.base_url
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get(self, path: str = "", timeout: int = 60) -> str:
        request = Request(self._make_url(path), headers=HEADERS)
        with self.opener.open(request, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def post_json(self, path: str, payload: Dict[str, str], timeout: int = 60) -> Dict:
        data = urlencode(payload).encode("utf-8")
        request = Request(self._make_url(path), data=data, headers=POST_HEADERS)
        with self.opener.open(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        return json.loads(raw)

    def post_html(self, path: str, payload: Dict[str, str], timeout: int = 60) -> str:
        data = urlencode(payload).encode("utf-8")
        request = Request(self._make_url(path), data=data, headers=POST_HEADERS)
        with self.opener.open(request, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")


class NutritionParser:
    """Parse the HTML nutrition label returned by NetNutrition."""

    def parse(self, label_html: str) -> Dict:
        root = parse_html(label_html)
        label_container = root.find_first(predicate=lambda node: node.attrs.get("id") == "nutritionLabel")
        if not label_container:
            return {}

        result: Dict[str, object] = {
            "servings_per_container": None,
            "serving_size": None,
            "calories": None,
            "nutrients": [],
            "ingredients": {"text": "", "list": []},
        }

        servings_div = label_container.find_first(
            tag="div", predicate=lambda node: "cbo_nn_LabelBottomBorderLabel" in node.class_list()
        )
        if servings_div:
            spans = [child for child in servings_div.children if child.tag == "span"]
            if spans:
                result["servings_per_container"] = spans[0].text()
            size_div = servings_div.find_first(
                tag="div", predicate=lambda node: "inline-div-left" in node.class_list()
            )
            value_div = servings_div.find_first(
                tag="div", predicate=lambda node: "inline-div-right" in node.class_list()
            )
            if size_div and value_div:
                result["serving_size"] = f"{size_div.text()} {value_div.text()}"

        calories_div = label_container.find_first(
            tag="div", predicate=lambda node: "cbo_nn_LabelSubHeader" in node.class_list()
        )
        if calories_div:
            calorie_value = calories_div.find_first(
                predicate=lambda node: "font-22" in node.class_list() or "font-21" in node.class_list()
            )
            if calorie_value:
                result["calories"] = calorie_value.text()

        nutrient_rows = label_container.find_all(
            tag="div",
            predicate=lambda node: any(
                klass in {"cbo_nn_LabelBorderedSubHeader", "cbo_nn_LabelNoBorderSubHeader"} for klass in node.class_list()
            ),
        )
        nutrients = []
        for row in nutrient_rows:
            left = row.find_first(predicate=lambda node: "inline-div-left" in node.class_list())
            right = row.find_first(predicate=lambda node: "inline-div-right" in node.class_list())
            if not left:
                continue
            spans = [child for child in left.children if child.tag == "span"]
            if not spans:
                continue
            label = spans[0].text()
            amount_text = spans[1].text() if len(spans) > 1 else ""
            dv = right.text() if right else ""
            nutrients.append(
                {
                    "label": label,
                    "amount": amount_text,
                    "daily_value": dv,
                }
            )
        result["nutrients"] = nutrients

        ingredients_table = label_container.find_first(
            tag="table", predicate=lambda node: "cbo_nn_Label_IngredientsTable" in node.class_list()
        )
        if ingredients_table:
            ingredients_text = ingredients_table.text()
            cleaned = ingredients_text.replace("Ingredients:", "").strip()
            result["ingredients"]["text"] = cleaned
            if cleaned:
                result["ingredients"]["list"] = [part.strip() for part in cleaned.split(",") if part.strip()]

        return result


class MenuParser:
    """Parse menu tables, capture categories, and attach nutrition payloads."""

    def __init__(self, nutrition_loader: Callable[[int], Dict]) -> None:
        self.nutrition_loader = nutrition_loader

    def parse(self, menu_html: str) -> List[Dict]:
        root = parse_html(menu_html)
        table = root.find_first(tag="table")
        if not table:
            return []

        categories: List[Dict] = []
        current_category: Optional[Dict] = None

        for row in table.find_all(tag="tr"):
            classes = set(row.class_list())
            if "cbo_nn_itemGroupRow" in classes:
                title_node = row.find_first(tag="div")
                name = title_node.text() if title_node else "Untitled Category"
                current_category = {"name": name, "items": []}
                categories.append(current_category)
            elif classes & {"cbo_nn_itemPrimaryRow", "cbo_nn_itemAlternateRow"}:
                if not current_category:
                    continue
                item = self._parse_item_row(row)
                if item:
                    current_category["items"].append(item)
        return categories

    def _parse_item_row(self, row: HTMLNode) -> Optional[Dict]:
        detail_node = row.find_first(predicate=lambda node: node.attrs.get("data-detailoid"))
        detail_id = None
        if detail_node:
            try:
                detail_id = int(detail_node.attrs["data-detailoid"])
            except (KeyError, ValueError):
                detail_id = None
        if detail_id is None:
            return None

        cells = [child for child in row.children if child.tag == "td"]
        if len(cells) < 4:
            return None
        name_cell = cells[1]
        serving_cell = cells[2]
        portion_cell = cells[3]

        name_anchor = name_cell.find_first(
            tag="a", predicate=lambda node: "cbo_nn_itemHover" in node.class_list()
        )
        name = name_anchor.text() if name_anchor else name_cell.text()
        badges = [
            img.attrs.get("title") or img.attrs.get("alt") or ""
            for img in (name_anchor.find_all(tag="img") if name_anchor else [])
        ]

        serving_size = serving_cell.text()
        portion_select = portion_cell.find_first(tag="select")
        portion_values = []
        if portion_select:
            for option in portion_select.find_all(tag="option"):
                portion_values.append(
                    {
                        "value": option.attrs.get("value"),
                        "label": option.text(),
                    }
                )

        components = []
        for ul in name_cell.find_all(tag="ul"):
            entries = [li.text() for li in ul.find_all(tag="li")]
            if entries:
                components.append({"type": "list", "items": entries})
        for div in name_cell.find_all(
            tag="div", predicate=lambda node: "component" in normalize_label(node.attrs.get("class", ""))
        ):
            entries = div.text()
            if entries:
                components.append({"type": "text", "items": [entries]})

        extra_selects = []
        for select in row.find_all(tag="select"):
            label = select.attrs.get("aria-label") or select.attrs.get("title") or select.attrs.get("name", "")
            if select is portion_select:
                continue
            options = [option.text() for option in select.find_all(tag="option")]
            if options:
                extra_selects.append({"prompt": label, "options": options})

        nutrition = self.nutrition_loader(detail_id)

        return {
            "detail_id": detail_id,
            "name": name,
            "labels": [badge for badge in badges if badge],
            "serving_size": serving_size,
            "portion_options": portion_values,
            "components": components,
            "customizations": extra_selects,
            "nutrition": nutrition,
        }


class DukeNetNutritionScraper:
    """High-level orchestrator that drives the scraping workflow."""

    def __init__(self, output_path: Path, limit: Optional[int] = None, delay: float = 0.2) -> None:
        self.client = NetNutritionClient(BASE_URL)
        self.output_path = output_path
        self.limit = limit
        self.delay = delay
        self.nutrition_cache: Dict[int, Dict] = {}
        self.nutrition_parser = NutritionParser()

    def fetch_nutrition(self, detail_id: int) -> Dict:
        if detail_id in self.nutrition_cache:
            return self.nutrition_cache[detail_id]
        time.sleep(self.delay)
        html = self.client.post_html("/NutritionDetail/ShowItemNutritionLabel", {"detailOid": detail_id})
        parsed = self.nutrition_parser.parse(html)
        self.nutrition_cache[detail_id] = parsed
        return parsed

    def run(self) -> Path:
        logging.info("Loading entry page")
        initial_html = self.client.get("")
        root = parse_html(initial_html)
        units = extract_unit_options(root)
        dates = extract_date_options(root)
        meals = extract_meal_options(root)

        if not units:
            raise RuntimeError("Unable to locate dining locations.")
        if not dates:
            raise RuntimeError("Unable to locate menu dates.")

        if self.limit:
            units = units[: self.limit]

        date_choice = dates[0]
        logging.info("Fixing menu date to %s (%s)", date_choice.label, date_choice.token)
        self.client.post_json(
            "/Home/HandleNavBarSelection",
            {"unit": -1, "meal": -1, "date": date_choice.token, "typeChange": "DT"},
        )

        menu_parser = MenuParser(self.fetch_nutrition)
        aggregated: Dict[str, Dict] = {}

        for idx, unit in enumerate(units, start=1):
            logging.info("(%s/%s) %s", idx, len(units), unit.name)
            unit_payload = self.client.post_json(
                "/Home/HandleNavBarSelection",
                {"unit": unit.unit_id, "meal": -1, "date": date_choice.token, "typeChange": "UN"},
            )
            panel_html = self._extract_panel(unit_payload, "itemPanel")
            meal_sections: Dict[str, Dict] = defaultdict(dict)
            seen_hashes = set()

            if panel_html and "cbo_nn_itemGroupRow" in panel_html:
                key = self._panel_hash(panel_html)
                seen_hashes.add(key)
                meal_sections["All Meals"] = self._structure_meal(panel_html, menu_parser)

            for meal in meals:
                time.sleep(self.delay)
                meal_payload = self.client.post_json(
                    "/Home/HandleNavBarSelection",
                    {
                        "unit": unit.unit_id,
                        "meal": meal.meal_id,
                        "date": date_choice.token,
                        "typeChange": "ML",
                    },
                )
                meal_html = self._extract_panel(meal_payload, "itemPanel")
                if not meal_html or "cbo_nn_itemGroupRow" not in meal_html:
                    continue
                key = self._panel_hash(meal_html)
                if key in seen_hashes:
                    continue
                seen_hashes.add(key)
                label = f"{meal.label} (meal #{meal.meal_id})"
                meal_sections[label] = self._structure_meal(meal_html, menu_parser)

            aggregated[unit.name] = meal_sections

        payload = {
            "source": BASE_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "date_token": date_choice.token,
            "locations": aggregated,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(payload, indent=2))
        logging.info("Wrote %s", self.output_path)
        return self.output_path

    def _structure_meal(self, panel_html: str, parser: MenuParser) -> Dict:
        sections = parser.parse(panel_html)
        structured: Dict[str, Dict] = {}
        for section in sections:
            category = section["name"]
            for item in section["items"]:
                key = f"{item['name']} [#{item['detail_id']}]"
                structured[key] = {
                    "meal": {
                        "category": category,
                        "detail_id": item["detail_id"],
                        "labels": item["labels"],
                        "serving_size": item["serving_size"],
                        "portion_options": item["portion_options"],
                        "customizations": item["customizations"],
                    },
                    "meal_nutrition": {
                        "servings_per_container": item["nutrition"].get("servings_per_container"),
                        "serving_size": item["nutrition"].get("serving_size"),
                        "calories": item["nutrition"].get("calories"),
                    },
                    "meal_components": {
                        "components": item["components"],
                        "ingredients": item["nutrition"].get("ingredients"),
                    },
                    "meal_nutrition_components": item["nutrition"].get("nutrients", []),
                }
        return structured

    @staticmethod
    def _extract_panel(payload: Dict, panel_id: str) -> Optional[str]:
        panels = payload.get("panels") or []
        for panel in panels:
            if panel.get("id") == panel_id:
                return panel.get("html")
        return None

    @staticmethod
    def _panel_hash(html_fragment: str) -> str:
        # A quick-and-dirty fingerprint to remove duplicate responses.
        return str(hash(html_fragment.strip()))


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Duke NetNutrition data.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / "Desktop" / "duke_netnutrition.json",
        help="Destination JSON path (defaults to Desktop).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of dining locations (useful for debugging).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Throttle between network calls (seconds).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    scraper = DukeNetNutritionScraper(output_path=args.output, limit=args.limit, delay=args.delay)
    try:
        scraper.run()
    except URLError as exc:
        logging.error("Network error: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        logging.exception("Scrape failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

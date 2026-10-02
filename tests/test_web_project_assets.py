from __future__ import annotations

import re
import unittest
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[1] / "apps" / "web"

INDEX_IDS = (
    "projectSelect",
    "bookPickerTrigger",
    "bookPickerMenu",
    "bookPickerGrid",
    "dashboardView",
    "createView",
    "projectStatus",
    "projectTitle",
    "projectSynopsis",
    "confirmButton",
    "editBriefButton",
    "regenerateBriefButton",
    "pauseButton",
    "recoverButton",
    "deleteDraftButton",
    "briefContent",
)

TEMPLATE_IDS = (
    "briefWorkbench",
    "briefEditForm",
    "briefFeedback",
    "briefSections",
    "briefVersionLeft",
    "briefVersionRight",
    "restoreBriefVersion",
    "briefCompareLeft",
    "briefCompareRight",
    "createForm",
    "genreSelect",
    "romanceSelect",
    "tagCatalogNote",
)

MOVED_CSS_SELECTORS = (
    ".hero-card",
    ".brief-workbench",
    ".form-layout",
    ".channel-switch",
    ".plan-panel",
    ".brief-grid",
    ".catalog-note",
)


class WebProjectAssetTests(unittest.TestCase):
    def test_index_contains_shell_and_dashboard_ids_once(self) -> None:
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        for item in INDEX_IDS:
            self.assertEqual(html.count(f'id="{item}"'), 1, item)
        for item in TEMPLATE_IDS:
            self.assertEqual(html.count(f'id="{item}"'), 0, f"should live in template: {item}")

    def test_templates_contain_migrated_ids_once(self) -> None:
        create_tpl = (
            WEB_ROOT / "js" / "features" / "novel-create" / "template.js"
        ).read_text(encoding="utf-8")
        brief_tpl = (
            WEB_ROOT / "js" / "features" / "story-brief" / "template.js"
        ).read_text(encoding="utf-8")
        for item in (
            "createForm",
            "genreSelect",
            "romanceSelect",
            "tagCatalogNote",
        ):
            self.assertEqual(create_tpl.count(f'id="{item}"'), 1, item)
        for item in (
            "briefWorkbench",
            "briefEditForm",
            "briefFeedback",
            "briefSections",
            "briefVersionLeft",
            "briefVersionRight",
            "restoreBriefVersion",
            "briefCompareLeft",
            "briefCompareRight",
        ):
            self.assertEqual(brief_tpl.count(f'id="{item}"'), 1, item)

    def test_local_assets_referenced_by_index_exist(self) -> None:
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r'(?:href|src)="(/[^"?]+)', html)
        for ref in refs:
            if ref.startswith("/api/"):
                continue
            target = WEB_ROOT / ref.lstrip("/")
            self.assertTrue(target.is_file(), f"missing asset: {ref}")

    def test_feature_css_links_present(self) -> None:
        html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        for href in (
            "/styles/features/project-dashboard.css",
            "/styles/features/story-brief.css",
            "/styles/features/novel-create.css",
        ):
            self.assertIn(href, html)

    def test_create_form_payload_field_names_in_template(self) -> None:
        create_tpl = (
            WEB_ROOT / "js" / "features" / "novel-create" / "template.js"
        ).read_text(encoding="utf-8")
        for name in (
            "preferred_title",
            "audience_channel",
            "genre",
            "romance",
            "idea",
            "must_have",
            "nice_to_have",
            "exclude",
            "chapter_target_chars",
            "daily_chapters",
            "reserve_target",
            "require_plan_confirmation",
        ):
            self.assertIn(f'name="{name}"', create_tpl)

    def test_app_js_no_longer_owns_project_brief_impl(self) -> None:
        app_js = (WEB_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("async function createNovel", app_js)
        self.assertNotIn("function renderBrief(", app_js)
        self.assertNotIn("function populateBriefEditor", app_js)
        self.assertNotIn("async function saveBriefEdit", app_js)
        self.assertNotIn("async function deleteProject", app_js)
        self.assertNotIn("function projectAction", app_js)
        self.assertIn("novelAgentProject", app_js)
        self.assertIn("/js/features/projects/index.js", app_js)
        self.assertIn("/js/features/novel-create/index.js", app_js)
        self.assertIn("/js/features/story-brief/index.js", app_js)
        self.assertIn("/js/features/project-dashboard/index.js", app_js)

    def test_styles_css_dropped_moved_feature_selectors(self) -> None:
        styles = (WEB_ROOT / "styles.css").read_text(encoding="utf-8")
        for selector in MOVED_CSS_SELECTORS:
            self.assertNotIn(selector, styles, selector)

    def test_es_module_imports_stay_inside_web_root(self) -> None:
        for path in (WEB_ROOT / "js").rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"""from\s+["']([^"']+)["']""", text):
                spec = match.group(1)
                if not spec.startswith("."):
                    continue
                target = (path.parent / spec).resolve()
                self.assertTrue(
                    str(target).startswith(str(WEB_ROOT.resolve())),
                    f"{path} imports outside web root: {spec}",
                )


if __name__ == "__main__":
    unittest.main()

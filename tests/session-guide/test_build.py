import json
import re
import unittest

from helpers import GitSandbox, lines


def minimal(**overrides):
    guide = {
        "title": "T-1 Fold", "context": "why", "ship": {"call": "show", "why": "small"},
        "evidence": {"notCovered": "nothing"}, "danger": {"door": "two-way", "why": "w", "blast": "b"},
        "sessions": [], "contracts": [], "review": [],
        "flows": [{"title": "Fold a task", "stops": [
            {"id": "w1", "at": "src/app/Service.java:9", "title": "Fold", "text": "t", "hunk": "src/app/Service.java:9-9"}]}],
        "decisions": [{"id": "d1", "title": "Fold", "door": "two-way", "by": "you", "why": "w", "alt": "none considered",
                       "hunks": [{"at": "src/app/Service.java:9-9", "text": "t"}]}],
        "readOrder": [{"tier": "read", "files": ["src/**"], "why": "w"}],
        "mr": {"summary": "s"},
    }
    guide.update(overrides)
    return guide


def page_data(repo, guide="guides/g"):
    html = (repo.root / f"{guide}.html").read_text()
    m = re.search(r'<script id="guide-data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.repo = GitSandbox()
        self.repo.write("src/app/Service.java", lines(10))
        self.base = self.repo.commit("base")
        self.repo.write("src/app/Service.java", lines(8) + "folded\n" + "line 10\n")

    def tearDown(self):
        self.repo.close()

    def build(self, guide):
        self.repo.gather("--base", self.base)
        self.repo.write_guide(guide)
        return self.repo.build()

    def assertProblem(self, result, text):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(text, result.stdout)

    def test_a_complete_guide_renders_one_page(self):
        r = self.build(minimal())

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(page_data(self.repo)["title"], "T-1 Fold")

    def test_a_second_build_does_not_count_the_first_builds_output_as_changed(self):
        self.build(minimal())

        r = self.repo.build()

        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_hunk_reference_becomes_the_diff_lines_of_that_range(self):
        self.build(minimal())

        self.assertEqual(page_data(self.repo)["hunks"]["src/app/Service.java:9-9"],
                         [["-", "line 9"], ["+", "folded"]])

    def test_code_that_closes_a_script_tag_stays_inside_the_data(self):
        self.repo.write("src/app/Service.java", lines(8) + 'html = "</script><b>&amp;"\n' + "line 10\n")

        self.build(minimal())

        self.assertIn(["+", 'html = "</script><b>&amp;"'], page_data(self.repo)["hunks"]["src/app/Service.java:9-9"])

    def test_in_a_large_change_only_decisions_and_cards_carry_hunks(self):
        for i in range(51):
            self.repo.write(f"src/many/F{i}.java", f"f {i}\n")
        guide = minimal(groups=[{"name": "many", "match": ["src/many/*"], "tier": "skim"}])
        guide["flows"][0]["stops"][0]["hunk"] = "src/app/Service.java:8-9"

        r = self.build(guide)

        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(list(page_data(self.repo)["hunks"]), ["src/app/Service.java:9-9"])

    def test_a_hunk_range_without_changed_lines_is_a_problem(self):
        guide = minimal()
        guide["decisions"][0]["hunks"][0]["at"] = "src/app/Service.java:1-3"

        self.assertProblem(self.build(guide), "decision d1: src/app/Service.java:1-3 holds no changed lines")

    def test_a_location_past_the_end_of_its_file_is_a_problem(self):
        guide = minimal()
        guide["flows"][0]["stops"][0]["at"] = "src/app/Service.java:11"

        self.assertProblem(self.build(guide), "stop w1: src/app/Service.java has 10 lines, not 11")

    def test_a_changed_file_no_panel_explains_is_a_problem(self):
        self.repo.write("src/app/Helper.java", lines(3, "helper"))

        self.assertProblem(self.build(minimal()), "src/app/Helper.java: changed, but no stop, decision, contract, "
                                                  "card or group explains it")

    def test_a_group_explains_the_files_it_matches(self):
        self.repo.write("src/fixtures/fold-01.json", "{}\n")
        self.repo.write("src/fixtures/deep/fold-02.json", "{}\n")

        r = self.build(minimal(groups=[{"name": "fold fixtures", "match": ["src/fixtures/**"]}]))

        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_decision_without_hunks_is_a_problem(self):
        guide = minimal()
        guide["decisions"].append({"id": "d2", "title": "Naming", "door": "two-way", "by": "agent",
                                   "why": "w", "alt": "a", "hunks": []})

        self.assertProblem(self.build(guide), "decision d2: no hunks")

    def test_a_link_to_a_panel_that_does_not_exist_is_a_problem(self):
        guide = minimal(context="see [the fold](#d9)")

        self.assertProblem(self.build(guide), "context: links to #d9, which is not a panel")

    def test_a_read_tier_file_missing_from_the_reading_order_is_a_problem(self):
        guide = minimal(readOrder=[{"tier": "read", "files": ["docs/**"], "why": "w"}])

        self.assertProblem(self.build(guide), "src/app/Service.java: read tier, but not in readOrder")

    def test_parts_written_by_subagents_merge_into_the_guide(self):
        self.repo.write("src/billing/Invoice.java", lines(3, "invoice"))
        self.repo.write_part("billing", {
            "flows": [{"title": "Bill a task", "stops": [
                {"id": "b1", "at": "src/billing/Invoice.java:1", "title": "Invoice", "text": "t",
                 "hunk": "src/billing/Invoice.java:1-3"}]}],
            "readOrder": [{"tier": "read", "files": ["src/billing/**"], "why": "w"}]})

        r = self.build(minimal())

        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual([f["title"] for f in page_data(self.repo)["flows"]], ["Fold a task", "Bill a task"])

    def test_a_part_adds_hunks_to_a_decision_the_guide_declares(self):
        self.repo.write("src/billing/Invoice.java", lines(3, "invoice"))
        self.repo.write_part("billing", {"decisions": [{"id": "d1", "hunks": [{"at": "src/billing/Invoice.java:1-3",
                                                                                "text": "billing folds too"}]}]})

        r = self.build(minimal())

        self.assertEqual(r.returncode, 0, r.stdout)
        decisions = page_data(self.repo)["decisions"]
        self.assertEqual((len(decisions), [h["at"] for h in decisions[0]["hunks"]]),
                         (1, ["src/app/Service.java:9-9", "src/billing/Invoice.java:1-3"]))

    def test_a_problem_in_a_part_names_the_part(self):
        self.repo.write_part("billing", {"decisions": [{"id": "d7", "title": "x", "door": "two-way", "by": "agent",
                                                        "why": "w", "alt": "a", "hunks": []}]})

        self.assertProblem(self.build(minimal()), "decision d7 (parts/billing.json): no hunks")

    def test_a_part_may_override_files(self):
        self.repo.write("src/billing/Invoice.java", lines(3, "invoice"))
        self.repo.write_part("job-1", {"files": {"src/billing/Invoice.java": {"panel": "d1"}},
                                       "readOrder": [{"tier": "read", "files": ["src/billing/**"], "why": "w"}]})

        r = self.build(minimal())

        self.assertEqual(r.returncode, 0, r.stdout)

    def build_part(self, guide, part):
        self.repo.gather("--base", self.base)
        self.repo.write_guide(guide)
        self.repo.write_part("job-1", part)
        return self.repo.run("build.py", str(self.repo.root / "guides/g"), "--part", "parts/job-1.json")

    def test_a_part_can_be_checked_before_the_guide_is_complete(self):
        guide = {"decisions": [{"id": "d1", "title": "Fold", "door": "two-way", "by": "you", "why": "w",
                                "alt": "none considered", "hunks": []}]}
        part = {k: minimal()[k] for k in ("flows", "readOrder")}

        r = self.build_part(guide, part)

        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(r.stdout.startswith("ok ") and r.stdout.strip().endswith("guides/g/parts/job-1.json"), r.stdout)
        self.assertFalse((self.repo.root / "guides/g.html").exists())

    def test_checking_a_part_prints_its_problems(self):
        part = {"flows": [{"title": "F", "stops": [{"id": "w9", "at": "src/app/Service.java", "title": "t", "text": "t"}]}]}

        self.assertProblem(self.build_part({}, part),
                           "stop w9 (parts/job-1.json): 'src/app/Service.java' needs line numbers")

    def test_the_review_size_counts_lines_per_tier_after_the_guides_overrides(self):
        self.repo.write("src/app/Mapper.java", lines(30, "mapper"))
        guide = minimal(files={"src/app/Mapper.java": {"tier": "skim", "panel": "d1"}})

        self.build(guide)

        self.assertEqual(page_data(self.repo)["size"], {"read": 2, "skim": 30, "skip": 0, "budget": 400})

    def test_a_group_is_one_chip_on_the_change_map_with_summed_counts(self):
        self.repo.write("src/fixtures/fold-01.json", lines(2, "a"))
        self.repo.write("src/fixtures/fold-02.json", lines(3, "b"))

        self.build(minimal(groups=[{"name": "fold fixtures", "match": ["src/fixtures/*"]}]))

        chips = [c for layer in page_data(self.repo)["map"] for c in layer["chips"]]
        self.assertIn({"label": "fold fixtures", "files": 2, "add": 5, "del": 0, "panel": None, "review": False,
                       "status": "A"}, chips)

    def test_a_group_can_place_its_files_in_a_layer(self):
        self.repo.write("src/fixtures/fold-01.json", lines(2, "a"))

        self.build(minimal(groups=[{"name": "fold fixtures", "match": ["src/fixtures/*"], "layer": "Domain"}]))

        layers = {c["label"]: l["layer"] for l in page_data(self.repo)["map"] for c in l["chips"]}
        self.assertEqual(layers["fold fixtures"], "Domain")

    def test_lineage_shows_the_renames_git_detects_and_the_links_only_the_session_knows(self):
        self.repo.write("src/app/Old.java", lines(20, "old"))
        self.base = self.repo.commit("old")
        self.repo.move("src/app/Old.java", "src/app/Kept.java")
        self.repo.write("src/app/Merged.java", lines(5, "merged"))
        self.repo.write("src/app/Service.java", lines(8) + "folded twice\n" + "line 10\n")
        guide = minimal(refactoring={"links": [{"from": ["src/app/Old.java"], "to": ["src/app/Merged.java"],
                                                "kind": "merged"}], "whereTo": [], "transit": [], "behaviour": []})

        r = self.build(guide)

        self.assertEqual(r.returncode, 0, r.stdout)
        links = page_data(self.repo)["lineage"][0]["links"]
        self.assertIn({"from": ["src/app/Old.java"], "to": ["src/app/Kept.java"], "kind": "renamed", "sim": 100,
                       "by": "git"}, links)
        self.assertIn({"from": ["src/app/Old.java"], "to": ["src/app/Merged.java"], "kind": "merged", "by": "agent"},
                      links)

    def refactor(self, **refactoring):
        self.repo.write("src/app/Old.java", lines(20, "old"))
        self.base = self.repo.commit("old")
        self.repo.delete("src/app/Old.java")
        self.repo.write("src/app/New.java", lines(5, "new") + "line 3 reworded\n")
        self.repo.write("src/app/Service.java", lines(8) + "folded twice\n" + "line 10\n")
        return minimal(files={"src/app/New.java": {"panel": "d1"}},
                       refactoring={"whereTo": [], "transit": [], "behaviour": [], **refactoring})

    def test_in_a_refactoring_a_deletion_needs_a_successor_or_a_reason(self):
        self.assertProblem(self.build(self.refactor()),
                           "src/app/Old.java: deleted with no successor; link it, or say why in refactoring.gone")

    def test_in_a_refactoring_a_rename_git_detects_is_explained_by_the_lineage(self):
        guide = self.refactor(gone={"src/app/Old.java": "nobody calls it"})
        self.repo.write("src/app/Kept.java", lines(15, "kept"))
        self.base = self.repo.commit("kept")
        self.repo.move("src/app/Kept.java", "src/app/Moved.java")
        self.repo.write("src/app/Service.java", lines(8) + "folded thrice\n" + "line 10\n")

        r = self.build(guide)

        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_hunk_in_a_file_moved_but_not_staged_comes_from_the_rename(self):
        (self.repo.root / "src/core").mkdir(parents=True)
        (self.repo.root / "src/app/Service.java").rename(self.repo.root / "src/core/Service.java")
        guide = minimal(readOrder=[{"tier": "read", "files": ["src/**"], "why": "w"}])
        guide["flows"][0]["stops"][0].update(at="src/core/Service.java:9", hunk="src/core/Service.java:9-9")
        guide["decisions"][0]["hunks"][0]["at"] = "src/core/Service.java:9-9"

        r = self.build(guide)

        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(page_data(self.repo)["hunks"]["src/core/Service.java:9-9"], [["-", "line 9"], ["+", "folded"]])

    def test_a_deletion_with_a_reason_is_fine(self):
        r = self.build(self.refactor(gone={"src/app/Old.java": "nobody calls it"}))

        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_piece_changed_in_transit_shows_its_old_lines_at_the_base_and_its_new_lines_now(self):
        guide = self.refactor(links=[{"from": ["src/app/Old.java"], "to": ["src/app/New.java"], "kind": "rewritten"}],
                              transit=[{"from": "src/app/Old.java:2-3", "to": "src/app/New.java:5-6", "text": "t"}])

        r = self.build(guide)

        self.assertEqual(r.returncode, 0, r.stdout)
        code = page_data(self.repo)["code"]
        self.assertEqual((code["base"]["src/app/Old.java:2-3"], code["now"]["src/app/New.java:5-6"]),
                         (["old 2", "old 3"], ["new 5", "line 3 reworded"]))

    def test_a_transit_range_outside_the_old_file_is_a_problem(self):
        guide = self.refactor(links=[{"from": ["src/app/Old.java"], "to": ["src/app/New.java"], "kind": "rewritten"}],
                              transit=[{"from": "src/app/Old.java:30-31", "to": "src/app/New.java:2-3", "text": "t"}])

        self.assertProblem(self.build(guide), "transit 1: src/app/Old.java has 20 lines at the base, not 31")

    def test_the_merge_request_text_lists_the_reading_order_and_the_open_review_cards(self):
        guide = minimal(review=[
            {"id": "r1", "sev": "high", "claim": "Voids resolve forward", "kinds": ["doc ≠ code"], "why": "w",
             "ask": "a", "hunk": "src/app/Service.java:9-9"},
            {"id": "r2", "sev": "ok", "claim": "Fold is pure", "kinds": [], "why": "w", "ask": "a"}])

        self.build(guide)

        mr = (self.repo.root / "guides/g.mr.md").read_text()
        self.assertIn("1. `src/**` *read*", mr)
        self.assertIn("- [ ] Voids resolve forward", mr)
        self.assertNotIn("Fold is pure", mr)
        self.assertIn(mr, page_data(self.repo)["mrText"])

    def test_the_merge_request_text_carries_the_split_plan_with_measured_sizes(self):
        guide = minimal(split=[{"title": "Fold in place", "kind": "behaviour", "call": "ask", "files": ["src/app/**"],
                                "items": ["the fold"], "alone": "the V4 migration"}])

        self.build(guide)

        mr = (self.repo.root / "guides/g.mr.md").read_text()
        self.assertIn("## Split plan", mr)
        self.assertIn("1. **Fold in place** (behaviour, Ask, ~2 lines to read): the fold. Merges with: the V4 migration.", mr)

    def test_a_missing_required_field_is_a_problem_not_a_crash(self):
        guide = minimal()
        del guide["danger"], guide["mr"]

        self.assertProblem(self.build(guide), "guide.json: missing danger, mr (see guide.schema.ts)")


if __name__ == "__main__":
    unittest.main()

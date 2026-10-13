import unittest

from helpers import GitSandbox, by_path, lines


class GatherTest(unittest.TestCase):
    def setUp(self):
        self.repo = GitSandbox()
        self.repo.write("src/app/Service.java", lines(10))
        self.base = self.repo.commit("base")

    def tearDown(self):
        self.repo.close()

    def test_counts_added_and_deleted_lines_per_file_since_the_base(self):
        self.repo.write("src/app/Service.java", lines(8) + "changed\n")
        self.repo.write("src/app/New.java", lines(3))
        self.repo.commit()

        files = by_path(self.repo.gather("--base", self.base))

        self.assertEqual((files["src/app/Service.java"]["add"], files["src/app/Service.java"]["del"]), (1, 2))
        self.assertEqual((files["src/app/New.java"]["add"], files["src/app/New.java"]["status"]), (3, "A"))

    def test_a_rename_git_detects_keeps_its_old_path_and_similarity(self):
        self.repo.move("src/app/Service.java", "src/app/Renamed.java")
        self.repo.commit()

        f = by_path(self.repo.gather("--base", self.base))["src/app/Renamed.java"]

        self.assertEqual((f["status"], f["old_path"], f["sim"]), ("R", "src/app/Service.java", 100))

    def test_a_move_not_yet_staged_is_still_a_rename(self):
        (self.repo.root / "src/core").mkdir(parents=True)
        (self.repo.root / "src/app/Service.java").rename(self.repo.root / "src/core/Service.java")

        f = by_path(self.repo.gather("--base", self.base))

        self.assertEqual(list(f), ["src/core/Service.java"])
        self.assertEqual((f["src/core/Service.java"]["status"], f["src/core/Service.java"]["sim"],
                          f["src/core/Service.java"]["tier"]), ("R", 100, "skip"))

    def test_gathering_leaves_the_index_alone(self):
        self.repo.write("src/app/Draft.java", lines(4))
        self.repo.write("guides/g/.keep", "")
        before = self.repo.git("status", "--porcelain")

        self.repo.gather("--base", self.base)

        self.assertEqual(self.repo.git("status", "--porcelain"), before)

    def test_uncommitted_and_untracked_files_are_part_of_the_change(self):
        self.repo.write("src/app/Service.java", lines(11))
        self.repo.write("src/app/Draft.java", lines(4))

        files = by_path(self.repo.gather("--base", self.base))

        self.assertEqual(files["src/app/Service.java"]["add"], 1)
        self.assertEqual((files["src/app/Draft.java"]["status"], files["src/app/Draft.java"]["add"]), ("A", 4))

    def test_the_guides_folder_is_not_part_of_the_change(self):
        self.repo.write("guides/g/guide.json", "{}")
        self.repo.write("guides/g.html", "<html>")

        self.assertEqual(list(by_path(self.repo.gather("--base", self.base))), [])

    def test_guesses_a_tier_per_file(self):
        self.repo.write("src/app/Other.java", lines(5, "other"))
        self.repo.write("src/app/Moved.java", lines(5, "moved"))
        self.base = self.repo.commit("more")
        self.repo.write("src/app/Service.java", lines(12))
        self.repo.write("src/test/app/ServiceTest.java", lines(5, "ServiceTest"))
        self.repo.write("web/src/cart.test.ts", lines(5, "cart"))
        self.repo.write("docs/adr/0007-fold.md", lines(5, "0007-fold"))
        self.repo.write("package-lock.json", lines(500))
        self.repo.delete("src/app/Other.java")
        self.repo.move("src/app/Moved.java", "src/core/Moved.java")
        self.repo.commit()

        tiers = {p: f["tier"] for p, f in by_path(self.repo.gather("--base", self.base)).items()}

        self.assertEqual(tiers, {
            "src/app/Service.java": "read",
            "src/test/app/ServiceTest.java": "skim",
            "web/src/cart.test.ts": "skim",
            "docs/adr/0007-fold.md": "skim",
            "package-lock.json": "skip",
            "src/app/Other.java": "skip",
            "src/core/Moved.java": "skip",
        })

    def test_sums_the_review_size_per_tier(self):
        self.repo.write("src/app/Service.java", lines(12))
        self.repo.write("src/test/app/ServiceTest.java", lines(7, "t"))

        totals = self.repo.gather("--base", self.base)["totals"]

        self.assertEqual((totals["files"], totals["read"], totals["skim"], totals["skip"]), (2, 2, 7, 0))

    def test_a_small_change_is_not_large(self):
        self.repo.write("src/app/Service.java", lines(3010))  # 3000 changed

        self.assertFalse(self.repo.gather("--base", self.base)["large"])

    def test_more_than_3000_changed_lines_is_large(self):
        self.repo.write("src/app/Service.java", lines(3011))  # 3001 changed

        self.assertTrue(self.repo.gather("--base", self.base)["large"])

    def test_more_than_50_files_is_large(self):
        for i in range(51):
            self.repo.write(f"src/app/F{i}.java", f"f {i}\n")

        self.assertTrue(self.repo.gather("--base", self.base)["large"])

    def test_groups_files_into_modules_below_their_common_package(self):
        self.repo.write("src/main/java/be/x/order/Order.java", lines(3, "o"))
        self.repo.write("src/main/java/be/x/order/api/OrderController.java", lines(3, "oc"))
        self.repo.write("src/test/java/be/x/order/OrderTest.java", lines(3, "ot"))
        self.repo.write("src/main/java/be/x/billing/Invoice.java", lines(3, "i"))

        facts = self.repo.gather("--base", self.base)
        modules = {p: f["module"] for p, f in by_path(facts).items()}

        self.assertEqual(modules, {
            "src/main/java/be/x/order/Order.java": "order",
            "src/main/java/be/x/order/api/OrderController.java": "order",
            "src/test/java/be/x/order/OrderTest.java": "order",
            "src/main/java/be/x/billing/Invoice.java": "billing",
        })

    def test_a_module_of_more_than_1500_read_lines_is_split_one_level_deeper(self):
        for i in range(20):
            self.repo.write(f"src/order/fold/F{i}.java", lines(40, f"fold {i}"))
            self.repo.write(f"src/order/api/A{i}.java", lines(40, f"api {i}"))
        self.repo.write("src/order/Order.java", "order\n")
        self.repo.write("src/billing/Invoice.java", "invoice\n")

        modules = {p: f["module"] for p, f in by_path(self.repo.gather("--base", self.base)).items()}

        self.assertEqual((modules["src/order/fold/F3.java"], modules["src/order/api/A3.java"],
                          modules["src/order/Order.java"], modules["src/billing/Invoice.java"]),
                         ("order/fold", "order/api", "order", "billing"))

    def test_a_module_within_1500_read_lines_stays_whole_however_many_files_it_has(self):
        for i in range(40):
            self.repo.write(f"src/order/fold/F{i}.java", f"fold {i}\n")
        self.repo.write("src/order/Order.java", "order\n")

        modules = {f["module"] for f in self.repo.gather("--base", self.base)["files"]}

        self.assertEqual(modules, {"order"})

    def test_packs_neighbouring_modules_into_jobs_of_at_most_1500_read_lines(self):
        self.repo.write("src/a/A.java", lines(1200, "a"))
        self.repo.write("src/b/B.java", lines(400, "b"))
        self.repo.write("src/c/C.java", lines(300, "c"))
        self.repo.write("src/test/d/DTest.java", lines(300, "d"))

        jobs = self.repo.gather("--base", self.base)["jobs"]

        self.assertEqual([j["modules"] for j in jobs], [["a"], ["b", "c"]])

    def test_guesses_the_layer_from_the_path(self):
        for p in ["src/order/api/OrderController.java", "src/order/domain/Order.java",
                  "src/order/persistence/OrderRepository.java", "src/order/service/OrderService.java",
                  "src/order/dto/OrderDto.java", "src/main/resources/db/migration/V9__fold.sql",
                  "web/src/components/Cart.tsx", "src/test/order/OrderTest.java", "docs/adr/0001-x.md"]:
            self.repo.write(p, p + "\n")

        layers = {p: f["layer"] for p, f in by_path(self.repo.gather("--base", self.base)).items()}

        self.assertEqual(layers, {
            "src/order/api/OrderController.java": "API",
            "src/order/domain/Order.java": "Domain",
            "src/order/persistence/OrderRepository.java": "Persistence",
            "src/order/service/OrderService.java": "Service",
            "src/order/dto/OrderDto.java": "API",
            "src/main/resources/db/migration/V9__fold.sql": "Migration",
            "web/src/components/Cart.tsx": "UI",
            "src/test/order/OrderTest.java": "Tests",
            "docs/adr/0001-x.md": "Docs",
        })

    def test_ticket_scope_starts_at_the_merge_base_with_the_default_branch(self):
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.write("src/app/Feature.java", lines(2, "feature"))
        self.repo.commit()
        self.repo.git("checkout", "-q", "main")
        self.repo.write("src/app/OnMain.java", lines(2, "main"))
        self.repo.commit()
        self.repo.git("checkout", "-q", "feature")

        facts = self.repo.gather("--ticket")

        self.assertEqual((facts["base"], list(by_path(facts))), (self.base, ["src/app/Feature.java"]))

    def test_since_a_reviewed_version_each_commit_is_unchanged_changed_added_or_dropped(self):
        self.repo.write("src/app/A.java", lines(20, "a"))
        self.repo.commit("A")
        self.repo.write("src/app/B.java", lines(20, "b"))
        self.repo.commit("B")
        self.repo.write("src/app/D.java", lines(20, "d"))
        reviewed = self.repo.commit("D")
        self.repo.git("reset", "-q", "--hard", "HEAD~2")
        self.repo.write("src/app/B.java", lines(19, "b") + "b changed\n")
        self.repo.commit("B")
        self.repo.write("src/app/C.java", lines(20, "c"))
        self.repo.commit("C")

        since = self.repo.gather("--base", self.base, "--reviewed", reviewed)["since"]

        self.assertEqual(since["reviewed"], reviewed)
        self.assertEqual([(r["st"], r["subject"]) for r in since["rows"]],
                         [("same", "A"), ("changed", "B"), ("dropped", "D"), ("added", "C")])

    def test_the_summary_of_a_small_change_lists_the_files_to_read(self):
        self.repo.write("src/app/Service.java", lines(12))
        self.repo.write("src/test/app/ServiceTest.java", lines(7, "t"))

        out = self.repo.run("gather.py", str(self.repo.root / "guides/g"), "--base", self.base).stdout

        self.assertIn("read: src/app/Service.java", out)
        self.assertNotIn("ServiceTest", out)

    def test_lists_the_files_of_one_job_with_their_tier(self):
        self.repo.write("src/a/A.java", lines(1200, "a"))
        self.repo.write("src/b/B.java", lines(400, "b"))
        self.repo.write("src/b/BTest.java", lines(4, "bt"))
        self.repo.gather("--base", self.base)

        out = self.repo.run("files.py", str(self.repo.root / "guides/g"), "--job", "2").stdout

        self.assertEqual(out.splitlines(), ["read A +400 -0 src/b/B.java", "skim A +4 -0 src/b/BTest.java"])


if __name__ == "__main__":
    unittest.main()

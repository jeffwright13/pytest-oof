from sys import exit
from typing import Dict

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual import events
from textual.app import App
from textual.widget import Widget
from textual.widgets import ScrollView, TreeClick

from pytest_oof.resources.tree_control import TreeControl
from pytest_oof.utils import Results, TerminalOutput

TREE_WIDTH = 120
SECTIONS = {
    "FAILURES": "bold red underline",
    "PASSES": "bold green underline",
    "ERRORS": "bold magenta underline",
    "WARNINGS_SUMMARY": "bold yellow underline",
}
CATEGORIES = {
    "FAILURES": "bold red underline",
    "PASSES": "bold green underline",
    "SKIPS": "bold cyan underline",
    "XFAILS": "bold indian_red underline",
    "XPASSES": "bold chartreuse1 underline",
    "ERRORS": "bold magenta underline",
}


class Tab(Widget):
    def __init__(
        self,
        label: str,
        style: str,
        content_type: str,  # either 'section' or 'tree'
    ) -> None:
        super().__init__()
        self.label = label
        self.content_type = content_type
        self.rich_text = Text(label, style=style)


class Tabs(Widget):
    def __init__(
        self,
        tabs: Dict[str, Tab],
    ) -> None:
        super().__init__()
        self.tabs = tabs

    async def action_clicked_tab(self, label: str) -> None:
        # Handle tabs being clicked
        if label == "Quit":
            quit()

        body = self.parent.parent.body
        results = self.parent.parent.results
        terminal_output = self.parent.parent.terminal_output
        section_content = {
            "Summary": results.output_fields.lastline.content
            + results.output_fields.test_session_starts.content
            + results.output_fields.short_test_summary.content,
            "Warnings": results.output_fields.warnings_summary.content,
            "Errors": results.output_fields.errors.content,
            "Full Output": terminal_output.output,
        }
        tree_names = {
            "Failures": "failures_tree",
            "Passes": "passes_tree",
            "Skips": "skips_tree",
            "Xfails": "xfails_tree",
            "Xpasses": "xpasses_tree",
        }

        # Render the clicked tab with bold underline
        for tab_name in self.tabs:
            if tab_name == label:
                self.tabs[tab_name].rich_text.stylize("bold underline")
            else:
                self.tabs[tab_name].rich_text.stylize("not bold not underline")
            self.refresh()

        # Render section info
        if self.tabs[label].content_type == "section":
            self.parent.parent.body.visible = True
            await body.update(Text.from_ansi(section_content[label]))
        # Render tree info
        elif self.tabs[label].content_type == "tree":
            self.parent.parent.view.refresh()
            self.tree_name = tree_names[label]
            await body.update(eval(f"self.parent.parent.{self.tree_name}"))

    def render(self) -> RenderableType:
        # Build up renderable Text instance from a series of Tabs;
        # this simulates a tabbed widget as a workaround until Textual's
        # Tabs object has been released
        text = Text()
        text.append("│ ")
        for tab_name in self.tabs:
            text.append(self.tabs[tab_name].rich_text)
            text.append(" │ ")
            self.tabs[tab_name].rich_text.on(click=f"clicked_tab('{tab_name}')")
        return Panel(text, height=3)


class TuiApp(App):
    async def on_load(self, event: events.Load) -> None:
        # Get test result sections
        # self.results = Results()
        self.results = Results.from_file(
            results_file_path="oof/results.pickle",
        )
        if not self.results.output_fields and self.results.test_results:
            exit()
        self.summary_results = self.results.output_fields.lastline.content.replace(
            "=", ""
        )
        self.terminal_output = TerminalOutput.from_file(
            terminal_output_file_path="oof/terminal_output.ansi",
        )
        await self.bind("q", "quit", "Quit")

    async def on_mount(self) -> None:
        tabs = {
            "Summary": Tab("Summary", "cyan bold underline", content_type="section"),
            "Failures": Tab("Failures", "red", content_type="tree"),
            "Passes": Tab("Passes", "green", content_type="tree"),
            "Skips": Tab("Skips", "yellow", content_type="tree"),
            "Xfails": Tab("Xfails", "yellow", content_type="tree"),
            "Xpasses": Tab("Xpasses", "yellow", content_type="tree"),
            "Warnings": Tab("Warnings", "yellow", content_type="section"),
            "Errors": Tab("Errors", "magenta", content_type="section"),
            "Full Output": Tab("Full Output", "cyan", content_type="section"),
            "Quit": Tab("Quit (Q)", "white", content_type="quit"),
        }
        self.tabs = Tabs(tabs)
        await self.view.dock(self.tabs, edge="top", size=3)

        # Body (to display result sections or result trees)
        self.body = ScrollView(
            Text.from_ansi(
                self.results.output_fields.lastline.content
                + self.results.output_fields.test_session_starts.content
                + self.results.output_fields.short_test_summary.content
            ),
            auto_width=True,
        )
        await self.view.dock(self.body)

        # Define the results trees
        self.failures_tree = TreeControl(
            Text("Failures:", style="bold red underline"),
            {},
            name="failures_tree",
        )
        self.passes_tree = TreeControl(
            Text("Passes:", style="bold green underline"), {}, name="passes_tree"
        )
        self.skips_tree = TreeControl(
            Text("Skips:", style="bold yellow underline"), {}, name="skips_tree"
        )
        self.xpasses_tree = TreeControl(
            Text("Xpasses:", style="bold yellow underline"), {}, name="xpasses_tree"
        )
        self.xfails_tree = TreeControl(
            Text("Xfails:", style="bold yellow underline"), {}, name="xfails_tree"
        )
        self.errors_tree = TreeControl(
            Text("Errors:", style="bold magenta underline"), {}, name="errors_tree"
        )
        for result in self.results.test_results.all_failures():
            await self.failures_tree.add(
                self.failures_tree.root.id,
                Text(result.nodeid),
                {
                    "results": (
                        f"{result.longreprtext or result.capstdout + result.capstderr + result.caplog}"
                    )
                },
            )
        for result in self.results.test_results.all_passes():
            await self.passes_tree.add(
                self.passes_tree.root.id,
                Text(result.nodeid),
                {
                    "results": (
                        f"{result.longreprtext or result.capstdout + result.capstderr + result.caplog}"
                    )
                },
            )
        for result in self.results.test_results.all_skips():
            await self.skips_tree.add(
                self.skips_tree.root.id,
                Text(result.nodeid),
                {
                    "results": (
                        f"{result.longreprtext or result.capstdout + result.capstderr + result.caplog}"
                    )
                },
            )
        for result in self.results.test_results.all_xpasses():
            await self.xpasses_tree.add(
                self.xpasses_tree.root.id,
                Text(result.nodeid),
                {
                    "results": (
                        f"{result.longreprtext or result.capstdout + result.capstderr + result.caplog}"
                    )
                },
            )
        for result in self.results.test_results.all_xfails():
            await self.xfails_tree.add(
                self.xfails_tree.root.id,
                Text(result.nodeid),
                {
                    "results": (
                        f"{result.longreprtext or result.capstdout + result.capstderr + result.caplog}"
                    )
                },
            )
        for result in self.results.test_results.all_errors():
            await self.errors_tree.add(
                self.errors_tree.root.id,
                Text(result.nodeid),
                {
                    "results": (
                        f"{result.longreprtext or result.capstdout + result.capstderr + result.caplog}"
                    )
                },
            )

        await self.failures_tree.root.expand()
        await self.passes_tree.root.expand()
        await self.errors_tree.root.expand()
        await self.skips_tree.root.expand()
        await self.xpasses_tree.root.expand()
        await self.xfails_tree.root.expand()

    async def handle_tree_click(self, message: TreeClick[dict]) -> None:
        # Display results in body when category header is clicked;
        # but don't try processing the category titles
        label = message.node.label
        if label.plain.upper().rstrip(":") in CATEGORIES:
            return
        category = message.sender.name.rstrip("_tree")
        all_tests_in_category = eval(
            f"self.results.test_results.all_{category.lower()}()"
        )
        for test in all_tests_in_category:
            if test.nodeid == label.plain:
                self.text = Text.from_ansi(
                    f"{test.longreprtext or test.capstdout + test.capstderr + test.caplog}"
                )
                break

        await self.body.update(self.text.markup)


def main():
    app = TuiApp()
    app.run()


if __name__ == "__main__":
    main()

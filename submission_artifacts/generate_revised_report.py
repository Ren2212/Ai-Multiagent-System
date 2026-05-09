#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PDF = ROOT / "submission_artifacts" / "generated" / "WarmUp_Revised_Technical_Report.pdf"
BENCHMARK_JSON = ROOT / "searchclient_python" / "benchmark_results_2026-04-19.json"
LIVE_SUMMARY_JSON = ROOT / "submission_artifacts" / "generated" / "live_run_summary.json"


@dataclass(frozen=True)
class CodeRef:
    label: str
    path: str
    line: str
    summary: str


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def fmt_int(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value:,}"


def fmt_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def load_benchmarks() -> list[dict]:
    return json.loads(BENCHMARK_JSON.read_text())


def load_live_summary() -> dict:
    return json.loads(LIVE_SUMMARY_JSON.read_text())


def select_rows(rows: list[dict], level_names: list[str]) -> list[dict]:
    order = {"bfs": 0, "astar": 1, "wastar5": 2, "greedy": 3}
    selected = [row for row in rows if row["level"] in level_names]
    selected.sort(key=lambda row: (level_names.index(row["level"]), order.get(row["algo"], 99)))
    return selected


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleLarge",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1b365d"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#1b365d"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#2b2b2b"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeSmall",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            leftIndent=10,
            rightIndent=10,
            borderColor=colors.HexColor("#d9d9d9"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#f8f8f8"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCellBold",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
        )
    )
    return styles


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(doc.leftMargin, 1.1 * cm, "Warm-Up revised technical report")
    canvas.drawRightString(A4[0] - doc.rightMargin, 1.1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def make_par(text: str, styles, style_name: str = "BodySmall") -> Paragraph:
    return Paragraph(text, styles[style_name])


def bullet_list(items: list[str], styles) -> ListFlowable:
    return ListFlowable(
        [
            ListItem(Paragraph(item, styles["BodySmall"]), leftIndent=10)
            for item in items
        ],
        bulletType="bullet",
        start="circle",
        bulletFontName="Helvetica",
        bulletFontSize=8,
        leftIndent=14,
    )


def make_table(data: list[list[str]], styles, col_widths=None, repeat_rows: int = 1) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=repeat_rows)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e7f5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1b365d")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 9.5),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#c8c8c8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fbff")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_code_refs() -> list[CodeRef]:
    return [
        CodeRef(
            label="CLI entry point",
            path="searchclient_python/main.py",
            line="5-14",
            summary="Declares the available search strategies and max-memory option.",
        ),
        CodeRef(
            label="Level parser and planner selection",
            path="searchclient_python/searchclient/client.py",
            line="19-143",
            summary="Parses colors, walls, boxes, goals, and chooses BFS/DFS/A*/WA*/greedy.",
        ),
        CodeRef(
            label="Phase trigger and phase planner",
            path="searchclient_python/searchclient/client.py",
            line="218-299",
            summary="Enables phased decomposition on large multi-agent instances and runs the per-letter subsearches.",
        ),
        CodeRef(
            label="Generic graph search",
            path="searchclient_python/searchclient/graphsearch.py",
            line="15-116",
            summary="Maintains frontier, explored set, best-g values, and goal termination.",
        ),
        CodeRef(
            label="Best-first frontier",
            path="searchclient_python/searchclient/frontier.py",
            line="84-125",
            summary="Priority queue with deterministic tie-breaking and stale-entry suppression.",
        ),
        CodeRef(
            label="Successor generation and pruning",
            path="searchclient_python/searchclient/state.py",
            line="167-339",
            summary="Generates successors, ranks active agents, and filters actions toward useful boxes.",
        ),
        CodeRef(
            label="Applicability, result, and conflicts",
            path="searchclient_python/searchclient/state.py",
            line="343-482",
            summary="Implements Move/Push/Pull legality, state transition, and multi-agent conflict tests.",
        ),
        CodeRef(
            label="Heuristic computation",
            path="searchclient_python/searchclient/heuristic.py",
            line="17-269",
            summary="Precomputes wall-aware distances and defines A*, WA*, and greedy evaluations.",
        ),
        CodeRef(
            label="Benchmark artifact",
            path="searchclient_python/benchmark_results_2026-04-19.json",
            line="1-...",
            summary="Stored benchmark results used for the comparison tables in this report.",
        ),
    ]


def benchmark_table_rows(rows: list[dict]) -> list[list[str]]:
    data = [[
        "Level",
        "Strategy",
        "Solved",
        "Expanded",
        "Generated",
        "Search s",
        "Plan len",
    ]]
    for row in rows:
        data.append(
            [
                row["level"].replace(".lvl", ""),
                row["algo"],
                row["server_solved"],
                fmt_int(row["expanded"]),
                fmt_int(row["generated"]),
                fmt_float(row["search_time_s"]),
                fmt_int(row["plan_len_reported"]),
            ]
        )
    return data


def live_table_rows(live_summary: dict) -> list[list[str]]:
    data = [[
        "Live run artifact",
        "Solved",
        "Expanded",
        "Generated",
        "Actions",
        "Wall s",
        "Notes",
    ]]
    for row in live_summary["live_runs"]:
        last = row.get("last_status") or {}
        note = "phased" if row.get("phased") else "single search"
        data.append(
            [
                row["log"].replace("_2026-04-26.log", ""),
                row.get("solved", "-"),
                fmt_int(last.get("expanded")),
                fmt_int(last.get("generated")),
                fmt_int(row.get("actions_used")),
                fmt_float(row.get("wall_time_s")),
                note,
            ]
        )
    return data


def phase_table_rows(live_summary: dict) -> list[list[str]]:
    phase_totals = live_summary.get("phase_totals") or {}
    data = [[
        "Phase",
        "Agent",
        "Letter",
        "Expanded",
        "Generated",
        "Time s",
    ]]
    for phase in phase_totals.get("phases", []):
        final = phase.get("final") or {}
        agent = f"{phase['agent']} ({phase['color']})" if phase.get("agent") is not None else "-"
        data.append(
            [
                f"{phase['color']}:{phase['letter']}",
                agent,
                phase.get("letter", "-"),
                fmt_int(final.get("expanded")),
                fmt_int(final.get("generated")),
                fmt_float(final.get("time_s")),
            ]
        )
    return data


def build_story() -> list:
    styles = build_styles()
    benchmarks = load_benchmarks()
    live_summary = load_live_summary()
    stored_rows = select_rows(
        benchmarks,
        [
            "SAsimple0.lvl",
            "SAsimple2.lvl",
            "SAsimple3.lvl",
            "MAExample.lvl",
            "MAsimple1.lvl",
            "MAthomasAppartment.lvl",
        ],
    )
    phase_totals = live_summary.get("phase_totals", {})
    code_refs = build_code_refs()

    story: list = []

    story.append(Spacer(1, 1.6 * cm))
    story.append(Paragraph("Revised Warm-Up Video Document and Technical Appendix", styles["TitleLarge"]))
    story.append(
        Paragraph(
            "Multi-Agent Systems, SearchClient implementation, benchmark evidence, and reproducible testing instructions",
            styles["Subtitle"],
        )
    )
    story.append(
        Paragraph(
            "Prepared from the current workspace on 2026-04-26. The purpose of this document is to directly answer the lecturer feedback: provide a better structure, explain the algorithmic ideas in enough detail to evaluate them, and include the concrete code and test procedure.",
            styles["BodySmall"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))
    story.append(make_par("<b>Submission contents:</b>", styles))
    story.append(
        bullet_list(
            [
                "This PDF report, which explains the solver, its design choices, its limitations, and how to reproduce the results.",
                "The full code in <font name='Courier'>searchclient_python/</font> together with the original level set and <font name='Courier'>server.jar</font> in the submission bundle.",
                "Stored benchmark data in <font name='Courier'>searchclient_python/benchmark_results_2026-04-19.json</font> and fresh live-run artifacts in <font name='Courier'>submission_artifacts/logs/</font>.",
                "Replayable server logs for recording an improved video with the official GUI.",
            ],
            styles,
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(make_par("<b>Direct response to the lecturer feedback.</b> The document below is structured as: problem definition, solver architecture, detailed algorithm description, code mapping, experimental evidence, how to test, and a suggested video script.", styles))

    story.append(Paragraph("1. Problem and Deliverables", styles["SectionHeading"]))
    story.append(
        make_par(
            "The warm-up assignment asks for a client that solves hospital/MAPF-style levels using search. A level contains walls, colored agents, colored boxes, and goal cells. A solution is a sequence of joint actions that moves every box to its matching letter goal and every agent to its agent goal if such a goal is present.",
            styles,
        )
    )
    story.append(
        make_par(
            "The deliverable in this revised submission is not only a video script. It is a technical package: the code itself, reproducible commands, benchmark data, replay logs, and this written explanation that connects the algorithmic ideas to concrete source files.",
            styles,
        )
    )
    story.append(make_par("<b>Main files to inspect.</b>", styles))
    ref_rows = [["Component", "Location", "Purpose"]]
    for ref in code_refs:
        ref_rows.append(
            [
                ref.label,
                f"{ref.path}:{ref.line}",
                ref.summary,
            ]
        )
    story.append(make_table(ref_rows, styles, col_widths=[4.1 * cm, 6.2 * cm, 7.0 * cm]))

    story.append(Paragraph("2. Solver Architecture", styles["SectionHeading"]))
    story.append(
        make_par(
            "At a high level, the client follows a simple pipeline:",
            styles,
        )
    )
    story.append(
        Preformatted(
            "read level from server stdin\n"
            "  -> build initial State(walls, boxes, agents, goals, colors)\n"
            "  -> choose planning mode\n"
            "       small / simple instances: one global search\n"
            "       large multi-agent instances: phased decomposition + tail search\n"
            "  -> output one joint action per time step to the server\n",
            styles["CodeSmall"],
        )
    )
    story.append(
        bullet_list(
            [
                "The CLI supports <font name='Courier'>-bfs</font>, <font name='Courier'>-dfs</font>, <font name='Courier'>-astar</font>, <font name='Courier'>-wastar [w]</font>, and <font name='Courier'>-greedy</font> (<font name='Courier'>main.py:5-14</font>).",
                "The initial state is parsed in <font name='Courier'>client.py:19-113</font>; walls, boxes, goals, and colors are stored in class variables of <font name='Courier'>State</font>.",
                "Search is executed through a generic graph-search loop in <font name='Courier'>graphsearch.py:15-116</font> and different frontier implementations in <font name='Courier'>frontier.py</font>.",
                "Multi-agent branching is controlled mainly inside <font name='Courier'>state.py</font>, where the code decides which agents may act and which actions are worth expanding.",
            ],
            styles,
        )
    )

    story.append(Paragraph("3. State Representation and Legality Tests", styles["SectionHeading"]))
    story.append(
        make_par(
            "The state representation is explicit. A state stores three dynamic objects: the row of each agent, the column of each agent, and a 2D array of box letters. The parent state, the joint action used to reach the state, and the path cost <font name='Courier'>g</font> are also stored. Walls, goals, and colors are static class-level data (<font name='Courier'>state.py:22-35</font>).",
            styles,
        )
    )
    story.append(
        make_par(
            "The action set contains <font name='Courier'>NoOp</font>, four <font name='Courier'>Move</font> actions, twelve <font name='Courier'>Push</font> actions, and eight <font name='Courier'>Pull</font> actions (<font name='Courier'>action.py:13-72</font>). Applicability is checked per action type in <font name='Courier'>state.py:343-383</font>:",
            styles,
        )
    )
    story.append(
        bullet_list(
            [
                "<b>Move:</b> the destination cell must be inside the grid, not a wall, not occupied by a box, and not occupied by another agent.",
                "<b>Push:</b> the adjacent cell in the agent movement direction must contain a box of the same color as the agent, and the target box destination must be free.",
                "<b>Pull:</b> the agent destination must be free, and the source box must be located behind the agent relative to the box movement direction; the pulled box must have the same color as the agent.",
            ],
            styles,
        )
    )
    story.append(
        make_par(
            "When a joint action is applied, <font name='Courier'>state.py:387-423</font> copies the state and updates agents and boxes deterministically. For the full synchronous model, conflict tests are implemented in <font name='Courier'>state.py:427-482</font>, covering agent-agent collisions, edge swaps, two agents grabbing the same box, two boxes moving to the same cell, and agent-box destination conflicts.",
            styles,
        )
    )

    story.append(Paragraph("4. Baseline Graph Search", styles["SectionHeading"]))
    story.append(
        make_par(
            "The graph-search loop is textbook in structure but includes one important practical improvement: a <font name='Courier'>best_g</font> map is maintained so that stale frontier entries can be ignored when a cheaper path to the same state has already been generated (<font name='Courier'>graphsearch.py:72-115</font>). That matters for best-first strategies implemented on a heap.",
            styles,
        )
    )
    story.append(
        Preformatted(
            "frontier.add(initial_state)\n"
            "best_g[initial_state] = 0\n"
            "explored = set()\n"
            "while frontier not empty:\n"
            "    state = frontier.pop()\n"
            "    if state.g != best_g[state]:\n"
            "        continue  # stale heap entry\n"
            "    if goal_test(state):\n"
            "        return extract_plan(state)\n"
            "    explored.add(state)\n"
            "    for neighbor in expand(state):\n"
            "        if neighbor not in explored and (neighbor not in best_g or neighbor.g < best_g[neighbor]):\n"
            "            best_g[neighbor] = neighbor.g\n"
            "            frontier.add(neighbor)\n",
            styles["CodeSmall"],
        )
    )
    story.append(
        bullet_list(
            [
                "<b>BFS</b> uses a FIFO queue and is the clean uninformed baseline.",
                "<b>DFS</b> uses a LIFO stack and is included mainly to satisfy the assignment requirements and compare search behavior.",
                "<b>A*</b>, <b>WA*</b>, and <b>Greedy</b> all use the best-first frontier in <font name='Courier'>frontier.py:84-125</font> with different evaluation functions defined in <font name='Courier'>heuristic.py:244-269</font>.",
            ],
            styles,
        )
    )

    story.append(Paragraph("5. Heuristic Design", styles["SectionHeading"]))
    story.append(
        make_par(
            "The heuristic implementation begins from the assignment idea of counting unsatisfied goals, but the active configuration in the code is a stronger distance-based heuristic (<font name='Courier'>heuristic.py:32-35</font> sets <font name='Courier'>HEURISTIC_MODE = \"goal_dist\"</font>).",
            styles,
        )
    )
    story.append(make_par("<b>Why the heuristic is stronger than simple Manhattan distance.</b>", styles))
    story.append(
        bullet_list(
            [
                "Before search starts, the code runs a BFS from each goal cell over the static wall grid (<font name='Courier'>heuristic.py:49-53</font> and <font name='Courier'>214-235</font>).",
                "These precomputed maps return the shortest wall-respecting path length from any reachable cell to the goal. This is more informative than Manhattan distance because walls are respected.",
                "For agent goals, the heuristic sums the precomputed distance from each agent to its own goal (<font name='Courier'>heuristic.py:126-135</font>).",
                "For box goals, the heuristic groups boxes by letter, then greedily matches each goal cell to the nearest currently available box of the same letter (<font name='Courier'>heuristic.py:137-174</font>).",
                "An extra term encourages an agent of the correct color to approach an unsolved box it can manipulate (<font name='Courier'>heuristic.py:175-200</font>).",
                "If static deadlock pruning is enabled and a state contains deadlocks, a large penalty is returned (<font name='Courier'>heuristic.py:117-123</font>).",
            ],
            styles,
        )
    )
    story.append(
        make_par(
            "<b>Important honesty note:</b> because the heuristic uses greedy box-goal assignment and an added agent-to-box encouragement term, it should be treated as an aggressive guiding heuristic rather than a formally admissible lower bound. Therefore the mode exposed as <font name='Courier'>-astar</font> is best understood as <font name='Courier'>f(n) = g(n) + h(n)</font> best-first search with a strong heuristic, not as a guarantee of optimality.",
            styles,
        )
    )
    story.append(
        make_par(
            "The implementation of the evaluation functions is direct: A* uses <font name='Courier'>g + h</font>, weighted A* uses <font name='Courier'>g + w*h</font>, and greedy uses <font name='Courier'>h</font> only (<font name='Courier'>heuristic.py:244-269</font>).",
            styles,
        )
    )

    story.append(Paragraph("6. Multi-Agent Branching Reduction", styles["SectionHeading"]))
    story.append(
        make_par(
            "The main challenge in the multi-agent levels is branching. If each agent can choose several actions, the naive joint-action successor function grows as the Cartesian product of those action sets. The code therefore defaults to a reduced successor generator in <font name='Courier'>state.py:248-339</font>.",
            styles,
        )
    )
    story.append(make_par("<b>Design choice 1: sequential joint-action mode.</b>", styles))
    story.append(
        make_par(
            "The class variable <font name='Courier'>State.JOINT_ACTION_MODE</font> is set to <font name='Courier'>\"sequential\"</font>. In this mode, a successor usually contains one non-<font name='Courier'>NoOp</font> action and all other agents perform <font name='Courier'>NoOp</font> (<font name='Courier'>state.py:284-315</font>). This is a deliberate approximation: it drastically cuts branching, but it also means the searched plan space is more asynchronous than the full synchronous server model.",
            styles,
        )
    )
    story.append(make_par("<b>Design choice 2: active-agent selection.</b>", styles))
    story.append(
        bullet_list(
            [
                "The code collects all unsolved boxes grouped by color (<font name='Courier'>state.py:169-182</font>).",
                "Agents are ranked by Manhattan distance to the nearest unsolved box of their color (<font name='Courier'>state.py:190-201</font>).",
                "At most two agents are kept active by default (<font name='Courier'>State.MAX_ACTIVE_AGENTS = 2</font>), and a rotating fallback agent is added so that one agent is not starved forever (<font name='Courier'>state.py:289-299</font>).",
            ],
            styles,
        )
    )
    story.append(make_par("<b>Design choice 3: action filtering.</b>", styles))
    story.append(
        bullet_list(
            [
                "For each active agent, applicable actions are split into box-moving actions and pure moves (<font name='Courier'>state.py:212-246</font>).",
                "If the agent has useful unsolved boxes of its color, moves are ranked by whether they reduce the distance to the nearest target.",
                "If box actions are available, they are preferred, optionally with one improving move added.",
                "If only move actions are available, only the best one or two moves are expanded. This is controlled by <font name='Courier'>State.MAX_MOVE_ACTIONS_PER_AGENT = 2</font>.",
            ],
            styles,
        )
    )
    story.append(
        make_par(
            "These pruning ideas are pragmatic rather than theoretically clean. They work because the warm-up levels are small enough that reducing branching helps far more than broadening the search helps, but they can miss solutions or yield longer plans on tightly coupled instances.",
            styles,
        )
    )

    story.append(Paragraph("7. Phased Decomposition in Detail", styles["SectionHeading"]))
    story.append(
        make_par(
            "The lecturer specifically commented that the previous explanation of phased decomposition was not detailed enough. This section therefore states the exact trigger, ordering rule, inner objective, search strategy, stopping criterion, and fallback mechanism as implemented in <font name='Courier'>client.py:218-299</font>.",
            styles,
        )
    )
    story.append(make_par("<b>Trigger condition.</b>", styles))
    story.append(
        bullet_list(
            [
                "Phased planning is never used for BFS or DFS (<font name='Courier'>client.py:219-221</font>).",
                "For informed search, it is enabled only when the level has at least three agents and at least ten unsolved boxes in the initial state (<font name='Courier'>client.py:222</font>).",
                "This means the decomposition is reserved for the larger instances where a flat global search became too expensive.",
            ],
            styles,
        )
    )
    story.append(make_par("<b>Agent ordering.</b>", styles))
    story.append(
        make_par(
            "Agents are sorted by the distance from the agent to the nearest unsolved same-color box (<font name='Courier'>client.py:232-235</font>). Intuitively, the algorithm starts with the agent that is already closest to useful work.",
            styles,
        )
    )
    story.append(make_par("<b>Per-color letter list.</b>", styles))
    story.append(
        make_par(
            "For a chosen agent, the code enumerates the unsatisfied goal letters whose color matches that agent’s color (<font name='Courier'>client.py:183-195</font> and <font name='Courier'>242-244</font>). Example: if an agent is blue and the unsatisfied blue box goals are D, E, F, G, then the phase sequence for that agent is exactly D, E, F, G in the order they are discovered while scanning the goal grid.",
            styles,
        )
    )
    story.append(make_par("<b>Phase search itself.</b>", styles))
    story.append(
        Preformatted(
            "for agent in sorted_agents:\n"
            "    ACTIVE_AGENT_IDS = {agent}\n"
            "    for letter in unsatisfied_letters_for_color(agent_color):\n"
            "        phase_root = clone(current_state)\n"
            "        phase_frontier = WA*(w = 15)\n"
            "        phase_goal = all goals with this letter are satisfied\n"
            "        phase_plan = search(phase_root, phase_frontier, phase_goal, max_expanded = 40000)\n"
            "        if phase_plan exists:\n"
            "            execute phase_plan into current_state and append it to the global prefix\n"
            "ACTIVE_AGENT_IDS = None\n"
            "if current_state is not yet goal:\n"
            "    run one final global search from the new current_state\n",
            styles["CodeSmall"],
        )
    )
    story.append(
        bullet_list(
            [
                "The per-phase search always uses weighted A* with weight 15, regardless of the outer strategy (<font name='Courier'>client.py:248-252</font>). This is an aggressive speed choice.",
                "The phase goal is not the full level goal. It is only that all goals for one letter become satisfied (<font name='Courier'>client.py:253-257</font> together with <font name='Courier'>175-180</font>).",
                "The phase search is capped at <font name='Courier'>max_expanded = 40,000</font> nodes (<font name='Courier'>client.py:264-269</font>). If the phase does not finish, the code logs that fact and moves on to the next letter.",
                "If the phased prefix already solves the entire level, the algorithm stops. Otherwise, a final tail search is launched from the resulting intermediate state using the strategy originally requested on the command line (<font name='Courier'>client.py:285-299</font>).",
                "If no complete solution is found but some useful prefix has been generated, the current code returns the best-effort prefix so the GUI still shows progress (<font name='Courier'>client.py:295-299</font>).",
            ],
            styles,
        )
    )
    story.append(
        make_par(
            "<b>Why this works in practice.</b> The decomposition turns one hard global coordination problem into a sequence of smaller subproblems that are much easier for weighted A* to solve. The price is that the decomposition can be myopic: it commits to a color and letter order that may later be inconvenient.",
            styles,
        )
    )
    story.append(make_par("<b>Live trace of the phased planner on <font name='Courier'>MAthomasAppartment.lvl</font>.</b>", styles))
    story.append(
        make_par(
            f"The workspace contains a fresh run log in <font name='Courier'>submission_artifacts/logs/MAthomasAppartment_astar_2026-04-26.log</font>. Summing the final status line of each phase gives {fmt_int(phase_totals.get('cumulative_expanded'))} expanded states and {fmt_int(phase_totals.get('cumulative_generated'))} generated states before the final 633-action solution was reported. This is more informative than the stored benchmark JSON, which only captured the last phase’s status line for phased runs.",
            styles,
        )
    )
    story.append(make_table(phase_table_rows(live_summary), styles, col_widths=[3.0 * cm, 3.1 * cm, 2.0 * cm, 3.0 * cm, 3.2 * cm, 2.3 * cm]))

    story.append(PageBreak())

    story.append(Paragraph("8. Experimental Evidence", styles["SectionHeading"]))
    story.append(
        make_par(
            "Two kinds of evidence are included: a stored benchmark table from 2026-04-19 and fresh live runs executed while preparing this document on 2026-04-26. The stored benchmark file is useful for broad comparison across algorithms. The fresh runs confirm that the current workspace still reproduces representative results.",
            styles,
        )
    )
    story.append(make_par("<b>Stored benchmark excerpt.</b>", styles))
    story.append(
        make_par(
            "The table below comes from <font name='Courier'>searchclient_python/benchmark_results_2026-04-19.json</font>. For non-phased runs it is reliable directly. For phased runs such as <font name='Courier'>MAthomasAppartment</font>, the reported expanded/generated counts reflect only the final phase status line, not the cumulative total; that caveat is handled explicitly in the live-run section.",
            styles,
        )
    )
    story.append(make_table(benchmark_table_rows(stored_rows), styles, col_widths=[3.7 * cm, 2.0 * cm, 1.5 * cm, 2.2 * cm, 2.4 * cm, 1.9 * cm, 1.8 * cm]))

    story.append(Spacer(1, 0.2 * cm))
    story.append(make_par("<b>Key observations from the stored benchmark data.</b>", styles))
    story.append(
        bullet_list(
            [
                "On <font name='Courier'>SAsimple2</font>, BFS expands 1,359 states, whereas the current <font name='Courier'>g+h</font> best-first mode expands only 36 and still returns a 30-step plan.",
                "On <font name='Courier'>MAsimple1</font>, BFS expands 80,724 states and takes 23.307 s; greedy and WA*(5) solve the same level in 27 expansions and roughly 0.02 s, with the same reported plan length 26.",
                "On <font name='Courier'>MAExample</font>, A* reduces generated states from 2,478 to 972 relative to BFS, while greedy/WA*(5) reduce it further to around 120 at the cost of a slightly longer plan.",
                "Some instances remain unsolved, for example <font name='Courier'>SAsimple3</font> and <font name='Courier'>MAsimple3</font>. The report therefore does not claim universal robustness.",
                "The large <font name='Courier'>MAthomasAppartment</font> instance is exactly where phased decomposition matters: BFS times out after generating 449,278 states in the stored run, whereas the informed phased planner completes the instance.",
            ],
            styles,
        )
    )

    story.append(make_par("<b>Fresh live verification runs (2026-04-26).</b>", styles))
    story.append(make_table(live_table_rows(live_summary), styles, col_widths=[7.1 * cm, 1.5 * cm, 2.1 * cm, 2.3 * cm, 1.8 * cm, 1.7 * cm, 2.0 * cm]))
    story.append(
        make_par(
            "The fresh artifacts also include replay logs produced by the official server: <font name='Courier'>submission_artifacts/logs/SAsimple2_astar_replay_2026-04-26.log</font>, <font name='Courier'>submission_artifacts/logs/MAsimple1_greedy_replay_2026-04-26.log</font>, and <font name='Courier'>submission_artifacts/logs/MAthomasAppartment_astar_replay_2026-04-26.log</font>.",
            styles,
        )
    )

    story.append(Paragraph("9. How to Run and Test the Code", styles["SectionHeading"]))
    story.append(
        make_par(
            "The goal of this section is that a lecturer or TA can test the solver immediately. The required runtime is minimal: Python 3 and Java 11+ are enough. The only Python dependency declared in <font name='Courier'>pyproject.toml</font> is <font name='Courier'>psutil == 6.1.1</font>, used only for memory reporting.",
            styles,
        )
    )
    story.append(make_par("<b>Basic commands.</b>", styles))
    story.append(
        Preformatted(
            "cd searchclient_python\n"
            "python3 main.py -h\n"
            "\n"
            "# Single-agent example\n"
            "java -jar ../server.jar -l ../levels/SAsimple2.lvl \\\n"
            "  -c \"python3 main.py -astar --max-memory 4096\" -t 60 -s 0\n"
            "\n"
            "# Multi-agent example\n"
            "java -jar ../server.jar -l ../levels/MAsimple1.lvl \\\n"
            "  -c \"python3 main.py -greedy --max-memory 4096\" -t 60 -s 0\n"
            "\n"
            "# Larger phased example\n"
            "java -jar ../server.jar -l ../levels/MAthomasAppartment.lvl \\\n"
            "  -c \"python3 main.py -astar --max-memory 4096\" -t 60 -s 0\n",
            styles["CodeSmall"],
        )
    )
    story.append(make_par("<b>How to generate an official replay log for the video.</b>", styles))
    story.append(
        Preformatted(
            "cd searchclient_python\n"
            "java -jar ../server.jar -l ../levels/MAthomasAppartment.lvl \\\n"
            "  -c \"python3 main.py -astar --max-memory 4096\" \\\n"
            "  -t 60 -o ../submission_artifacts/logs/my_run.log\n"
            "\n"
            "cd ..\n"
            "java -jar server.jar -r submission_artifacts/logs/my_run.log -g -p -s 200\n",
            styles["CodeSmall"],
        )
    )
    story.append(
        make_par(
            "The replay command is the recommended way to record the revised video, because it uses the official course server GUI with pause, step, playback speed, and fullscreen support. The server help confirms these flags (<font name='Courier'>-g</font>, <font name='Courier'>-p</font>, <font name='Courier'>-s</font>, <font name='Courier'>-o</font>, and <font name='Courier'>-r</font>).",
            styles,
        )
    )

    story.append(Paragraph("10. Suggested Structure for the Revised Video", styles["SectionHeading"]))
    story.append(
        make_par(
            "The lecturer asked for a better-structured video. A simple way to improve the resubmission is to follow an explicit script and tie every spoken claim to visible code or visible execution output. The following outline is a concrete template for a 9-10 minute recording.",
            styles,
        )
    )
    story.append(
        bullet_list(
            [
                "<b>0:00-0:45:</b> State the assignment, show the repository structure, and say what is included in the submission package.",
                "<b>0:45-2:00:</b> Explain the state representation: walls, agents, boxes, goals, colors, and why color constraints matter.",
                "<b>2:00-3:15:</b> Show the generic graph-search loop and the frontier implementations. Make it clear how BFS/DFS differ from best-first search.",
                "<b>3:15-5:00:</b> Explain the heuristic carefully: precomputed wall-aware distances, box-goal matching, and the trade-off between speed and admissibility.",
                "<b>5:00-7:15:</b> Explain multi-agent branching reduction and then the phased decomposition algorithm step by step, including the exact trigger condition, WA*(15), per-letter subgoals, and fallback tail search.",
                "<b>7:15-8:15:</b> Show benchmark results and compare at least one single-agent level and one multi-agent level.",
                "<b>8:15-9:15:</b> Replay the official server log on a representative level and narrate what the agents are doing.",
                "<b>9:15-10:00:</b> End with limitations: the heuristic is aggressive, pruning sacrifices guarantees, and some levels remain unsolved.",
            ],
            styles,
        )
    )
    story.append(
        make_par(
            "The important improvement over the previous submission is that the video should not only show that the system works. It should also explain why the code is written this way, what each approximation buys, and what it gives up.",
            styles,
        )
    )

    story.append(Paragraph("11. Limitations and Honest Assessment", styles["SectionHeading"]))
    story.append(
        bullet_list(
            [
                "The distance heuristic is tuned for performance, not optimality guarantees. The <font name='Courier'>-astar</font> mode is therefore not formally optimal A*.",
                "Sequential joint-action mode and action pruning reduce branching dramatically, but they can also miss globally coordinated solutions or produce longer plans than a richer synchronous search would.",
                "Static deadlock pruning is disabled by default because classical Sokoban deadlock rules are not generally sound in a domain with Pull actions (<font name='Courier'>state.py:18-20</font>).",
                "The benchmark JSON should be read carefully on phased runs because a naive parser records only the final phase’s status line. This report corrects that by also including the fresh phase-by-phase live trace.",
                "Some benchmark levels remain unsolved, notably <font name='Courier'>SAsimple3</font> and <font name='Courier'>MAsimple3</font>, so the solver is best presented as a strong warm-up implementation rather than a complete MAPF planner.",
            ],
            styles,
        )
    )

    story.append(Paragraph("12. Conclusion", styles["SectionHeading"]))
    story.append(
        make_par(
            "The revised submission now contains what the lecturer asked for: a structured explanation of the algorithmic ideas, a detailed account of the phased decomposition strategy, concrete mappings from those ideas to code files, reproducible commands, benchmark data, and replayable logs for a better video. The strongest technical idea in the implementation is not any single search strategy by itself; it is the combination of (1) wall-aware heuristic guidance, (2) branching reduction in multi-agent successor generation, and (3) phased subgoal planning on the larger instances.",
            styles,
        )
    )
    story.append(
        make_par(
            "If this document is followed as a recording script, the revised video should be far easier to evaluate than the earlier attempt because every major design decision is now explicit and testable.",
            styles,
        )
    )

    return story


def main() -> None:
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.7 * cm,
        title="Revised Warm-Up Technical Report",
        author="OpenAI Codex",
    )
    story = build_story()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Wrote {OUTPUT_PDF}")


if __name__ == "__main__":
    main()

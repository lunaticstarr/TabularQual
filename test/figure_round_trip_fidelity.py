"""
Round-trip fidelity figures for TabularQual benchmarking (BioDivine dataset).

Main figure  — "Can you trust this tool for round-trip conversion?"
  Panel A : Summary bar — % of models with full round-trip fidelity per model source
  Panel B : Topology scatter — species / transition counts before vs. after
  Panel C : Rule fidelity histogram — per-model fraction of transition rules preserved
  Panel D : Annotation fidelity by qualifier type — retention rate per RDF qualifier
  Panel E : Conversion time boxplots (existing panel B, reframed)

Supplementary figure — "Dataset characteristics" (moved from main)
  Panel S1A : Model scale scatter (original panel A)
  Panel S1B : Species annotation density (original panel C)
  Panel S1C : Transition annotation density (original panel D)

Usage:
    python figure_round_trip_fidelity.py

Outputs are saved as PDF next to this script.
"""

from __future__ import annotations

import os
import re
import sys
import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import libsbml
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

# ---------------------------------------------------------------------------
# Paths — adjust if your data live elsewhere
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
BIODIVINE_DIR = Path("/Users/luna/Desktop/CRBM/AMAS_proj/Models/BioDivine_260125")
SOURCES_DIR = BIODIVINE_DIR / "sources"
CONVERTED_SBML_DIR = BIODIVINE_DIR / "converted_sbml_260420"
RESULTS_CSV = SCRIPT_DIR / "biodivine_260420_results.csv"

sys.path.insert(0, str(SCRIPT_DIR.parent))
from tabularqual.sbml_reader import read_sbml  # noqa: E402

# ---------------------------------------------------------------------------
# Visual style
# ---------------------------------------------------------------------------

SOURCE_PALETTE = {
    "cell-collective": "#4E9AC7",
    "ginsim": "#E8853D",
    "biomodels": "#56A868",
    "other": "#A585C5",
}
SOURCE_ORDER = ["cell-collective", "ginsim", "biomodels", "other"]

MATCH_GREEN = "#1D9E75"
MISS_RED = "#E24B4A"

# ---------------------------------------------------------------------------
# Source mapping helpers
# ---------------------------------------------------------------------------


def build_source_map() -> Dict[str, str]:
    """
    Returns {model_filename: source_label} from BioDivine metadata.json files.
    Priority: ginsim > biomodels > cell-collective > other.
    """
    src_map: Dict[str, str] = {}
    if not SOURCES_DIR.exists():
        return src_map

    for folder in sorted(SOURCES_DIR.iterdir()):
        meta = folder / "metadata.json"
        if not meta.exists():
            continue
        with open(meta) as fh:
            data = json.load(fh)
        keywords = data.get("keywords", [])
        num = folder.name.split("_")[0]

        if "ginsim" in keywords:
            label = "ginsim"
        elif "biomodels" in keywords:
            label = "biomodels"
        elif "cell-collective" in keywords:
            label = "cell-collective"
        else:
            label = "other"

        # The SBML files are named <num>_<NAME>_source.sbml
        # Reconstruct partial key from numeric prefix only
        src_map[num] = label

    return src_map


def assign_source(model_filename: str, src_map: Dict[str, str]) -> str:
    """Extract leading numeric prefix from filename and look up the source."""
    num = model_filename.split("_")[0]
    return src_map.get(num, "other")


# ---------------------------------------------------------------------------
# Annotation fidelity by qualifier type
# ---------------------------------------------------------------------------


def _extract_qualifier_uri_pairs(sbml_path: str) -> List[Tuple[str, str]]:
    """
    Extract all (full_qualifier, normalized_uri) pairs from species and
    transition annotations in a SBML-qual file using raw XML regex.

    Returns list of ("bqbiol:is", "pubmed:12345") style tuples.
    """
    reader = libsbml.SBMLReader()
    doc = reader.readSBML(sbml_path)
    model = doc.getModel()
    if model is None:
        return []
    qp = model.getPlugin("qual")
    if qp is None:
        return []

    pairs: List[Tuple[str, str]] = []
    entities = (
        [qp.getQualitativeSpecies(i) for i in range(qp.getNumQualitativeSpecies())]
        + [qp.getTransition(i) for i in range(qp.getNumTransitions())]
    )
    for entity in entities:
        if not entity.isSetAnnotation():
            continue
        anno = entity.getAnnotationString()
        # Walk each qualifier block: <bqbiol:is> ... </bqbiol:is>
        for block_m in re.finditer(
            r'<(bq(?:biol|model):\w+)>(.*?)</\1>', anno, re.DOTALL
        ):
            qualifier = block_m.group(1)
            block = block_m.group(2)
            for uri_m in re.finditer(r'rdf:resource="([^"]+)"', block):
                uri = uri_m.group(1)
                # Normalize URI: strip common prefixes
                uri = (
                    uri.replace("urn:miriam:", "")
                    .replace("https://identifiers.org/", "")
                    .replace("http://identifiers.org/", "")
                    .strip()
                )
                pairs.append((qualifier, uri))
    return pairs


def compute_annotation_fidelity_by_qualifier(
    orig_path: str, conv_path: str
) -> Dict[str, Tuple[int, int]]:
    """
    Returns {qualifier: (n_original, n_retained)} across all entities.
    """
    orig_pairs = _extract_qualifier_uri_pairs(orig_path)
    conv_set = set(_extract_qualifier_uri_pairs(conv_path))

    by_qual: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    for qual, uri in orig_pairs:
        n, r = by_qual[qual]
        retained = 1 if (qual, uri) in conv_set else 0
        by_qual[qual] = (n + 1, r + retained)
    return dict(by_qual)


# ---------------------------------------------------------------------------
# Rule fidelity helpers
# ---------------------------------------------------------------------------


def _normalize_rule(rule: Optional[str]) -> str:
    """Strip surrounding whitespace and collapse internal runs."""
    if rule is None:
        return ""
    return " ".join(rule.split())


def _rule_to_sympy(rule_str: str):
    """
    Convert an operator-style Boolean rule string (&, |, !) into a SymPy
    expression.  Variable names are preserved as SymPy Symbol objects.
    Returns None on parse failure.
    """
    try:
        from sympy import symbols as sym_symbols

        # Extract variable names (sort longest-first to avoid partial substitution)
        var_names = sorted(
            set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\b', rule_str)),
            key=len,
            reverse=True,
        )
        if not var_names:
            return None

        # Map each name to a placeholder token _vN_ and a SymPy Symbol
        sym_dict: Dict[str, object] = {}
        expr = rule_str
        for i, name in enumerate(var_names):
            token = f"_v{i}_"
            expr = re.sub(r'\b' + re.escape(name) + r'\b', token, expr)
            sym_dict[token] = sym_symbols(name)

        # Replace ! with ~ (SymPy overloads __invert__ on Symbol)
        expr = expr.replace("!", "~")

        # Evaluate with the placeholder namespace
        return eval(expr, {"__builtins__": {}}, sym_dict)  # noqa: S307
    except Exception:
        return None


def _rules_logically_equivalent(rule1: str, rule2: str) -> bool:
    """
    True if rule1 and rule2 are logically equivalent.
    Fast path: whitespace-normalized string equality.
    Slow path: SymPy satisfiability of (rule1 XOR rule2) — unsatisfiable → equivalent.
    """
    if _normalize_rule(rule1) == _normalize_rule(rule2):
        return True
    try:
        from sympy.logic.boolalg import Xor
        from sympy.logic.inference import satisfiable

        e1 = _rule_to_sympy(rule1)
        e2 = _rule_to_sympy(rule2)
        if e1 is None or e2 is None:
            return False
        # satisfiable returns False (Python bool) when the formula is unsatisfiable
        return satisfiable(Xor(e1, e2)) is False
    except Exception:
        return False


def compute_rule_fidelity(
    orig_path: str, conv_path: str
) -> Tuple[Optional[float], List[Dict]]:
    """
    Compute logical-equivalence rule fidelity for one model.

    Returns:
        (fidelity, mismatches)
        fidelity  – fraction of transitions whose rules are logically equivalent,
                    or None if the model has no transitions or SBML reading fails.
        mismatches – list of dicts with keys (target, orig_rule, conv_rule,
                     string_match, logical_match) for every transition where
                     string equality fails.
    """
    mismatches: List[Dict] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            orig_model = read_sbml(orig_path)
            conv_model = read_sbml(conv_path)
    except Exception:
        return None, mismatches

    if not orig_model.transitions:
        return None, mismatches

    orig_rules = {t.target: _normalize_rule(t.rule) for t in orig_model.transitions}
    conv_rules = {t.target: _normalize_rule(t.rule) for t in conv_model.transitions}

    n_logical_match = 0
    for tgt, orig_r in orig_rules.items():
        conv_r = conv_rules.get(tgt, "")
        str_eq = orig_r == conv_r
        if str_eq:
            n_logical_match += 1
        else:
            log_eq = _rules_logically_equivalent(orig_r, conv_r)
            if log_eq:
                n_logical_match += 1
            mismatches.append(
                {
                    "target": tgt,
                    "orig_rule": orig_r,
                    "conv_rule": conv_r,
                    "string_match": str_eq,
                    "logical_match": log_eq,
                }
            )

    fidelity = n_logical_match / len(orig_rules)
    return fidelity, mismatches


# ---------------------------------------------------------------------------
# Main data assembly
# ---------------------------------------------------------------------------


def load_and_enrich(cache_csv: Optional[Path] = None) -> pd.DataFrame:
    """
    Load the existing results CSV, add source labels, and compute new
    per-model fidelity columns (rule_fidelity, and per-qualifier annotation
    data are aggregated separately).

    If cache_csv is provided and exists, load from there to skip recomputation.
    """
    if cache_csv and cache_csv.exists():
        print(f"Loading enriched data from cache: {cache_csv}")
        return pd.read_csv(cache_csv)

    df = pd.read_csv(RESULTS_CSV)
    src_map = build_source_map()
    df["source"] = df["model"].apply(lambda m: assign_source(m, src_map))

    # --- Rule fidelity (per model) — uses logical equivalence via SymPy ---
    rule_fidelities: List[Optional[float]] = []
    all_mismatches: List[Dict] = []
    print(f"Computing rule fidelity for {len(df)} models …")
    for _, row in df.iterrows():
        if pd.notna(row.get("sbml_to_xlsx_error")) or pd.notna(
            row.get("xlsx_to_sbml_error")
        ):
            rule_fidelities.append(None)
            continue
        base = os.path.splitext(row["model"])[0]
        orig_path = str(BIODIVINE_DIR / row["model"])
        conv_path = str(CONVERTED_SBML_DIR / f"{base}_converted.sbml")
        if not os.path.exists(orig_path) or not os.path.exists(conv_path):
            rule_fidelities.append(None)
            continue
        fidelity, mismatches = compute_rule_fidelity(orig_path, conv_path)
        rule_fidelities.append(fidelity)
        for m in mismatches:
            m["model"] = row["model"]
        all_mismatches.extend(mismatches)

    df["rule_fidelity"] = rule_fidelities

    # Save all string-unequal rules (both logical matches and genuine mismatches)
    if all_mismatches:
        mismatch_path = SCRIPT_DIR / "rule_fidelity_mismatches.csv"
        pd.DataFrame(all_mismatches)[
            ["model", "target", "orig_rule", "conv_rule", "string_match", "logical_match"]
        ].to_csv(mismatch_path, index=False)
        n_logical_fail = sum(not m["logical_match"] for m in all_mismatches)
        print(
            f"  {len(all_mismatches)} string mismatches found; "
            f"{n_logical_fail} are also logically inequivalent. "
            f"Saved to {mismatch_path.name}"
        )
    else:
        print("No rule fidelity mismatches found")

    if cache_csv:
        df.to_csv(cache_csv, index=False)
        print(f"Cached to {cache_csv}")
    return df


def aggregate_annotation_by_qualifier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Walk every successfully converted model and aggregate
    (qualifier, n_original, n_retained) across the full dataset.
    Returns a DataFrame sorted by total original count descending.
    """
    successful = df[
        df["sbml_to_xlsx_error"].isna() & df["xlsx_to_sbml_error"].isna()
    ]

    agg: Dict[str, Tuple[int, int]] = defaultdict(lambda: (0, 0))
    total = len(successful)
    for idx, (_, row) in enumerate(successful.iterrows()):
        if (idx + 1) % 20 == 0:
            print(f"  Annotation qualifier scan: {idx + 1}/{total}")
        base = os.path.splitext(row["model"])[0]
        orig_path = str(BIODIVINE_DIR / row["model"])
        conv_path = str(CONVERTED_SBML_DIR / f"{base}_converted.sbml")
        if not os.path.exists(orig_path) or not os.path.exists(conv_path):
            continue
        per_model = compute_annotation_fidelity_by_qualifier(orig_path, conv_path)
        for qual, (n, r) in per_model.items():
            n0, r0 = agg[qual]
            agg[qual] = (n0 + n, r0 + r)

    rows = []
    for qual, (n, r) in agg.items():
        rows.append(
            {
                "qualifier": qual,
                "n_original": n,
                "n_retained": r,
                "retention_rate": r / n if n > 0 else 1.0,
            }
        )
    result = pd.DataFrame(rows).sort_values("n_original", ascending=False)
    return result


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------


def _setup_style() -> None:
    sns.set_context("paper", font_scale=1.15)
    sns.set_style("white")
    matplotlib.rcParams.update(
        {
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.family": "sans-serif",
        }
    )


def _despine(ax: plt.Axes) -> None:
    sns.despine(ax=ax)
    ax.grid(False)


# ---------------------------------------------------------------------------
# Main figure
# ---------------------------------------------------------------------------


def make_main_figure(df: pd.DataFrame, anno_df: pd.DataFrame) -> plt.Figure:
    """
    4-panel main figure answering "Can you trust this tool?"
    B merges topology scatter + rule fidelity annotation.
    """
    successful = df[
        df["sbml_to_xlsx_error"].isna() & df["xlsx_to_sbml_error"].isna()
    ].copy()

    fig = plt.figure(figsize=(16, 12))

    from matplotlib.gridspec import GridSpec

    gs = GridSpec(
        2, 3,
        figure=fig,
        hspace=0.52,
        wspace=0.38,
        left=0.07, right=0.97,
        top=0.93, bottom=0.10,
    )

    ax_a = fig.add_subplot(gs[0, 0:2]) # Panel A: categorized stacked bar (wide)
    ax_b = fig.add_subplot(gs[0, 2])   # Panel B: topology scatter + rule fidelity note
    ax_c = fig.add_subplot(gs[1, 0:2]) # Panel C: annotation by qualifier (wide)
    ax_d = fig.add_subplot(gs[1, 2])   # Panel D: timing

    _panel_a_summary_bar(ax_a, df)     # full df (includes conversion failures)
    _panel_b_topology_scatter(ax_b, successful)
    _panel_c_annotation_qualifier(ax_c, anno_df)
    _panel_d_timing(ax_d, successful)

    titles = [
        "Overall round-trip fidelity",
        "Topology & rule fidelity",
        "Annotation fidelity by qualifier",
        "Conversion time",
    ]
    for ax, letter, title in zip([ax_a, ax_b, ax_c, ax_d], "ABCD", titles):
        ax.set_title(f"{letter}. {title}", fontweight="bold", loc="left", fontsize=11)

    return fig


def _panel_a_summary_bar(ax: plt.Axes, df: pd.DataFrame) -> None:
    """
    Stacked horizontal bar per model source with categorized mismatch breakdown.
    Categories (mutually exclusive, sum to 100%):
      Full fidelity | Annotation mismatch | Topology mismatch | Invalid SBML
    Accepts full df (including failed conversions).
    """
    df = df.copy()

    failed_mask = df["sbml_to_xlsx_error"].notna() | df["xlsx_to_sbml_error"].notna()
    ok = df[~failed_mask].copy()

    ok["topo_match"] = ok["species_match"] & ok["transitions_match"]
    ok["anno_match"] = ok["species_anno_match"] & ok["trans_anno_match"]
    ok["rule_full"] = ok["rule_fidelity"].apply(
        lambda x: True if pd.isna(x) else (x == 1.0)
    )
    ok["full_match"] = ok["topo_match"] & ok["anno_match"] & ok["rule_full"]
    # Anno-only mismatch: topology OK, but annotation count differs
    ok["anno_mismatch"] = ok["topo_match"] & ~ok["anno_match"]
    # Topology mismatch (overrides anno label for simplicity)
    ok["topo_mismatch"] = ~ok["topo_match"]

    CAT_COLORS = {
        "Full fidelity":        MATCH_GREEN,
        "Annotation mismatch":  "#E8853D",
        "Topology mismatch":    MISS_RED,
        "Invalid SBML":    "#BBBBBB",
    }
    CATEGORIES = list(CAT_COLORS.keys())

    rows = []
    for src in SOURCE_ORDER:
        src_mask = df["source"] == src
        sub_all = df[src_mask]
        sub_ok  = ok[ok["source"] == src]
        n = len(sub_all)
        if n == 0:
            continue
        n_fail = (failed_mask & src_mask).sum()
        rows.append({
            "source": src,
            "n": n,
            "Full fidelity":        100.0 * sub_ok["full_match"].sum() / n,
            "Annotation mismatch":  100.0 * sub_ok["anno_mismatch"].sum() / n,
            "Topology mismatch":    100.0 * sub_ok["topo_mismatch"].sum() / n,
            "Invalid SBML":    100.0 * n_fail / n,
        })

    bar_df = pd.DataFrame(rows).sort_values("n", ascending=True).reset_index(drop=True)

    max_n = bar_df["n"].max()
    heights = (bar_df["n"] / max_n * 0.72).clip(lower=0.15)

    y = np.arange(len(bar_df), dtype=float)
    for i, (_, row) in enumerate(bar_df.iterrows()):
        h = heights.iloc[i]
        left = 0.0
        for cat in CATEGORIES:
            pct = row[cat]
            if pct <= 0:
                left += pct
                continue
            ax.barh(y[i], pct, left=left, height=h,
                    color=CAT_COLORS[cat], alpha=0.88,
                    label=cat if i == 0 else "_nolegend_")
            # Label segment if wide enough
            if pct > 4:
                ax.text(left + pct / 2, y[i], f"{pct:.0f}%",
                        ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold")
            left += pct

    ax.set_yticks(list(y))
    ax.set_yticklabels(
        [f"{row['source']}  (n={row['n']})" for _, row in bar_df.iterrows()]
    )
    ax.set_xlim(0, 105)
    ax.set_xlabel("Models (%)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
              ncol=4, fontsize=8, frameon=False)
    _despine(ax)


def _panel_b_topology_scatter(ax: plt.Axes, df: pd.DataFrame) -> None:
    """
    Scatter: input count (x) vs. output count (y) for species and transitions.
    Perfect preservation → points on y = x diagonal.
    """
    sp_ok = df[["original_sbml_species", "converted_sbml_species"]].dropna()
    tr_ok = df[["original_sbml_transitions", "converted_sbml_transitions"]].dropna()

    max_val = max(
        sp_ok["original_sbml_species"].max(),
        tr_ok["original_sbml_transitions"].max(),
    )

    # Identity line
    ax.plot([0, max_val * 1.05], [0, max_val * 1.05], color="#BBBBBB", lw=1, zorder=0)

    ax.scatter(
        sp_ok["original_sbml_species"],
        sp_ok["converted_sbml_species"],
        s=18,
        alpha=0.55,
        color="#4E9AC7",
        label="Species",
        zorder=2,
    )
    ax.scatter(
        tr_ok["original_sbml_transitions"],
        tr_ok["converted_sbml_transitions"],
        s=18,
        alpha=0.55,
        color="#E8853D",
        marker="s",
        label="Transitions",
        zorder=2,
    )
    ax.set_xlabel("Count before conversion")
    ax.set_ylabel("Count after round-trip")
    ax.legend(fontsize=8, frameon=False, markerscale=1.2)

    # Rule fidelity annotation
    if "rule_fidelity" in df.columns:
        rf = df["rule_fidelity"].dropna()
        if len(rf) > 0:
            pct_perfect = 100 * (rf == 1.0).sum() / len(rf)
            ax.text(
                0.03, 0.97,
                f"Rules: {pct_perfect:.0f}% perfectly preserved",
                transform=ax.transAxes,
                fontsize=9.5, va="top", ha="left",
                color=MATCH_GREEN, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                          edgecolor=MATCH_GREEN, alpha=0.9, linewidth=1.0),
            )

    _despine(ax)


def _panel_c_rule_histogram(ax: plt.Axes, df: pd.DataFrame) -> None:
    """
    Histogram of per-model rule match rate (0–1).
    """
    rf = df["rule_fidelity"].dropna()
    if rf.empty:
        ax.text(0.5, 0.5, "No rule data", ha="center", va="center",
                transform=ax.transAxes)
        _despine(ax)
        return

    bins = np.linspace(0, 1.0, 21)
    ax.hist(rf, bins=bins, color="#D85A30", alpha=0.80, edgecolor="white", linewidth=0.4)

    pct_perfect = 100 * (rf == 1.0).sum() / len(rf)
    ax.axvline(1.0, color="#2C2C2A", lw=1.2, linestyle="--", alpha=0.7)
    ax.text(
        0.97, 0.95,
        f"{pct_perfect:.0f}% perfect",
        ha="right", va="top",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#2C2C2A",
    )
    ax.set_xlabel("Fraction of rules preserved (logical equivalence)")
    ax.set_ylabel("Number of models")
    ax.set_xlim(-0.02, 1.05)
    _despine(ax)


def _panel_c_annotation_qualifier(ax: plt.Axes, anno_df: pd.DataFrame) -> None:
    """
    Vertical grouped bar chart: qualifiers on X, retention rate on Y.
    Valid qualifiers ordered by n descending; invalid/gray qualifiers appended at end.
    Bar width ∝ log10(n) to encode prevalence visually.
    """
    INVALID_QUALIFIERS = {
        "bqmodel:is",
        "bqmodel:isDescribedBy",
        "bqbiol:unknownQualifier",
    }

    plot_df = anno_df[anno_df["n_original"] >= 10].copy()
    if plot_df.empty:
        ax.text(0.5, 0.5, "No annotation data", ha="center", va="center",
                transform=ax.transAxes)
        _despine(ax)
        return

    # Valid qualifiers first (by n desc), then invalid/gray qualifiers (by n desc)
    valid_df = plot_df[~plot_df["qualifier"].isin(INVALID_QUALIFIERS)].sort_values(
        "n_original", ascending=False
    )
    invalid_df = plot_df[plot_df["qualifier"].isin(INVALID_QUALIFIERS)].sort_values(
        "n_original", ascending=False
    )
    plot_df = pd.concat([valid_df, invalid_df]).reset_index(drop=True)
    n_valid = len(valid_df)

    # Bar width ∝ log10(n)
    log_n = np.log10(plot_df["n_original"].clip(lower=1))
    widths = (log_n / log_n.max() * 0.72).clip(lower=0.12)

    # Color by retention rate; invalid qualifiers use desaturated tones
    def _bar_color(qual, rate):
        if qual in INVALID_QUALIFIERS:
            return "#BBBBBB"  # gray — invalid qualifier
        return "#378ADD" if rate >= 0.95 else "#E8853D" if rate >= 0.8 else MISS_RED

    x = np.arange(len(plot_df), dtype=float)
    bars = []
    for i, (_, row) in enumerate(plot_df.iterrows()):
        col = _bar_color(row["qualifier"], row["retention_rate"])
        b = ax.bar(x[i], row["retention_rate"] * 100,
                   color=col, alpha=0.82, width=widths.iloc[i],
                   edgecolor="white", linewidth=0.3)
        bars.append(b.patches[0])

    # X-axis labels: short qualifier name + count; invalid ones in gray
    short_labels = []
    label_colors = []
    for _, row in plot_df.iterrows():
        q = row["qualifier"]
        label = f"{q}\n(n={row['n_original']:,})"
        short_labels.append(label)
        label_colors.append("#AAAAAA" if q in INVALID_QUALIFIERS else "#2C2C2A")

    ax.set_xticks(list(x))
    ax.set_xticklabels(short_labels, fontsize=7.5, rotation=30, ha="right")
    for tick_label, color in zip(ax.get_xticklabels(), label_colors):
        tick_label.set_color(color)

    ax.set_ylim(0, 122)
    ax.axhline(100, color="#BBBBBB", lw=0.8, linestyle="--")
    ax.set_ylabel("Annotation retention rate (%)")

    # Annotate bars with % value
    for bar, (_, row) in zip(bars, plot_df.iterrows()):
        pct = row["retention_rate"] * 100
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            min(pct + 1.5, 114),
            f"{pct:.1f}%",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#2C2C2A",
        )

    # Separator line between valid and invalid qualifiers
    if n_valid > 0 and len(invalid_df) > 0:
        sep_x = n_valid - 0.5
        ax.axvline(sep_x, color="#CCCCCC", lw=0.9, linestyle=":")

    # Legend above bars (upper right — bars max at ~100, ylim extends to 122)
    legend_elements = [
        mpatches.Patch(facecolor="#378ADD", alpha=0.82, label="≥ 95%"),
        mpatches.Patch(facecolor="#E8853D", alpha=0.82, label="80–95%"),
        mpatches.Patch(facecolor=MISS_RED, alpha=0.72, label="< 80%"),
        mpatches.Patch(facecolor="#BBBBBB", alpha=0.82, label="invalid qualifier"),
    ]
    ax.legend(handles=legend_elements, title="Retention",
              fontsize=7.5, frameon=False, loc="upper right", ncol=2)

    _despine(ax)


def _panel_d_timing(ax: plt.Axes, df: pd.DataFrame) -> None:
    """
    Boxplot of conversion times per direction.
    """
    time_df = df.melt(
        id_vars=["source"],
        value_vars=["sbml_to_xlsx_time", "xlsx_to_sbml_time"],
        var_name="Direction",
        value_name="Seconds",
    ).dropna(subset=["Seconds"])
    time_df["Direction"] = time_df["Direction"].map(
        {"sbml_to_xlsx_time": "SBML→XLSX", "xlsx_to_sbml_time": "XLSX→SBML"}
    )

    sns.boxplot(
        data=time_df,
        x="Direction",
        y="Seconds",
        hue="source",
        hue_order=[s for s in SOURCE_ORDER if s in time_df["source"].unique()],
        palette=SOURCE_PALETTE,
        width=0.55,
        linewidth=0.8,
        fliersize=2,
        ax=ax,
    )
    ax.set_xlabel("")
    ax.set_ylabel("Time (seconds)")
    legend = ax.get_legend()
    if legend:
        legend.set_title("Source", prop={"size": 8})
        legend.get_frame().set_visible(False)
        for text in legend.get_texts():
            text.set_fontsize(7.5)
    _despine(ax)


# ---------------------------------------------------------------------------
# Supplementary figure
# ---------------------------------------------------------------------------


def make_supplementary_figure(df: pd.DataFrame) -> plt.Figure:
    """
    3-panel supplementary figure: dataset characteristics.
    """
    successful = df[
        df["sbml_to_xlsx_error"].isna() & df["xlsx_to_sbml_error"].isna()
    ].copy()
    successful["sp_status"] = successful["species_anno_match"].map(
        {True: "Match", False: "Mismatch"}
    )
    successful["tr_status"] = successful["trans_anno_match"].map(
        {True: "Match", False: "Mismatch"}
    )

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    plt.subplots_adjust(wspace=0.32, left=0.07, right=0.97, top=0.88, bottom=0.14)

    ax_s1a, ax_s1b, ax_s1c = axes

    # S1A: model scale
    sns.scatterplot(
        data=successful,
        x="original_sbml_species",
        y="original_sbml_transitions",
        hue="source",
        hue_order=[s for s in SOURCE_ORDER if s in successful["source"].unique()],
        palette=SOURCE_PALETTE,
        s=55,
        alpha=0.72,
        ax=ax_s1a,
        legend=True,
    )
    ax_s1a.set_title("S1A. Model scale", fontweight="bold", loc="left")
    ax_s1a.set_xlabel("Number of species")
    ax_s1a.set_ylabel("Number of transitions")
    leg = ax_s1a.get_legend()
    if leg:
        leg.set_title("Source", prop={"size": 8})
        leg.get_frame().set_visible(False)
        for t in leg.get_texts():
            t.set_fontsize(7.5)
    _despine(ax_s1a)

    # S1B: species annotation density
    for status, marker, color in [("Match", "o", MATCH_GREEN), ("Mismatch", "X", MISS_RED)]:
        sub = successful[successful["sp_status"] == status]
        ax_s1b.scatter(
            sub["original_sbml_species"],
            sub["original_sbml_species_anno"],
            marker=marker,
            s=40,
            alpha=0.65,
            color=color,
            label=status,
            edgecolors="white",
            linewidths=0.3,
        )
    ax_s1b.set_yscale("log")
    ax_s1b.set_title("S1B. Species annotation density", fontweight="bold", loc="left")
    ax_s1b.set_xlabel("Number of species")
    ax_s1b.set_ylabel("Species annotations (log scale)")
    ax_s1b.legend(title="Count match", fontsize=8, frameon=False)
    _despine(ax_s1b)

    # S1C: transition annotation density
    for status, marker, color in [("Match", "o", MATCH_GREEN), ("Mismatch", "X", MISS_RED)]:
        sub = successful[successful["tr_status"] == status]
        ax_s1c.scatter(
            sub["original_sbml_transitions"],
            sub["original_sbml_trans_anno"],
            marker=marker,
            s=40,
            alpha=0.65,
            color=color,
            label=status,
            edgecolors="white",
            linewidths=0.3,
        )
    # Avoid log-scale issues if all zero
    if successful["original_sbml_trans_anno"].max() > 0:
        ax_s1c.set_yscale("log")
    ax_s1c.set_title("S1C. Transition annotation density", fontweight="bold", loc="left")
    ax_s1c.set_xlabel("Number of transitions")
    ax_s1c.set_ylabel("Transition annotations (log scale)")
    ax_s1c.legend(title="Count match", fontsize=8, frameon=False)
    _despine(ax_s1c)

    return fig


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    _setup_style()

    cache_csv = SCRIPT_DIR / "biodivine_enriched_cache.csv"

    print("=== Loading / enriching data ===")
    df = load_and_enrich(cache_csv=cache_csv)

    print("\n=== Computing annotation fidelity by qualifier ===")
    anno_cache = SCRIPT_DIR / "biodivine_annotation_qualifier_cache.csv"
    if anno_cache.exists():
        print(f"Loading annotation qualifier data from cache: {anno_cache}")
        anno_df = pd.read_csv(anno_cache)
    else:
        anno_df = aggregate_annotation_by_qualifier(df)
        anno_df.to_csv(anno_cache, index=False)
        print(f"Cached annotation qualifier data to {anno_cache}")

    successful = df[
        df["sbml_to_xlsx_error"].isna() & df["xlsx_to_sbml_error"].isna()
    ]
    n_total = len(df)
    n_ok = len(successful)
    print(f"\nDataset: {n_total} models, {n_ok} successfully converted")
    if "rule_fidelity" in df.columns:
        rf = df["rule_fidelity"].dropna()
        print(
            f"Rule fidelity: {(rf == 1.0).sum()} / {len(rf)} models have 100% rule preservation"
        )

    print("\n=== Generating main figure ===")
    fig_main = make_main_figure(df, anno_df)
    out_main = SCRIPT_DIR / "figure_round_trip_fidelity_main.pdf"
    fig_main.savefig(out_main, dpi=300, bbox_inches="tight")
    fig_main.savefig(str(out_main).replace(".pdf", ".png"), dpi=200, bbox_inches="tight")
    print(f"Saved: {out_main}")

    print("\n=== Generating supplementary figure ===")
    fig_supp = make_supplementary_figure(df)
    out_supp = SCRIPT_DIR / "figure_round_trip_fidelity_supp.pdf"
    fig_supp.savefig(out_supp, dpi=300, bbox_inches="tight")
    fig_supp.savefig(str(out_supp).replace(".pdf", ".png"), dpi=200, bbox_inches="tight")
    print(f"Saved: {out_supp}")

    plt.show()


if __name__ == "__main__":
    main()

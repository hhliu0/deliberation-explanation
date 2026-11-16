"""Compare completed dialogue ratings with the two saved individual benchmarks."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
ORIGINAL_ID = "c2b6db26719e47dba55c7dca8134dabf"
BATCH_PREFIX = "skeptic-extrapolator-followup19"
AGENTS = {"agent_a": "Skeptic", "agent_b": "Extrapolator"}
LABELS = ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"]
SCORES = {label: i + 1 for i, label in enumerate(LABELS)}
SHORT = [
    "Progress stays gradual",
    "Goal conflict by 2044",
    "Extinction risk is a priority",
    "AI worsens social problems",
    "Progress should be slower",
    "No advanced AI without control",
    "Concentrate development",
    "Companies self-manage risks",
    "Protect liberty and agency",
    "Public concerns are misunderstandings",
    "Current harms deserve more attention",
    "Competition drives progress, not choice",
]


def load_json(path):
    """Read one unchanged source artifact."""
    return json.loads(path.read_text(encoding="utf-8"))


def source_record(path, role):
    """Retain source identity and content hash without copying conversations."""
    return {
        "path": str(path.resolve()),
        "role": role,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def rating_vector(record, statements, agent):
    """Require a complete, ordered, non-thinking rating of the same statements."""
    assert record["ended_at"] and record["thinking"] == "not enabled"
    assert (
        record["agent_message"]["agent_name"]
        == {"agent_a": "Agent A", "agent_b": "Agent B"}[agent]
    )
    assert record["agent_message"]["thinking_token_count"] == 0
    assert not record["agent_message"]["thinking"]
    assert [r["statement_number"] for r in record["ratings"]] == list(range(1, 13))
    assert [r["statement"] for r in record["ratings"]] == [
        s["text"] for s in statements
    ]
    assert json.loads(record["inputs"]["statements.txt"])["statements"] == statements
    return [SCORES[r["rating"]] for r in record["ratings"]]


def probabilities(values):
    """Return empirical probabilities for each statement and ordinal category."""
    return np.stack([(values == score).mean(axis=0) for score in range(1, 6)], axis=-1)


def expected_gap(left, right):
    """Average independent-draw absolute category distance on the same statement."""
    cost = np.abs(np.arange(1, 6)[:, None] - np.arange(1, 6)[None, :])
    return np.einsum("...jk,kl,...jl->...", left, cost, right) / 12


def interval(values):
    """Describe a whole-trial percentile bootstrap interval."""
    return np.quantile(values, [0.025, 0.975], axis=0).tolist()


def descriptive(values):
    """Summarize each statement; all variances use the sample convention."""
    return {
        "n": len(values),
        "means": values.mean(axis=0).tolist(),
        "medians": np.median(values, axis=0).tolist(),
        "sample_variances": values.var(axis=0, ddof=1).tolist(),
        "counts": np.stack(
            [(values == k).sum(axis=0) for k in range(1, 6)], axis=-1
        ).tolist(),
    }


def seed_vectors(dialogue, statements):
    """Extract both explicitly labeled seed rating vectors from each memory."""
    memories = []
    for agent in AGENTS:
        pieces = re.split(
            r"\[(agent_[ab])\]\n", dialogue[agent + "_inputs"]["memory.txt"]
        )
        assert not pieces[0].strip() and len(pieces) == 5
        vectors = {}
        for speaker, text in zip(pieces[1::2], pieces[2::2]):
            ratings = json.loads(text)["ratings"]
            assert [r["id"] for r in ratings] == [s["id"] for s in statements]
            vectors[speaker] = [SCORES[r["score"]] for r in ratings]
        assert set(vectors) == set(AGENTS)
        memories.append(vectors)
    assert memories[0] == memories[1]
    return memories[0]


def analyze(expected_complete, bootstrap_replicates, output):
    """Validate source cohorts, calculate differences, and retain reproducible evidence."""
    statements = json.loads(
        (PROJECT / "ratings/prompt/agent_a/statements.txt").read_text()
    )["statements"]
    assert len(statements) == 12
    manifest, baseline = [], {}
    rating_ids = set()
    for agent, name in AGENTS.items():
        folder = PROJECT / "ratings/archive" / (name.lower() + " bench")
        paths = sorted(folder.glob("*.json"))
        assert len(paths) == 200
        records = sorted(
            [(p, load_json(p)) for p in paths], key=lambda pair: pair[1]["started_at"]
        )
        assert len({r["trial_id"] for _, r in records}) == 200
        for _, record in records:
            assert record["trial_id"] not in rating_ids
            rating_ids.add(record["trial_id"])
        assert len({json.dumps(r["inputs"], sort_keys=True) for _, r in records}) == 1
        baseline[agent] = np.array(
            [rating_vector(r, statements, agent) for _, r in records]
        )
        manifest.extend(source_record(p, "individual " + agent) for p, _ in records)
        pdf = folder / (name.lower() + "-bench.pdf")
        manifest.append(source_record(pdf, "benchmark PDF " + agent))

    all_ratings = [
        (p, load_json(p)) for p in (PROJECT / "ratings/archive").glob("*.json")
    ]
    candidates = []
    for path in (PROJECT / "dialogue/archive").glob("*.json"):
        record = load_json(path)
        if record["trial_id"] == ORIGINAL_ID or record["trial_name"].startswith(
            BATCH_PREFIX
        ):
            candidates.append((path, record))
    candidates.sort(key=lambda pair: pair[1]["started_at"])
    assert len({r["trial_id"] for _, r in candidates}) == len(candidates)
    seeds = seed_vectors(
        next(r for _, r in candidates if r["trial_id"] == ORIGINAL_ID), statements
    )
    complete, excluded, post = [], [], {a: [] for a in AGENTS}
    for path, dialogue in candidates:
        manifest.append(source_record(path, "dialogue attempt"))
        assert dialogue["thinking"] == "not enabled"
        assert dialogue["ended_at"], "A selected dialogue is still running."
        assert seed_vectors(dialogue, statements) == seeds
        matched = [
            (p, r) for p, r in all_ratings if dialogue["trial_id"] in r["trial_name"]
        ]
        info = {
            "dialogue_id": dialogue["trial_id"],
            "trial_name": dialogue["trial_name"],
            "path": str(path),
            "accepted_replies": len(dialogue["messages"]),
            "started_at": dialogue["started_at"],
            "ended_at": dialogue["ended_at"],
        }
        if len(dialogue["messages"]) != 20:
            assert not matched
            excluded.append({**info, "reason": "incomplete dialogue"})
            continue
        assert [m["speaker"] for m in dialogue["messages"]] == [
            "agent_a",
            "agent_b",
        ] * 10
        assert all(
            m["thinking_token_count"] == 0 and not m["thinking"]
            for m in dialogue["messages"]
        )
        assert len(matched) <= 2, "Ambiguous duplicate rating records for one dialogue."
        if len(matched) < 2:
            excluded.append({**info, "reason": "missing ratings"})
            manifest.extend(
                source_record(p, "incomplete-pair rating") for p, _ in matched
            )
            continue
        by_name = {r["agent_message"]["agent_name"]: (p, r) for p, r in matched}
        assert set(by_name) == {"Agent A", "Agent B"}
        if any(any(v["rating"] is None for v in r["ratings"]) for _, r in matched):
            excluded.append({**info, "reason": "incomplete ratings"})
            manifest.extend(source_record(p, "failed-pair rating") for p, _ in matched)
            continue
        transcript = "\n\n".join(
            "[" + m["speaker"] + "]\n" + m["message"] for m in dialogue["messages"]
        )
        for agent, label in [("agent_a", "Agent A"), ("agent_b", "Agent B")]:
            p, r = by_name[label]
            assert r["trial_id"] not in rating_ids
            rating_ids.add(r["trial_id"])
            initial = dialogue[agent + "_inputs"]["memory.txt"]
            assert (
                r["inputs"]["memory.txt"]
                == initial + ("\n\n" if initial else "") + transcript
            )
            for filename, text in dialogue[agent + "_inputs"].items():
                assert (
                    text == (PROJECT / "dialogue/prompt" / agent / filename).read_text()
                )
            for filename, text in r["inputs"].items():
                if filename != "memory.txt":
                    assert (
                        text
                        == (PROJECT / "ratings/prompt" / agent / filename).read_text()
                    )
            post[agent].append(rating_vector(r, statements, agent))
            manifest.append(source_record(p, "post-dialogue " + agent))
            info[agent + "_rating_id"] = r["trial_id"]
        complete.append(info)
    assert expected_complete >= 2
    assert len(complete) >= expected_complete, (len(complete), expected_complete)
    available_complete = len(complete)
    extra_complete = complete[expected_complete:]
    complete = complete[:expected_complete]
    assert ORIGINAL_ID in {trial["dialogue_id"] for trial in complete}
    post = {a: np.array(v[:expected_complete]) for a, v in post.items()}
    n = len(complete)
    assert n >= 2
    rng = np.random.default_rng(20261116)
    pair_indices = rng.integers(0, n, size=(bootstrap_replicates, n))
    summary = {
        "complete_pairs": n,
        "available_complete_pairs": available_complete,
        "extra_complete_trials_excluded_from_primary": extra_complete,
        "attempts_including_original": len(candidates),
        "excluded_attempts": excluded,
        "complete_trials": complete,
        "labels": LABELS,
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": 20261116,
        "baseline": {},
        "post_dialogue": {},
        "agents": {},
        "statements": statements,
        "statement_short_labels": SHORT,
        "fixed_seed_ratings": seeds,
        "interpretation": {
            "scale": "1 strongly disagree, 2 disagree, 3 neutral, 4 agree, 5 strongly agree",
            "mean_assumption": "Means and category distances treat adjacent Likert categories as equally spaced.",
            "interval_scope": "Whole-trial percentile bootstrap, conditional on these 12 fixed statements and completed runs; exploratory, not multiplicity-adjusted.",
            "absolute_shift_interval": "Descriptive uncertainty only: a positive lower bound is not a test of a nonzero shift.",
            "baseline_modes": "Unique modes computed from all 200 individual runs; held fixed for descriptive mode-match rates, no interval estimated.",
            "comparison": "Independent blank-memory benchmarks versus seeded dialogue plus memory-framed rating prompts; not a paired before/after causal estimate.",
            "selection": "Use the first requested number of complete trials in start-time order, including the original. Retain incomplete and later complete attempts separately. Results are conditional on completion.",
        },
    }
    boot_base_probs = {}
    for agent in AGENTS:
        before, after = baseline[agent], post[agent]
        bp, ap = probabilities(before), probabilities(after)
        base_indices = rng.integers(
            0, len(before), size=(bootstrap_replicates, len(before))
        )
        sampled_before, sampled_after = before[base_indices], after[pair_indices]
        before_means, after_means = sampled_before.mean(axis=1), sampled_after.mean(
            axis=1
        )
        boot_base_probs[agent] = np.stack(
            [(sampled_before == k).mean(axis=1) for k in range(1, 6)], axis=-1
        )
        delta = after.mean(axis=0) - before.mean(axis=0)
        modes = np.argmax(bp, axis=-1) + 1
        assert np.all((bp == bp.max(axis=1)[:, None]).sum(axis=1) == 1)
        summary["baseline"][agent] = descriptive(before)
        summary["post_dialogue"][agent] = descriptive(after)
        summary["agents"][agent] = {
            "mean_differences": delta.tolist(),
            "mean_difference_ci95": np.array(
                interval(after_means - before_means)
            ).T.tolist(),
            "mean_absolute_profile_shift": float(np.abs(delta).mean()),
            "mean_absolute_profile_shift_ci95": interval(
                np.abs(after_means - before_means).mean(axis=1)
            ),
            "mean_distribution_distance_steps": float(
                np.abs(ap.cumsum(axis=1) - bp.cumsum(axis=1)).sum(axis=1).mean()
            ),
            "mean_total_variation": float(np.abs(ap - bp).sum(axis=1).mean() / 2),
            "benchmark_modes": modes.tolist(),
            "post_match_benchmark_mode": float((after == modes).mean()),
            "baseline_match_own_mode": float((before == modes).mean()),
            "post_match_benchmark_mode_by_statement": (after == modes)
            .mean(axis=0)
            .tolist(),
            "independent_cross_condition_gap": float(expected_gap(ap, bp)),
            "baseline_within_condition_gap": float(
                expected_gap(bp, bp) * len(before) / (len(before) - 1)
            ),
            "average_sample_variance_before": float(before.var(axis=0, ddof=1).mean()),
            "average_sample_variance_after": float(after.var(axis=0, ddof=1).mean()),
            "post_run_vectors": after.tolist(),
            "seed_to_post_mean_differences": (
                after.mean(axis=0) - np.array(seeds[agent])
            ).tolist(),
            "post_match_fixed_seed": float((after == np.array(seeds[agent])).mean()),
        }
    ba, bb = (probabilities(baseline[a]) for a in AGENTS)
    pa, pb = (post[a] for a in AGENTS)
    before_gap = float(expected_gap(ba, bb))
    after_gaps = np.abs(pa - pb).mean(axis=1)
    before_agreement = float((ba * bb).sum(axis=1).mean())
    after_agreements = (pa == pb).mean(axis=1)
    boot_before_gap = expected_gap(
        boot_base_probs["agent_a"], boot_base_probs["agent_b"]
    )
    boot_after_gap = after_gaps[pair_indices].mean(axis=1)
    boot_before_agreement = (
        (boot_base_probs["agent_a"] * boot_base_probs["agent_b"])
        .sum(axis=-1)
        .mean(axis=1)
    )
    boot_after_agreement = after_agreements[pair_indices].mean(axis=1)
    summary["between_agents"] = {
        "baseline_expected_absolute_gap": before_gap,
        "post_paired_absolute_gap": float(after_gaps.mean()),
        "absolute_gap_change": float(after_gaps.mean() - before_gap),
        "absolute_gap_change_ci95": interval(boot_after_gap - boot_before_gap),
        "gap_reduction_fraction": float(1 - after_gaps.mean() / before_gap),
        "baseline_expected_exact_agreement": before_agreement,
        "post_paired_exact_agreement": float(after_agreements.mean()),
        "agreement_change_ci95": interval(boot_after_agreement - boot_before_agreement),
        "post_exact_agreement_count": int((pa == pb).sum()),
        "post_comparison_count": int(pa.size),
        "post_gap_by_statement": np.abs(pa - pb).mean(axis=0).tolist(),
        "post_agreement_by_statement": (pa == pb).mean(axis=0).tolist(),
        "post_gap_by_trial": after_gaps.tolist(),
        "fixed_seed_absolute_gap": float(
            np.abs(np.array(seeds["agent_a"]) - np.array(seeds["agent_b"])).mean()
        ),
        "fixed_seed_exact_agreement": float(
            (np.array(seeds["agent_a"]) == np.array(seeds["agent_b"])).mean()
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "complete_pairs": n,
                "excluded": len(excluded),
                "agents": {
                    a: {
                        k: v
                        for k, v in s.items()
                        if k
                        in (
                            "mean_absolute_profile_shift",
                            "mean_absolute_profile_shift_ci95",
                            "post_match_benchmark_mode",
                            "baseline_match_own_mode",
                            "average_sample_variance_before",
                            "average_sample_variance_after",
                        )
                    }
                    for a, s in summary["agents"].items()
                },
                "between_agents": summary["between_agents"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-complete", type=int, default=10)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT / "ratings/archive/dialogue-benchmark-comparison",
    )
    args = parser.parse_args()
    analyze(args.expected_complete, args.bootstrap_replicates, args.output)

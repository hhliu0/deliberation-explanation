"""Use Mingled as Y for the paper's two-agent, twelve-statement score."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path

import numpy as np

from compare_dialogue_benchmarks import (
    AGENTS,
    PROJECT,
    descriptive,
    expected_gap,
    interval,
    load_json,
    probabilities,
    rating_vector,
    source_record,
)

DEFAULT = PROJECT / "ratings/archive/dialogue-benchmark-comparison"


def entropy(vectors):
    """Plug-in Shannon entropy of whole rating vectors, using natural logarithms."""
    counts = Counter(tuple(int(x) for x in row) for row in vectors)
    n = len(vectors)
    return -sum(count / n * math.log(count / n) for count in counts.values())


def profile_distance(left, right):
    """Mean absolute difference of the twelve statement means, in rating units."""
    return float(np.abs(left.mean(axis=0) - right.mean(axis=0)).mean())


def compute(comparison_path, output, replicates):
    """Calculate the explicitly independent-target model and separate target distances."""
    comparison = load_json(comparison_path)
    statements = comparison["statements"]
    folder = PROJECT / "ratings/archive/check mingle stability"
    records = sorted(
        [(p, load_json(p)) for p in folder.glob("*.json")],
        key=lambda pair: pair[1]["started_at"],
    )
    assert len(records) == 200
    assert len({record["trial_id"] for _, record in records}) == 200
    assert (
        len({json.dumps(record["inputs"], sort_keys=True) for _, record in records})
        == 1
    )
    assert not records[0][1]["inputs"]["memory.txt"]
    persona = records[0][1]["inputs"]["persona.txt"]
    assert (
        "You are The Skeptic" in persona and "You are also The Extrapolator" in persona
    )
    target = np.array([rating_vector(r, statements, "agent_a") for _, r in records])
    target_entropy = entropy(target)
    target_prob = probabilities(target)
    rng = np.random.default_rng(20261117)
    npost = comparison["complete_pairs"]
    post_indices = rng.integers(npost, size=(replicates, npost))
    target_indices = rng.integers(len(target), size=(replicates, len(target)))
    boot_target_means = target[target_indices].mean(axis=1)
    manifest = [source_record(p, "Mingled target Y") for p, _ in records]
    source_paper = PROJECT / "complementation_note/complementation_paper.pdf"
    manifest.append(source_record(source_paper, "governing score definition"))
    manifest.append(source_record(comparison_path, "selected ten-trial comparison"))
    upstream_manifest_path = comparison_path.parent / "source_manifest.json"
    upstream_manifest = load_json(upstream_manifest_path)
    for source in upstream_manifest:
        if source["role"].startswith("individual "):
            assert (
                source_record(Path(source["path"]), source["role"])["sha256"]
                == source["sha256"]
            )
    manifest.append(
        source_record(
            upstream_manifest_path, "upstream baseline and dialogue source hashes"
        )
    )
    result = {
        "pool": {"X_A": "Skeptic", "X_B": "Extrapolator"},
        "target_Y": "Mingled complete twelve-rating vector; not a third pool contributor",
        "units": "nats per complete twelve-statement vector",
        "definition": "C_A=I(X_B;Y|X_A); C_B=I(X_A;Y|X_B)",
        "population_coupled_score_identified_from_saved_observations": False,
        "missing_information": "No recorded trial linkage or conditional model connects a Mingled Y realization to each (X_A,X_B) pair.",
        "assumed_joint_laws": {
            "individual_benchmarks": "P(X_A,X_B,Y)=P(X_A)P(X_B)P(Y), product of entire-vector empirical distributions",
            "post_dialogue": "P(X_A,X_B,Y)=P_dialogue(X_A,X_B)P(Y), preserving the observed within-dialogue agent pairing",
        },
        "assumption_warning": "The independent-draw scores are zero by construction. They do not establish that the paper's unspecified coupled-target score is zero or that agents cannot learn.",
        "statement_dependence": "No assumption of independence among the twelve coordinates is made; whole vectors are retained.",
        "per_trial_score": "The score is a functional of a joint distribution, not a separately estimable quantity for each single trial.",
        "mingled": {
            **descriptive(target),
            "unique_vectors": len(Counter(map(tuple, target))),
            "vector_entropy_nats": target_entropy,
            "entropy_estimator": "Empirical plug-in entropy of complete twelve-rating vectors; not bias-corrected population entropy.",
            "first_started_at": records[0][1]["started_at"],
            "last_started_at": records[-1][1]["started_at"],
            "last_trial_id": records[-1][1]["trial_id"],
        },
        "independent_draw_model_scores": {},
        "descriptive_distances_not_complementation_scores": {},
        "bootstrap_replicates": replicates,
        "bootstrap_seed": 20261117,
    }
    all_ids = {record["trial_id"] for _, record in records}
    for agent, name in AGENTS.items():
        before_records = [
            load_json(p)
            for p in (PROJECT / "ratings/archive" / (name.lower() + " bench")).glob(
                "*.json"
            )
        ]
        before_records.sort(key=lambda r: r["started_at"])
        assert not (all_ids & {r["trial_id"] for r in before_records})
        before = np.array([rating_vector(r, statements, agent) for r in before_records])
        after = np.array(comparison["agents"][agent]["post_run_vectors"])
        assert before.shape == (200, 12) and after.shape == (npost, 12)
        for condition in ("individual_benchmarks", "post_dialogue"):
            result["independent_draw_model_scores"].setdefault(condition, {})[agent] = {
                "H_Y_given_own_nats": target_entropy,
                "H_Y_given_both_nats": target_entropy,
                "C_nats": target_entropy - target_entropy,
            }
        bp, ap = probabilities(before), probabilities(after)
        before_distance, after_distance = profile_distance(
            before, target
        ), profile_distance(after, target)
        base_indices = rng.integers(len(before), size=(replicates, len(before)))
        boot_before = np.abs(
            before[base_indices].mean(axis=1) - boot_target_means
        ).mean(axis=1)
        boot_after = np.abs(after[post_indices].mean(axis=1) - boot_target_means).mean(
            axis=1
        )
        result["descriptive_distances_not_complementation_scores"][agent] = {
            "mean_profile_distance_before": before_distance,
            "mean_profile_distance_after": after_distance,
            "mean_profile_distance_change": after_distance - before_distance,
            "change_ci95": interval(boot_after - boot_before),
            "relative_distance_change": after_distance / before_distance - 1,
            "independent_expected_rating_gap_before": float(
                expected_gap(bp, target_prob)
            ),
            "independent_expected_rating_gap_after": float(
                expected_gap(ap, target_prob)
            ),
            "independent_expected_label_match_before": float(
                (bp * target_prob).sum(axis=1).mean()
            ),
            "independent_expected_label_match_after": float(
                (ap * target_prob).sum(axis=1).mean()
            ),
            "distribution_distance_steps_before": float(
                np.abs(bp.cumsum(axis=1) - target_prob.cumsum(axis=1))
                .sum(axis=1)
                .mean()
            ),
            "distribution_distance_steps_after": float(
                np.abs(ap.cumsum(axis=1) - target_prob.cumsum(axis=1))
                .sum(axis=1)
                .mean()
            ),
            "signed_mean_differences_from_Y_before": (
                before.mean(axis=0) - target.mean(axis=0)
            ).tolist(),
            "signed_mean_differences_from_Y_after": (
                after.mean(axis=0) - target.mean(axis=0)
            ).tolist(),
        }
    result["mingled_reference_note"] = (
        "Using Y as the focal variable would make I(pool;Y|Y)=0 identically; it is a reference, not a third fitted agent score."
    )
    post_a = np.array(comparison["agents"]["agent_a"]["post_run_vectors"])
    post_b = np.array(comparison["agents"]["agent_b"]["post_run_vectors"])
    paired = np.concatenate([post_a, post_b], axis=1)
    h_ab = entropy(paired)
    h_a_given_b = max(0.0, h_ab - entropy(post_b))
    h_b_given_a = max(0.0, h_ab - entropy(post_a))
    result["finite_empirical_support_diagnostic"] = {
        "unique_A_vectors": len(Counter(map(tuple, post_a))),
        "unique_B_vectors": len(Counter(map(tuple, post_b))),
        "unique_AB_vectors": len(Counter(map(tuple, paired))),
        "H_A_given_B_nats": h_a_given_b,
        "H_B_given_A_nats": h_b_given_a,
        "C_A_upper_bound_fixed_empirical_AB": min(target_entropy, h_b_given_a),
        "C_B_upper_bound_fixed_empirical_AB": min(target_entropy, h_a_given_b),
        "note": "For any Y coupling preserving this exact ten-pair empirical AB law, C_B is zero because A is a function of B on the observed support. C_A is between zero and its listed (not claimed sharp) upper bound. This is a sparse-sample property, not identification of the population scores or proof of no learning.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "complementation.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "mingled_source_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "mingled_n": len(target),
                "H_Y_nats": target_entropy,
                "population_coupled_score_identified_from_saved_observations": False,
                "assumption_warning": result["assumption_warning"],
                "assumed_joint_laws": result["assumed_joint_laws"],
                "model_scores": result["independent_draw_model_scores"],
                "target_distances": result[
                    "descriptive_distances_not_complementation_scores"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, default=DEFAULT / "comparison.json")
    parser.add_argument("--output", type=Path, default=DEFAULT)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    args = parser.parse_args()
    compute(args.comparison, args.output, args.bootstrap_replicates)

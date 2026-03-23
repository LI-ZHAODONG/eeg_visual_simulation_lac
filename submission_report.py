# %% [markdown]
# # EEG Visual Simulation Project Report
#
# This file is written in a notebook-style Python format so it can be opened as a
# script, or converted into a Jupyter notebook later if needed. The goal of the
# report is to document the reasoning behind the pipeline, the parameter choices,
# and the interpretation of the results in a way that makes grading easy.
#
# ## Project Goal
#
# The goal of this project is to reproduce the main qualitative findings of the
# target visual EEG paper using the provided open dataset. In particular, I aimed
# to recover:
#
# 1. Broad posterior alpha suppression after visual stimulation.
# 2. Gamma-band increases that are more selective than alpha.
# 3. Retinotopy- and orientation-related differences across conditions.
# 4. A group-level trend consistent with a divisive normalization account.
#
# ## Submission Format
#
# This report is designed to accompany the project repository. It documents:
#
# - the preprocessing pipeline,
# - why specific parameters were chosen,
# - how ICA was reviewed,
# - how alpha/gamma, retinotopy, and orientation analyses were carried out,
# - which results were replicated well,
# - and which parts remained weaker or noisier than the paper.

# %%
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt


ROOT = Path("/Volumes/personal/EEG/eeg_visual_simulation_lac")
OUTPUTS = ROOT / "Dataset" / "outputs"
SUBJECTS = ["sub-01", "sub-02", "sub-03"]


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def show_image(path: Path, figsize=(10, 6), title: str | None = None):
    if not path.exists():
        print(f"Missing image: {path}")
        return
    image = mpimg.imread(path)
    plt.figure(figsize=figsize)
    plt.imshow(image)
    plt.axis("off")
    if title:
        plt.title(title)
    plt.show()


# %% [markdown]
# ## Dataset and Subject Selection
#
# I used the dataset in:
#
# - `/Volumes/personal/EEG/ds006547`
#
# The initial full pipeline was run for three subjects:
#
# - `sub-01`
# - `sub-02`
# - `sub-03`
#
# I started with a small subject set because this made it possible to debug the
# pipeline carefully, inspect ICA decisions manually, and evaluate how close the
# outputs were to the paper before scaling further.
#
# ## Important Data-Handling Detail
#
# The BrainVision files are stored through `git-annex` symlinks. Early in the
# project, resolving the `.vhdr` path caused the scripts to follow the annex
# object path instead of the subject path, which broke `.vmrk` lookup. I fixed
# the scripts so they preserve the subject-level BrainVision path instead of
# resolving it.

# %% [markdown]
# ## Preprocessing Pipeline
#
# The preprocessing pipeline was implemented in `Dataset/Scripts/preprocess.py`
# and followed this logic:
#
# 1. Load the BrainVision recording.
# 2. Apply montage information.
# 3. Detect bad channels.
# 4. Filter data for ICA preparation.
# 5. Fit ICA on event-centered data.
# 6. Save the ICA model and a review template JSON.
#
# ### Why ICA Was Done Manually
#
# I did not want automatic component rejection because ICA decisions are highly
# consequential and easy to over-apply. The repository was set up so that:
#
# - ICA is fit automatically,
# - component plots are generated automatically,
# - but keep/reject decisions are made manually in a JSON file.
#
# This was important because a major risk in EEG cleaning is accidentally
# removing neural signal instead of artifact.
#
# ### Key Parameter Choices
#
# - ICA components were capped by the number of usable EEG channels so the fit
#   stays valid across subjects.
# - Harmonic notch filtering was extended beyond a single 60 Hz notch to include
#   harmonics (for example 60, 120, 180 Hz up to Nyquist).
# - Gamma summary power was made more robust by avoiding the 60 Hz bin and using
#   sub-bands `40-55 Hz` and `65-80 Hz`.
#
# ### Why These Changes Were Necessary
#
# The single biggest problem during analysis was that residual line noise still
# affected gamma-band results. Alpha results were more stable, but gamma and ERSP
# outputs were visibly degraded when 60 Hz contamination remained in the spectra.
# Strengthening harmonic notch filtering and avoiding the 60 Hz bin in gamma
# summaries improved the robustness of the downstream results.

# %% [markdown]
# ## ICA Review Strategy
#
# ICA was reviewed manually subject by subject using:
#
# - topographies,
# - component property plots,
# - spectral shape,
# - and plausibility of neural versus artifact origin.
#
# ### Decision Rule
#
# I kept components that looked like broad, smooth posterior or plausible
# cortical sources, especially when they were consistent with visual cortex
# activity.
#
# I rejected components that looked like:
#
# - frontal blink/eye artifacts,
# - temporal muscle artifacts,
# - edge-dominant focal hotspots,
# - inferior neck/jaw contamination,
# - or diffuse non-dipolar/global artifact patterns.
#
# ### Why This Was Important
#
# A major lesson from the project was that ICA choices strongly change the final
# physiological interpretability of the results. Early conservative choices that
# kept too many mixed or temporal components often produced noisier gamma and ERSP
# outputs. Later, stricter posterior-focused selections improved the quality of
# the outputs.

# %% [markdown]
# ## Subject-Level Observations
#
# The pipeline was tested and iteratively refined on `sub-01`, `sub-02`, and
# `sub-03`.
#
# Broadly:
#
# - `sub-01`: pipeline validation subject, but still noisy.
# - `sub-02`: usable but less convincing than hoped for orientation/gamma.
# - `sub-03`: strongest of the first three subjects, but still noisier than the
#   paper at the single-subject ERSP level.
#
# This led to an important interpretation choice: I treated single-subject ERSP
# outputs mainly as quality-control and exploratory evidence, rather than as the
# main basis for claiming replication of the paper.

# %%
subject_summaries = {}
for subject in SUBJECTS:
    subject_dir = OUTPUTS / subject
    summary_path = subject_dir / f"{subject}_ses-01_task-visual_eeg-band_power_summary.json"
    if summary_path.exists():
        subject_summaries[subject] = load_json(summary_path)

print("Subjects with band-power summaries:", sorted(subject_summaries))


# %% [markdown]
# ## Group-Level Analysis
#
# After subject-level debugging, I moved to group-level analyses because the
# paper's claims should be evaluated primarily through cross-subject consistency,
# not by expecting a perfect ERSP map from a single subject.
#
# The main group scripts used were:
#
# - `Dataset/Scripts/grand_average_analysis.py`
# - `Dataset/Scripts/group_topomaps.py`
# - `Dataset/Scripts/retinotopy_model_fit.py`
#
# These scripts summarized the processed subject outputs into:
#
# - grand-average alpha and gamma topographies,
# - condition-wise topographic summaries,
# - orientation tuning summaries,
# - and model-fit comparisons between linear and divisive normalization accounts.

# %%
grand_average_summary_path = OUTPUTS / "grand_average_summary.json"
group_topomap_summary_path = OUTPUTS / "group_topomap_summary.json"
model_fit_summary_path = OUTPUTS / "retinotopy_model_fit_summary.json"

grand_average_summary = load_json(grand_average_summary_path) if grand_average_summary_path.exists() else {}
group_topomap_summary = load_json(group_topomap_summary_path) if group_topomap_summary_path.exists() else {}
model_fit_summary = load_json(model_fit_summary_path) if model_fit_summary_path.exists() else {}

print("Grand-average summary keys:", sorted(grand_average_summary.keys()))
print("Group topomap summary keys:", sorted(group_topomap_summary.keys()))
print("Model-fit summary keys:", sorted(model_fit_summary.keys()))


# %% [markdown]
# ## Main Group Figures
#
# The following figures summarize the strongest group-level results.

# %%
show_image(
    OUTPUTS / "grand_average_topomaps.png",
    figsize=(12, 5),
    title="Grand Average Alpha and Gamma Topomaps",
)

show_image(
    OUTPUTS / "Condition_Wise_Alpha_Topomaps_rebuilt.png",
    figsize=(12, 14),
    title="Condition-Wise Alpha Topomaps",
)

show_image(
    OUTPUTS / "Orientation_Tuning_Curves.png",
    figsize=(10, 4),
    title="Posterior Orientation Tuning Curves",
)

show_image(
    OUTPUTS / "retinotopy_model_fit_errors.png",
    figsize=(14, 5),
    title="Retinotopy Model Fit Errors",
)


# %% [markdown]
# ## Interpretation of Group Results
#
# ### 1. Alpha Replication
#
# Alpha was the strongest and cleanest part of the project.
#
# The grand-average alpha topography shows broad posterior suppression, which is
# qualitatively consistent with the expected visual alpha response. The condition-
# wise alpha maps also show systematic variation rather than flat or random
# structure.
#
# This is the part of the replication I consider the most convincing.
#
# ### 2. Gamma Replication
#
# Gamma was weaker and noisier than alpha throughout the project.
#
# Even after improving harmonic notch filtering and avoiding the 60 Hz bin in the
# gamma summary, gamma remained sensitive to residual noise and outlier channels.
# Group-level gamma patterns are suggestive but not as clean or as stable as the
# paper.
#
# I therefore interpret the gamma findings as partially supportive but weaker than
# the target paper.
#
# ### 3. Orientation Tuning
#
# The posterior tuning curves show that gamma varies with orientation more than
# alpha, while alpha remains broader and more negative overall. This is
# qualitatively in the direction expected from the paper.
#
# However, the ERSP-based orientation ANOVA maps remained fragmented and speckled.
# The orientation effect was therefore more convincing in the summarized tuning
# curves than in the cluster-based ERSP maps.
#
# ### 4. Retinotopy Model Comparison
#
# The model-fit comparison is promising. In the current outputs, the divisive
# normalization model generally performs better than the linear model across the
# retinotopy groupings shown in the figure.
#
# This does not prove a perfect replication, but it does suggest that the overall
# direction of the model comparison is meaningful and aligned with the paper's
# conceptual interpretation.

# %% [markdown]
# ## What Matched the Paper Well
#
# The main qualitative findings that were reproduced reasonably well are:
#
# - broad posterior alpha suppression,
# - orientation dependence in posterior summaries,
# - and a promising group-level divisive-normalization advantage over a linear
#   model.
#
# These are the parts of the project I would defend most confidently.

# %% [markdown]
# ## What Matched the Paper Less Well
#
# The weakest part of the reproduction was the gamma/ERSP side:
#
# - group gamma topographies were still noisier than desired,
# - subject-level gamma remained sensitive to residual line noise and outliers,
# - and the ERSP ANOVA maps produced many small scattered clusters instead of a
#   clean coherent effect region.
#
# Because of this, I would not claim a strong one-to-one replication of the
# paper's gamma/ERSP figures. Instead, I would say that the project provides a
# partial qualitative replication with alpha being strongest, and gamma being
# suggestive but not cleanly reproduced.

# %% [markdown]
# ## Why I Made These Choices
#
# I made the following major methodological choices intentionally:
#
# - **Manual ICA review instead of automatic rejection**
#   because I wanted to avoid accidental removal of neural components.
#
# - **Posterior-focused keep strategy for ICA**
#   because the paper is primarily about visual alpha/gamma effects, not about
#   retaining every plausible cortical source.
#
# - **Harmonic notch filtering**
#   because a single 60 Hz notch was not sufficient for stable gamma analysis.
#
# - **Gamma sub-bands excluding 60 Hz**
#   because including the line-noise bin made the gamma summary less trustworthy.
#
# - **Moving to group-level interpretation**
#   because single-subject ERSP results were too noisy to serve as the main
#   replication criterion.

# %% [markdown]
# ## Limitations
#
# The main limitations of the project are:
#
# 1. Only a small number of subjects were processed at the current stage.
# 2. Gamma remains sensitive to residual noise.
# 3. The ERSP cluster method is relatively simple and can produce fragmented maps.
# 4. Manual ICA review introduces reasonable but subjective judgment.
# 5. Some subject-level outputs remain noisier than ideal despite cleaning.

# %% [markdown]
# ## What I Would Improve Next
#
# If I continued this project, I would prioritize:
#
# 1. processing more subjects,
# 2. strengthening group-level statistical analysis,
# 3. improving ERSP cluster inference,
# 4. adding explicit group exclusions for unusually noisy subjects/channels,
# 5. and refining the gamma summary further if residual line-noise effects remain.
#
# In other words, the next biggest improvement would likely come from scaling and
# stronger group inference, not from endlessly tuning one subject at a time.

# %% [markdown]
# ## Final Conclusion
#
# This project achieved a partial qualitative replication of the target paper.
#
# The strongest replicated result is broad posterior alpha suppression. The
# orientation and retinotopy analyses are partially supportive and show structured
# effects. The model-fit comparison is promising and points in the expected
# direction for divisive normalization. The weakest part is the gamma/ERSP
# replication, which remains noisier and less coherent than the paper.
#
# Overall, I understand the full analysis pipeline and can justify the decisions
# made at each stage, even where the results remained imperfect. The report is
# meant to make that reasoning transparent.

# %%
print("Report file ready:", ROOT / "submission_report.py")


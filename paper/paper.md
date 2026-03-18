---
title: 'DeformView: Quantitative Visualization of Non-Linear Deformation Fields for Use in Image-Guided
Neurosurgery'
tags:
  - Medical Imaging
  - Image Registration
  - Non-linear Deformation
  - Visualization
  - 3D Slicer
authors:
  - name: Isabel Frolick
    orcid: 0000-0000-0000-0000
    equal-contrib: true
    affiliation: 1
  - name: Elise Donszelmann-Lund
    orcid: 0000-0000-0000-0000
    equal-contrib: true
    affiliation: 1
  - name: Louis Collins
    affiliation: 1
affiliations:
 - name: McGill University, Canada
   index: 1
date: 17 March 2026
bibliography: paper.bib

---

# Summary

DeformView is a 3D Slicer module designed for novel dense, intuitive and quantitative visualization of non-linear deformation fields in image registration. The module produces two interactive voxel-wise overlays: a displacement magnitude map in millimeters and a Jacobian determinant map encoding local volumetric expansion and compression. A real-time cursor enables point-wise numerical readout directly on the image volume and an Increment Transform feature supports progressive visualization of the deformation across discrete time steps. DeformView can be installed from the 3D Slicer software through the Extension Wizard.  

# Statement of need

Non-linear image registration is a key task in computational medical imaging where a spatially varying deformation field maps a source image (image being transformed) onto a target image (fixed reference image). There is an extensive corpus of work on non-linear image registration methods, reflecting their broad applicability and importance across medical imaging modalities and anatomical systems. A typical non-linear image registration pipeline often iteratively optimizes the deformation field, parameterized as a deformable grid of control points, such that the transformed source image maximizes some similarity metric with the target image. As such, the final product of a non-linear image registration task is the deformed source image, which has been non-linearly warped into alignment with the target image. 

In progressive diagnostic monitoring, longitudinal imaging carried out across multiple timepoints to evaluate whether a disease is advancing, regressing, or remaining stable; for example, tracking tumour response to treatment or measuring neurodegeneration over time. In interventional guidance, where procedures are performed in real time,  and where accurate spatial alignment is essential for maximizing therapeutic precision, reducing operative duration, and improving outcomes. As non-linear registration is a general problem, these use cases extend across many anatomical systems and modalities. 

In these non-linear image registration tasks, clinicians and surgeons must interpret the resulting deformation fields - either to guide clinical decision-making or to validate that a registration algorithm is performing correctly. This is typically done by visualizing the deformed intraoperative anatomy (source image). However, existing deformation visualization methods for non-linear image registration are largely sparse and qualitative, limiting users’ ability to interpret local tissue deformation. Correct interpretation of deformed anatomy is especially difficult for inexperienced surgeons or researchers who are not usually trained anatomists. For trainees and surgeons, these limitations may prolong procedures and increase patient risk; for researchers, they risk overlooking biologically implausible registration results. 

These challenges motivate the development of better non-linear deformation visualization tools. In response to these challenges,  DeformView addresses this need by providing dense, quantitative visualization of non-linear deformation fields, supporting both clinical training and algorithmic research across the range of medical imaging tasks where registration is applied. 

# State of the field                                                                                                                  

The primary existing tool for deformation visualization within 3D Slicer is the Transform Visualizer module, which renders sparse representations of the deformation field. The Transform Visualizer module contains three visualizations: glyphs (arrows), uniform grid, and isocontours. Glyphs are placed at a sampled subset of voxel locations, meaning local deformation between glyph positions is entirely invisible to the user, and no numerical displacement information is conveyed.  

One advantage of the Transform Visualizer module over the proposed DeformView module is the glyphs show the direction of deformation, a feature not included in DeformView. However, the DeformView functionality can be integrated with the TransformVisualizer glyphs directly in 3D Slicer without requiring integration from the user. 

Transform Visualizer (3D Slicer) Sparse glyph-based visualization, qualitative only, no numerical readout, no Jacobian information. 

Lack of quantitative readout — no existing tools in 3D Slicer allow users to hover over a point and get a displacement value in physical units (mm).  

No Jacobian visualization in existing tools — compression/expansion information is not available in any standard 3D Slicer workflow.  

No incremental/progressive deformation display — existing tools show only the final deformation state. 

# Software design

...

# Research impact statement

In image-guided neurosurgery (IGNS), patient-to-image registration is used to align preoperative scans with patient anatomy. Registration has been shown to enhance the surgeon’s understanding and improve accurate targeting of brain structures, leading to improved patient outcomes [1]. During brain tumour surgery, ’brain shift’ or non-linear shifts in brain tissue cause a mismatch between preoperative images and the patient’s current anatomy [2]. It is then necessary to use non-linear image registration to deform the preoperative images into alignment with the intraoperative anatomy. 

During brain tumour resection surgery, the brain undergoes non-linear deformations or ‘brain shift’ due to the removal of tissue, changes in intercranial pressure when the skull is opened, medications, etc. Due to brain shift, intraoperative imaging does not align with preoperative imaging spaces, necessitating deformable image registration to put these images in the same space.  Computational imaging researchers who are developing these deformable registration methods must interpret where the deformation occurs to understand where the algorithms are being applied. 

# Overview of DeformView Module

DeformView is an open-source 3D Slicer module designed for research and training use in medical imaging tasks involving deformable image registration. The module accepts a deformation field (transform node) and a reference image as inputs and produces interactive, quantitative visualizations of the transformation directly overlaid on the image. 

Visualization Maps 

DeformView provides two complementary dense visualization maps: 

Displacement Magnitude Map. The first map renders the Euclidean magnitude of the displacement vector at every voxel, in millimeters. There are numerous scientifically-derived, intuitive colour maps available, which encode displacement magnitude continuously across the image volume. An interactive voxel-wise cursor displays the numerical displacement magnitude at the pointer location in real time, enabling point-wise quantitative comprehension directly on the volume. This displacement magnitude map provides a dense spatial understanding of where and by how much deformation has occurred in each discrete location in the 3D volume, intuitively projected into 2D space for ease of interpretation.  

Jacobian Determinant Magnitude Map. The second map renders the magnitude of the Jacobian determinant of the deformation field at every voxel, expressed as a percentage of deformation. The Jacobian determinant encodes local volumetric change. Values greater than 1.0 indicate local tissue expansion, values less than 1.0 indicate compression, and a value of exactly 1.0 indicates no local volume change. The map encodes these values with an intuitive three-colour scheme: compression (values less than 1.0) is rendered in blue as negative percentages, expansion (values greater than 1.0) in red as positive percentages, and no change (values equal to 1.0) in white. Displaying this map densely allows researchers to identify regions of physiologically implausible compression or expansion, which may indicate registration errors, and support biological validation of registration algorithms. 
Increment Transform Feature 

DeformView introduces an Increment Transform feature. Rather than displaying only the final deformation, the transformation is incrementally applied to the moving image across 10 discrete steps (0.1x, 0.2x, … 1.0x of the full transform). This sliding scale allows users to observe the progressive warping of the image and develop an intuitive understanding of how the deformation accumulates spatially, which is particularly useful for training and for diagnosing registration behaviour at intermediate stages.  

# Mathematics

Single dollars ($) are required for inline mathematics e.g. $f(x) = e^{\pi/x}$

Double dollars make self-standing equations:

$$\Theta(x) = \left\{\begin{array}{l}
0\textrm{ if } x < 0\cr
1\textrm{ else}
\end{array}\right.$$

You can also use plain \LaTeX for equations
\begin{equation}\label{eq:fourier}
\hat f(\omega) = \int_{-\infty}^{\infty} f(x) e^{i\omega x} dx
\end{equation}
and refer to \autoref{eq:fourier} from text.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Figure sizes can be customized by adding an optional second parameter:
![Caption for example figure.](figure.png){ width=20% }

# AI usage disclosure

Generative AI tools were used in the development of this software. It was not used for writing
of this manuscript, or the preparation of supporting materials.

# Acknowledgements

We acknowledge contributions from Etienne....

# References

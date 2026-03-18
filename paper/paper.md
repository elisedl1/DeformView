<img width="468" height="25" alt="image" src="https://github.com/user-attachments/assets/07569720-4bd7-46cd-a4bc-e0369617e277" />---
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
    orcid: 0009-0001-5947-6973
    equal-contrib: true
    affiliation: 1
  - name: Elise Donszelmann-Lund
    orcid: 0009-0000-4634-9118
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

DeformView is a 3D Slicer module `[@fedorov2012:2012]` designed for novel dense, intuitive, and quantitative visualization of non-linear deformation fields in image registration. The module produces two interactive voxel-wise overlays: a displacement magnitude map in millimeters and a Jacobian determinant map encoding local volumetric expansion and compression. A real-time cursor enables point-wise numerical readout directly on the image volume, and an Increment Transform feature supports progressive visualization of the deformation across discrete time steps. DeformView can be installed from the 3D Slicer software through the Extension Wizard.

# Statement of need

Non-linear image registration is a key task in computation medical imaging, where a spatially varying deformation field maps a source image onto a fixed target image. There is an extensive body of work on non-linear registration methods, reflecting its broad applicability across imaging modalities. While the primary output of a registration pipeline is the deformed source image – warped into alignment with the target – the underlying deformation field itself encodes quantitative information about spatial correspondence and local tissue mechanics.  

Clinicians and surgeons must interpret these resulting deformation fields, either to guide clinical decision-making or to validate that a registration algorithm is performing correctly, by visualizing the deformed anatomy (source image). However, existing deformation visualization methods for non-linear image registration are largely sparse and qualitative, making it difficult to interpret and localize tissue deformation. Correct interpretation of deformed anatomy is especially difficult for inexperienced surgeons or researchers. 

In image-guided neurosurgery (IGNS), patient-to-image registration is used to align preoperative scans with patient anatomy. ‘Brain shift’, or non-linear shifts in brain tissue, cause a mismatch between preoperative images and the patient’s current anatomy, necessitating the use of non-linear image registration to deform preoperative images into the intraoperative image space. Those developing registration methods must be able to accurately interpret where deformation is occurring to understand how the algorithms are being applied.   

DeformView is designed to address these challenges by providing an intuitive, user-friendly 3D Slicer plugin that enables efficient, dense, and quantitative visualization of deformation fields in medical imaging tasks where registration is applied.  

# State of the field

The primary existing tool for deformation visualization within 3D Slicer is the Transform Visualizer module, which renders sparse representations of the deformation field. The Transform Visualizer module contains three visualizations: glyphs (arrows), uniform grid, and isocontours. These visualizations are placed at a sampled subset of voxel locations, meaning local deformation between glyph positions is entirely invisible to the user, and no numerical displacement information is conveyed.  

The glyph (arrow) visualization does show the direction of deformation, which can advantageously show the user how the image has deformed from its initial state. However, existing tools like the Transform Visualizer module only show the final state deformation; the user is unable to visualize how the deformation was incrementally applied or how specific anatomical regions were compressed or expanded to accommodate the deformation. These unimplemented features increase the user’s uncertainty and lack of confidence when interpreting deformation fields.   

# Software design

DeformView is implemented as a Python extension for 3D Slicer, an open-source medical image computing platform available on Linux, macOS, and Windows under a BSD-style license. Most Slicer basic infrastructure is implemented in C++ and made available in Python through the slicer namespace by PythonQt and VTK Python Wrapper. 

The DeformView module was developed using Python 3.12 and Qt6, following community guidelines for Slicer extension development, and built from the official Slicer extension template to ensure consistency and modularity with the Slicer ecosystem. The core architecture follows Slicer conventions, maintaining the standard Widget and Logic class structure. 

A key design principle of DeformView is compatibility, both with Slicer's data model and with existing modules. All input selectors expose only the data types relevant to each function: for example, the transformation input accepts all transform types available in Slicer (linear, BSpline, grid, thin-plate spline, and composite), while incompatible data types such as images are hidden from selection.  

# Research impact statement

DeformView has generated demonstrable interest from the medical imaging research community beyond its core development team. The module was presented at NA-MIC Project Week 43 and 44 [CITE], the biannual workshop hosted by the National Alliance for Medical Image Computing (NA-MIC), the organization responsible for the continued development of 3D Slicer. These presentations generated substantive discussion among Slicer developers and requests for adoption from external research groups, including researchers at Texas A&M University College of Dentistry for applications in orofacial surgery, and at the Instituto de Microelectrónica Aplicada, Universidad de Las Palmas de Gran Canaria, Spain. The DeformView module has also been used in ongoing research on groupwise ultrasound-CT image registration for spinal surgery [CITE].  

This work is additionally being presented as a peer-reviewed poster at the Imaging Network of Ontario (ImNO) 2026 symposium in the Image Guided Intervention and Surgery category.  

# Overview of DeformView Module

DeformView accepts a deformation field (transform node) and a reference image as inputs and produces two complementary, dense quantitative visualizations overlaid directly on the image, as shown in \autoref{fig:UI_overview}. 

![Overview of DeformView 3D Slicer Module. Left: user interface for the proposed module Right: dense colour map (red is higher deformation) with cursor displaying point-wise deformation magnitude on hover.\label{fig:UI_overview}](figures/UI_overview.png)

### Displacement Magnitude Map

The first map renders the Euclidean magnitude of the displacement vector at every voxel, in millimeters. That is to say, how much that voxel has moved between its original position and its deformed position, in millimeters. To do this, he transform is converted into a dense vector field sampled across the entire reference image grid, and the length of each displacement vector is stored as a scalar value and displayed using a scientifically derived colour map. There are eight scientifically-derived, intuitive colour maps available for this map, including consideration for colour-blind readability. An interactive voxel-wise cursor displays the numerical displacement magnitude at the pointer location in real time, as shown in Figure X. This provides a dense spatial understanding of where and by how much deformation has occurred across the full 3D volume.  

### Jacobian Determinant Magnitude Map

This map renders the magnitude of the Jacobian determinant of the deformation field at every voxel, expressed as a percentage of local volumetric change. That is to say, the magnitude of Jacobian determinant indicates if a region has expanded or contracted with the deformation field. Tissue expansion (values > 1.0) is rendered in red, tissue compression (values < 1.0) in blue, and no change (values = 1.0) in white, as shown in Figure X. Displaying this map densely allows researchers to identify changes to anatomical regions or regions of physiologically implausible compression or expansion, which may indicate registration errors, and support biological validation of registration algorithms. 

### Increment Transform:

DeformView introduces an Increment Transform feature. Rather than displaying only the final deformation, the transformation is incrementally applied to the moving image across 10 discrete steps (0.1x, 0.2x, … 1.0x of the full transform). This sliding scale allows users to observe the progressive warping of the image and develop an intuitive understanding of how the deformation accumulates spatially, which is particularly useful for training and for diagnosing registration behaviour at intermediate stages.  

![DeformView visualizations versus existing Transform module visualizations. Top left: displacement magnitude overlay. Top right: jacobian overlay. Bottom left: glyph visualization. Bottom right: grid visualization.\label{fig:four_plot}](figures/4_plot.png)

### Integration of Previous Methods

DeformView integrates with the existing 3D Slicer Transform Module, combining displacement magnitude maps with overlaid glyphs from the Transform Module in a single view. As shown in \autoref{fig:glyph}, this overlay provides both a quantified, spatially localized understanding of deformation magnitude and an intuitive representation of local direction changes.  

![Integration of DeformView displacement magnitude and existing Transform glyph visualization.\label{fig:glyph}](figures/glyph_overlay.png)

# Preliminary Results

To evaluate if DeformView has achieved its stated goals to improve user interpretability and confidence when visualizing deformed images, we conducted a user study in which participants were randomly shown one image pair from three cases of preoperative and intraoperative T2-FLAIR brain MRI and tasked with interpreting the deformation using both DeformView and Transform Visualizer. 

Ten participants (technical researchers without clinical expertise, mean imaging research experience: 2.9 years) completed the study. Participants were given unlimited time to freely explore each module before providing responses. The image pairs were randomized, and a counterbalanced design was employed to control for order effects.  

Module functionality was assessed on four attributes: helpfulness in comprehension, interpretability, intuitiveness, and user confidence. The assessment has been conducted using a 5-point Likert scale (1 = None, 5 = Great) and the System Usability Scale [CITE]. 

DeformView achieved higher mean scores than Transform Visualizer across all four attributes (mean: 4.1/5.0 vs. 3.2/5.0; standard deviation range: 4.0–4.3 vs. 3.0–3.5). Improvements in helpfulness and intuitiveness reached statistical significance (p = 0.008 and p = 0.027, respectively). Overall, 80% of participants (8/10) preferred DeformView over Transform Visualizer. On the SUS, DeformView achieved an adjusted mean score of 82.8/100 (std: 14.6), which falls in the "excellent" usability range per established SUS benchmarks [Bangor, 2009]. 

![User study (n=10) results comparing our DeformView module and existing Transform module on four attributes
(1–5 scale; green is better). DeformView significantly outperforms existing module on helpfulness (p=0.008) and intuition
(p=0.027), with higher mean scores across all metrics.\label{fig:user}](figures/user_study.png)

### Conclusion

The module shows promise as a training and research tool, with future work aimed at evaluation by expert users (clinicians), additional features, and open-source integration within surgical navigation systems, such as IBIS [cite].

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

Generative AI tools (Claude Sonnet 4.6) were used in the development of this software, specifically for debugging purposes. Authors have reviewed and validated all AI-assisted code output and made all core design decisions. AI was not used for writing this manuscript, or the preparation of supporting materials.  

# Acknowledgements

We acknowledge contributions from Etienne Leger, Taj Choksi, Raphael Christin, Kaleem Siddiqi and Louis Collins

# References

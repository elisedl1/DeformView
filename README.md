# Overview

DeformView provides intuitive, quantified visualization of non-linear deformation fields. It allows users to interpret deformations with dense, voxel-wise maps.

DeformView provides two complementary visualization maps:

1. Displacement Magnitude Map (mm) - shows local displacement of tissue.
2. Jacobian Determinant Magnitude (%) - shows local tissue expansion or compression.

A real-time cursor display allows users to hover over any voxel and see the displacement/jacobian value. 

# Use Cases

- understanding non-linear tissue deformation
- evaluation of registration algorithms
- research in brain shift modeling
- quantitative interpretation of deformation fields
- comparing preoperative and intraoperative scans

# Panels and Their Use
Moving Image: Image after transform has been applied
Fixed Image: Reference image
Transformation: Known transformation between images

Compute Displacement Field Mapping
- computes both the dense mm displacement volume and the dense jacobian determinant volume
- automatically loads the fixed volume into the scene with 100% of the transformation applied, overlayed with the corresponding displacement volume

Color Map/Loading Function
- switch between displacement volume and Jacobian volume 
- must reload to update color map 
- includes a selection of intuitive color maps
- only applied to the computed displacement volume
- * Jacobian volume has a fixed color map and cannot be changed
 
Display Settings
- change opacity of displacement/jacobian volume overlay
- Increment slider
- --> change the step of the transform
- --> ie apply 0-100% of the transform onto the overlayed/background volume
- change visible displacement range (threshold)
- change level/window of displacement volume

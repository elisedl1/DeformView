import numpy as np
import nibabel as nib
import json


matrix_size = 128  # Size of volume
voxel_size = 1.0   # Voxel spacing in mm
sphere_radius = 40  # Radius in voxels

# Create coordinate grids
center = matrix_size // 2
x, y, z = np.ogrid[:matrix_size, :matrix_size, :matrix_size]

# Create sphere mask
distance_from_center = np.sqrt((x - center)**2 + (y - center)**2 + (z - center)**2)
sphere = (distance_from_center <= sphere_radius).astype(np.float32)

# Create affine matrix (identity with voxel spacing)
affine = np.eye(4)
affine[0, 0] = voxel_size
affine[1, 1] = voxel_size
affine[2, 2] = voxel_size
affine[0, 3] = -center * voxel_size  # Center the sphere at origin
affine[1, 3] = -center * voxel_size
affine[2, 3] = -center * voxel_size

# Save sphere as NIfTI
nifti_img = nib.Nifti1Image(sphere, affine)
nifti_img.to_filename('GeometricTestCase/sphere.nii.gz') # BrainShiftModuelValidation folder

print(f"Sphere created with:")
print(f"  Matrix size: {matrix_size}^3")
print(f"  Voxel size: {voxel_size} mm")
print(f"  Sphere radius: {sphere_radius} voxels ({sphere_radius * voxel_size} mm)")

# Define anatomical landmarks on the sphere surface
# These are classic anatomical positions: anterior, posterior, left, right, superior, inferior
landmarks = {
    "Anterior": [center, center, center + sphere_radius], 
    "Posterior": [center, center, center - sphere_radius],
    "Right": [center + sphere_radius, center, center],
    "Left": [center - sphere_radius, center, center],
    "Superior": [center, center + sphere_radius, center],
    "Inferior": [center, center - sphere_radius, center],
    #on a globe centered on the Atlantic - these would be mongolia and easter islands
    "Anterior-Right-Superior": [center + sphere_radius/np.sqrt(3), center + sphere_radius/np.sqrt(3), center + sphere_radius/np.sqrt(3)],
    "Posterior-Left-Inferior": [center - sphere_radius/np.sqrt(3), center - sphere_radius/np.sqrt(3), center - sphere_radius/np.sqrt(3)]
}

# Convert landmarks to RAS physical coordinates
landmarks_ras = {}
for name, voxel_coords in landmarks.items():
    # Convert voxel to RAS coordinates using affine
    voxel_homogeneous = np.array([voxel_coords[0], voxel_coords[1], voxel_coords[2], 1])
    ras_coords = affine @ voxel_homogeneous
    landmarks_ras[name] = ras_coords[:3].tolist()

# Save landmarks in 3D Slicer FCSV format (Fiducial Coordinate System V)
#TODO: Some testing on the landmark conversion feature as well
fcsv_content = """# Markups fiducial file version = 4.11
# CoordinateSystem = RAS
# columns = id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID
"""

for idx, (name, coords) in enumerate(landmarks_ras.items()):
    # FCSV format: id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID
    fcsv_content += f"vtkMRMLMarkupsFiducialNode_{idx},{coords[0]},{coords[1]},{coords[2]},0,0,0,1,1,1,0,{name},,\n"

with open('GeometricTestCase/sphere_landmarks.fcsv', 'w') as f:
    f.write(fcsv_content)

# Also save as JSON for easier reading/manipulation
landmarks_json = {
    "coordinate_system": "RAS",
    "voxel_size_mm": voxel_size,
    "landmarks": landmarks_ras
}

with open('GeometricTestCase/sphere_landmarks.json', 'w') as f:
    json.dump(landmarks_json, f, indent=2)

print("\nLandmarks created:")
for name, coords in landmarks_ras.items():
    print(f"  {name}: [{coords[0]:.2f}, {coords[1]:.2f}, {coords[2]:.2f}] mm (RAS)")

print("\nFiles created:")
print("  - sphere.nii.gz (NIfTI image)")
print("  - sphere_landmarks.fcsv (3D Slicer fiducial file)")
print("  - sphere_landmarks.json (JSON format for reference)")
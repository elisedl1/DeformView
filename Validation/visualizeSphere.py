import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import json

# Load the sphere
sphere_img = nib.load('GeometricTestCase/sphere_deformed_compression.nii.gz')
sphere_data = sphere_img.get_fdata()

# Load landmarks
with open('GeometricTestCase/sphere_landmarks_deformed_compression.json', 'r') as f:
    landmarks_data = json.load(f)

# Create figure with 2x2 subplots
fig = plt.figure(figsize=(14, 12))

# Axial slice (z)
ax1 = fig.add_subplot(2, 2, 1)
z_slice = sphere_data.shape[2] // 2
ax1.imshow(sphere_data[:, :, z_slice].T, cmap='gray', origin='lower')
ax1.set_title('Axial Slice (z = middle)')
ax1.set_xlabel('X')
ax1.set_ylabel('Y')
ax1.axis('equal')

# Sagittal slice (x)
ax2 = fig.add_subplot(2, 2, 2)
x_slice = sphere_data.shape[0] // 2
ax2.imshow(sphere_data[x_slice, :, :].T, cmap='gray', origin='lower')
ax2.set_title('Sagittal Slice (x = middle)')
ax2.set_xlabel('Y')
ax2.set_ylabel('Z')
ax2.axis('equal')

# Coronal slice (y)
ax3 = fig.add_subplot(2, 2, 3)
y_slice = sphere_data.shape[1] // 2
ax3.imshow(sphere_data[:, y_slice, :].T, cmap='gray', origin='lower')
ax3.set_title('Coronal Slice (y = middle)')
ax3.set_xlabel('X')
ax3.set_ylabel('Z')
ax3.axis('equal')

# 3D visualization of sphere surface and landmarks
ax4 = fig.add_subplot(2, 2, 4, projection='3d')

# Find surface points (sample for visualization)
surface_points = np.argwhere(sphere_data > 0.5)
# Downsample for visualization
sample_indices = np.random.choice(len(surface_points), min(2000, len(surface_points)), replace=False)
surface_sample = surface_points[sample_indices]

ax4.scatter(surface_sample[:, 0], surface_sample[:, 1], surface_sample[:, 2], 
           c='lightblue', marker='.', s=1, alpha=0.3, label='Sphere surface')

# Convert RAS landmarks back to voxel coordinates for plotting
affine = sphere_img.affine
inv_affine = np.linalg.inv(affine)

landmark_voxels = {}
for name, ras_coords in landmarks_data['landmarks'].items():
    ras_homogeneous = np.array([ras_coords[0], ras_coords[1], ras_coords[2], 1])
    voxel_coords = inv_affine @ ras_homogeneous
    landmark_voxels[name] = voxel_coords[:3]

# Plot landmarks
for name, coords in landmark_voxels.items():
    ax4.scatter(coords[0], coords[1], coords[2], c='red', marker='o', s=100)
    ax4.text(coords[0], coords[1], coords[2], f'  {name}', fontsize=6)

ax4.set_xlabel('X')
ax4.set_ylabel('Y')
ax4.set_zlabel('Z')
ax4.set_title('3D View with Landmarks')
ax4.legend()

# Set equal aspect ratio
max_range = sphere_data.shape[0] // 2
ax4.set_xlim([sphere_data.shape[0]//2 - max_range, sphere_data.shape[0]//2 + max_range])
ax4.set_ylim([sphere_data.shape[1]//2 - max_range, sphere_data.shape[1]//2 + max_range])
ax4.set_zlim([sphere_data.shape[2]//2 - max_range, sphere_data.shape[2]//2 + max_range])

plt.tight_layout()
plt.savefig('GeometricTestCase/sphere_visualization.png', dpi=150, bbox_inches='tight')
print("Visualization saved to sphere_visualization.png")

# Print summary information
print("\n" + "="*60)
print("SPHERE AND LANDMARKS SUMMARY")
print("="*60)
print(f"\nSphere Properties:")
print(f"  Dimensions: {sphere_data.shape}")
print(f"  Voxel size: {landmarks_data['voxel_size_mm']} mm isotropic")
print(f"  Coordinate system: {landmarks_data['coordinate_system']}")
print(f"\nLandmarks (in RAS coordinates):")
for name, coords in landmarks_data['landmarks'].items():
    print(f"  {name:30s}: [{coords[0]:7.2f}, {coords[1]:7.2f}, {coords[2]:7.2f}] mm")
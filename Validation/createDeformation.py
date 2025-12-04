"""
Displacement Field Visualization with Arrows using Plotly
==========================================================
This script visualizes displacement vectors between original and deformed
landmark positions, showing both the sphere surfaces and displacement arrows.

Usage:
    python plot_displacement_vectors.py [deformation_type]
    
    deformation_type: 'compression', 'twist', 'bend', or 'custom'

Requirements:
    - nibabel
    - plotly
    - numpy

    voxel → affine → RAS → deform → voxel

    Do : voxel -> voxel-based deformation 

"""
import SimpleITK as sitk
import numpy as np
import nibabel as nib
import plotly.graph_objects as go
import json
import sys
from scipy.ndimage import map_coordinates
import nrrd
radius = 60.0

def load_sphere_and_landmarks(sphere_path, landmarks_path):
    """Load sphere image and landmarks from files"""
    sphere_img = nib.load(sphere_path)
    sphere_data = sphere_img.get_fdata()
    affine = sphere_img.affine
    
    with open(landmarks_path, 'r') as f:
        landmarks_data = json.load(f)
    
    return sphere_img, sphere_data, affine, landmarks_data


# -------------------------------------------------------
# 1. Deformations are now defined in VOXEL SPACE only
# -------------------------------------------------------
def voxel_space_deformation(i, j, k, deformation_type="compression"):
    """
    Apply synthetic deformation in *voxel space*.

    Parameters
    ----------
    i, j, k : 3D arrays
        Voxel coordinate grids
    deformation_type : str
        'compression', 'twist', 'bend', etc.

    Returns
    -------
    di, dj, dk : 3D arrays
        Displacements (in voxel units)
    """

    # Normalize coordinates to [-1, 1] for stable behavior
    I = (i - i.mean()) / (np.ptp(i) / 2)
    J = (j - j.mean()) / (np.ptp(j) / 2)
    K = (k - k.mean()) / (np.ptp(k) / 2)

    # Initialize displacement fields
    di = np.zeros_like(I, dtype=float)
    dj = np.zeros_like(I, dtype=float)
    dk = np.zeros_like(I, dtype=float)

    if deformation_type == "compression":
        print("  Applying compression deformation in voxel space...")
        # Compress along Z (K axis), expand in X/Y - need to be big enough (in voxels)
        di = +20.0 * I   
        dj = +15.0 * J   
        dk = -10.0 * K   


    elif deformation_type == "twist":
        # Twist around center axis, angle increases with K
        angle = 0.5 * K
        cosA = np.cos(angle)
        sinA = np.sin(angle)

        newI = I * cosA - J * sinA
        newJ = I * sinA + J * cosA

        di = newI - I
        dj = newJ - J
        dk = np.zeros_like(K)

    elif deformation_type == "bend":
        # Bend along I axis depending on height (K)
        di = 0.20 * K
        dj = np.zeros_like(J)
        dk = np.zeros_like(K)

    else:
        print("WARNING: Unknown deformation_type. No deformation applied.")

    return di, dj, dk


def apply_deformation_to_volume_voxel_space(volume, deformation_type):
    """
    Apply voxel-space deformation using trilinear interpolation.
    Returns:
      - deformed volume
      - voxel-space displacement field (di, dj, dk)
    """

    print(f"Applying voxel-space deformation: {deformation_type}")

    shape = volume.shape
    i, j, k = np.meshgrid(
        np.arange(shape[0]),
        np.arange(shape[1]),
        np.arange(shape[2]),
        indexing='ij'
    )

    # Compute displacement field in voxel units
    di, dj, dk = voxel_space_deformation(i, j, k, deformation_type)

    # print(f"  Displacement field stats:")
    # print(f"    di: min={di.min():.4f}, max={di.max():.4f}, mean={di.mean():.4f}")
    # print(f"    dj: min={dj.min():.4f}, max={dj.max():.4f}, mean={dj.mean():.4f}")
    # print(f"    dk: min={dk.min():.4f}, max={dk.max():.4f}, mean={dk.mean():.4f}")

    # Generate deformed sampling grid
    i_def = i - di
    j_def = j - dj
    k_def = k - dk

    # Interpolate smoothly
    coords = np.array([i_def, j_def, k_def])
    deformed = map_coordinates(volume, coords, order=3, mode="constant", cval=0)

    #print("  Deformation applied to volume.")
    return deformed, (di, dj, dk)


def simulate_deformation_voxel(coords_vox, deformation_type='compression'):
    """
    coords_vox: (N,3) voxel coordinates
    Returns: deformed voxel coordinates
    """
    deformed = coords_vox.copy()
    
    if deformation_type == 'compression':
        deformed[:, 0] = coords_vox[:, 0] * 1.15  # expand X
        deformed[:, 1] = coords_vox[:, 1] * 1.15  # expand Y
        deformed[:, 2] = coords_vox[:, 2] * 0.8   # compress Z
    
    elif deformation_type == 'twist':
        r = np.sqrt(coords_vox[:,0]**2 + coords_vox[:,1]**2)
        theta = np.arctan2(coords_vox[:,1], coords_vox[:,0])
        z_factor = coords_vox[:,2] / np.max(coords_vox[:,2])
        theta_new = theta + z_factor * 0.5
        deformed[:,0] = r * np.cos(theta_new)
        deformed[:,1] = r * np.sin(theta_new)
    
    elif deformation_type == 'bend':
        z_norm = coords_vox[:,2] / np.max(coords_vox[:,2])
        offset = z_norm * 10
        deformed[:,0] = coords_vox[:,0] + offset
    
    return deformed


def load_displacement_field(displacement_field_path):
    """
    Load displacement field from NIfTI file
    
    Parameters:
    -----------
    displacement_field_path : str
        Path to the displacement field NIfTI file
        
    Returns:
    --------
    displacement_field : tuple of numpy arrays
        Displacement field components (di, dj, dk) in voxel space
    affine : numpy array
        Affine transformation matrix from the NIfTI file
    """
    # Load NIfTI image
    disp_img = nib.load(displacement_field_path)
    
    # Get affine matrix
    affine = disp_img.affine
    
    # Get displacement field data (shape: [X, Y, Z, 3])
    displacement_field = disp_img.get_fdata()
    
    # Split into components
    di = displacement_field[..., 0]
    dj = displacement_field[..., 1]
    dk = displacement_field[..., 2]
    
    #displacement_field = np.stack([di, dj, dk], axis=-1)

    return (di, dj, dk), affine

def save_displacement_field(displacement_field, affine, deformation_type, output_path=None):
    """
    Save displacement field as NIfTI file
    
    Parameters:
    -----------
    displacement_field : numpy array
        Displacement field in voxel space (shape: [X, Y, Z, 3])
    affine : numpy array
        Affine transformation matrix
    deformation_type : str
        Type of deformation (for filename)
    output_path : str
        Output filename (optional)
        
    Returns:
    --------
    output_path : str
        Path where file was saved
    """
    if output_path is None:
        output_path = f'GeometricTestCase/displacement_field_{deformation_type}.nii.gz'
    
    # Create NIfTI image
    # Note: NIfTI expects 4D array for vector fields [X, Y, Z, 3]
    (di, dj, dk) = displacement_field

    displacement_field = np.stack([di, dj, dk], axis=-1)
    disp_img = nib.Nifti1Image(displacement_field.astype(np.float32), affine)
    
    # Set intent code to indicate this is a displacement field
    disp_img.header.set_intent('vector', (), '')
    
    # Save
    nib.save(disp_img, output_path)
    
    return output_path


def deform_landmarks_voxel_space(landmark_voxels, displacement_field):
    """
    Deforms landmark voxel coordinates using the SAME voxel-space field.

    Parameters
    ----------
    landmark_voxels : (N, 3) array
        Landmark positions in voxel coordinates (not RAS!)
    displacement_field : (di, dj, dk)
        Same field used for the volume

    Returns
    -------
    deformed_landmarks_voxel : (N, 3)
        Deformed positions in voxel space
    """

    di, dj, dk = displacement_field
    shape = di.shape

    # Split coordinates
    lv_i = landmark_voxels[:, 0]
    lv_j = landmark_voxels[:, 1]
    lv_k = landmark_voxels[:, 2]

    # Use trilinear interpolation of displacement at landmark locations
    disp_i = map_coordinates(di, [lv_i, lv_j, lv_k], order=1, mode='nearest')
    disp_j = map_coordinates(dj, [lv_i, lv_j, lv_k], order=1, mode='nearest')
    disp_k = map_coordinates(dk, [lv_i, lv_j, lv_k], order=1, mode='nearest')

    # Apply deformation
    new_i = lv_i + disp_i
    new_j = lv_j + disp_j
    new_k = lv_k + disp_k

    return np.vstack([new_i, new_j, new_k]).T

def save_deformed_landmarks(landmark_names, landmark_coords_deformed, deformation_type, 
                           landmarks_data, output_json=None, output_fcsv=None):
    """
    Save deformed landmarks in both JSON and FCSV formats
    
    Parameters:
    -----------
    landmark_names : list
        Names of landmarks
    landmark_coords_deformed : numpy array
        Deformed landmark coordinates in RAS
    deformation_type : str
        Type of deformation (for filename)
    landmarks_data : dict
        Original landmarks data (for coordinate system info)
    output_json : str
        Output JSON filename (optional)
    output_fcsv : str
        Output FCSV filename (optional)
        
    Returns:
    --------
    tuple : (json_path, fcsv_path)
        Paths where files were saved
    """
    if output_json is None:
        output_json = f'GeometricTestCase/sphere_landmarks_deformed_{deformation_type}.json'
    if output_fcsv is None:
        output_fcsv = f'GeometricTestCase/sphere_landmarks_deformed_{deformation_type}.fcsv'
    
    # Create JSON format
    landmarks_json = {
        "coordinate_system": landmarks_data.get('coordinate_system', 'RAS'),
        "voxel_size_mm": landmarks_data.get('voxel_size_mm', 1.0),
        "deformation_type": deformation_type,
        "landmarks": {}
    }
    
    for name, coords in zip(landmark_names, landmark_coords_deformed):
        landmarks_json["landmarks"][name] = coords.tolist()
    
    # Save JSON
    with open(output_json, 'w') as f:
        json.dump(landmarks_json, f, indent=2)
    
    # Create FCSV format (3D Slicer fiducials)
    fcsv_content = """# Markups fiducial file version = 4.11
# CoordinateSystem = RAS
# columns = id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID
"""
    
    for idx, (name, coords) in enumerate(zip(landmark_names, landmark_coords_deformed)):
        # FCSV format: id,x,y,z,ow,ox,oy,oz,vis,sel,lock,label,desc,associatedNodeID
        fcsv_content += f"vtkMRMLMarkupsFiducialNode_{idx},{coords[0]},{coords[1]},{coords[2]},0,0,0,1,1,1,0,{name},,\n"
    
    # Save FCSV
    with open(output_fcsv, 'w') as f:
        f.write(fcsv_content)
    
    return output_json, output_fcsv



def save_deformed_sphere(sphere_img, deformed_data, deformation_type, output_path=None):
    """
    Save deformed sphere as NIfTI file
    
    Parameters:
    -----------
    sphere_img : nibabel image
        Original sphere image (for header information)
    deformed_data : numpy array
        Deformed volume data
    deformation_type : str
        Type of deformation (for filename)
    output_path : str
        Output filename (optional)
        
    Returns:
    --------
    output_path : str
        Path where file was saved
    """
    if output_path is None:
        output_path = f'GeometricTestCase/sphere_deformed_{deformation_type}.nii.gz'
    
    # Create new NIfTI image with same header as original
    deformed_img = nib.Nifti1Image(deformed_data, sphere_img.affine, sphere_img.header)
    
    # Save
    nib.save(deformed_img, output_path)
    
    return output_path


def extract_mesh_surface(sphere_data, affine, downsample_factor=2):
    """
    Extract mesh surface using marching cubes algorithm
    
    Parameters:
    -----------
    sphere_data : numpy array
        3D volume data
    affine : numpy array
        Affine transformation matrix
    downsample_factor : int
        Factor to downsample volume before mesh extraction
        
    Returns:
    --------
    verts_ras : numpy array
        Vertices in RAS coordinates
    faces : numpy array
        Triangle faces
    """
    from scipy.ndimage import zoom
    from skimage import measure
    
    # Downsample for faster processing
    sphere_downsampled = zoom(sphere_data, 1/downsample_factor, order=1)
    
    # Extract mesh using marching cubes
    verts, faces, normals, values = measure.marching_cubes(
        sphere_downsampled, 
        level=0.5
    )
    
    # Scale vertices back to original size
    verts_scaled = verts * downsample_factor
    
    # Convert to RAS coordinates
    verts_ras = []
    for vert in verts_scaled:
        voxel_homogeneous = np.array([vert[0], vert[1], vert[2], 1])
        ras_coords = affine @ voxel_homogeneous
        verts_ras.append(ras_coords[:3])
    
    verts_ras = np.array(verts_ras)
    
    return verts_ras, faces

def ras_to_voxel(ras_points, affine):
    inv_aff = np.linalg.inv(affine)
    pts = []
    for p in ras_points:
        h = np.array([*p, 1])
        v = inv_aff @ h
        pts.append(v[:3])
    return np.array(pts)

def voxel_to_ras(vox_points, affine):
    pts = []
    for p in vox_points:
        h = np.array([*p, 1])
        r = affine @ h
        pts.append(r[:3])
    return np.array(pts)

def get_landmark_coords(landmarks_data):
    landmark_coords = []
    # Get original landmark positions
    landmark_names = []

    for name, coords in landmarks_data['landmarks'].items():
        landmark_names.append(name)
        landmark_coords.append(coords)
    
    landmark_coords = np.array(landmark_coords)

    return landmark_coords, landmark_names



# def save_displacement_field_nrrd(displacement_field, affine, deformation_type, output_path=None):
#     """
#     Save displacement field as NRRD file
    
#     Parameters:
#     -----------
#     displacement_field : tuple of numpy arrays
#         Displacement field in voxel space (di, dj, dk)
#     affine : numpy array
#         Affine transformation matrix
#     deformation_type : str
#         Type of deformation (for filename)
#     output_path : str
#         Output filename (optional)
        
#     Returns:
#     --------
#     output_path : str
#         Path where file was saved
#     """
#     if output_path is None:
#         output_path = f'GeometricTestCase/displacement_field_{deformation_type}.nrrd'
    
#     # Stack displacement components into 4D array [X, Y, Z, 3]
#     (di, dj, dk) = displacement_field
#     displacement_array = np.stack([di, dj, dk], axis=-1)
    
#     # Create NRRD header with spatial information
#     header = {
#         'type': 'float',
#         'dimension': 4,
#         'space': 'left-posterior-superior',  # Standard medical imaging space
#         'sizes': np.array(displacement_array.shape),
#         'space directions': np.array([
#             affine[0, :3],
#             affine[1, :3],
#             affine[2, :3],
#             [np.nan, np.nan, np.nan]  # Vector dimension has no spatial direction
#         ]),
#         'kinds': ['domain', 'domain', 'domain', 'vector'],
#         'space origin': affine[:3, 3],
#         'encoding': 'gzip'
#     }
    
#     # Save as NRRD
#     nrrd.write(output_path, displacement_array.astype(np.float32), header)
    
#     print(f"  Saved displacement field (NRRD) to: {output_path}")
#     return output_path


def save_displacement_field_as_transform(displacement_field, affine, deformation_type, output_path=None):
    """
    Save displacement field as ITK transform file (.h5) for 3D Slicer
    
    Parameters:
    -----------
    displacement_field : tuple of numpy arrays
        Displacement field in voxel space (di, dj, dk)
    affine : numpy array
        Affine transformation matrix
    deformation_type : str
        Type of deformation (for filename)
    output_path : str
        Output filename (optional)
        
    Returns:
    --------
    output_path : str
        Path where file was saved
    """
    if output_path is None:
        output_path = f'GeometricTestCase/displacement_field_{deformation_type}.h5'
    
    # Stack displacement components into 4D array [X, Y, Z, 3]
    (di, dj, dk) = displacement_field
    displacement_array = np.stack([di, dj, dk], axis=-1)
    
    # Create SimpleITK displacement field image
    # Note: SimpleITK uses (Z, Y, X, components) ordering
    displacement_sitk = sitk.GetImageFromArray(
        displacement_array.transpose(2, 1, 0, 3),  # Reorder to ZYX
        isVector=True
    )
    
    # Set spacing and origin from affine matrix
    spacing = np.sqrt(np.sum(affine[:3, :3]**2, axis=0))
    origin = affine[:3, 3]
    
    displacement_sitk.SetSpacing(spacing.tolist())
    displacement_sitk.SetOrigin(origin.tolist())
    
    # Extract direction matrix from affine
    direction_matrix = affine[:3, :3] / spacing
    displacement_sitk.SetDirection(direction_matrix.flatten().tolist())
    
    # Create displacement field transform
    displacement_transform = sitk.DisplacementFieldTransform(displacement_sitk)
    
    # Write transform file
    sitk.WriteTransform(displacement_transform, output_path)
    
    print(f"  Saved displacement field transform to: {output_path}")
    return output_path


def displacement(sphere_path, landmarks_path, deformation_type='compression',
                          output_html=None, show_surface=True, mesh_downsample=2,
                          mesh_opacity=0.4, save_deformed_volume=True, 
                          save_landmarks=True, save_disp_field=True):
    """
    Create interactive displacement visualization with mesh surfaces
    """
    
    if output_html is None:
        output_html = f'GeometricTestCase/displacement_{deformation_type}.html'
    
    # Load data
    #print("Loading data...")
    sphere_img, sphere_data, affine, landmarks_data = load_sphere_and_landmarks(
        sphere_path, landmarks_path
    )
    

    landmark_coords_original, landmark_names_original = get_landmark_coords(landmarks_data)
   
    
    # First deform volume so we get displacement field
    deformed_data, displacement_field = apply_deformation_to_volume_voxel_space(
        sphere_data, deformation_type
    )

    # Convert landmark RAS → voxel before deformation
    landmark_vox = ras_to_voxel(landmark_coords_original, affine)

    # Deform landmark voxel positions using SAME displacement field
    landmark_vox_deformed = deform_landmarks_voxel_space(
        landmark_vox, displacement_field
    )

    # Convert voxel → RAS for visualization
    landmark_coords_deformed = voxel_to_ras(landmark_vox_deformed, affine)


    # Calculate displacement vectors
    displacement_vectors = landmark_coords_deformed - landmark_coords_original
    displacement_magnitudes = np.linalg.norm(displacement_vectors, axis=1)
    with open('GeometricTestCase/output.txt', 'w') as f:
        for vec in range(len(displacement_vectors)):
            f.write(f"Landmark {landmark_names_original[vec]}:\n")
            f.write(f"  Displacement vector: {displacement_vectors[vec]}\n")
            f.write(f"  Deformed coords: {landmark_coords_deformed[vec]}\n")
            f.write(f"  Original coords: {landmark_coords_original[vec]}\n")
            f.write(f"  Magnitude: {displacement_magnitudes[vec]:.4f}\n")
            f.write("\n")

    
    # Print statistics
    print(f"\nDisplacement Statistics:")
    print(f"  Mean: {np.mean(displacement_magnitudes):.2f} mm")
    print(f"  Max:  {np.max(displacement_magnitudes):.2f} mm")
    print(f"  Min:  {np.min(displacement_magnitudes):.2f} mm")
    print(f"  Std:  {np.std(displacement_magnitudes):.2f} mm")
    
    # Save deformed landmarks if requested
    landmarks_json_path = None
    landmarks_fcsv_path = None
    if save_landmarks:
        print(f"\nSaving deformed landmarks...")
        landmarks_json_path, landmarks_fcsv_path = save_deformed_landmarks(
            landmark_names_original, 
            landmark_coords_deformed, 
            deformation_type,
            landmarks_data
        )
        # print(f"  Saved JSON: {landmarks_json_path}")
        # print(f"  Saved FCSV: {landmarks_fcsv_path}")
    
    # Save deformed volume and displacement field if landm
    deformed_volume_path = None
    displacement_field_path = None
 
    if save_deformed_volume:
        deformed_volume_path = save_deformed_sphere(sphere_img, deformed_data, deformation_type)
        #print(f"  Saved deformed sphere to: {deformed_volume_path}")
    
    if save_disp_field:
        displacement_field_path = save_displacement_field(displacement_field, affine, deformation_type)
        #print(f"  Saved displacement field to: {displacement_field_path}")
        displacement_field_nrrd_path = save_displacement_field_as_transform(displacement_field, affine, deformation_type)


    # # OPTIONAL: Verify landmarks are on/near surface
    # if save_deformed_volume or save_disp_field:
    #     print("\nVerifying landmark positions on deformed surface...")
    #     inv_affine = np.linalg.inv(affine)
    #     for i, (name, ras_coord) in enumerate(zip(landmark_names_original, landmark_coords_deformed)):
    #         # Convert to voxel coordinates
    #         ras_homogeneous = np.array([ras_coord[0], ras_coord[1], ras_coord[2], 1])
    #         #voxel = inv_affine @ ras_homogeneous
    #         #voxel = voxel[:3].astype(int)
    #         voxel = ras_to_voxel(landmark_coords_deformed[i:i+1], affine)[0]
    #         voxel = voxel.astype(int)
    #         # Check if on surface (within bounds)
    #         if (0 <= voxel[0] < deformed_data.shape[0] and 
    #             0 <= voxel[1] < deformed_data.shape[1] and 
    #             0 <= voxel[2] < deformed_data.shape[2]):
    #             voxel_value = deformed_data[voxel[0], voxel[1], voxel[2]]
    #             status = "ON SURFACE" if voxel_value > 0.5 else "OFF SURFACE"
    #             print(f"  {name:30s}: {status} (value={voxel_value:.3f})")
    #         else:
    #             print(f"  {name:30s}: OUT OF BOUNDS")
    return displacement_vectors, displacement_magnitudes, deformed_volume_path, displacement_field_path, landmarks_json_path, landmarks_fcsv_path



    
def createVisualization(sphere_path, landmarks_path, deformation_path, deformed_landmark_path, displacement_field_path, displacement_vectors, displacement_magnitudes, deformation_type='compression',
                          show_surface=True, mesh_downsample=1,
                          mesh_opacity=0.4):
    # Rest of the visualization code remains the same...
    # Create figure
    print("\nCreating visualization...")
    fig = go.Figure()
    
    sphere_img, sphere_data, affine, landmarks_data = load_sphere_and_landmarks(
        sphere_path, landmarks_path
    )

    deformed_sphere_img, deformed_sphere_data, deformed_affine, deformed_landmarks_data = load_sphere_and_landmarks(
        deformation_path, deformed_landmark_path
    )

    (di, dj, dk), displacement_affine = load_displacement_field(displacement_field_path)
    # Add surfaces if requested
    if show_surface:
        print(f"  Extracting mesh surfaces (downsample factor: {mesh_downsample})...")
        verts_ras, faces = extract_mesh_surface(sphere_data, affine, downsample_factor=mesh_downsample)
        print(f"    Original mesh: {len(verts_ras)} vertices, {len(faces)} faces")
        
        # Original surface mesh
        fig.add_trace(go.Mesh3d(
            x=verts_ras[:, 0],
            y=verts_ras[:, 1],
            z=verts_ras[:, 2],
            i=faces[:, 0],
            j=faces[:, 1],
            k=faces[:, 2],
            color='lightgray',
            opacity=mesh_opacity * 0.7,
            name='Original Sphere',
            hoverinfo='skip',
            flatshading=True,
            lighting=dict(ambient=0.5, diffuse=0.8, specular=0.2),
            lightposition=dict(x=100, y=100, z=100)
        ))
        
        landmark_coords_original, landmark_names  = get_landmark_coords(landmarks_data)
        landmark_coords_deformed, landmark_names_deformed  = get_landmark_coords(deformed_landmarks_data)


        # Deformed surface mesh
        #verts_deformed = voxel_space_deformation(verts_ras, deformation_type)
        # Convert mesh vertices from RAS → voxel
        verts_vox = ras_to_voxel(verts_ras, affine)

        # Interpolate displacement for each mesh vertex
        #(di, dj, dk) = displacement_field
        disp_i = map_coordinates(di, verts_vox.T, order=1, mode="nearest")
        disp_j = map_coordinates(dj, verts_vox.T, order=1, mode="nearest")
        disp_k = map_coordinates(dk, verts_vox.T, order=1, mode="nearest")

        verts_vox_deformed = verts_vox + np.vstack([disp_i, disp_j, disp_k]).T


        # Convert back voxel → RAS
        verts_deformed = voxel_to_ras(verts_vox_deformed, affine)
        fig.add_trace(go.Mesh3d(
            x=verts_deformed[:, 0],
            y=verts_deformed[:, 1],
            z=verts_deformed[:, 2],
            i=faces[:, 0],
            j=faces[:, 1],
            k=faces[:, 2],
            color='lightblue',
            opacity=mesh_opacity,
            name='Deformed Sphere',
            hoverinfo='skip',
            flatshading=True,
            lighting=dict(ambient=0.5, diffuse=0.8, specular=0.2),
            lightposition=dict(x=100, y=100, z=100)
        ))
    
    # Add original landmarks
    fig.add_trace(go.Scatter3d(
        x=landmark_coords_original[:, 0],
        y=landmark_coords_original[:, 1],
        z=landmark_coords_original[:, 2],
        mode='markers',
        marker=dict(size=8, color='darkred', symbol='circle', 
                   line=dict(color='black', width=1)),
        name='Original Landmarks',
        text=landmark_names,
        hovertemplate='<b>%{text}</b><br>Original<br>X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>'
    ))
    
    # Add deformed landmarks
    fig.add_trace(go.Scatter3d(
        x=landmark_coords_deformed[:, 0],
        y=landmark_coords_deformed[:, 1],
        z=landmark_coords_deformed[:, 2],
        mode='markers',
        marker=dict(size=8, color='red', symbol='diamond',
                   line=dict(color='darkred', width=1)),
        name='Deformed Landmarks',
        text=landmark_names,
        hovertemplate='<b>%{text}</b><br>Deformed<br>X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>'
    ))
    
    # Add displacement vectors as arrows
    print("  Adding displacement arrows...")
    for i in range(len(landmark_coords_original)):
        orig = landmark_coords_original[i]
        deform = landmark_coords_deformed[i]
        
        # Create arrow line
        fig.add_trace(go.Scatter3d(
            x=[orig[0], deform[0]],
            y=[orig[1], deform[1]],
            z=[orig[2], deform[2]],
            mode='lines',
            line=dict(color='red', width=5),
            showlegend=False,
            hovertemplate=f'<b>{landmark_names[i]}</b><br>' +
                         f'Displacement: {displacement_magnitudes[i]:.2f} mm<br>' +
                         f'Vector: [{displacement_vectors[i,0]:.2f}, {displacement_vectors[i,1]:.2f}, {displacement_vectors[i,2]:.2f}]<extra></extra>'
        ))
        
        # Add cone at the end of arrow
        direction = displacement_vectors[i]
        direction_normalized = direction / (np.linalg.norm(direction) + 1e-10)
        
        fig.add_trace(go.Cone(
            x=[deform[0]],
            y=[deform[1]],
            z=[deform[2]],
            u=[direction_normalized[0]],
            v=[direction_normalized[1]],
            w=[direction_normalized[2]],
            colorscale=[[0, 'red'], [1, 'red']],
            showscale=False,
            sizemode='absolute',
            sizeref=2.5,
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text=f'Displacement Visualization: {deformation_type.capitalize()} Deformation<br>' +
                 f'<sub>Compression: +20 (X), +15 (Y), -10 (Z) </sub>',
            x=0.5,
            xanchor='center'
        ),
        scene=dict(
            xaxis=dict(title='X (Right) [mm]', backgroundcolor="white", gridcolor="lightgray"),
            yaxis=dict(title='Y (Anterior) [mm]', backgroundcolor="white", gridcolor="lightgray"),
            zaxis=dict(title='Z (Superior) [mm]', backgroundcolor="white", gridcolor="lightgray"),
            aspectmode='data',
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
        ),
        width=1000,
        height=800,
        showlegend=True,
        legend=dict(x=0.7, y=0.9)
    )
    
    # Save    
    # Print individual displacements
    print(f"\nIndividual Landmark Displacements:")
    for i, name in enumerate(landmark_names):
        print(f"  {name:30s}: {displacement_magnitudes[i]:6.2f} voxels")
    
    
    # Optionally show
    try:
        fig.show()
    except:
        print("  (Could not auto-open browser, please open the HTML file manually)")
    
    return fig#, #displacement_vectors, displacement_magnitudes, deformed_volume_path, displacement_field_path, landmarks_json_path, landmarks_fcsv_path



if __name__ == "__main__":
    # Default parameters
    sphere_path = 'GeometricTestCase/sphere.nii.gz'
    landmarks_path = 'GeometricTestCase/sphere_landmarks.json'
    deformation_type = 'compression'
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        deformation_type = sys.argv[1]
    
    valid_types = ['compression', 'twist', 'bend', 'custom']
    if deformation_type not in valid_types:
        print(f"Error: Invalid deformation type '{deformation_type}'")
        print(f"Valid types: {', '.join(valid_types)}")
        sys.exit(1)
    

    
    # Create visualization with mesh surfaces and save deformed data
    results = displacement(
        sphere_path, 
        landmarks_path, 
        deformation_type,
        show_surface=True,              # Set to False to hide surfaces
        mesh_downsample=2,              # 1=high quality, 2=balanced, 3+=fast
        mesh_opacity=0.4,               # 0=transparent, 1=opaque
        save_deformed_volume=True,      # Set to False to skip saving deformed volume
        save_landmarks=True,            # Set to False to skip saving deformed landmarks
        save_disp_field=True            # Set to False to skip saving displacement field
    )


    
    displacement_vectors, displacement_magnitudes, deformed_path, disp_field_path, deformed_landmarks_json, deformed_landmarks_fcsv = results
    createVisualization(
        sphere_path,
        landmarks_path,
        deformed_path,
        deformed_landmarks_json,   
        disp_field_path,
        displacement_vectors,
        displacement_magnitudes, 
        deformation_type='compression',
        show_surface=True,
        mesh_downsample=1,
        mesh_opacity=0.4)
    

"""
Interactive 3D Sphere Mesh Visualization with Landmarks using Plotly
====================================================================
This script creates an interactive 3D mesh visualization of a sphere with landmarks.
The mesh provides a smoother surface representation than point clouds.

Usage:
    python plot_sphere_mesh.py

Requirements:
    - nibabel
    - plotly
    - numpy
    - scipy
    - scikit-image
"""

import numpy as np
import nibabel as nib
import plotly.graph_objects as go
import json
import sys
from scipy.ndimage import zoom
from skimage import measure


def load_sphere_and_landmarks(sphere_path, landmarks_path):
    """Load sphere image and landmarks from files"""
    sphere_img = nib.load(sphere_path)
    sphere_data = sphere_img.get_fdata()
    affine = sphere_img.affine
    
    with open(landmarks_path, 'r') as f:
        landmarks_data = json.load(f)
    
    return sphere_img, sphere_data, affine, landmarks_data


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
    # Downsample for faster processing
    sphere_downsampled = zoom(sphere_data, 1/downsample_factor, order=1)
    
    # Extract mesh using marching cubes
    print(f"  Running marching cubes on {sphere_downsampled.shape} volume...")
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
    
    print(f"  Extracted mesh: {len(verts_ras)} vertices, {len(faces)} faces")
    
    return verts_ras, faces


def create_mesh_visualization(sphere_path, landmarks_path, output_html='sphere_mesh.html', 
                             downsample_factor=2):
    """
    Create interactive 3D mesh visualization of sphere with landmarks
    
    Parameters:
    -----------
    sphere_path : str
        Path to sphere NIfTI file
    landmarks_path : str
        Path to landmarks JSON file
    output_html : str
        Output HTML filename
    downsample_factor : int
        Downsample factor for mesh extraction (higher = faster but less detail)
    """
    
    # Load data
    print("Loading data...")
    sphere_img, sphere_data, affine, landmarks_data = load_sphere_and_landmarks(
        sphere_path, landmarks_path
    )
    
    # Extract mesh surface
    print("Extracting mesh surface...")
    verts_ras, faces = extract_mesh_surface(sphere_data, affine, downsample_factor)
    
    # Prepare landmark data
    landmark_names = []
    landmark_coords = []
    for name, coords in landmarks_data['landmarks'].items():
        landmark_names.append(name)
        landmark_coords.append(coords)
    
    landmark_coords = np.array(landmark_coords)
    
    # Create Plotly figure
    print("Creating visualization...")
    fig = go.Figure()
    
    # Add mesh surface
    fig.add_trace(go.Mesh3d(
        x=verts_ras[:, 0],
        y=verts_ras[:, 1],
        z=verts_ras[:, 2],
        i=faces[:, 0],
        j=faces[:, 1],
        k=faces[:, 2],
        color='lightblue',
        opacity=0.5,
        name='Sphere Surface',
        hoverinfo='skip',
        flatshading=True,
        lighting=dict(ambient=0.5, diffuse=0.8, specular=0.2),
        lightposition=dict(x=100, y=100, z=100)
    ))
    
    # Add landmarks
    fig.add_trace(go.Scatter3d(
        x=landmark_coords[:, 0],
        y=landmark_coords[:, 1],
        z=landmark_coords[:, 2],
        mode='markers+text',
        marker=dict(
            size=8,
            color='red',
            symbol='diamond',
            line=dict(color='darkred', width=2)
        ),
        text=landmark_names,
        textposition='top center',
        textfont=dict(size=10, color='black'),
        name='Landmarks',
        hovertemplate='<b>%{text}</b><br>X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text='Interactive 3D Sphere with Surface Mesh<br><sub>Smooth surface representation with landmarks</sub>',
            x=0.5,
            xanchor='center'
        ),
        scene=dict(
            xaxis=dict(title='X (Right) [mm]', backgroundcolor="white", gridcolor="lightgray"),
            yaxis=dict(title='Y (Anterior) [mm]', backgroundcolor="white", gridcolor="lightgray"),
            zaxis=dict(title='Z (Superior) [mm]', backgroundcolor="white", gridcolor="lightgray"),
            aspectmode='data',
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.5)
            )
        ),
        width=1000,
        height=800,
        showlegend=True
    )
    
    # Save
    fig.write_html(output_html)
    print(f"\n✓ Saved mesh visualization to: {output_html}")
    print("  Open this file in a web browser to view and interact with the 3D visualization")
    
    # Optionally show in browser
    try:
        fig.show()
    except:
        print("  (Could not auto-open browser, please open the HTML file manually)")
    
    return fig


if __name__ == "__main__":
    # Default paths
    sphere_path = 'GeometricTestCase/sphere_deformed_compression.nii.gz'
    landmarks_path = 'GeometricTestCase/sphere_landmarks_deformed_compression.json'
    output_html = 'GeometricTestCase/sphere_mesh_deformed.html'
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        sphere_path = sys.argv[1]
    if len(sys.argv) > 2:
        landmarks_path = sys.argv[2]
    if len(sys.argv) > 3:
        output_html = sys.argv[3]
    
    print("="*70)
    print("INTERACTIVE SPHERE MESH VISUALIZATION")
    print("="*70)
    print(f"Sphere: {sphere_path}")
    print(f"Landmarks: {landmarks_path}")
    print(f"Output: {output_html}")
    print("="*70)
    
    # Create visualization
    fig = create_mesh_visualization(sphere_path, landmarks_path)
    
    print("="*70)
    print("DONE!")
    print("="*70)
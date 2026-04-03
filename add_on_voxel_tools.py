bl_info = {
    "name": "Voxel Gen Tools",
    "author": "Riva Verma",
    "version": (0, 3, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar (N) > Voxel Gen Tools",
    "description": "Generate and smooth voxel meshes from .npy arrays",
    "category": "Object",
}

import bpy
import os
import numpy as np


# -----------------------------
# Helpers
# -----------------------------

def _parse_npy_stem(filepath):
    """
    Extracts organelle + cell suffix from a mask filename.
    e.g. Binary_Mask_vesicles_cell1.npy  ->  'vesicles_cell1'
         Norm_LAC_Value_Mask_mito_cell3.npy -> 'mito_cell3'
    Returns None if pattern not found.
    """
    stem = os.path.splitext(os.path.basename(filepath))[0]  # strip .npy
    lower = stem.lower()
    # find 'mask_' and take everything after it
    idx = lower.find("mask_")
    if idx == -1:
        return None
    return stem[idx + 5:]  # everything after 'mask_'


def _get_cloud_obj(context, settings):
    """
    Returns the Cloud object to operate on.
    Tries the stored object name first, then falls back to active object.
    """
    obj = bpy.data.objects.get(settings.object_name)
    if obj is not None:
        return obj
    # fallback: active object
    active = context.view_layer.objects.active
    if active is not None:
        return active
    return None


def _get_smooth_obj(context, settings):
    """
    Returns the Smooth object to operate on.
    Tries stored smooth name first, then falls back to active object.
    """
    obj = bpy.data.objects.get(settings.smooth_name)
    if obj is not None:
        return obj
    active = context.view_layer.objects.active
    if active is not None:
        return active
    return None


# -----------------------------
# Properties
# -----------------------------

class VOXELTOOLS_PG_Settings(bpy.types.PropertyGroup):

    mask_path: bpy.props.StringProperty(
        name="Binary Mask (.npy)",
        description="Path to the binary segmentation mask .npy file",
        subtype='FILE_PATH',
        default=""
    )
    param_path: bpy.props.StringProperty(
        name="Param Mask (.npy)",
        description="Path to the normalized parameter values .npy file",
        subtype='FILE_PATH',
        default=""
    )
    attribute_name: bpy.props.StringProperty(
        name="Attribute Name",
        description="Name of the vertex/point attribute to store values — auto-filled from filename",
        default="param"
    )
    object_name: bpy.props.StringProperty(
        name="Object Name",
        description="Name for the generated Cloud object — auto-filled from filename",
        default="Cloud"
    )
    smooth_name: bpy.props.StringProperty(
        name="",
        description="Internal: name of the Smooth object for this generation",
        default="Smooth"
    )
    material_name: bpy.props.StringProperty(
        name="Material Name",
        description="Name of the material assigned to the voxel mesh",
        default="Voxel_Map"
    )
    voxel_amount: bpy.props.IntProperty(
        name="Voxel Amount",
        description="Resolution of the volume grid (higher = smoother but heavier)",
        default=512,
        min=16,
        max=2048
    )
    voxel_radius: bpy.props.FloatProperty(
        name="Radius",
        description="Radius for converting points into volume (affects smoothness)",
        default=1.0,
        min=0.1,
        max=10.0
    )
    subdivide_levels: bpy.props.IntProperty(
        name="Subdivision Levels",
        description="Number of subdivision levels — keep at 1 to avoid overloading",
        default=1,
        min=1,
        max=3
    )
    use_active_for_smooth: bpy.props.BoolProperty(
        name="Smooth Active Object",
        description="If on, smooth operates on the active selected object instead of the stored name",
        default=False
    )
    use_active_for_subdivide: bpy.props.BoolProperty(
        name="Subdivide Active Object",
        description="If on, subdivide operates on the active selected object instead of the stored name",
        default=False
    )


# ----------------------------------
# Operator: auto-fill names from path
# ----------------------------------

class VOXELTOOLS_OT_AutoFill(bpy.types.Operator):
    bl_idname = "voxeltools.autofill"
    bl_label = "Auto-fill from Filename"
    bl_description = "Fill Object Name and Attribute Name from the mask filename"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.voxeltools_settings
        path = bpy.path.abspath(s.mask_path) if s.mask_path else ""
        stem = _parse_npy_stem(path)
        if stem is None:
            self.report({'WARNING'}, "Could not parse name from filename. Fill manually.")
            return {'CANCELLED'}
        # extract organelle part — everything before '_cell'
        parts = stem.rsplit("_cell", 1)
        organelle = parts[0] if len(parts) > 1 else stem

        s.object_name    = f"Cloud_{stem}"
        s.smooth_name    = f"Smooth_{stem}"
        s.attribute_name = f"param_{stem}"
        s.material_name  = f"Voxel_Map_{organelle}"
        self.report({'INFO'}, f"Set names from '{stem}' | material: Voxel_Map_{organelle}")
        return {'FINISHED'}


# -----------------------------
# Operator: Generate
# -----------------------------

class VOXELTOOLS_OT_Generate(bpy.types.Operator):
    bl_idname = "voxeltools.generate"
    bl_label = "Generate Voxel Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.voxeltools_settings

        mask_path  = bpy.path.abspath(s.mask_path)  if s.mask_path  else ""
        param_path = bpy.path.abspath(s.param_path) if s.param_path else ""
        attr_name  = s.attribute_name.strip()
        obj_name   = s.object_name.strip() or "Cloud"
        mat_name   = s.material_name.strip() or "Voxel_Map"

        # ---- validate
        if not mask_path or not os.path.isfile(mask_path):
            self.report({'ERROR'}, "Invalid or missing Binary Mask .npy path.")
            return {'CANCELLED'}
        if not param_path or not os.path.isfile(param_path):
            self.report({'ERROR'}, "Invalid or missing Param Mask .npy path.")
            return {'CANCELLED'}
        if not attr_name:
            self.report({'ERROR'}, "Attribute Name cannot be empty.")
            return {'CANCELLED'}

        try:
            # ---- load arrays
            param = np.load(param_path)
            param = np.transpose(param, (2, 1, 0))
            mask  = np.load(mask_path)
            mask  = np.transpose(mask, (2, 1, 0))
            dims  = mask.shape

            coords = np.argwhere(mask > 0)

            # ---- create mesh object
            mesh = bpy.data.meshes.new(obj_name)
            obj  = bpy.data.objects.new(obj_name, mesh)

            # store smooth name for later operators
            s.smooth_name = f"Smooth_{obj_name[6:]}" if obj_name.startswith("Cloud_") else f"Smooth_{obj_name}"

            # ---- place in collection
            coll_name  = "Voxel Gen Output"
            collection = bpy.data.collections.get(coll_name)
            if collection is None:
                collection = bpy.data.collections.new(coll_name)
                context.scene.collection.children.link(collection)
            collection.objects.link(obj)

            # ---- build point cloud
            verts = [tuple(coord) for coord in coords]
            mesh.from_pydata(verts, [], [])
            mesh.update()

            # ---- color attribute — always create fresh to avoid naming collisions
            if attr_name in mesh.color_attributes:
                mesh.color_attributes.remove(mesh.color_attributes[attr_name])
            vcol   = mesh.color_attributes.new(name=attr_name, type="FLOAT_COLOR", domain="POINT")
            colors = vcol.data

            for i, vert in enumerate(mesh.vertices):
                x, y, z = map(lambda v: int(round(v)), vert.co)
                if 0 <= x < dims[0] and 0 <= y < dims[1] and 0 <= z < dims[2]:
                    if mask[x, y, z] > 0:
                        val = float(param[x, y, z])
                        colors[i].color = (val, val, val, 1.0)
                    else:
                        colors[i].color = (0.0, 0.0, 0.0, 0.0)

            # ---- geometry nodes
            ng_name = "Voxel_Instances"
            if ng_name in bpy.data.node_groups:
                ng = bpy.data.node_groups[ng_name]
            else:
                ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')

            ng.nodes.clear()
            nodes = ng.nodes
            links = ng.links

            input_node        = nodes.new("NodeGroupInput")
            output_node       = nodes.new("NodeGroupOutput")
            ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
            ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

            mesh_to_points    = nodes.new("GeometryNodeMeshToPoints")
            instance_on_pts   = nodes.new("GeometryNodeInstanceOnPoints")
            realize           = nodes.new("GeometryNodeRealizeInstances")
            set_mat           = nodes.new("GeometryNodeSetMaterial")
            cube_primitive    = nodes.new("GeometryNodeMeshCube")

            input_node.location     = (-800, 0)
            mesh_to_points.location = (-600, 0)
            instance_on_pts.location = (-400, 0)
            realize.location        = (-200, 0)
            set_mat.location        = (0, 0)
            output_node.location    = (200, 0)
            cube_primitive.location = (-400, -200)

            links.new(input_node.outputs["Geometry"],          mesh_to_points.inputs["Mesh"])
            links.new(mesh_to_points.outputs["Points"],        instance_on_pts.inputs["Points"])
            links.new(cube_primitive.outputs["Mesh"],          instance_on_pts.inputs["Instance"])
            links.new(instance_on_pts.outputs["Instances"],    realize.inputs["Geometry"])
            links.new(realize.outputs["Geometry"],             set_mat.inputs["Geometry"])
            links.new(set_mat.outputs["Geometry"],             output_node.inputs["Geometry"])

            # ---- material — update attribute name if exists, else create fresh
            if mat_name in bpy.data.materials:
                mat        = bpy.data.materials[mat_name]
                attr_nodes = [n for n in mat.node_tree.nodes if n.type == 'ATTRIBUTE']
                if attr_nodes:
                    attr_nodes[0].attribute_name = attr_name
            else:
                mat            = bpy.data.materials.new(mat_name)
                mat.use_nodes  = True
                mnodes         = mat.node_tree.nodes
                mlinks         = mat.node_tree.links
                mnodes.clear()

                out_node = mnodes.new("ShaderNodeOutputMaterial")
                bsdf     = mnodes.new("ShaderNodeBsdfPrincipled")
                colramp  = mnodes.new("ShaderNodeValToRGB")
                attr     = mnodes.new("ShaderNodeAttribute")

                attr.attribute_name = attr_name
                attr.location     = (-600, 0)
                colramp.location  = (-400, 0)
                bsdf.location     = (-200, 0)
                out_node.location = (0, 0)

                mlinks.new(attr.outputs["Fac"],       colramp.inputs["Fac"])
                mlinks.new(colramp.outputs["Color"],  bsdf.inputs["Base Color"])
                mlinks.new(bsdf.outputs["BSDF"],      out_node.inputs["Surface"])

            set_mat.inputs["Material"].default_value = mat

            # ---- attach geo nodes modifier
            mod            = obj.modifiers.new(name="VoxelGeoNodes", type='NODES')
            mod.node_group = ng

            # ---- assign material directly to object so it shows without smoothing
            if mat.name not in [m.name for m in obj.data.materials]:
                obj.data.materials.append(mat)

            self.report({'INFO'}, f"Generated '{obj_name}' with attribute '{attr_name}'")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Generation failed: {e}")
            return {'CANCELLED'}


# -----------------------------
# Operator: Smooth
# -----------------------------

class VOXELTOOLS_OT_Smooth(bpy.types.Operator):
    bl_idname = "voxeltools.smooth"
    bl_label = "Smooth Voxel Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s         = context.scene.voxeltools_settings
        attr_name = s.attribute_name.strip()

        # ---- find source object
        if s.use_active_for_smooth:
            cloud_obj = context.view_layer.objects.active
            if cloud_obj is None:
                self.report({'ERROR'}, "No active object selected.")
                return {'CANCELLED'}
        else:
            cloud_obj = bpy.data.objects.get(s.object_name)
            if cloud_obj is None:
                self.report({'ERROR'}, f"Object '{s.object_name}' not found. Enable 'Smooth Active Object' or check the name.")
                return {'CANCELLED'}

        smooth_name = s.smooth_name or f"Smooth_{cloud_obj.name}"

        # ---- remove old smooth object if present
        old_smooth = bpy.data.objects.get(smooth_name)
        if old_smooth:
            bpy.data.objects.remove(old_smooth, do_unlink=True)

        # ---- duplicate cloud -> smooth
        smooth_obj      = cloud_obj.copy()
        smooth_obj.data = cloud_obj.data.copy()
        smooth_obj.name = smooth_name

        coll_name  = "Voxel Gen Output"
        collection = bpy.data.collections.get(coll_name)
        if collection is None:
            collection = bpy.data.collections.new(coll_name)
            context.scene.collection.children.link(collection)
        collection.objects.link(smooth_obj)

        # ---- apply instancing modifier
        for mod in list(smooth_obj.modifiers):
            if mod.type == 'NODES' and mod.name == "VoxelGeoNodes":
                context.view_layer.objects.active = smooth_obj
                bpy.ops.object.modifier_apply(modifier=mod.name)

        for mod in list(smooth_obj.modifiers):
            smooth_obj.modifiers.remove(mod)

        # ---- smooth geo nodes
        ng_name = "Voxel_Smooth"
        if ng_name in bpy.data.node_groups:
            ng = bpy.data.node_groups[ng_name]
        else:
            ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')
            ng.nodes.clear()
            nodes = ng.nodes
            links = ng.links

            input_node  = nodes.new("NodeGroupInput")
            output_node = nodes.new("NodeGroupOutput")
            ng.interface.new_socket("Geometry", in_out='INPUT',  socket_type='NodeSocketGeometry')
            ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

            mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
            pts_to_vol     = nodes.new("GeometryNodePointsToVolume")
            vol_to_mesh    = nodes.new("GeometryNodeVolumeToMesh")

            input_node.location     = (-800, 0)
            mesh_to_points.location = (-600, 0)
            pts_to_vol.location     = (-400, 0)
            vol_to_mesh.location    = (-200, 0)
            output_node.location    = (0, 0)

            pts_to_vol.inputs["Voxel Amount"].default_value = s.voxel_amount
            pts_to_vol.inputs["Radius"].default_value       = s.voxel_radius

            links.new(input_node.outputs["Geometry"],    mesh_to_points.inputs["Mesh"])
            links.new(mesh_to_points.outputs["Points"],  pts_to_vol.inputs["Points"])
            links.new(pts_to_vol.outputs["Volume"],      vol_to_mesh.inputs["Volume"])
            links.new(vol_to_mesh.outputs["Mesh"],       output_node.inputs["Geometry"])

        # update smoothing params every run
        for node in ng.nodes:
            if node.type == "POINTS_TO_VOLUME":
                node.inputs["Voxel Amount"].default_value = s.voxel_amount
                node.inputs["Radius"].default_value       = s.voxel_radius

        mod            = smooth_obj.modifiers.new(name="SmoothGeoNodes", type='NODES')
        mod.node_group = ng

        context.view_layer.objects.active = smooth_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

        # ---- KD-tree attribute transfer
        source = cloud_obj.data
        target = smooth_obj.data

        if attr_name not in source.color_attributes:
            self.report({'ERROR'}, f"Attribute '{attr_name}' not found on '{cloud_obj.name}'.")
            return {'CANCELLED'}

        src_attr = source.color_attributes[attr_name]

        from mathutils import kdtree, Vector
        kd = kdtree.KDTree(len(source.vertices))
        for i, v in enumerate(source.vertices):
            kd.insert(cloud_obj.matrix_world @ v.co, i)
        kd.balance()

        if attr_name not in target.color_attributes:
            target.color_attributes.new(name=attr_name, type='FLOAT_COLOR', domain='POINT')
        tar_attr   = target.color_attributes[attr_name]
        src_colors = [Vector(src_attr.data[i].color) for i in range(len(source.vertices))]

        for i, v in enumerate(target.vertices):
            _, nearest_idx, _ = kd.find(smooth_obj.matrix_world @ v.co)
            tar_attr.data[i].color = src_colors[nearest_idx]

        target.update()

        # ---- reassign material
        smooth_obj.data.materials.clear()
        mat = bpy.data.materials.get(s.material_name)
        if mat:
            smooth_obj.data.materials.append(mat)

        self.report({'INFO'}, f"Smoothed mesh '{smooth_name}' created from '{cloud_obj.name}'")
        return {'FINISHED'}


# -----------------------------
# Operator: Subdivide
# -----------------------------

class VOXELTOOLS_OT_Subdivide(bpy.types.Operator):
    bl_idname = "voxeltools.subdivide"
    bl_label = "Subdivide Voxel Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.voxeltools_settings

        if s.use_active_for_subdivide:
            smooth_obj = context.view_layer.objects.active
            if smooth_obj is None:
                self.report({'ERROR'}, "No active object selected.")
                return {'CANCELLED'}
        else:
            smooth_obj = bpy.data.objects.get(s.smooth_name)
            if smooth_obj is None:
                self.report({'ERROR'}, f"Object '{s.smooth_name}' not found. Enable 'Subdivide Active Object' or check the name.")
                return {'CANCELLED'}

        levels     = s.subdivide_levels
        subdiv_mod = smooth_obj.modifiers.new(name="Subdiv", type='SUBSURF')
        subdiv_mod.levels        = levels
        subdiv_mod.render_levels = levels

        context.view_layer.objects.active = smooth_obj
        bpy.ops.object.modifier_apply(modifier=subdiv_mod.name)

        self.report({'INFO'}, f"Subdivided '{smooth_obj.name}' by {levels} level(s)")
        return {'FINISHED'}


# -----------------------------
# UI Panel
# -----------------------------

class VOXELTOOLS_PT_Panel(bpy.types.Panel):
    bl_label = "Voxel Gen Tools"
    bl_idname = "VOXELTOOLS_PT_panel"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "Voxel Gen Tools"

    def draw(self, context):
        layout = self.layout
        s      = context.scene.voxeltools_settings

        # ---- Step 1: File Inputs
        box = layout.box()
        box.label(text="Step 1: File Inputs", icon='FILE_FOLDER')
        box.prop(s, "mask_path")
        box.prop(s, "param_path")
        box.operator("voxeltools.autofill", icon='EYEDROPPER')

        layout.separator()

        # ---- Step 2: Generate
        box2 = layout.box()
        box2.label(text="Step 2: Generate", icon='MESH_CUBE')
        box2.prop(s, "object_name")
        box2.prop(s, "attribute_name")
        box2.prop(s, "material_name")
        box2.operator("voxeltools.generate", icon='MESH_CUBE')

        layout.separator()

        # ---- Step 3: Smooth
        box3 = layout.box()
        box3.label(text="Step 3: Smooth", icon='MOD_SMOOTH')
        box3.prop(s, "voxel_amount")
        box3.prop(s, "voxel_radius")
        box3.prop(s, "use_active_for_smooth")
        box3.operator("voxeltools.smooth", icon='MOD_SMOOTH')

        layout.separator()

        # ---- Step 4: Subdivide
        box4 = layout.box()
        box4.label(text="Step 4: Subdivide (optional)", icon='MOD_SUBSURF')
        box4.prop(s, "subdivide_levels")
        box4.prop(s, "use_active_for_subdivide")
        box4.operator("voxeltools.subdivide", icon='MOD_SUBSURF')


# -----------------------------
# Registration
# -----------------------------

classes = (
    VOXELTOOLS_PG_Settings,
    VOXELTOOLS_OT_AutoFill,
    VOXELTOOLS_OT_Generate,
    VOXELTOOLS_OT_Smooth,
    VOXELTOOLS_OT_Subdivide,
    VOXELTOOLS_PT_Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.voxeltools_settings = bpy.props.PointerProperty(type=VOXELTOOLS_PG_Settings)

def unregister():
    del bpy.types.Scene.voxeltools_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
bl_info = {
    "name": "Voxel Tools",
    "author": "Riva Verma",
    "version": (0, 2, 0),
    "blender": (4, 3, 2),
    "location": "View3D > Sidebar (N) > Voxel Tools",
    "description": "Generate and smooth voxel meshes from .npy arrays (Step 2: Generation logic)",
    "category": "Object",
}

import bpy
import os
import numpy as np

# -----------------------------
# Properties
# -----------------------------
class VOXELTOOLS_PG_Settings(bpy.types.PropertyGroup):
    lac_path: bpy.props.StringProperty(
        name="Param File Path",
        description="Path to the .npy file containing color/scalar values",
        subtype='FILE_PATH',
        default=""
    )
    mask_path: bpy.props.StringProperty(
        name="Mask File Path",
        description="Path to the .npy file containing binary/selection mask",
        subtype='FILE_PATH',
        default=""
    )
    attribute_name: bpy.props.StringProperty(
        name="Attribute Name",
        description="Name of the vertex/point attribute to store values (e.g., lac_ves)",
        default="lac_ves"
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



# -----------------------------
# Operators
# -----------------------------
class VOXELTOOLS_OT_Generate(bpy.types.Operator):
    bl_idname = "voxeltools.generate"
    bl_label = "Generate Voxel Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.voxeltools_settings

        lac_path = bpy.path.abspath(s.lac_path) if s.lac_path else ""
        mask_path = bpy.path.abspath(s.mask_path) if s.mask_path else ""
        attr_name = s.attribute_name.strip()

        if not lac_path or not os.path.isfile(lac_path):
            self.report({'ERROR'}, "Invalid or missing Param .npy path.")
            return {'CANCELLED'}

        if not mask_path or not os.path.isfile(mask_path):
            self.report({'ERROR'}, "Invalid or missing Mask .npy path.")
            return {'CANCELLED'}

        if not attr_name:
            self.report({'ERROR'}, "Attribute Name cannot be empty.")
            return {'CANCELLED'}

        # ---------------------
        # Actual Generation
        # ---------------------
        try:
            lac = np.load(lac_path)
            lac = np.transpose(lac, (2, 1, 0))
            mask = np.load(mask_path)
            mask = np.transpose(mask, (2, 1, 0))
            dims = mask.shape

            coords = np.argwhere(mask > 0)

            mesh = bpy.data.meshes.new("Cloud")
            obj = bpy.data.objects.new("Cloud", mesh)

            # Place object in dedicated collection
            coll_name = "Voxel Gen Output"
            collection = bpy.data.collections.get(coll_name)
            if collection is None:
                collection = bpy.data.collections.new(coll_name)
                context.scene.collection.children.link(collection)
            collection.objects.link(obj)

            verts = [tuple(coord) for coord in coords]
            mesh.from_pydata(verts, [], [])
            mesh.update()

            if attr_name not in mesh.color_attributes:
                vcol = mesh.color_attributes.new(name=attr_name, type="FLOAT_COLOR", domain="POINT")
            else:
                vcol = mesh.color_attributes[attr_name]

            colors = vcol.data

            for i, vert in enumerate(mesh.vertices):
                x, y, z = map(lambda v: int(round(v)), vert.co)
                if 0 <= x < dims[0] and 0 <= y < dims[1] and 0 <= z < dims[2]:
                    if mask[x, y, z] > 0:
                        val = float(lac[x, y, z])
                        colors[i].color = (val, val, val, 1.0)
                    else:
                        colors[i].color = (0.0, 0.0, 0.0, 0.0)

            ng_name = "Voxel_Instances"
            if ng_name in bpy.data.node_groups:
                ng = bpy.data.node_groups[ng_name]
            else:
                ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')

            # Clear nodes
            ng.nodes.clear()
            nodes = ng.nodes
            links = ng.links

            # Core nodes
            input_node = nodes.new("NodeGroupInput")
            output_node = nodes.new("NodeGroupOutput")
            ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
            ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

            mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
            instance_on_points = nodes.new("GeometryNodeInstanceOnPoints")
            realize = nodes.new("GeometryNodeRealizeInstances")
            set_mat = nodes.new("GeometryNodeSetMaterial")
            cube_primitive = nodes.new("GeometryNodeMeshCube")

            # Layout
            input_node.location = (-800, 0)
            mesh_to_points.location = (-600, 0)
            instance_on_points.location = (-400, 0)
            realize.location = (-200, 0)
            set_mat.location = (0, 0)
            output_node.location = (200, 0)
            cube_primitive.location = (-400, -200)

            # Links
            links.new(input_node.outputs["Geometry"], mesh_to_points.inputs["Mesh"])
            links.new(mesh_to_points.outputs["Points"], instance_on_points.inputs["Points"])
            links.new(cube_primitive.outputs["Mesh"], instance_on_points.inputs["Instance"])
            links.new(instance_on_points.outputs["Instances"], realize.inputs["Geometry"])
            links.new(realize.outputs["Geometry"], set_mat.inputs["Geometry"])
            links.new(set_mat.outputs["Geometry"], output_node.inputs["Geometry"])

            mat_name = "Voxel_Map"
            if mat_name in bpy.data.materials:
                mat = bpy.data.materials[mat_name]
                attr_nodes = [n for n in mat.node_tree.nodes if n.type == 'ATTRIBUTE']
                if attr_nodes:
                    attr_nodes[0].attribute_name = attr_name

            else:
                mat = bpy.data.materials.new(mat_name)
                mat.use_nodes = True

                nodes = mat.node_tree.nodes
                links = mat.node_tree.links

                # Clear old nodes
                nodes.clear()

                # Create nodes
                out_node = nodes.new("ShaderNodeOutputMaterial")
                bsdf = nodes.new("ShaderNodeBsdfPrincipled")
                colramp = nodes.new("ShaderNodeValToRGB")
                attr = nodes.new("ShaderNodeAttribute")

                # Set attribute name dynamically
                attr.attribute_name = attr_name

                # Position nodes
                attr.location = (-600, 0)
                colramp.location = (-400, 0)
                bsdf.location = (-200, 0)
                out_node.location = (0, 0)

                # Links
                links.new(attr.outputs["Fac"], colramp.inputs["Fac"])
                links.new(colramp.outputs["Color"], bsdf.inputs["Base Color"])
                links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])

            set_mat.inputs["Material"].default_value = mat

            # Attach modifier to the mesh
            mod = obj.modifiers.new(name="VoxelGeoNodes", type='NODES')
            mod.node_group = ng

            self.report({'INFO'}, f"Generated voxel mesh with attribute '{attr_name}'")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Generation failed: {e}")
            return {'CANCELLED'}

class VOXELTOOLS_OT_Smooth(bpy.types.Operator):
    bl_idname = "voxeltools.smooth"
    bl_label = "Smooth Voxel Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.voxeltools_settings
        attr_name = s.attribute_name.strip()

        # Always use the original Cloud object
        cloud_obj = bpy.data.objects.get("Cloud")
        if cloud_obj is None:
            self.report({'ERROR'}, "No 'Cloud' object found. Run Generate first.")
            return {'CANCELLED'}

        # Delete existing Smooth object if present
        old_smooth = bpy.data.objects.get("Smooth")
        if old_smooth:
            bpy.data.objects.remove(old_smooth, do_unlink=True)

        # Duplicate Cloud → Smooth
        smooth_obj = cloud_obj.copy()
        smooth_obj.data = cloud_obj.data.copy()
        smooth_obj.name = "Smooth"

        # Place object in dedicated collection
        coll_name = "Voxel Gen Output"
        collection = bpy.data.collections.get(coll_name)
        if collection is None:
            collection = bpy.data.collections.new(coll_name)
            context.scene.collection.children.link(collection)
        collection.objects.link(smooth_obj)

        # Apply the instancing modifier if it exists
        for mod in list(smooth_obj.modifiers):
            if mod.type == 'NODES' and mod.name == "VoxelGeoNodes":
                bpy.context.view_layer.objects.active = smooth_obj
                bpy.ops.object.modifier_apply(modifier=mod.name)

        # Now remove any extra modifiers
        for mod in list(smooth_obj.modifiers):
            smooth_obj.modifiers.remove(mod)

        # Create or reuse GN node group
        ng_name = "Voxel_Smooth"
        if ng_name in bpy.data.node_groups:
            ng = bpy.data.node_groups[ng_name]
        else:
            ng = bpy.data.node_groups.new(ng_name, 'GeometryNodeTree')
            ng.nodes.clear()
            nodes = ng.nodes
            links = ng.links

            input_node = nodes.new("NodeGroupInput")
            output_node = nodes.new("NodeGroupOutput")
            ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
            ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

            mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
            pts_to_vol = nodes.new("GeometryNodePointsToVolume")
            vol_to_mesh = nodes.new("GeometryNodeVolumeToMesh")

            # Layout
            input_node.location = (-800, 0)
            mesh_to_points.location = (-600, 0)
            pts_to_vol.location = (-400, 0)
            vol_to_mesh.location = (-200, 0)
            output_node.location = (0, 0)

            # Default smoothing parameters
            pts_to_vol.inputs["Voxel Amount"].default_value = s.voxel_amount
            pts_to_vol.inputs["Radius"].default_value = s.voxel_radius

            # Links
            links.new(input_node.outputs["Geometry"], mesh_to_points.inputs["Mesh"])
            links.new(mesh_to_points.outputs["Points"], pts_to_vol.inputs["Points"])
            links.new(pts_to_vol.outputs["Volume"], vol_to_mesh.inputs["Volume"])
            links.new(vol_to_mesh.outputs["Mesh"], output_node.inputs["Geometry"])

        # Attach modifier
        mod = smooth_obj.modifiers.new(name="SmoothGeoNodes", type='NODES')
        mod.node_group = ng
        # Attach modifier

        # Update node group input defaults (ensures UI changes apply every time)
        for node in ng.nodes:
            if node.type == "POINTS_TO_VOLUME":
                node.inputs["Voxel Amount"].default_value = s.voxel_amount
                node.inputs["Radius"].default_value = s.voxel_radius

        # Apply modifier to bake geometry
        bpy.context.view_layer.objects.active = smooth_obj
        bpy.ops.object.modifier_apply(modifier=mod.name)

        # --- KD-tree transfer of attributes
        source = cloud_obj.data
        target = smooth_obj.data

        if attr_name not in source.color_attributes:
            self.report({'ERROR'}, f"Attribute '{attr_name}' not found on Cloud.")
            return {'CANCELLED'}

        src_attr = source.color_attributes[attr_name]

        # build KD-tree
        from mathutils import kdtree, Vector
        kd = kdtree.KDTree(len(source.vertices))
        for i, v in enumerate(source.vertices):
            world_pos = cloud_obj.matrix_world @ v.co
            kd.insert(world_pos, i)
        kd.balance()

        # prepare target attribute
        if attr_name not in target.color_attributes:
            target.color_attributes.new(name=attr_name, type='FLOAT_COLOR', domain='POINT')
        tar_attr = target.color_attributes[attr_name]

        src_colors = [Vector(src_attr.data[i].color) for i in range(len(source.vertices))]

        for i, v in enumerate(target.vertices):
            world_pos2 = smooth_obj.matrix_world @ v.co
            _, nearest_idx, _ = kd.find(world_pos2)
            tar_attr.data[i].color = src_colors[nearest_idx]

        target.update()

        # reassign material
        smooth_obj.data.materials.clear()
        mat = bpy.data.materials.get("Voxel_Map")
        if mat and mat.name not in smooth_obj.data.materials:
            smooth_obj.data.materials.append(mat)

        self.report({'INFO'}, f"Smoothed mesh created from original 'Cloud' with attribute '{attr_name}'")
        return {'FINISHED'}
    
class VOXELTOOLS_OT_Subdivide(bpy.types.Operator):
    bl_idname = "voxeltools.subdivide"
    bl_label = "Subdivide Voxel Mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        smooth_obj = bpy.data.objects.get("Smooth")
        if smooth_obj is None:
            self.report({'ERROR'}, "No 'Smooth' object found. Run Smooth first.")
            return {'CANCELLED'}

        # Add and apply subdivision modifier (1 level)
        subdiv_mod = smooth_obj.modifiers.new(name="Subdiv", type='SUBSURF')
        subdiv_mod.levels = 1
        subdiv_mod.render_levels = 1

        bpy.context.view_layer.objects.active = smooth_obj
        bpy.ops.object.modifier_apply(modifier=subdiv_mod.name)

        self.report({'INFO'}, "Subdivided 'Smooth' mesh by 1 level")
        return {'FINISHED'}


# -----------------------------
# UI Panel
# -----------------------------

class VOXELTOOLS_PT_Panel(bpy.types.Panel):
    bl_label = "Voxel Gen Tools"
    bl_idname = "VOXELTOOLS_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Voxel Gen Tools"

    def draw(self, context):
        layout = self.layout
        s = context.scene.voxeltools_settings

        box = layout.box()
        box.label(text="File Inputs")
        box.prop(s, "lac_path")
        box.prop(s, "mask_path")

        layout.separator()

        box2 = layout.box()
        box2.label(text="Generation")
        box2.prop(s, "attribute_name")
        box2.operator("voxeltools.generate", icon='MESH_CUBE')

        layout.separator()

        box3 = layout.box()
        box3.label(text="Smoothening")
        box3.prop(s, "voxel_amount")
        box3.prop(s, "voxel_radius")
        box3.operator("voxeltools.smooth", icon='MOD_SMOOTH')
        box3.operator("voxeltools.subdivide", icon='MOD_SUBSURF')


# -----------------------------
# Registration
# -----------------------------
classes = (
    VOXELTOOLS_PG_Settings,
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
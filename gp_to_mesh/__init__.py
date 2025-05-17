bl_info = {
    "name": "GP to Mesh",
    "author": "Eduardo - netkingZ - Bartali",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > GP to Mesh",
    "description": "Convert Grease Pencil to 3D mesh with advanced thickness and color control",
    "category": "Object",
    "warning": "Use Accurate Thickness is Experimental feature",
    "doc_url": "",
    "type": "EXTENSION"
}

import bpy


class OBJECT_OT_gp_to_enhanced_3d_mesh(bpy.types.Operator):
    """Convert Grease Pencil to 3D mesh with control over thickness and color"""
    bl_idname = "object.gp_to_enhanced_3d_mesh"
    bl_label = "Execute Conversion"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get values from panel
        scene = context.scene
        keep_original = scene.gp_keep_original
        keep_original_thickness = scene.gp_keep_original_thickness
        extrude_amount = scene.gp_extrude_amount
        keep_original_color = scene.gp_keep_original_color
        custom_color = scene.gp_custom_color
        subdivision_level = scene.gp_subdivision_level
        smooth_shading = scene.gp_smooth_shading
        use_accurate_thickness = scene.gp_use_accurate_thickness

        # Check if there's an object selected
        if not context.selected_objects:
            self.report({'ERROR'}, "No object selected")
            return {'CANCELLED'}

        # Find selected Grease Pencil objects
        gp_objects = [obj for obj in context.selected_objects if obj.type == 'GREASEPENCIL']

        if not gp_objects:
            self.report({'ERROR'}, "No Grease Pencil object selected")
            return {'CANCELLED'}

        # Process each Grease Pencil object
        converted_count = 0

        for gp_obj in gp_objects:
            original_name = gp_obj.name

            # Extract color from GP
            original_color = self.get_gp_color(gp_obj) if keep_original_color else custom_color

            # Deselect all
            bpy.ops.object.select_all(action='DESELECT')

            # Select only the current object
            gp_obj.select_set(True)
            context.view_layer.objects.active = gp_obj

            try:
                # Duplicate if necessary
                if keep_original:
                    bpy.ops.object.duplicate()
                    duplicated_obj = context.active_object
                    duplicated_obj.name = original_name + "_3D"
                else:
                    duplicated_obj = gp_obj

                # Different method for accurate thickness
                if keep_original_thickness and use_accurate_thickness:
                    # Use the simple accurate method (no bmesh, just direct conversion)
                    self.convert_with_simple_accurate_method(context, duplicated_obj)
                else:
                    # Standard method
                    # Convert to mesh
                    bpy.ops.object.convert(target='MESH')
                    mesh_obj = context.active_object

                    if mesh_obj.type != 'MESH':
                        self.report({'WARNING'}, f"Failed to convert {original_name} to mesh")
                        continue

                    # Enter Edit Mode
                    bpy.ops.object.editmode_toggle()

                    # Select all edges
                    bpy.ops.mesh.select_all(action='SELECT')

                    # Extrude edges
                    bpy.ops.mesh.extrude_region_move()

                    # Move along normals
                    # Use the original thickness or the specified value
                    thickness_value = self.get_gp_thickness(
                        duplicated_obj) if keep_original_thickness else extrude_amount
                    bpy.ops.transform.shrink_fatten(value=thickness_value, use_even_offset=True)

                    # Return to Object Mode
                    bpy.ops.object.editmode_toggle()

                # Get the active object (which should be our mesh)
                mesh_obj = context.active_object

                # Handle color
                # Create a new material with the correct color
                mat_name = f"{mesh_obj.name}_material"

                # Remove existing materials
                mesh_obj.data.materials.clear()

                # Create new material
                if mat_name in bpy.data.materials:
                    new_mat = bpy.data.materials[mat_name]
                else:
                    new_mat = bpy.data.materials.new(name=mat_name)

                new_mat.use_nodes = True

                # Set color in the material
                principled_node = new_mat.node_tree.nodes.get('Principled BSDF')
                if principled_node:
                    principled_node.inputs['Base Color'].default_value = original_color

                # Assign material to the object
                mesh_obj.data.materials.append(new_mat)

                # Add subdivision if requested
                if subdivision_level > 0:
                    # Remove any previous Subdivision modifiers
                    for mod in mesh_obj.modifiers:
                        if mod.name == "GPSubdivision":
                            mesh_obj.modifiers.remove(mod)

                    # Add new Subdivision modifier
                    subsurf_mod = mesh_obj.modifiers.new(name="GPSubdivision", type='SUBSURF')
                    subsurf_mod.levels = subdivision_level

                # Apply smooth shading if requested
                if smooth_shading:
                    bpy.ops.object.shade_smooth()
                else:
                    bpy.ops.object.shade_flat()

                converted_count += 1

            except Exception as e:
                self.report({'ERROR'}, f"Error: {str(e)}")
                import traceback
                traceback.print_exc()

        if converted_count > 0:
            self.report({'INFO'}, f"Converted {converted_count} objects to 3D mesh")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No objects were converted")
            return {'CANCELLED'}

    def convert_with_simple_accurate_method(self, context, gp_obj):
        """Simple accurate method that uses a direct approach - no BMesh, just direct conversion"""
        try:
            # Try with curve method first
            bpy.ops.object.convert(target='CURVE')
            curve_obj = context.active_object

            if curve_obj and curve_obj.type == 'CURVE':
                # Configure curve for thickness
                curve_obj.data.dimensions = '3D'
                curve_obj.data.bevel_depth = 0.05
                curve_obj.data.bevel_resolution = 4
                curve_obj.data.resolution_u = 12

                # Try to enable radius
                try:
                    curve_obj.data.use_radius = True
                except:
                    pass

                # Convert to mesh
                bpy.ops.object.convert(target='MESH')

                # Add a Displace modifier to add some imperfection
                mesh_obj = context.active_object
                if mesh_obj and mesh_obj.type == 'MESH':
                    # This will help make the mesh look more like a hand-drawn stroke
                    displace_mod = mesh_obj.modifiers.new(name="GPDisplacement", type='DISPLACE')

                    # Create a noise texture
                    noise_tex_name = f"{mesh_obj.name}_noise"
                    if noise_tex_name in bpy.data.textures:
                        noise_tex = bpy.data.textures[noise_tex_name]
                    else:
                        noise_tex = bpy.data.textures.new(name=noise_tex_name, type='CLOUDS')
                        noise_tex.noise_scale = 0.2

                    displace_mod.strength = 0.02
                    displace_mod.texture = noise_tex

                    # Add a Smooth modifier to soften the result
                    smooth_mod = mesh_obj.modifiers.new(name="GPSmooth", type='SMOOTH')
                    smooth_mod.factor = 0.5
                    smooth_mod.iterations = 2

                return True
            else:
                # If curve method fails, try direct mesh conversion
                bpy.ops.object.convert(target='MESH')

                # Apply a Solidify modifier to give volume
                mesh_obj = context.active_object
                if mesh_obj and mesh_obj.type == 'MESH':
                    solidify_mod = mesh_obj.modifiers.new(name="GPSolidify", type='SOLIDIFY')
                    solidify_mod.thickness = 0.1
                    solidify_mod.offset = 0.0

                return True

        except Exception as e:
            print(f"Error in simple accurate method: {str(e)}")

            # If everything fails, just convert to mesh
            try:
                bpy.ops.object.convert(target='MESH')
                return True
            except:
                return False

    def get_gp_thickness(self, gp_obj):
        """Extract the average thickness from the Grease Pencil"""
        thickness = 0.1  # Default value

        try:
            # Try to extract thickness from strokes
            stroke_count = 0
            total_thickness = 0

            if hasattr(gp_obj, 'data') and hasattr(gp_obj.data, 'layers'):
                for layer in gp_obj.data.layers:
                    for frame in layer.frames:
                        for stroke in frame.strokes:
                            if hasattr(stroke, 'line_width'):
                                total_thickness += stroke.line_width
                                stroke_count += 1

                if stroke_count > 0:
                    # Convert thickness from pixels to Blender units (approximated)
                    thickness = (total_thickness / stroke_count) * 0.01
        except:
            pass

        return max(thickness, 0.01)  # Ensure minimum thickness

    def get_gp_color(self, gp_obj):
        """Extract main color from Grease Pencil"""
        # Default color
        default_color = (0.8, 0.2, 0.2, 1.0)

        try:
            # Look for a material with color
            if hasattr(gp_obj, 'material_slots') and len(gp_obj.material_slots) > 0:
                for slot in gp_obj.material_slots:
                    if slot.material and hasattr(slot.material, 'grease_pencil'):
                        # Grease Pencil material
                        gp_mat = slot.material.grease_pencil
                        if hasattr(gp_mat, 'color'):
                            return (gp_mat.color[0], gp_mat.color[1], gp_mat.color[2], 1.0)

                # Try to get color from standard material
                for slot in gp_obj.material_slots:
                    if slot.material:
                        # Try to get diffuse color
                        if hasattr(slot.material, 'diffuse_color'):
                            return slot.material.diffuse_color
                        # Or try from node tree
                        elif slot.material.use_nodes:
                            for node in slot.material.node_tree.nodes:
                                if node.type == 'BSDF_PRINCIPLED':
                                    if 'Base Color' in node.inputs:
                                        return node.inputs['Base Color'].default_value
        except:
            pass

        return default_color


class VIEW3D_PT_gp_to_enhanced_3d_mesh_panel(bpy.types.Panel):
    """Panel for converting Grease Pencil to enhanced 3D mesh"""
    bl_label = "GP to Mesh"
    bl_idname = "VIEW3D_PT_gp_to_enhanced_3d_mesh_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'GP to Mesh'  # Category name

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Header
        box = layout.box()
        box.label(text="Convert GP to 3D Mesh")
        box.label(text="1. Select Grease Pencil object")
        box.label(text="2. Configure options below")
        box.label(text="3. Click Execute Conversion")

        # Base section
        box = layout.box()
        box.label(text="Base Options")
        box.prop(scene, "gp_keep_original")

        # Thickness options
        box = layout.box()
        box.label(text="Thickness Options")
        box.prop(scene, "gp_keep_original_thickness")

        if scene.gp_keep_original_thickness:
            box.prop(scene, "gp_use_accurate_thickness")
            if scene.gp_use_accurate_thickness:
                box.label(text="Warning: Experimental feature", icon='ERROR')
        else:
            box.prop(scene, "gp_extrude_amount")

        # Color section
        box = layout.box()
        box.label(text="Color")
        box.prop(scene, "gp_keep_original_color")
        col = box.column()
        col.enabled = not scene.gp_keep_original_color
        col.prop(scene, "gp_custom_color")

        # Quality section
        box = layout.box()
        box.label(text="Quality")
        box.prop(scene, "gp_subdivision_level")
        box.prop(scene, "gp_smooth_shading")

        # Operator button
        row = layout.row(align=True)
        row.scale_y = 1.5
        row.operator("object.gp_to_enhanced_3d_mesh", text="Execute Conversion", icon='MESH_DATA')


# Scene property definitions
def register_properties():
    bpy.types.Scene.gp_keep_original = bpy.props.BoolProperty(
        name="Keep Original GP",
        description="Keep the original Grease Pencil object",
        default=True
    )

    bpy.types.Scene.gp_keep_original_thickness = bpy.props.BoolProperty(
        name="Keep Original Thickness",
        description="Preserve the original thickness of the Grease Pencil",
        default=True
    )

    bpy.types.Scene.gp_use_accurate_thickness = bpy.props.BoolProperty(
        name="Use Accurate Thickness",
        description="Experimental feature to better preserve stroke appearance",
        default=False
    )

    bpy.types.Scene.gp_extrude_amount = bpy.props.FloatProperty(
        name="Custom Thickness",
        description="Extrusion thickness (used only if 'Keep Original Thickness' is disabled)",
        default=0.1,
        min=0.01,
        max=1.0
    )

    bpy.types.Scene.gp_keep_original_color = bpy.props.BoolProperty(
        name="Keep Original Color",
        description="Preserve the original color of the Grease Pencil",
        default=True
    )

    bpy.types.Scene.gp_custom_color = bpy.props.FloatVectorProperty(
        name="Custom Color",
        description="Custom color for the resulting mesh",
        subtype='COLOR',
        default=(0.8, 0.2, 0.2, 1.0),
        size=4,
        min=0.0,
        max=1.0
    )

    bpy.types.Scene.gp_subdivision_level = bpy.props.IntProperty(
        name="Subdivision",
        description="Subdivision level for smoothing the mesh",
        default=1,
        min=0,
        max=4
    )

    bpy.types.Scene.gp_smooth_shading = bpy.props.BoolProperty(
        name="Smooth Shading",
        description="Apply smooth shading to the mesh",
        default=True
    )


def unregister_properties():
    del bpy.types.Scene.gp_keep_original
    del bpy.types.Scene.gp_keep_original_thickness
    del bpy.types.Scene.gp_use_accurate_thickness
    del bpy.types.Scene.gp_extrude_amount
    del bpy.types.Scene.gp_keep_original_color
    del bpy.types.Scene.gp_custom_color
    del bpy.types.Scene.gp_subdivision_level
    del bpy.types.Scene.gp_smooth_shading


# Registration
classes = (
    OBJECT_OT_gp_to_enhanced_3d_mesh,
    VIEW3D_PT_gp_to_enhanced_3d_mesh_panel,
)


def register():
    register_properties()
    for cls in classes:
        bpy.utils.register_class(cls)
    print("GP to Mesh add-on registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_properties()


if __name__ == "__main__":
    register()
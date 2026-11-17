"""Run in Blender's Text Editor to build editable Hopf fiber meshes."""

import math

import bpy
from mathutils import Vector


# Edit these counts from the innermost layer outward.
# Add or remove a count to change how many layers are generated.
FIBERS_PER_LAYER = [5, 8, 11, 14, 18]

# Layer positions are spread evenly across this range.
INNER_LAYER = 0.24
OUTER_LAYER = 0.90
SHOW_CORE = True
SHOW_AXIS = True
AXIS_LENGTH = 10.0

# Colors repeat if you add more layers than there are colors.
LAYER_COLORS = [
    (0.95, 0.29, 0.06),
    (0.95, 0.65, 0.10),
    (0.11, 0.72, 0.51),
    (0.06, 0.37, 0.89),
    (0.42, 0.15, 0.83),
]
CORE_COLOR = (0.92, 0.14, 0.18)
AXIS_COLOR = (0.85, 0.85, 0.85)

TUBE_RADIUS = 0.019
FIBER_SEGMENTS = 256
TUBE_SIDES = 10
COLLECTION_NAME = "Hopf Fibration"


def add_fiber(vertices, faces, ratio, phase):
    """Append a closed tube around one stereographically projected fiber."""
    a = math.sqrt(1 - ratio**2)
    start = len(vertices)
    for step in range(FIBER_SEGMENTS):
        t = math.tau * step / FIBER_SEGMENTS
        denominator = 1 - ratio * math.sin(t)
        angle = t + phase
        radial = Vector((math.cos(angle), math.sin(angle), 0))
        azimuthal = Vector((-math.sin(angle), math.cos(angle), 0))
        vertical = Vector((0, 0, 1))
        rho = a / denominator
        z = ratio * math.cos(t) / denominator
        center = rho * radial + z * vertical

        # Differentiate the projected coordinates and use the torus normal
        # to give the tube a periodic frame, including at the closing seam.
        tangent = (
            (a * ratio * math.cos(t) / denominator**2) * radial
            + rho * azimuthal
            + (ratio * (ratio - math.sin(t)) / denominator**2) * vertical
        ).normalized()
        normal = (
            ((rho - 1 / a) * radial + z * vertical).normalized()
            if ratio else radial
        )
        binormal = tangent.cross(normal).normalized()
        for side in range(TUBE_SIDES):
            u = math.tau * side / TUBE_SIDES
            vertices.append(center + TUBE_RADIUS * (
                math.cos(u) * normal + math.sin(u) * binormal
            ))

    for step in range(FIBER_SEGMENTS):
        row = start + step * TUBE_SIDES
        next_row = start + ((step + 1) % FIBER_SEGMENTS) * TUBE_SIDES
        for side in range(TUBE_SIDES):
            next_side = (side + 1) % TUBE_SIDES
            faces.append((row + side, row + next_side,
                          next_row + next_side, next_row + side))


def add_mesh(collection, name, vertices, faces, color):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True

    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = 0.32
    mesh.materials.append(material)

    obj = bpy.data.objects.new(name, mesh)
    obj.color = (*color, 1)
    collection.objects.link(obj)


def add_layer(collection, name, ratio, count, color):
    vertices, faces = [], []
    for fiber in range(count):
        add_fiber(vertices, faces, ratio, math.tau * fiber / count)
    add_mesh(collection, name, vertices, faces, color)


def add_axis(collection):
    # The fiber through the projection point is an infinite line.
    # Show a finite section so it can be edited like the other fibers.
    vertices = []
    for z in (-AXIS_LENGTH / 2, AXIS_LENGTH / 2):
        for side in range(TUBE_SIDES):
            angle = math.tau * side / TUBE_SIDES
            vertices.append((TUBE_RADIUS * math.cos(angle),
                             TUBE_RADIUS * math.sin(angle), z))

    faces = [tuple(reversed(range(TUBE_SIDES))),
             tuple(range(TUBE_SIDES, 2 * TUBE_SIDES))]
    for side in range(TUBE_SIDES):
        next_side = (side + 1) % TUBE_SIDES
        faces.append((side, next_side, next_side + TUBE_SIDES, side + TUBE_SIDES))
    add_mesh(collection, "Hopf Axis", vertices, faces, AXIS_COLOR)


def main():
    collection = bpy.data.collections.new(COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)
    if SHOW_CORE:
        add_layer(collection, "Hopf Core", 0, 1, CORE_COLOR)
    if SHOW_AXIS:
        add_axis(collection)

    intervals = max(1, len(FIBERS_PER_LAYER) - 1)
    for index, count in enumerate(FIBERS_PER_LAYER):
        ratio = INNER_LAYER + (OUTER_LAYER - INNER_LAYER) * index / intervals
        color = LAYER_COLORS[index % len(LAYER_COLORS)]
        add_layer(collection, f"Hopf Layer {index + 1:02d}", ratio, count, color)


if __name__ == "__main__":
    main()
